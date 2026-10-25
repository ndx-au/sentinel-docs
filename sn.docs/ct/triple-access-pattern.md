---
title: "Triple-Access Pattern for Sentinel Services"
description: "How to share Sentinel business logic across REST API, CLI, and Lua interfaces."
type: Guide
tags: [architecture]
status: stable
---

<!-- ndx-ste-mode: description -->

# Triple-Access Pattern for Sentinel Services

## Overview

The Triple-Access Pattern is an internal Sentinel architecture. A shared service provides the same feature through the REST API, CLI, and Lua. This avoids duplicate business logic and keeps behavior consistent. This guide is for harness contributors.

### Why This Pattern Exists

In a system like Sentinel, the same operation (for example "list all vendors" or "create a trigger") needs to be available in multiple contexts:

1. **REST API** -- External clients, the dashboard, AI agents, and automation tools interact with Sentinel through HTTP endpoints. The API must be consistent, follow the brevity regime, and always return HTTP 200 with structured error bodies.

2. **CLI** -- Operators and administrators manage Sentinel from the command line. CLI commands must provide human-readable output (tables, formatted text) while also supporting machine-readable JSON output for scripting and agent consumption.

3. **Lua** -- Flows running inside the Sentinel sandbox need to access service functionality programmatically. Lua bindings must be context-aware, handle errors using the `(result, error_string)` pattern, and integrate with the Lua VM lifecycle.

Without a shared architecture, each interface needs its own business logic. The API and CLI can then produce different results. Developers must repeat fixes and update three implementations for each change.

The Triple-Access Pattern solves this by placing all business logic in a single **service layer** that the three interfaces simply call into. Each interface is a thin adapter that translates between its transport format (HTTP, CLI args, Lua tables) and the service layer's Go types.

### When to Apply This Pattern

For a feature that needs API, CLI, and Lua access, use the Triple-Access Pattern from the start. For an internal feature with one interface, use a simpler architecture. The Migration Path section explains how to convert existing features. That conversion adds work.

---

## Architecture

Three interface layers call a shared service layer. The service delegates persistence to a repository layer. Shared domain models define the data for all layers.

```
+-------------------------------------------------------------+
|                   Service Package                            |
|-------------------------------------------------------------|
|                                                              |
|  +-------------------------------------------------------+  |
|  |           Domain Models (types.go)                     |  |
|  |  - Core types (Vendor, Endpoint, Call, etc.)           |  |
|  |  - Filters (VendorFilter, EndpointFilter, etc.)        |  |
|  |  - Query options (limit, offset, sorting)              |  |
|  +-------------------------------------------------------+  |
|                          ^                                   |
|                          |                                   |
|  +-------------------------------------------------------+  |
|  |        Repository Layer (repository.go)                |  |
|  |  - SQL operations                                      |  |
|  |  - Parameterized queries                               |  |
|  |  - Transaction handling                                |  |
|  |  - JSON marshaling/unmarshaling                        |  |
|  +-------------------------------------------------------+  |
|                          ^                                   |
|                          |                                   |
|  +-------------------------------------------------------+  |
|  |         Service Layer (service.go)                     |  |
|  |  - Business logic                                      |  |
|  |  - Orchestration                                       |  |
|  |  - Query interface (flexible filtering)                |  |
|  |  - Batch operations (import/export)                    |  |
|  |  - Lazy schema initialization                          |  |
|  +-------------------------------------------------------+  |
|                          ^                                   |
|          +---------------+---------------+                   |
|          |               |               |                   |
|          v               v               v                   |
|    +-----------+   +-----------+   +-----------+             |
|    |    CLI    |   |    API    |   |    Lua    |             |
|    |  Commands |   |  Handlers |   |  Bindings |             |
|    +-----------+   +-----------+   +-----------+             |
+-------------------------------------------------------------+
```

Each layer has a specific responsibility and a strict contract with the layers above and below it. The following sections describe each layer in detail, with implementation guidelines and code examples.

---

## Layer Definitions

### 1. Domain Models (`types.go`)

**Purpose:** Domain models define shared data structures. They describe entities such as a "Vendor", filters such as a "Filter", and query options.

**Why a separate file:** By isolating types in `types.go`, you make sure that no layer owns the type definitions. The repository, service, and all three interface layers all import the same types. This eliminates the risk of type drift (where each layer has its own slightly different version of a struct).

