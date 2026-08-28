---
title: "Troubleshooting & FAQ"
description: "This guide is your comprehensive reference for diagnosing and resolving problems with Sentinel."
---

# Troubleshooting & FAQ

This guide is your comprehensive reference for diagnosing and resolving problems with Sentinel. It covers startup failures, flow execution issues, database problems, API errors, security configuration, performance tuning, and common Lua programming mistakes. Each section explains the underlying cause of the problem, not just the fix, so you can develop an intuition for how Sentinel works and anticipate issues before they occur.

## How to Approach Debugging in Sentinel

Before diving into specific issues, it helps to understand Sentinel's debugging philosophy and the tools available to you. Sentinel provides multiple layers of observability that you should use in combination.

### The Debugging Toolkit

**1. Health endpoint (`/hl`)** -- Your first check for any problem. If the harness is running, `curl http://localhost:8080/hl` returns a JSON object with status, version, mode, and uptime. If this fails, the harness itself is the problem.

**2. Execution logs (`/ex/{id}/lg`)** -- Every flow execution records its logs. When a flow fails, find its execution ID (from the response or the dashboard) and query its logs for the full story.

**3. System logs (`/lg`)** -- The harness writes structured logs to stdout and to the `/lg` endpoint. These capture harness-level events like kit loading, trigger registration, and component lifecycle.

**4. Dashboard log viewer** -- The dashboard at port 9090 provides a real-time log viewer with filtering. This is the easiest way to watch multiple flows executing simultaneously.

**5. Debug logging** -- Set `SENTINEL_LOG_LEVEL=debug` to get verbose output from every component. This produces a lot of output but is invaluable for tracking down subtle issues.

**6. Execution detail (`/ex/{id}`)** -- Returns the full execution record including status, timing, parameters, return value, and any error message.

### General Debugging Strategy

When something goes wrong, follow this sequence:

1. **Check the health endpoint** -- Is the harness running? What mode is it in?
2. **Find the execution** -- If a flow failed, find its execution ID via `/ex?s=failed` or the dashboard.
3. **Read the execution logs** -- Query `/ex/{id}/lg` for the specific execution's log entries.
4. **Check the execution detail** -- Query `/ex/{id}` for the error message, parameters, and timing.
5. **Enable debug logging** -- If the logs do not reveal the problem, restart with `SENTINEL_LOG_LEVEL=debug`.
6. **Check the system logs** -- Look for harness-level errors that might explain the problem.

### Log Analysis Techniques

**Filtering by level:**
```bash
# Show only errors from the harness log
curl -s http://localhost:8080/lg?lv=error

# Show errors and warnings
curl -s http://localhost:8080/lg?lv=warn
```

**Finding failed executions:**
```bash
# List recent failed executions
curl -s http://localhost:8080/ex?s=failed

# Get the full log for a specific execution
curl -s http://localhost:8080/ex/exec_abc123/lg
```

**Streaming live logs (for watching in real time):**
```bash
# Stream all logs as they happen (SSE stream)
curl -N http://localhost:8080/lg/live
```

**Dashboard approach:**
The dashboard at `http://localhost:9090` provides a graphical log viewer with:
- Real-time log streaming via WebSocket
- Filtering by flow, level, and text search
- Execution detail views with timing and parameter data
- Color-coded log levels for quick scanning

---

## Common First-Time Setup Mistakes

These are issues that new users frequently encounter when setting up Sentinel for the first time. Most are simple configuration oversights.

### Running Sentinel Without the -p Flag

**Mistake:** Running `./sentinel harness start` at the repository root without specifying a project path.

**What happens:** Sentinel creates SRE artifacts (sentinel.yaml, kit directories, etc.) in the current directory, which pollutes your source tree.

**Fix:** Always use the `-p` flag to point at your SRE directory:
```bash
./sentinel harness start -p /path/to/your/sre
```

### Confusing the Two Config Files

**Mistake:** Putting infrastructure settings (port, logging, TLS) in `sentinel.yaml`, or behavior settings (name, version, git) in `.sentinel/config.json`.

**What happens:** Settings in the wrong file are either ignored or cause validation errors.

**Fix:** Remember the rule:
- `sentinel.yaml` -- Checked into git. Contains behavior: name, description, version, hot reload, git settings.
- `.sentinel/config.json` -- Gitignored. Contains infrastructure: port, logging, TLS, tokens, marketplace settings.

### Not Creating the .sentinel Directory

**Mistake:** Trying to configure a port or tokens without first initializing the project.

