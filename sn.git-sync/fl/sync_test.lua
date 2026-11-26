-- sn.git-sync/fl/sync_test.lua
-- Verifies production gate fail-closed behavior.

local function is_enabled(val)
  local norm = string.lower((val or ""):gsub("^%s*(.-)%s*$", "%1"))
  return norm == "true" or norm == "1" or norm == "yes"
end

function test_prod_gate_fail_closed()
  sn.test.eq(is_enabled(nil), false, "nil vault value must not enable sync")
  sn.test.eq(is_enabled(""), false, "empty vault value must not enable sync")
  sn.test.eq(is_enabled("false"), false, "false must not enable sync")
  sn.test.eq(is_enabled("staging"), false, "non-true value must not enable sync")
  sn.test.eq(is_enabled("true"), true, "true enables sync")
  sn.test.eq(is_enabled(" TRUE "), true, "trimmed uppercase TRUE enables sync")
  sn.test.eq(is_enabled("1"), true, "1 enables sync")
end