**Implementation guidelines:**

- All types must be JSON-serializable, with exported fields and `json` tags. The API returns JSON. The CLI can print JSON. The Lua layer converts JSON to Lua tables.
- Use pointer types for optional filter fields. A `nil` pointer means "no filter on this field," with no SQL condition. A non-nil pointer means "filter on this field." This includes a pointer to an empty string. SQL WHERE clauses depend on this distinction.
- Include pagination fields (Limit, Offset) in filter types. Use the same pagination fields for all three interfaces.
- Define a generic `QueryOptions` type for the flexible query interface that AI agents and programmatic clients use. This type accepts string-based entity type selection and a map of filter keys, making it adaptable to different query styles.

```go
// Core entity -- represents a domain object that the service manages.
// Every field has a json tag for API responses, CLI JSON output, and Lua table conversion.
type Vendor struct {
    ID        string    `json:"id"`
    Name      string    `json:"name"`
    // ... additional fields
}

// Typed filter -- used when the caller knows what entity type they are querying.
// Pointer fields allow distinguishing between "not filtering" (nil) and
// "filtering on empty string" (pointer to "").
type VendorFilter struct {
    Name  *string       // LIKE filter: if non-nil, WHERE name LIKE '%{value}%'
    Limit, Offset int   // Pagination
}

// Generic query options -- used by the agent-friendly query interface.
// This allows AI agents to construct queries without knowing the exact
// filter struct types, using string keys and values instead.
type QueryOptions struct {
    EntityType string            // "vendor", "endpoint", "call"
    Filter     map[string]any    // Generic filter map
    Limit      int
    Offset     int
}
```

---

### 2. Repository Layer (`repository.go`)

**Purpose:** The repository handles database interactions. It translates between domain models and SQL operations. Other layers contain no SQL statements.

**Why a separate layer:** The repository isolates SQL from business logic. Developers can change schemas, optimize queries, or replace database engines without changing the interfaces. Tests can use a mock repository for the service.

**Implementation guidelines:**

- **Always use parameterized queries.** Never concatenate user input into SQL strings. This prevents SQL injection vulnerabilities and ensures correct handling of special characters.
- **Handle NULL values correctly.** For nullable SQL columns, use `sql.NullString`, `sql.NullInt64`, or another suitable nullable type. Map the values to pointer fields in domain types.
- **Wrap cascading operations in transactions.** If one operation needs multiple SQL statements, use a transaction. The statements then succeed or fail as one operation.
- **Return package-level error variables.** Define sentinel errors like `var ErrNotFound = errors.New("...")` and return them from repository methods. This allows the service layer to make decisions based on error types without parsing error strings.

```go
type Repository struct {
    db *sql.DB
}

// CRUD operations -- each method maps to a single logical database operation.
// The service layer composes these into higher-level workflows.
func (r *Repository) ListVendors(ctx context.Context, filter *VendorFilter) ([]Vendor, error)
func (r *Repository) GetVendor(ctx context.Context, id string) (*Vendor, error)
func (r *Repository) CreateVendor(ctx context.Context, v *Vendor) error
func (r *Repository) UpdateVendor(ctx context.Context, v *Vendor) error
func (r *Repository) DeleteVendor(ctx context.Context, id string) error

// Batch operations for import/export functionality
func (r *Repository) Import(ctx context.Context, payload *ImportPayload) error
func (r *Repository) Export(ctx context.Context, filter *QueryOptions) (*ExportPayload, error)
```

---

### 3. Service Layer (`service.go`)

**Purpose:** The service defines "how this feature works." It validates inputs, enforces rules, coordinates repository calls, and returns structured results. All three interfaces call the service. They never call the repository directly.

**Why this is the critical layer:** The service layer is where the Triple-Access Pattern delivers its value. Because the CLI, API, and Lua layers all call the same service methods, you are guaranteed consistent behavior. If you fix a validation bug in the service layer, it is fixed for all three interfaces simultaneously.

**Implementation guidelines:**

- **The service is a thin orchestration layer.** It contains validation, authorization, and workflow coordination. HTTP parsing, CLI flags, and Lua table conversion belong in the interface layers.
- **All logging goes through the service layer.** The repository returns data or errors. Interface layers log only transport events, such as incoming requests and sent responses. The service logs business events, such as entity creation and failed validation.
- **Use `sync.Once` for lazy initialization.** Many services need to create database tables or load default data on first use. Using `sync.Once` ensures this happens exactly once, even under concurrent access.
- **Return structured data, not formatted strings.** The service returns Go structs. Each interface layer formats those structs for its own needs (JSON for API, tables for CLI, Lua tables for Lua).