**Fix:** Run `./sentinel sre init my-project` to create the project structure, including the `.sentinel/` directory. Or create it manually:
```bash
mkdir -p my-project/.sentinel
echo '{"api":{"port":8080}}' > my-project/.sentinel/config.json
```

### Forgetting to Set the Vault Passphrase

**Mistake:** Trying to use secrets without setting the vault passphrase.

**Fix:** Set the passphrase before starting the harness:
```bash
export SENTINEL_VAULT_PASSPHRASE="your_passphrase_here"
./sentinel harness start -p ./my-project
```

---

## Startup Issues

### "Port already in use"

**Error:**
```
error: listen tcp :8080: bind: address already in use
```

**Understanding the cause:** Only one process can listen on a given TCP port at a time. This error means something else is already bound to port 8080 on your machine. The most common causes are:

1. Another Sentinel instance is still running (perhaps from a previous session or a background daemon).
2. Another application (a web server, another development tool) is using the port.
3. The operating system has not yet released the port after a previous process exited. This typically resolves within 30-60 seconds but can take longer depending on TCP TIME_WAIT settings.

**Solutions:**

1. **Force reset of any existing Sentinel process:**
   ```bash
   ./sentinel harness start --force-reset
   ```
   This command terminates any running Sentinel instance and cleans up lock files.

2. **Use a different port:**
   ```bash
   ./sentinel harness start -p ./project --port 9000
   ```
   Or configure it permanently in `.sentinel/config.json`:
   ```json
   {"api": {"port": 9000}}
   ```

3. **Find and kill the process occupying the port:**
   ```bash
   # Find what is using port 8080
   lsof -i :8080
   # or on systems without lsof:
   ss -tlnp | grep 8080

   # Kill the process (replace PID with the actual process ID)
   kill -9 <PID>
   ```

4. **Wait for the port to be released.** If the previous process just exited, the operating system may still be in TCP TIME_WAIT state. Waiting 30-60 seconds usually resolves this.

### "vault locked"

**Error:**
```
error: vault locked - set SENTINEL_VAULT_PASSPHRASE
```

**Understanding the cause:** The Sentinel vault stores secrets (API keys, tokens, passwords) encrypted with AES-256-GCM. The vault is unlocked using a passphrase that you provide via an environment variable. Without this passphrase, the harness cannot decrypt the vault and therefore cannot provide secrets to flows.

**Solution:**
```bash
export SENTINEL_VAULT_PASSPHRASE="your_passphrase_here"
./sentinel harness start -p ./project
```

**Important notes:**
- The passphrase is set when the vault is first created. You must use the same passphrase every time you start the harness.
- If you lose the passphrase, the vault contents cannot be recovered. You will need to create a new vault and re-enter all secrets.
- In production, store the passphrase in your deployment system's secret management (e.g., systemd EnvironmentFile, Docker secrets, Kubernetes secrets). Never hard-code it in scripts or commit it to version control.

### "project not found"

**Error:**
```
error: project directory not found: /path/to/project
```

**Understanding the cause:** The path passed to `-p` does not point to an existing directory, or it points to a directory that is not a valid SRE project (missing `sentinel.yaml`).

**Solutions:**

1. **Verify the path exists and is correct:**
   ```bash
   ls -la /path/to/project
   ls -la /path/to/project/sentinel.yaml
   ```

2. **Use an absolute path to avoid confusion with working directory:**
   ```bash
   ./sentinel harness start -p /absolute/path/to/project
   ```

3. **Initialize a new project if you are starting fresh:**
   ```bash
   ./sentinel sre init my-project
   ./sentinel harness start -p ./my-project
   ```

---

## Flow Execution Issues

### Flow times out

**Error:**
```
error: execution timeout after 30000ms
```

**Understanding the cause:** Every flow execution has a timeout (default 30 seconds). If the flow does not complete within this time, Sentinel terminates it. This is a safety mechanism that prevents runaway flows from consuming resources indefinitely. Common reasons a flow exceeds its timeout:

- An external API call is slow or hanging (the remote server is not responding).
- A database query is scanning a large table without proper indexes.
- The flow has a logic bug that causes an infinite loop.
- The flow is performing too many sequential operations that each take a small amount of time but add up.

**Solutions:**

1. **Increase the timeout for specific flows that legitimately need more time:**
   ```yaml
   # sentinel.yaml
   flows:
     overrides:
       sn-core-agent:my-flow:
         timeout_ms: 60000  # 1 minute
   ```
   Only increase timeouts for flows that you know are doing legitimate long-running work. A timeout increase should be a deliberate decision, not a blanket fix.

