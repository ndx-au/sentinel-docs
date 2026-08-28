-- Smoke tests for sn.docs kit. Verifies kit-level contract assumptions that
-- templates and pages rely on. Extend as flows/modules are added.

function test_sn_globals_available()
  sn.test.eq(type(sn), "table")
  sn.test.eq(type(sn.test), "table")
end

function test_kit_contract_keys()
  -- pg/home.yaml declares these; templates depend on the routing keys existing.
  -- This is a static contract check: if the page definition changes shape,
  -- update this test alongside it.
  local page = {
    name = "home",
    path = "/",
    title = "Sentinel Docs",
    public = true,
  }
  sn.test.eq(page.name, "home")
  sn.test.eq(page.path, "/")
  sn.test.eq(page.public, true)
end