```go
type Service struct {
    repo *Repository
    mu   sync.Mutex // for operations requiring serialization
    once sync.Once  // for lazy schema initialization
}

// init runs once on first use. It creates database tables, loads defaults,
// and performs any other first-time setup.
func (s *Service) init(ctx context.Context) error {
    s.once.Do(func() {
        // Create schema, load defaults, etc.
    })
}

// Query is the generic, agent-friendly query interface.
// It accepts flexible filter options and returns a unified result type.
func (s *Service) Query(ctx context.Context, opts *QueryOptions) (*QueryResult, error)

// Type-specific CRUD methods delegate to the repository.
// The service layer adds validation, authorization, and logging.
func (s *Service) ListVendors(ctx context.Context, filter *VendorFilter) ([]Vendor, error)
func (s *Service) GetVendor(ctx context.Context, id string) (*Vendor, error)

// Batch operations coordinate multiple repository calls,
// often within a transaction.
func (s *Service) Import(ctx context.Context, payload *ImportPayload) error
func (s *Service) Export(ctx context.Context, filter *QueryOptions) (*ExportPayload, error)

// Statistics aggregate data for dashboards and monitoring.
func (s *Service) Stats(ctx context.Context) (*Stats, error)
```

---

### 4. CLI Layer (`cmd/sentinel/commands/{service}.go`)

**Purpose:** Expose the service to command-line users. CLI commands parse flags and arguments, call the service layer, and format the output for human or machine consumption.

**Why this layer is thin:** The CLI translates flags, arguments, and output formats into service method calls. Business rules belong in the service.

If a CLI handler uses an `if` statement for a business rule, move the rule to the service.

**Implementation guidelines:**

- **Commands map directly to service methods.** `sentinel lib vendor list` calls `svc.ListVendors()`. `sentinel lib export-all` calls `svc.ExportAll()`. Keep this mapping direct.
- **Use the CLI formatter for human-readable output.** Tables, colors, and summary lines make the output readable for operators in a terminal.
- **Support JSON output for machine consumption.** The generic `query` command outputs JSON specifically for AI agents and automation scripts that need to parse the results.
- **Inherit logger and runner context from the global Runner.** Use the logger and database connection from the DI container.

```go
var libCmd = &cobra.Command{
    Use: "lib",
    // ...
}

var vendorListCmd = &cobra.Command{
    Use:   "list",
    Short: "List vendors",
    RunE: func(cmd *cobra.Command, args []string) error {
        // The CLI handler is a thin adapter: parse flags, call service, format output.
        svc := library.NewService(db)
        vendors, err := svc.ListVendors(ctx, &library.VendorFilter{
            Name:   name,
            Limit:  limit,
            Offset: offset,
        })
        if err != nil {
            return err
        }
        // Format output as a human-readable table
        return formatter.PrintTable(vendors)
    },
}

var queryCmd = &cobra.Command{
    Use:   "query",
    Short: "Agent-friendly JSON query interface",
    RunE: func(cmd *cobra.Command, args []string) error {
        svc := library.NewService(db)
        result, err := svc.Query(ctx, &library.QueryOptions{
            EntityType: entityType,
            Filter:     filterMap,
            Limit:      limit,
            Offset:     offset,
        })
        if err != nil {
            return err
        }
        // Output as JSON for agents to parse
        return json.NewEncoder(os.Stdout).Encode(result)
    },
}
```

---

### 5. API Layer (`internal/api/{service}_handlers.go`)

**Purpose:** Expose the service through REST HTTP endpoints. API handlers parse HTTP requests, call the service layer, and write JSON responses.

**Why this layer is thin:** The API translates query parameters, request bodies, and headers into service calls. It translates service results and errors into HTTP responses. Business rules belong in the service.

**Implementation guidelines:**