2. **Set explicit timeouts on HTTP calls so a single slow API does not consume the entire flow timeout:**
   ```lua
   -- Without a timeout, this call uses the flow's remaining timeout budget.
   -- With an explicit timeout, it fails fast if the API is slow.
   local resp = sn.http.get(url, {timeout_ms = 5000})
   ```

3. **Optimize your flow logic:**
   - Replace loops of individual database queries with batch queries using `WHERE id IN (...)`.
   - Add database indexes for columns used in WHERE clauses.
   - Cache results from external APIs instead of fetching them on every execution.
   - Process large datasets in batches rather than all at once.

### Flow returns error

**Error:**
```
error: SYSTEM.ERROR - flow execution failed
```

**Understanding the cause:** This is a generic error indicating that something went wrong during flow execution. The actual error details are in the execution logs.

**Debugging:**

1. **Get the execution details (including the error message):**
   ```bash
   curl -s http://localhost:8080/ex/exec_abc123 | python3 -m json.tool
   ```
   Look at the `error` field for the specific error message.

2. **Read the execution logs for the full context:**
   ```bash
   curl -s http://localhost:8080/ex/exec_abc123/lg
   ```
   The logs show every `ctx.log()` call the flow made before it failed, which helps you identify which step failed and why.

3. **Enable debug logging for maximum detail:**
   ```bash
   export SENTINEL_LOG_LEVEL=debug
   ./sentinel harness start -p ./project
   ```
   Debug logging includes Lua VM lifecycle events, trigger matching details, and detailed error stack traces.

### Secret not found

**Error:**
```
secret 'api_key' not found
```

**Understanding the cause:** The flow called `ctx.secret("api_key")` but no secret with that name exists in the vault. This is commonly caused by a typo in the secret name, or the secret simply has not been created yet.

**Solutions:**

1. **List all existing secrets to check for typos:**
   ```bash
   ./sentinel secret list
   ```
   Secret names are case-sensitive. `api_key` and `API_KEY` are different secrets.

2. **Create the missing secret:**
   ```bash
   ./sentinel secret set api_key "your_secret_value_here"
   ```

3. **Verify the vault is accessible and unlocked:**
   ```bash
   ls -la .sentinel/vault.db
   echo $SENTINEL_VAULT_PASSPHRASE
   ```
   If the vault file does not exist, secrets have not been initialized. If the passphrase is not set, the vault is locked.

### Webhook not triggering

**Understanding the cause:** When a webhook does not trigger, the request is either not reaching Sentinel, being rejected before it reaches your flow, or matching a different trigger than expected. The debugging process involves checking each layer in sequence.

**Debugging:**

1. **Verify the harness is running and reachable:**
   ```bash
   curl http://localhost:8080/hl
   ```

2. **Check that the trigger is registered. List all triggers and look for yours:**
   ```bash
   curl -s http://localhost:8080/tr | python3 -m json.tool
   ```

3. **Verify the webhook URL is correct.** Webhook URLs are prefixed with `/wh/`. If your trigger path is `/api/webhook`, the full URL to POST to is:
   ```
   http://localhost:8080/wh/api/webhook
   ```
   A common mistake is forgetting the `/wh/` prefix.

4. **Test the webhook manually with curl:**
   ```bash
   curl -X POST http://localhost:8080/wh/api/webhook \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```
   Check the response. If it returns an error, the error message tells you what went wrong.

5. **Check signature verification if HMAC is configured:**
   Note: HMAC verification is done automatically by the harness for webhook triggers with HMAC configured. If the signature is invalid, the request is rejected before your flow runs. To debug, check the received signature header:
   ```lua
   -- Webhook data arrives in main(params); HTTP headers are in ctx.req.headers
   local sig_header = ctx.req.headers["x-hub-signature-256"]
   ctx.log("info", "Received signature header: " .. (sig_header or "missing"))
   ```

6. **Check IP whitelist (CIDR) configuration.** If you have configured IP whitelisting, requests from non-whitelisted IPs are silently rejected. Verify your source IP is in the allowed CIDR ranges.

7. **Check rate limits.** If the webhook is rate-limited and you are exceeding the configured RPS, additional requests are rejected.

### Cron not running

**Understanding the cause:** Cron triggers execute on a schedule within the harness process. If a cron job is not running, it is either not registered, the cron expression is wrong, or the harness was not running at the scheduled time.

**Debugging:**

1. **Verify the trigger is registered:**
   ```bash
   curl -s http://localhost:8080/tr | python3 -m json.tool
   ```
   Look for your trigger in the list. If it is not there, the flow either failed to load or the trigger setup has a syntax error.

