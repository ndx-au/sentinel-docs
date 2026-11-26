-- sn.git-sync/fl/sync.lua
-- Runs a git sync on the SRE every 5 minutes, ONLY when the machine-local
-- vault secret `prod_git_sync_enabled` is set to "true".

triggers = type(cron) == "function" and {
  cron("*/5 * * * *"),
} or {}

local JOB_KEY = "sn.git-sync:sync"
local lease_held = false

local function read_secret(key)
  local ok, val = pcall(function()
    return ctx.secret(key)
  end)
  if not ok or type(val) ~= "string" then
    return ""
  end
  return val
end

local function is_enabled(val)
  local norm = string.lower((val or ""):gsub("^%s*(.-)%s*$", "%1"))
  return norm == "true" or norm == "1" or norm == "yes"
end

local function build_headers(token)
  local headers = {
    ["Accept"] = "application/json",
    ["Content-Type"] = "application/json",
  }
  if token and token ~= "" then
    headers["Authorization"] = "Bearer " .. token
  end
  return headers
end

local function decode_json_safe(body)
  if not body or body == "" then
    return nil
  end
  local ok, decoded = pcall(sn.json.dec, body)
  if not ok then
    return nil
  end
  return decoded
end

function setup()
  -- Keep top-level and setup free of host I/O.
end

function main(params)
  -- 1. Fail-closed production gate via machine-local vault secret.
  if not is_enabled(read_secret("prod_git_sync_enabled")) then
    ctx.log("debug", "Skipping git sync: prod_git_sync_enabled is not true")
    return { skipped = true, reason = "not_production" }
  end

  -- 2. Owner-fenced flow-level lease so slow syncs never overlap across ticks.
  sn.db.exec([[
    CREATE TABLE IF NOT EXISTS job_leases (
      job_key TEXT PRIMARY KEY,
      owner_exec_id TEXT NOT NULL,
      lease_until TEXT NOT NULL
    )
  ]])
  local ins = sn.db.exec(
    "INSERT OR IGNORE INTO job_leases (job_key, owner_exec_id, lease_until) VALUES (?, ?, datetime('now', '+4 minutes'))",
    { JOB_KEY, ctx.execution_id }
  )
  local acquired = (ins.rows_affected == 1)
  if not acquired then
    local take = sn.db.exec(
      "UPDATE job_leases SET owner_exec_id = ?, lease_until = datetime('now', '+4 minutes') WHERE job_key = ? AND lease_until < datetime('now')",
      { ctx.execution_id, JOB_KEY }
    )
    acquired = (take.rows_affected == 1)
  end
  if not acquired then
    ctx.log("warn", "Skipping git sync: previous sync lease still active")
    return { skipped = true, reason = "lease_active" }
  end
  lease_held = true

  -- 3. Resolve optional machine-local config from vault.
  local base_url = read_secret("prod_harness_url")
  if base_url == "" then
    base_url = "http://127.0.0.1:8290"
  end
  base_url = base_url:gsub("/+$", "")

  local mode = string.lower(read_secret("prod_git_sync_mode"))
  local sync_path = "/git/sync"
  if mode == "pull" then
    sync_path = "/git/pull"
  end

  local reload_kit = read_secret("prod_reload_kit")
  if reload_kit == "" then
    reload_kit = "sn/docs"
  end

  local headers = build_headers(read_secret("prod_harness_token"))

  -- 4. Record HEAD before sync.
  local before_head = ""
  local info_ok, info_resp = pcall(sn.http.get, base_url .. "/git/info", {
    headers = headers,
    timeout_ms = 10000,
  })
  if info_ok and info_resp and info_resp.status == 200 then
    local info_data = decode_json_safe(info_resp.body)
    if type(info_data) == "table" and info_data.head then
      before_head = tostring(info_data.head)
    end
  end

  -- 5. Run git sync (or pull) via local harness API.
  local sync_resp = sn.http.post(base_url .. sync_path, "{}", {
    headers = headers,
    timeout_ms = 25000,
  })
  if sync_resp.status ~= 200 then
    error("git sync HTTP status: " .. tostring(sync_resp.status))
  end
  local sync_data = decode_json_safe(sync_resp.body)
  if type(sync_data) == "table" and sync_data.ok == false then
    error("git sync error: " .. tostring(sync_data.err or sync_data.msg or "unknown"))
  end

  -- 6. Check if HEAD moved and reload the docs kit if configured.
  local after_head = before_head
  local post_ok, post_resp = pcall(sn.http.get, base_url .. "/git/info", {
    headers = headers,
    timeout_ms = 10000,
  })
  if post_ok and post_resp and post_resp.status == 200 then
    local post_data = decode_json_safe(post_resp.body)
    if type(post_data) == "table" and post_data.head then
      after_head = tostring(post_data.head)
    end
  end

  local head_changed = (before_head ~= "" and after_head ~= "" and before_head ~= after_head)
  local reloaded = false
  if head_changed and string.lower(reload_kit) ~= "none" then
    local rl_ok, rl_resp = pcall(sn.http.post, base_url .. "/hl/kt/" .. reload_kit .. "/rl", "{}", {
      headers = headers,
      timeout_ms = 15000,
    })
    if rl_ok and rl_resp and rl_resp.status == 200 then
      local rl_data = decode_json_safe(rl_resp.body)
      reloaded = not (type(rl_data) == "table" and rl_data.ok == false)
    end
  end

  ctx.log("info", "Production git sync complete",
    "mode", sync_path,
    "head_changed", head_changed,
    "reloaded", reloaded
  )

  return {
    synced = true,
    mode = sync_path,
    before_head = before_head,
    after_head = after_head,
    head_changed = head_changed,
    reloaded = reloaded,
  }
end

function cleanup()
  if lease_held then
    sn.db.exec(
      "DELETE FROM job_leases WHERE job_key = ? AND owner_exec_id = ?",
      { JOB_KEY, ctx.execution_id }
    )
    lease_held = false
  end
end

function failed()
  ctx.log("error", "Production git sync failed", "exec_id", ctx.execution_id)
end