- **Always return HTTP 200.** Sentinel communicates errors in the body as `{ok: false, err: "CODE", msg: "..."}`. Some HTTP clients and proxies retry or open a circuit after a non-200 response. This behavior is unsuitable for application errors.
- **Use the brevity regime for query parameters.** Short parameter names (`?n=`, `?lv=`, `?cp=`) reduce URL length and token count for AI agent consumers. Document the full name alongside the abbreviation.
- **Delegate all logic to the service.** The handler parses the request, calls the service, and writes the response. Keep `if` statements for business rules in the service.
- **Map service errors to response body error codes.** The service returns typed errors. The handler maps these to the appropriate error code strings.

```go
type APIHandler struct {
    svc *library.Service
}

// ListVendors handles GET /lib
func (h *APIHandler) ListVendors(w http.ResponseWriter, r *http.Request) {
    // Parse query parameters into a filter struct
    filter := &library.VendorFilter{
        Name:   r.URL.Query().Get("name"),
        Limit:  parseLimit(r),
        Offset: parseOffset(r),
    }

    // Call the service layer -- the exact same method the CLI calls
    vendors, err := h.svc.ListVendors(r.Context(), filter)
    if err != nil {
        h.writeError(w, err)
        return
    }

    // Write the JSON response. Always HTTP 200.
    h.writeJSON(w, 200, vendors)
}

// Query handles GET /lib/query -- the agent-friendly generic interface
func (h *APIHandler) Query(w http.ResponseWriter, r *http.Request) {
    opts := &library.QueryOptions{
        EntityType: r.URL.Query().Get("entity_type"),
        Filter:     parseFilter(r),
        Limit:      parseLimit(r),
        Offset:     parseOffset(r),
    }

    result, err := h.svc.Query(r.Context(), opts)
    if err != nil {
        h.writeError(w, err)
        return
    }

    h.writeJSON(w, 200, result)
}
```

---

### 6. Lua Layer (`internal/{service}/lua.go`)

**Purpose:** Expose the service to Lua flows running inside the Sentinel sandbox. Lua bindings allow flows to interact with harness services programmatically, enabling automation that spans multiple services.

**Why this layer exists:** Lua bindings give flows direct access to services within the harness process. Without bindings, flows need HTTP calls such as `sn.http.get("http://localhost:8080/lib")`. Those calls add serialization, transport, and deserialization. They also depend on the harness URL.

**Implementation guidelines:**

- **Registration follows the orchestrator pattern.** The Lua binding registration function is called from `orchestrator.RegisterLuaState()` during Lua VM initialization. This ensures bindings are available to every flow.
- **Function names follow Lua convention.** Examples include `sn.lib.vendor_list()` and `sn.lib.endpoint_create()`. The prefix matches the service's API route prefix.
- **Accept both positional args and Lua tables.** This gives flow authors flexibility. Positional arguments work for simple calls. Lua table arguments work for complex queries with many options.
- **Error handling uses the `(result, error_string)` return pattern.** On success, return the result and `nil`. On failure, return `nil` and an error string. This is the standard Lua convention that flow authors expect.
- **All operations are context-aware.** Use `L.Context()` to respect execution timeouts and cancellation.

```go
func RegisterLibraryAPI(L *lua.LState, svc *library.Service) {
    libTable := L.NewTable()

    // Each binding is a closure that captures the service instance.
    // This means every Lua VM gets its own set of closures, but they
    // all share the same underlying service (which is safe because
    // the service layer handles its own concurrency).
    libTable.RawSetString("vendor_list", L.NewClosure(func(L *lua.LState) int {
        filter := &library.VendorFilter{
            Name:   luaGetString(L, "name", 1),
            Limit:  luaGetInt(L, "limit", 10),
            Offset: luaGetInt(L, "offset", 0),
        }

        vendors, err := svc.ListVendors(L.Context(), filter)
        if err != nil {
            L.Push(lua.LNil)
            L.Push(lua.LString(err.Error()))
            return 2  // Return nil, error_string
        }

        return luaReturnJSON(L, vendors)  // Return JSON-encoded result
    }))

    // Query interface for agents calling from within Lua flows
    libTable.RawSetString("query", L.NewClosure(func(L *lua.LState) int {
        opts := &library.QueryOptions{}
        // Parse from Lua table argument
        result, err := svc.Query(L.Context(), opts)
        if err != nil {
            L.Push(lua.LNil)
            L.Push(lua.LString(err.Error()))
            return 2
        }
        return luaReturnJSON(L, result)
    }))

    // Batch import for efficiency
    libTable.RawSetString("import", L.NewClosure(func(L *lua.LState) int {
        data := lua.CheckString(L, 1)
        payload := &library.ImportPayload{}
        err := json.Unmarshal([]byte(data), payload)
        if err != nil {
            L.Push(lua.LNil)
            L.Push(lua.LString("invalid JSON: " + err.Error()))
            return 2
        }
        err = svc.Import(L.Context(), payload)
        if err != nil {
            L.Push(lua.LNil)
            L.Push(lua.LString(err.Error()))
            return 2
        }
        L.Push(lua.LTrue)
        return 1
    }))

    L.SetGlobal("sn.lib", libTable)
}
```