2. **Verify the cron expression is correct:**
   ```
   Field    Allowed values    Meaning
   -----    --------------    -------
   1st      0-59              Minute
   2nd      0-23              Hour
   3rd      1-31              Day of month
   4th      1-12              Month
   5th      0-6               Day of week (0=Sunday)
   ```

   Common expressions:
   ```
   0 0 * * *      = Daily at midnight
   */5 * * * *    = Every 5 minutes
   0 9-17 * * *   = Hourly between 9 AM and 5 PM
   0 0 * * 1      = Every Monday at midnight
   30 8 * * 1-5   = 8:30 AM on weekdays
   ```

3. **Check the timezone.** If you specified a timezone in the trigger and the cron expression refers to a specific hour, make sure you are accounting for the correct timezone. A job scheduled for "9 AM America/New_York" will not run at 9 AM UTC.

4. **Verify the harness was running at the scheduled time.** If the harness was stopped when a cron trigger was supposed to fire, the execution is missed (not retroactively run).

---

## Database Issues

### Database locked

**Error:**
```
error: database is locked
```

**Understanding the cause:** SQLite allows multiple readers but only one writer at a time. When a write operation encounters a lock held by another write operation, it waits for a configurable timeout before giving up with this error. Common scenarios:

- Multiple flows running simultaneously are all trying to write to the database.
- A long-running transaction holds the write lock, blocking other writers.
- The database is being accessed by an external tool (like `sqlite3` shell) while the harness is running.

**Solutions:**

1. **Increase the busy timeout** to give SQLite more time to acquire the lock:
   ```json
   {
     "state": {
       "busy_timeout": 10000
     }
   }
   ```
   The default is usually sufficient for normal operation. If you need to increase it, your flows may be holding write locks for too long and should be optimized.

2. **Check database health:**
   ```bash
   ./sentinel db shell
   sqlite> PRAGMA integrity_check;
   ```
   The result should be `ok`. If it reports errors, the database may be corrupted (see next section).

3. **Close external tools.** If you have a `sqlite3` shell open on the same database, close it. External writers can hold locks that block the harness.

4. **Optimize long-running transactions.** Keep your `sn.db.transaction()` blocks as short as possible. Move any computation or HTTP calls outside the transaction so the write lock is held for the minimum time.

5. **Restart the harness** as a last resort. This closes all database connections and releases any held locks.

### Data corruption

**Error:**
```
database disk image is malformed
```

**Understanding the cause:** SQLite databases can become corrupted due to hardware failures (disk errors, power loss during a write), bugs in the operating system's filesystem, or forcefully killing the harness process during a transaction. This is rare but serious.

**Recovery:**

1. **Backup the corrupted database immediately:**
   ```bash
   cp .sentinel/state.db .sentinel/state.db.corrupt
   ```

2. **Attempt to dump what data can be recovered:**
   ```bash
   sqlite3 .sentinel/state.db.corrupt ".dump" > dump.sql
   ```
   This may recover most or all of the data even from a corrupted database.

3. **Create a fresh database and restore the dump:**
   ```bash
   sqlite3 .sentinel/state.db < dump.sql
   ```

4. **Verify the restored database:**
   ```bash
   sqlite3 .sentinel/state.db "PRAGMA integrity_check;"
   ```

5. **Restart the harness:**
   ```bash
   ./sentinel harness start -p ./project
   ```

**Prevention:** To minimize corruption risk, never use `kill -9` on the harness process (use `kill` or `./sentinel harness stop` for graceful shutdown), ensure your server has reliable storage, and consider enabling database encryption (`"encrypt_db": true` in config.json) which also adds integrity verification.

---

## API Issues

### Authentication failed

**Error:**
```
{"ok": false, "err": "AUTH.REQUIRED", "msg": "Bearer token required"}
```

**Understanding the cause:** The harness is running in production mode (has tokens configured in `.sentinel/config.json`) and the request did not include a valid Bearer token. In debug mode (no tokens configured), authentication is relaxed to IP-whitelist only.

**Solutions:**

1. **Include the token in your request:**
   ```bash
   curl -H "Authorization: Bearer your_token_here" http://localhost:8080/hl
   ```

2. **Verify your token matches what is configured:**
   ```bash
   cat .sentinel/config.json | python3 -c "
   import sys, json
   config = json.load(sys.stdin)
   tokens = config.get('api', {}).get('tokens', [])
   print(f'{len(tokens)} token(s) configured')
   for t in tokens:
       print(f'  {t[:8]}...')
   "
   ```

3. **Use the environment variable for scripts:**
   ```bash
   export SENTINEL_API_KEY="your_token_here"
   ```

### CORS errors

**Symptom:** The dashboard shows "Connection refused" or browser console shows CORS errors when trying to connect to the harness API.

**Understanding the cause:** CORS (Cross-Origin Resource Sharing) errors occur when the dashboard and harness are served from different origins (different hostnames or ports). Browsers enforce the same-origin policy, blocking cross-origin requests unless the server explicitly allows them.

**Solution:** In development, run both the harness and dashboard on localhost:

```bash
# Terminal 1: Harness on port 8080
./sentinel harness start -p ./project --port 8080

# Terminal 2: Dashboard on port 9090
./sentinel dashboard start --port 9090
```

The dashboard proxies API requests to the harness through its BFF (Backend-for-Frontend) layer, avoiding CORS issues. Make sure the harness URL configured in the dashboard settings matches the actual harness address.

### Rate limit exceeded

**Error:**
```
{"ok": false, "err": "AUTH.RATE_LIMIT", "msg": "Rate limit exceeded"}
```

**Understanding the cause:** The harness enforces a rate limit on API requests to prevent abuse and protect system resources. The default limit is typically sufficient for normal operation but may be exceeded by automated scripts making rapid-fire requests.

**Solution:** Increase the rate limit in `.sentinel/config.json`:
```json
{
  "limits": {
    "rate_limit_rps": 1000
  }
}
```

If you are hitting rate limits in normal operation, consider whether your client is making unnecessary requests (e.g., polling too frequently when WebSocket streaming is available).

---

## Network and Firewall Troubleshooting

### Harness not reachable from another machine

**Symptom:** `curl http://<server-ip>:8080/hl` fails from another machine, but works with `curl http://localhost:8080/hl` on the server itself.

**Understanding the cause:** By default, Sentinel listens on all interfaces (`0.0.0.0`), but firewalls on the server may block incoming connections to port 8080.

**Solutions:**

1. **Check the firewall rules:**
   ```bash
   # Ubuntu/Debian with ufw
   sudo ufw status
   sudo ufw allow 8080/tcp

   # CentOS/RHEL with firewalld
   sudo firewall-cmd --list-ports
   sudo firewall-cmd --add-port=8080/tcp --permanent
   sudo firewall-cmd --reload

   # Check iptables directly
   sudo iptables -L -n | grep 8080
   ```

2. **Verify the harness is listening on the correct interface:**
   ```bash
   ss -tlnp | grep 8080
   ```
   The output should show `0.0.0.0:8080` (all interfaces) or the specific IP you expect.

3. **Test connectivity:**
   ```bash
   # From the remote machine
   telnet <server-ip> 8080
   # or
   nc -zv <server-ip> 8080
   ```

### Dashboard cannot reach harness behind a proxy

**Symptom:** The dashboard is accessible but shows "Cannot reach harness" in the settings.

**Understanding the cause:** When running behind a reverse proxy (nginx, Caddy), the proxy must be configured to forward requests to the correct harness port. The dashboard's BFF layer needs to know the harness address.

**Solution:** In the dashboard settings, configure the harness address using the internal (non-proxied) address:
- If dashboard and harness are on the same server: `http://localhost:8080`
- If on different servers: `http://<harness-server-ip>:8080`

The dashboard should never need to go through the public reverse proxy to reach the harness -- use the direct internal address.

---

## Git Integration Issues

### Hot reload not detecting changes

**Symptom:** You modify a Lua flow file but the harness continues running the old version.

**Understanding the cause:** Hot reload monitors the SRE directory for file changes. If the filesystem notification system is not working (common in Docker volumes, NFS mounts, or some VM configurations), changes may not be detected.

**Solutions:**

1. **Verify hot reload is enabled:**
   ```yaml
   # sentinel.yaml
   hotreload: true
   ```

2. **Force a manual reload:**
   ```bash
   curl -X POST http://localhost:8080/hl/reload
   ```

3. **Check file watcher limitations.** On Docker volumes and NFS mounts, inotify events may not propagate. In these environments, Sentinel falls back to periodic polling. If changes are still not detected, restart the harness.

### Flow files not being discovered

**Symptom:** You created a new `.lua` file in `fl/` but it does not appear in the flow list.

**Understanding the cause:** Flows are auto-discovered from the `fl/` directory of each kit. Discovery happens at startup and when hot reload triggers. The file must have a `.lua` extension and be in the correct location.