---

## Registration Flow

Understanding how the layers connect at runtime is essential for adding new services correctly.

### At Application Startup

The following sequence shows how a Lua VM is initialized with all service bindings:

```
Application Start
  -> App struct created with DI container
  -> Services instantiated (Service structs created, repos wired up)
  -> FlowManager.SetLuaStateSetup(setupFunc) called with the setup function

When a Flow Loads (triggered by API call, cron, webhook, or event):
  -> LStatePool.Get() creates a new Lua LState
  -> SetupSandbox(L) loads safe Lua libraries (string, table, math, etc.)
  -> setupFunc(L) is called:
     -> orch.RegisterLuaState(L) runs:
        -> RegAPI(L)              -- Connector and module APIs
        -> RegisterUtilities(L)   -- JSON, HTTP, time, crypto utilities
        -> RegisterLibraryAPI(L, svc)  -- Service Lua bindings
        -> RegisterTriggerHelpers(L)   -- Trigger registration functions
     -> RegisterCtxObject(L, flowCtx)  -- Flow execution context (ctx global)
  -> L.DoString(flowScript) executes the flow's Lua source code
```

### Step-by-Step: How to Register a New Service

For a new service that needs all three interfaces, follow these steps:

**Step 1: Create the service package** (`internal/{service_name}/`)

Create these files:
- `types.go` -- Domain models, filters, query options.
- `repository.go` -- All SQL operations.
- `service.go` -- Business logic, orchestration.
- `errors.go` -- Package-level error variables.
- `lua.go` -- Lua binding registration function.

**Step 2: Create CLI commands** (`cmd/sentinel/commands/{service_name}.go`)

- Define cobra commands that call service methods.
- Register the commands in `root.go` or the appropriate parent command.
- Use the formatter for table output, JSON for machine output.

**Step 3: Create API handlers** (`internal/api/{service_name}_handlers.go`)

- Define handler methods on an API handler struct.
- Register routes in the router setup (follow the brevity regime for route prefixes).
- Remember: always HTTP 200, errors in body.

**Step 4: Wire it all together in the DI container**

- Add the service instance to the `App` struct in `internal/app/`.
- Call the Lua binding registration in `orchestrator.RegisterLuaState()`.
- Initialize the service during app startup.

**Step 5: Update documentation**

- Add the new routes to `system-specs/api.yaml`.
- Add Lua bindings to the SRE Lua reference.
- Add CLI commands to the CLI reference.
- Update the URL map if new route prefixes were added.

---

## Error Handling

### Defining Error Codes

Each service must define error codes as package variables. Callers can compare error types with `errors.Is()`. All interfaces then use the same error codes.

```go
// internal/library/errors.go
var (
    ErrNotFound        = errors.New("RESOURCE_NOT_FOUND")
    ErrAlreadyExists   = errors.New("RESOURCE_ALREADY_EXISTS")
    ErrValidation      = errors.New("VALIDATION_ERROR")
    ErrInternal        = errors.New("INTERNAL_ERROR")
    ErrPermissionDenied = errors.New("PERMISSION_DENIED")
)
```

### Error Propagation Across Layers

Each layer handles errors differently, but they all originate from the same service-layer error:

- **Repository** -- Returns wrapped errors: `fmt.Errorf("query vendors: %w", err)`. The wrapping preserves the original error for `errors.Is()` while adding context.
- **Service** -- Maps repository errors to service-level errors. For example, if the repository returns `sql.ErrNoRows`, the service returns `ErrNotFound`. The service also logs errors at this point.
- **CLI** -- Uses the error code to format a user-friendly message. For example, `ErrNotFound` becomes "Resource not found: {id}".
- **API** -- Returns HTTP 200 with `{ok: false, err: "RESOURCE_NOT_FOUND", msg: "Vendor xyz not found"}`. The error code string comes directly from the error variable's message.
- **Lua** -- Returns `(nil, "RESOURCE_NOT_FOUND: Vendor xyz not found")`. The flow author can then examine the error string or simply handle any non-nil error.