**Solutions:**

1. **Verify file location.** The file must be at `{kit-dir}/fl/{flow-name}.lua`. For example: `acme.mykit/fl/my-flow.lua`.

2. **Check file permissions.** The harness process must be able to read the file.

3. **Check for syntax errors.** If a Lua file has syntax errors, it fails to load and is skipped. Check the system logs for parsing errors:
   ```bash
   curl -s http://localhost:8080/lg?lv=error | grep -i lua
   ```

4. **Trigger a reload:**
   ```bash
   curl -X POST http://localhost:8080/hl/reload
   ```

---

## Marketplace and Licensing Troubleshooting

### License activation fails

**Symptom:** `./sentinel license activate` returns an error or the license key is rejected.

**Solutions:**

1. **Verify the license key format.** Valid keys start with `sk_free_` or `sk_ent_` followed by a base64url payload and an Ed25519 signature separated by a period.

2. **Check network connectivity to the marketplace:**
   ```bash
   curl -s https://kits.example.com/v1/drm/pubkey
   ```
   If this fails, you have a network connectivity issue.

3. **Check the marketplace URL in config:**
   ```bash
   cat .sentinel/config.json | python3 -c "
   import sys, json
   config = json.load(sys.stdin)
   print(config.get('marketplace', {}).get('url', 'NOT SET'))
   "
   ```

### Phone-home failures

**Symptom:** Dashboard shows license as invalid or marketplace features are blocked.

**Understanding the cause:** The phone-home system verifies the license periodically (default every 7 days). If verification fails for 48 hours (the grace period), marketplace features are blocked. This can happen due to network issues, DNS problems, or the marketplace server being unavailable.

**Solutions:**

1. **Check when the next verification is scheduled:**
   ```bash
   cat .sentinel/config.json | python3 -c "
   import sys, json
   config = json.load(sys.stdin)
   print('Next check:', config.get('marketplace', {}).get('next_check', 'NOT SET'))
   "
   ```

2. **Verify network connectivity to the marketplace server.**

3. **Check if you are within the grace period.** Marketplace features continue to work for 48 hours after the first phone-home failure. If you resolve the network issue within this window, everything returns to normal automatically.

4. **Restart the harness** to force an immediate phone-home attempt.

---

## Security Issues

### Certificate errors

**Error:**
```
curl: (60) SSL certificate problem: self signed certificate
```

**Understanding the cause:** When Sentinel's TLS is enabled, it generates self-signed certificates by default. Clients (including curl) do not trust self-signed certificates unless explicitly told to.

**Solutions:**

Use the CA certificate:
```bash
curl --cacert .sentinel/certs/ca.crt https://localhost:8443/hl
```

Or skip verification in development only (never in production):
```bash
curl -k https://localhost:8443/hl
```

For production, use a proper certificate from Let's Encrypt, Cloudflare Origin Certificates, or your organization's CA. See the Edge Deployment guide for details.

### Encryption errors

**Error:**
```
error: could not decrypt vault
```

**Understanding the cause:** The vault was encrypted with one passphrase, but you are trying to open it with a different passphrase. This can happen when the environment variable is set incorrectly, or when you copy a vault database from one environment to another without copying the passphrase.

**Solutions:**

1. **Verify the passphrase is set correctly:**
   ```bash
   echo $SENTINEL_VAULT_PASSPHRASE
   ```
   Check for accidental whitespace, quote characters, or shell escaping issues.

2. **Backup the encrypted vault before any recovery attempts:**
   ```bash
   cp .sentinel/vault.db .sentinel/vault.db.backup
   ```

3. **If the passphrase is lost:** There is no recovery mechanism for the vault contents. You must create a new vault and re-enter all secrets:
   ```bash
   rm .sentinel/vault.db
   export SENTINEL_VAULT_PASSPHRASE="new_passphrase"
   ./sentinel harness start -p ./project
   # Then re-add all secrets:
   ./sentinel secret set api_key "value"
   ```

---

## Performance Issues

### Slow startup

**Symptom:** Harness takes 30+ seconds to start.

**Understanding the cause:** At startup, Sentinel loads all kits, discovers all flows, compiles Lua scripts, registers triggers, and initializes the database. If any of these steps is slow, startup is slow. Common bottlenecks:

- Many kits or flows (50+) requiring compilation.
- Slow disk I/O (especially on network-attached storage).
- Large database requiring migration or integrity checks.
- Network calls during kit discovery (marketplace kits checking for updates).

**Solutions:**

1. **Profile startup to identify the bottleneck:**
   ```bash
   time ./sentinel harness start -p ./project
   ```

2. **Reduce the number of kits and flows.** If you have many kits that are not currently needed, move them out of the SRE directory temporarily.

3. **Disable web cache if it is causing startup delays:**
   ```bash
   ./sentinel harness start -p ./project --drop-web-cache
   ```

4. **Check disk I/O performance.** On slow storage (NFS, network-attached), consider moving the SRE to local SSD storage.

### High memory usage

**Symptom:** Harness uses 500MB+ RAM.

**Understanding the cause:** Each concurrent flow execution uses a Lua VM instance with its own memory allocation. If many flows run simultaneously, or if individual flows allocate large tables, memory usage can spike. Database queries that return large result sets also contribute to memory usage.

**Solutions:**

1. **Limit concurrent flow executions:**
   ```json
   {
     "limits": {
       "max_concurrent_flows": 5
     }
   }
   ```

2. **Fix memory-heavy Lua patterns:**
   ```lua
   -- BAD: Loads 1 million items into memory at once
   local data = {}
   for i = 1, 1000000 do
     table.insert(data, i)
   end

   -- GOOD: Process in batches, keeping only one batch in memory
   for i = 1, 1000000, 1000 do
     local batch = load_batch(i, math.min(i + 999, 1000000))
     process_batch(batch)
     -- batch is garbage collected after this iteration
   end
   ```

3. **Use database queries with LIMIT to avoid loading entire tables into memory:**
   ```lua
   -- BAD: Loads all rows
   local all_rows = sn.db.query("SELECT * FROM big_table")

   -- GOOD: Loads one page at a time
   local page = sn.db.query("SELECT * FROM big_table LIMIT 100 OFFSET 0")
   ```

4. **Force garbage collection in long-running flows:**
   ```lua
   collectgarbage("collect")
   ```

### Performance Diagnostics Guide

When you need to diagnose a performance problem, collect these data points:

```bash
# 1. Check harness health and uptime
curl -s http://localhost:8080/hl | python3 -m json.tool

# 2. Count active executions
curl -s http://localhost:8080/ex?s=running | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Active executions: {len(data.get(\"executions\", []))}')"

# 3. Check system resources
free -h          # Memory usage
df -h            # Disk space
top -bn1 | head  # CPU usage

# 4. Check database size
ls -lh .sentinel/state.db

# 5. Profile slow flows by checking execution durations
curl -s http://localhost:8080/ex?fmt=json | python3 -c "
import sys, json
data = json.load(sys.stdin)
for ex in sorted(data.get('executions', []), key=lambda x: x.get('duration_ms', 0), reverse=True)[:5]:
    print(f'{ex[\"fid\"]:40s} {ex.get(\"duration_ms\", 0):8d}ms  {ex[\"st\"]}')"
```

---

## Common Lua Errors

These are programming errors that occur frequently in Lua flows. They are not Sentinel-specific -- they are standard Lua runtime errors -- but understanding them helps you debug flows faster.

### "attempt to index nil value"

**Error:**
```
error: attempt to index a nil value (field '?')
```

**Understanding the cause:** This error occurs when you try to access a field or method on a value that is `nil`. In Lua, only tables (and userdata) can be indexed. If a function returns `nil` and you try to access `.property` on the result, you get this error.

**Example and fix:**
```lua
-- WRONG: get_user() might return nil
local user = get_user()
local name = user.name   -- Error if user is nil!

-- RIGHT: Check for nil before indexing
local user = get_user()
if user then
  local name = user.name
  -- proceed with name
else
  ctx.log("error", "User not found")
end
```

### "attempt to concatenate a nil value"

**Error:**
```
error: attempt to concatenate a nil value
```

**Understanding the cause:** Lua's `..` operator concatenates strings. If either operand is `nil`, this error occurs. This commonly happens when a variable has not been assigned or a function returned `nil` instead of a string.

**Example and fix:**
```lua
-- WRONG: count might be nil
local count = nil
ctx.log("info", "Count: " .. count)  -- Error!

-- RIGHT: Provide a fallback value
local count = nil
ctx.log("info", "Count: " .. (count or "unknown"))

-- Also RIGHT: Convert explicitly
ctx.log("info", "Count: " .. tostring(count))  -- "Count: nil"
```

### "bad argument to 'table.insert'"

**Error:**
```
error: bad argument to 'table.insert'
```

**Understanding the cause:** `table.insert()` expects its first argument to be a table. If the variable is `nil` (because it was not initialized), you get this error.