---

## Logging

All business-level logging goes through the service layer. This centralizes log output and ensures that the same operation produces the same log entries regardless of which interface initiated it.

```go
// In service methods -- use slog-style key-value pairs
logger.Info("vendor_created",
    "vendor_id", vendor.ID,
    "vendor_name", vendor.Name,
)

logger.Error("vendor_delete_failed",
    "vendor_id", id,
    "error", err,
)
```

**Logging guidelines:**

- Use slog-style logging (key-value pairs, not printf format strings). This produces structured logs that are easy to parse and filter.
- Include IDs and names that identify the entity and operation in each log entry.
- Log errors with the `"error"` key so log aggregators can filter on it.
- The CLI inherits the Runner's logger. The API has its own middleware logger for request-level events. Lua flows log through `ctx.log()` from the execution context.

---

## Agent Optimization

AI agents are first-class consumers of Sentinel's APIs. The Triple-Access Pattern includes specific optimizations for agent interaction:

**1. Generic Query Interface:** The `Query()` method accepts flexible, string-based filters that agents can construct without knowing the exact filter struct types:

```lua
local result = sn.lib.query({
    entity_type = "endpoint",
    filter = {vendor_id = "openai", name_like = "chat%"},
    limit = 50,
    offset = 0
})
-- result.items contains the matching entities
-- result.total contains the total count (for pagination)
-- result.count contains the count of returned items
```

**2. Batch Operations:** Agents often need to create or update many entities at once. The `import`/`export` methods handle this efficiently:

```lua
local payload = {
    endpoints = {...},
    calls = {...}
}
sn.lib.import(sn.json.enc(payload))
```

**3. JSON Exchange:** All data is JSON-serializable, so agents can pipe data between services without transformation:

```lua
local data = sn.http.get("https://api.example.com/endpoints")
sn.lib.import(data.body)  -- Directly import from API response
```

---

## Testing Strategy

Each layer has its own testing approach, but the service layer receives the most testing because it contains the most logic:

- **Repository layer** -- Unit tests with an in-memory SQLite database (no mocking needed since SQLite is fast). Test SQL correctness, NULL handling, and transaction behavior.
- **Service layer** -- Integration tests use a real database in memory. They test business logic, validation, errors, and interactions between methods. Most tests belong in this layer.
- **CLI layer** -- Run commands as subprocesses. Make sure that the output is correct. Test argument parsing and output formatting.
- **API layer** -- Use `httptest` for HTTP client tests. Test request parsing, response formatting, and error code mapping.
- **Lua layer** -- End-to-end tests through Lua flows in test SREs. Make sure that Lua bindings correctly translate between Lua types and Go types.

---

## Example: Library Service

The `library` service in this codebase implements the full Triple-Access Pattern and serves as the reference implementation:

- Domain models + filters: `internal/library/types.go`.
- Repository layer: `internal/library/repository.go`.
- Service layer: `internal/library/service.go`.
- CLI commands: `cmd/sentinel/commands/lib.go`.
- API handlers: `internal/api/apilib_handlers.go`.
- Lua bindings: `internal/library/lua.go` (planned).

When adding a new service, model it after the library service. Copy its structure, adapt the types, and follow the same patterns.

---

## Migration Path for Existing Services

If API and CLI handlers duplicate business logic, follow this migration path:

1. **Extract domain models** into `types.go`. Pull struct definitions out of handler files and CLI files into a shared types file.
2. **Create `repository.go`** with all SQL operations. Find every SQL query in the existing handlers and CLI commands and move them into repository methods.
3. **Create `service.go`** with orchestration logic. Extract validation, business rules, and multi-step workflows from handlers and CLI into service methods.
4. **Refactor API handlers** to call service methods. Keep each handler limited to parsing the request, calling the service, and writing the response.
5. **Refactor CLI commands** to call the same service methods. Make sure that behavior is identical to the API.
6. **Add Lua bindings** in `lua.go`. Follow the registration pattern described above.
7. **Focus tests on the service layer.** Test the shared business logic here to reduce duplicate tests.

This migration ensures all three interfaces stay in sync automatically from now on. Any new feature or bug fix only needs to be implemented once, in the service layer.