**Example and fix:**
```lua
-- WRONG: items was never initialized as a table
local items = nil
table.insert(items, "value")  -- Error!

-- RIGHT: Initialize as an empty table
local items = {}
table.insert(items, "value")
```

---

## Form Issues

### Form not rendering

**Error:**
```
No form found with stub: my-form
```

**Understanding the cause:** The form system looks up forms by their stub (a short identifier defined in the form's YAML file). This error means either the form file does not exist, the stub in the file does not match what you are requesting, or the kit containing the form was not loaded.

**Solutions:**

1. **Verify the form file exists in the kit's `fm/` directory:**
   ```bash
   ls -la my.kit/fm/my-form.yaml
   ```

2. **Verify the stub in the form file matches your request:**
   ```yaml
   # fm/my-form.yaml
   name: My Form
   stub: my-form  # This must match exactly
   ```

3. **Check that the kit is loaded:**
   ```bash
   curl -s http://localhost:8080/kt | python3 -m json.tool
   ```

### Form submission not triggering flow

**Understanding the cause:** Form submissions emit events with a specific naming pattern. Your flow must register a trigger for the exact event name that the form emits.

**Solution:** The event name follows the pattern `kf.{namespace}.{kit-name}.{form-stub}`. For example, a form with stub `payment` in kit `acme.billing` emits the event `kf.acme.billing.payment`.

```lua
function setup()
  -- The event name must match exactly: kf.{namespace}.{kit-name}.{form-stub}
  event("kf.acme.billing.payment")
end

function main(params)
  -- Form field values are available via ctx.fm.{stub}.{field}
  local amount = ctx.fm.payment.amount
  -- process the submission
  return {ok = true}
end
```

---

## Dashboard Issues

### Dashboard can't connect to harness

**Symptom:** "Connection refused" or "Cannot reach harness" in the dashboard.

**Solutions:**

1. **Verify the harness is running:**
   ```bash
   curl http://localhost:8080/hl
   ```

2. **Check the harness address in dashboard settings.** Navigate to Dashboard > Settings > Harness and verify the URL is `http://localhost:8080` (or the correct address for your setup).

3. **If behind a firewall:** Ensure port 8080 is accessible from where the dashboard is running. If the dashboard and harness are on the same machine, `localhost` should always work.

4. **Check that the harness started successfully** by reviewing its stdout/stderr output or system logs.

### Dashboard shows stale data

**Understanding the cause:** The dashboard caches some data in the browser's localStorage. If the harness was restarted or data was modified outside the dashboard, the cached data may be out of date.

**Solution:**
```bash
# In browser developer console (F12):
localStorage.clear()
location.reload()
```

Or use the Refresh links on individual dashboard pages to fetch fresh data from the harness.

---

## Getting More Help

### Enable Debug Logging

```bash
export SENTINEL_DEBUG=1
export SENTINEL_LOG_LEVEL=debug
./sentinel harness start -p ./project
```

Debug logging produces verbose output from every harness component, including:
- Lua VM lifecycle events (creation, destruction, script loading)
- Trigger matching (which triggers were evaluated and why they did or did not match)
- HTTP request details (method, path, response status for every API call)
- Database operations (query timing, transaction begin/commit/rollback)
- Component health checks

### Check System Status

```bash
# Overall health
curl http://localhost:8080/hl

# Component health (kits, triggers, database, vault)
curl http://localhost:8080/hl/kt

# List all registered components
./sentinel components list
```

### Review Audit Logs

```bash
# Recent audit entries
./sentinel audit list --limit 100

# Filter by type
./sentinel audit list --filter type=ERROR
```

### Check Configuration

```bash
# Check specific config values
./sentinel config get api.port
./sentinel config get logging.level

# Dump the full configuration (be careful -- may contain sensitive values)
cat .sentinel/config.json | python3 -m json.tool
```

### Database Inspection

```bash
# Open an interactive SQLite shell on the state database
./sentinel db shell

# Useful queries:
sqlite> .tables                                    -- List all tables
sqlite> SELECT * FROM executions ORDER BY started_at DESC LIMIT 5;  -- Recent executions
sqlite> SELECT * FROM triggers;                    -- All registered triggers
sqlite> SELECT COUNT(*) FROM executions WHERE status = 'failed';    -- Count failures
sqlite> PRAGMA integrity_check;                    -- Verify database health
```

---

**Still stuck?** Review the relevant guides in this documentation set: the API Reference for endpoint details, the Configuration Guide for all available settings, the Workflows and Patterns guide for working code examples, or the system-specs directory for the authoritative technical specifications.
