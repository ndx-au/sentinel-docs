---
title: "Kit Development Guide"
description: "Complete guide to building kits -- the fundamental unit of organization in Sentinel -- with flows, connectors, modules, forms, pages, databases, CMS content, and templates."
---

# Kit Development Guide

Complete guide to building kits -- the fundamental unit of organization in Sentinel -- with flows, connectors, modules, forms, pages, databases, CMS content, and templates.

---

## Introduction

A **kit** is a self-contained, composable package that encapsulates a set of related automation workflows, integrations, user interfaces, and data. Kits are the building blocks of every Sentinel project.

The kit philosophy is built on three principles:

1. **Self-contained**: A kit carries everything it needs -- its flows, connectors, modules, forms, pages, templates, assets, database schema, and documentation. You can copy a kit directory from one project to another and it works (assuming its dependencies are met).

2. **Composable**: Kits can depend on other kits, import from their databases, and emit events that other kits listen for. A complex automation system is built by composing multiple focused kits rather than building one monolithic codebase.

3. **Git-native**: Kits are plain directories of files. They are tracked in git, diffed, branched, merged, and code-reviewed using standard git workflows. There is no binary package format, no registry lock files, and no hidden state outside the `.sentinel/` directory.

Every Sentinel project is ultimately a collection of kits. Even a project with a single automation flow has that flow inside a kit. The harness discovers kits automatically at startup by scanning the project root for directories that match the naming pattern and contain a `kit.yaml` manifest.

Fresh projects initialized with `sentinel sre init` now ship with a starter ecosystem as working references: `sn.core-agent`, `sn.core-rag`, `sn.tools-http`, `sn.supervisor`, `sn.eg-support`, `sn.eg-itops`, `sn.eg-rag-chat`, plus the legacy compatibility examples `sn.example-support` and `sn.example-itops`.

---

## Kit Discovery

When the harness starts, it scans the project root directory for kit directories. A directory is recognized as a kit if:

1. Its name follows the `{namespace}.{name}` pattern (e.g., `acme.billing`, `sn.core-agent`, `my.utils`).
2. It contains a `kit.yaml` file at its root.

Both conditions must be met. A directory called `acme.billing` without a `kit.yaml` is ignored. A directory called `utilities` with a `kit.yaml` is also ignored because it does not match the naming pattern.

**Naming rules:**

- The **namespace** is a short identifier for the organization or author. Examples: `sn` (Sentinel built-in), `acme` (a company), `jd` (a developer's initials).
- The **name** is a short identifier for the kit's purpose. Examples: `core`, `billing`, `diag`, `blog`.
- Both parts must be lowercase alphanumeric. Hyphens are allowed within each part but not as the first or last character.
- The dot (`.`) is the separator and must appear exactly once.

**Discovery is flat**: Kits must be direct children of the project root. Nested kits (a kit inside another kit) are not supported. The harness does not recurse into subdirectories.

**Discovery is automatic**: You do not need to list kits in any configuration file. Simply create the directory with a `kit.yaml` and the harness finds it on startup (or via hot-reload if the harness is already running).

**Flow ID format**: Flows within a kit have a fully-qualified ID of `{namespace}-{name}:{flow}`. For example, the file `acme.billing/fl/process-payment.lua` becomes the flow `acme-billing:process-payment`. The `fl/` directory prefix and `.lua` extension are stripped.

---

## Kit Structure

A kit directory can contain any combination of the following subdirectories. Only `kit.yaml` is required; everything else is optional.

```
acme.billing/
  kit.yaml                    # Manifest (required)
  kit.yaml.md                 # Skill twin for AI agent context
  README.md                   # Human/operator docs with compatibility matrix

  fl/                         # Flows (Lua scripts -- the core business logic)
    process-payment.lua
    process-payment.lua.md    # Skill twin
    generate-invoice.lua
    generate-invoice.lua.md
    refund.lua
    refund.lua.md

  cn/                         # Connectors (Lua scripts for external integrations)
    stripe.lua
    stripe.lua.md

  md/                         # Modules (reusable Lua libraries)
    invoice.lua               # Module: reusable code
    invoice.lua.md            # Skill twin for the module
  ct/                         # CMS content (.md files)
    hello-world.md            # CMS: Markdown content (if kit has CMS content)

  pg/                         # Pages (YAML definitions for web UI pages)
    dashboard.yaml
    dashboard.yaml.md
    settings.yaml
    settings.yaml.md

  fm/                         # Forms (YAML definitions for user input forms)
    payment.yaml
    payment.yaml.md

  tp/                         # Templates (Go HTML templates for rendering pages)
    dashboard.gohtml
    dashboard.gohtml.md

  pb/                         # Public assets (CSS, JavaScript, images)
    styles.css
    styles.css.md
    logo.png
    app.js

  dd/                         # Data definitions (database schema)
    schema.yaml

  assets.yaml                 # Optional: CMS asset URL rewriting rules
```

**Directory name conventions:**

| Directory | Purpose | Content Types |
|-----------|---------|---------------|
| `fl/` | Flows | `.lua` files (auto-discovered, each becomes a runnable flow) |
| `cn/` | Connectors | `.lua` files (registered in the `sn.cn.{ns}.{name}` namespace) |
| `md/` | Modules | `.lua` files (registered in the `sn.md.*` namespace) |
| `ct/` | CMS content | `.md` files (parsed and exposed through `sn.cms.*` and `/cm`) |
| `pg/` | Pages | `.yaml` files (page definitions referencing templates) |
| `fm/` | Forms | `.yaml` files (form definitions with fields and events) |
| `tp/` | Templates | `.gohtml` files (Go HTML templates for rendering pages) |
| `pb/` | Public assets | Any file type (served publicly via HTTP) |
| `dd/` | Data definitions / migrations | **ccms:** ordered `.sql` migrations (`sentinel ccms migrate`). Legacy kit SQLite helpers may still use `.yaml` schemas — do not confuse with ccms SQL migrations. |

---

## Creating a Kit

### Via CLI

The fastest way to create a kit is with the `kit new` command:

```bash
./sentinel sre kit new acme.billing --desc "Payment processing workflows" -p /path/to/project
```

This creates the directory with a `kit.yaml` and the standard subdirectories (`fl/`, `cn/`, `md/`). It also creates a git commit unless you pass `--no-commit`.

For common workflows, use scaffold presets instead of starting from empty files:

```bash
./sentinel sre flow new assistant --kit acme.billing --preset agent
./sentinel connector new stripe_lookup --kit acme.billing --preset tool
./sentinel module new knowledge --kit acme.billing --preset rag
```

### Manual Creation

You can also create a kit by hand:

1. Create the directory at the project root: `mkdir acme.billing`
2. Create the manifest file `acme.billing/kit.yaml`:

```yaml
name: Billing Module
version: 1.0.0
description: Process payments and invoices
author: Your Name
```

3. Create any subdirectories you need:

```bash
mkdir -p acme.billing/{fl,cn,md,fm,pg,tp,pb,dd}
```

The harness discovers the kit on next startup (or immediately via hot-reload if running).

Validate it before handoff:

```bash
./sentinel sre validate
./sentinel sre validate acme.billing
```

---

## Kit Manifest (kit.yaml)

The `kit.yaml` file is the only required file in a kit. It describes the kit's identity, configuration, and capabilities.

### Minimal Manifest

The absolute minimum is a single `name` field:

```yaml
name: My Module
```

This is sufficient for a kit that contains only flows. The namespace and kit-name are inferred from the directory name.

### Complete Schema Reference

```yaml
# ── Identity ────────────────────────────────────────────────────────

name: E-Commerce Billing
# Required. Human-readable display name shown in the dashboard and API.

namespace: acme
# Optional. Override the namespace inferred from the directory name.
# Normally inferred from the part before the dot (e.g., "acme" from "acme.billing").

kit-name: billing
# Optional. Override the kit name inferred from the directory name.
# Normally inferred from the part after the dot (e.g., "billing" from "acme.billing").

version: 2.1.0
# Optional. Semantic version of the kit. Used for marketplace publishing
# and dependency resolution. Follow semver: MAJOR.MINOR.PATCH.

description: |
  Complete billing system with payment processing,
  invoice generation, and refund handling.
# Optional. Multi-line description of the kit's purpose. Displayed in
# the dashboard kit explorer and marketplace listings.

author: "Acme Corp <billing@acme.com>"
# Optional. Author or organization name with optional email.

# ── Visibility ──────────────────────────────────────────────────────

public: false
# Optional (default: false). When true, the kit's pages and forms are
# accessible without bearer token authentication. When false, all kit
# web routes require authentication.

protected: false
# Optional (default: false). When true, the kit prompts for a password
# on first access. This is a lightweight access control for kits that
# need a gate but not full authentication.

# ── Branding ────────────────────────────────────────────────────────
# UI customization for kits that serve web pages. Only relevant if the
# kit has a pg/ directory with page definitions.

branding:
  title: Billing Dashboard
  # Page title shown in the browser tab and dashboard header.

  logo: /pb/logo.png
  # Path to the logo image, relative to the kit's public assets.

  favicon: /pb/favicon.ico
  # Path to the favicon.

  theme:
    primary_color: "#2563eb"
    # Primary UI color for buttons, links, and headings.

    accent_color: "#3b82f6"
    # Secondary accent color for highlights and hover states.

    dark_mode: true
    # Enable dark mode for the kit's web UI.

# ── Navigation ──────────────────────────────────────────────────────
# Define the navigation menu for kits with web pages. Items appear in
# the sidebar or header navigation of the kit's web UI.

navigation:
  primary:
    - name: Dashboard
      path: /
      icon: dashboard
      # Built-in icon name. Available icons depend on the dashboard theme.

    - name: Invoices
      path: /invoices
      icon: receipt

    - name: Settings
      path: /settings
      icon: settings

# ── Pages ───────────────────────────────────────────────────────────
# Page definitions can be here or in separate pg/*.yaml files.
# When defined here, they do not need separate YAML files.

pages:
  - name: dashboard
    path: /
    # URL path within the kit's route space.
    # Full URL: /kt/{namespace}/{name}{path}

    title: Billing Dashboard
    template: dashboard.gohtml
    # References a file in the tp/ directory.

    layout: default
    # Layout template to wrap this page in.

    requires_auth: true
    # Whether this page requires authentication.

  - name: invoices
    path: /invoices
    title: Invoices
    template: invoices.gohtml
    requires_auth: true

# ── Forms ───────────────────────────────────────────────────────────
# Form definitions can be here or in separate fm/*.yaml files.

forms:
  - name: payment
    stub: billing-payment
    # The stub is a unique identifier for this form, used in event names
    # and form data access. Event: kf.{namespace}.{name}.{form-name}

    fields:
      - name: invoice_id
        type: text
        label: Invoice ID
        required: true
      - name: amount
        type: number
        label: Amount
        required: true

# ── Database ────────────────────────────────────────────────────────
# Database schema definition. The harness creates tables on startup.
# Each kit gets its own isolated SQLite database.

database:
  enabled: true
  tables:
    - name: invoices
      columns:
        - id TEXT PRIMARY KEY
        - amount REAL
        - status TEXT
        - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    - name: payments
      columns:
        - id TEXT PRIMARY KEY
        - invoice_id TEXT
        - amount REAL
        - created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

  imports:
    - shared
    # Import read access to another kit's database. This allows
    # cross-kit queries. The imported kit's name (without namespace) is used.

# ── Dependencies ────────────────────────────────────────────────────
# Declare what this kit requires to function correctly.

dependencies:
  harness: ">=1.0.0"
  # Minimum harness version required.

  kits:
    sn.core-agent: ">=1.0.0"
    # Other kits this kit depends on. Used for dependency resolution
    # during marketplace installation.

  primitives: ["email", "http"]
  # Built-in harness primitives that this kit uses.

# ── Permissions ─────────────────────────────────────────────────────
# Role-based access control for kit pages and forms.

permissions:
  roles:
    admin:
      pages: ["*"]
      forms: ["*"]
      # Wildcard: access to all pages and forms.

    user:
      pages: ["dashboard"]
      forms: ["payment"]
      # Specific pages and forms by name.

    viewer:
      pages: ["dashboard"]
      # Read-only: pages but no forms.

# ── Cache ───────────────────────────────────────────────────────────
# Response caching for kit web pages.

cache:
  ttl: 3600
  # Cache TTL in seconds. Pages are cached for this duration.

  vary_by: ["user_id"]
  # Cache key includes these variables, creating separate caches per user.

  bust_on_submit: true
  # Clear the cache when a form is submitted, ensuring the user sees
  # fresh data after submitting.

# ── Events ──────────────────────────────────────────────────────────
# Event definitions for this kit. Events are emitted by flows and can
# trigger other flows (in this kit or other kits).

events:
  payment.processed:
    flows: ["send-confirmation-email"]
    # Flows to trigger when this event fires.

    on_submit: confirmation.gohtml
    # Template to display after the event is processed (for form-triggered events).

# ── CMS Flags ──────────────────────────────────────────────────────

cms_full_html: false
# Optional (default: false). When true, the CMS parser generates a
# full_html field containing the entire document rendered as a single
# HTML string. Useful for templates that render the whole document at
# once. Note: full_html is only populated on cold start, not during
# hot-reload.

# ── Kit Configuration ──────────────────────────────────────────────
# Arbitrary key-value pairs accessible from flows via kit config API.

config:
  stripe_api_key: "vault_key"
  # "vault_key" indicates this value should be retrieved from the vault.

  notification_email: "billing@example.com"
  # Plain text configuration values.
```

---

## Flows (fl/)

Flows are the core business logic of a kit. Each `.lua` file in the `fl/` directory becomes a runnable flow, identified by its filename (without the `.lua` extension).

### Flow Lifecycle

Every flow follows a strict lifecycle with four callback functions:

```lua
function setup()
  -- Called before main(). Use for initialization, resource allocation,
  -- or pre-flight checks. Optional.
end

function main(params)
  -- The primary entry point. This is where your business logic goes.
  -- Called after setup() completes successfully. Required.
  --
  -- The params table contains trigger data (webhook payload, cron metadata,
  -- event data, etc.). The ctx global is also available here with logging,
  -- secrets, execution metadata, and trigger information.
end

function cleanup()
  -- Called after main() completes (whether success or failure).
  -- Use for releasing resources, closing connections, or final logging.
  -- Optional.
end

function failed(err)
  -- Called when main() throws an error or exceeds the execution timeout.
  -- The err parameter contains the error message.
  -- Use for error reporting, alerting, or rollback logic.
  -- Optional.
end
```

**Execution order:**

- Normal execution: `setup()` -> `main()` -> `cleanup()`
- Error execution: `setup()` -> `main()` (error occurs) -> `failed(err)` -> `cleanup()`

**Important notes:**

- The `main(params)` function receives a params table containing trigger data. Additional context is available through the `ctx` global.
- There is no `flow = {}` metadata table. Flow metadata is auto-discovered from the file's triggers and the kit manifest.
- The `ctx` global is available in all four functions.

### The ctx Global

The `ctx` global provides access to execution context, logging, secrets, state, and trigger information.

| Function/Field | Description |
|---------------|-------------|
| `ctx.log(level, message)` | Write a log entry. Level is one of: `"debug"`, `"info"`, `"warn"`, `"error"`. |
| `ctx.get(key)` | Reserved for future use. Currently a stub that always returns `nil`. |
| `ctx.set(key, value)` | Reserved for future use. Currently a no-op stub. |
| `ctx.secret(name)` | Retrieve a secret from the vault by name. |
| `ctx.execution_id` | The unique ID of this execution (string). |
| `ctx.trigger_type` | How this execution was triggered: `"manual"`, `"cron"`, `"webhook"`, `"event"`, `"form"`. |
| `ctx.params` | Trigger data table (same data as the `params` argument to `main(params)`). |
| `ctx.req` | HTTP request metadata (available for webhook and manual triggers). |
| `ctx.fm` | Form data table (populated when triggered by a form submission). |

### Basic Flow Example

```lua
-- acme.billing/fl/process-payment.lua

function setup()
  ctx.log("info", "Payment flow starting")
end

function main(params)
  -- Access trigger parameters
  local invoice_id = params.invoice_id

  -- Access secrets from the vault
  local stripe_key = ctx.secret("stripe_api_key")

  -- Make an HTTP request via a connector
  local resp = sn.cn.acme.billing.exec({
    method = "POST",
    path = "/charges",
    data = { amount = 1000, source = "tok_visa" }
  })

  -- Store data in the kit's database
  sn.db.exec(
    "INSERT INTO payments (id, invoice_id, amount, status) VALUES (?, ?, ?, ?)",
    { "pay_123", invoice_id, 1000, "completed" }
  )

  -- Emit an event for other flows to react to
  sn.event.emit("payment.completed", {
    invoice_id = invoice_id,
    amount = 1000
  })

  ctx.log("info", "Payment processed successfully")
end

function cleanup()
  ctx.log("debug", "Payment flow cleanup complete")
end

function failed(err)
  ctx.log("error", "Payment failed: " .. err)
end
```

### Trigger Definitions

Triggers define how a flow is automatically invoked. They are declared as a top-level `triggers` table in the Lua file, outside of any function.

**Cron trigger** -- Execute on a schedule:

```lua
triggers = {
  cron("0 1 * * *", { tz = "UTC" })  -- Daily at 1:00 AM UTC
}

function main(params)
  ctx.log("info", "Daily billing summary running")
  -- Your scheduled logic here
end
```

The cron expression follows standard 5-field cron syntax: `minute hour day-of-month month day-of-week`. The optional `tz` parameter sets the timezone (default: UTC).

**Webhook trigger** -- Execute when an HTTP request arrives:

```lua
triggers = {
  webhook("/stripe-events", {
    auth = "hmac",              -- "none" | "hmac" | "bearer" | "header"
    key = "stripe_webhook_secret", -- Vault secret name (hmac/bearer/header)
    alg = "sha256",             -- HMAC algorithm
    sig_hdr = "Stripe-Signature", -- HMAC signature header
    hdr = "X-Telegram-Bot-Api-Secret-Token" -- shared-secret header (auth="header")
  })
}

function main(params)
  -- Webhook payload is available via params
  ctx.log("info", "Webhook event received: " .. ctx.trigger_type)
  -- params contain the parsed webhook body
end
```

Webhook URLs are constructed as:
- Global: `/wh/{webhook-path}` (e.g., `/wh/stripe-events`)
- Kit-scoped: `/kt/{ns}/{name}/wh/{webhook-path}` (e.g., `/kt/acme/billing/wh/stripe-events`)

**Event trigger** -- Execute when an internal event is emitted:

```lua
triggers = {
  event("payment.*"),        -- Wildcard: any event starting with "payment."
  event("invoice.created")   -- Specific event name
}

function main(params)
  ctx.log("info", "Event triggered: " .. ctx.trigger_type)
  -- Handle the event
end
```

Events are emitted from Lua flows via `sn.event.emit("event.name", data)`. A flow can listen for multiple events by declaring multiple `event()` entries in its triggers table.

**Form trigger** -- Execute when a form is submitted:

```lua
triggers = {
  event("kf.acme.billing.payment")  -- Form submission event
}

function main(params)
  -- Form data is accessible via ctx.fm
  -- The key is the form's stub name
  local invoice_id = ctx.fm["billing-payment"].invoice_id
  local amount = ctx.fm["billing-payment"].amount

  ctx.log("info", "Processing form submission for invoice " .. invoice_id)
end
```

Form submission events follow the pattern `kf.{namespace}.{name}.{form-name}`. The form data is stored in `ctx.fm` keyed by the form's `stub` value.

---

## Connectors (cn/)

Connectors are Lua scripts that encapsulate integration with an external service. They provide a reusable, standardized interface that flows call to interact with APIs, databases, or other systems.

### How Connectors Work

When the harness loads a kit, it scans the `cn/` directory for `.lua` files. Each connector registers whichever public table/functions it chooses under `sn.cn.*`. For example, the shipped `sn.tools-http/cn/http_json.lua` connector registers `sn.cn.http_json`.

### Example Connector

```lua
-- acme.billing/cn/stripe.lua
local connector = {}

function connector.exec(config)
  local method = config.method or "GET"
  local path = config.path or "/"
  local data = config.data

  -- Retrieve the API key from the vault
  local api_key = ctx.secret("stripe_api_key")

  local headers = {
    Authorization = "Bearer " .. api_key,
    ["Content-Type"] = "application/json"
  }

  local url = "https://api.stripe.com/v1" .. path

  if method == "GET" then
    return sn.http.get(url, { headers = headers })
  elseif method == "POST" then
    return sn.http.post(url, sn.json.enc(data), { headers = headers })
  elseif method == "DELETE" then
    return sn.http.del(url, { headers = headers })
  end
end

return connector
```

### Using Connectors in Flows

Connectors are called through the `sn.cn` namespace:

```lua
-- In a flow
function main(params)
  local resp = sn.cn.acme.billing.exec({
    method = "POST",
    path = "/charges",
    data = { amount = 1000, currency = "usd", source = "tok_visa" }
  })

  if resp.status ~= 200 then
    ctx.log("error", "Stripe error: " .. resp.body)
    return
  end

  local charge = sn.json.dec(resp.body)
  ctx.log("info", "Charge created: " .. charge.id)
end
```

### Connector Best Practices

- Keep connectors focused on a single external service.
- Handle authentication inside the connector (using `ctx.secret()`) so flows do not need to manage API keys.
- Return structured responses that flows can easily work with.
- Log errors inside the connector for debugging, but also propagate them to the calling flow.

---

## Modules (md/)

Modules are reusable Lua code libraries that provide shared functionality across multiple flows within a kit. Unlike connectors (which integrate with external services), modules contain internal business logic, data transformations, validation rules, and utility functions.

### How Modules Work

Modules in the `md/` directory are registered in the `sn.md.{namespace}.{name}` namespace. A module must return a table containing its public functions.

### Example Module

```lua
-- acme.billing/md/invoice.lua
local invoice_module = {}

function invoice_module.create(amount, customer_id)
  ctx.log("info", "Creating invoice for customer: " .. customer_id)

  local invoice_id = "inv_" .. sn.crypto.random_bytes(16)

  sn.db.exec(
    "INSERT INTO invoices (id, amount, customer_id, status, created_at) VALUES (?, ?, ?, ?, ?)",
    { invoice_id, amount, customer_id, "draft", os.time() }
  )

  return invoice_id
end

function invoice_module.finalize(invoice_id)
  sn.db.exec(
    "UPDATE invoices SET status = ? WHERE id = ?",
    { "finalized", invoice_id }
  )

  sn.event.emit("invoice.finalized", { invoice_id = invoice_id })
end

function invoice_module.get(invoice_id)
  return sn.db.query_one(
    "SELECT * FROM invoices WHERE id = ?",
    { invoice_id }
  )
end

return invoice_module
```

### Using Modules in Flows

Modules are accessed through the `sn.md` namespace:

```lua
-- In a flow
function main(params)
  local invoice = sn.md.acme.billing

  local inv_id = invoice.create(9999, "cust_123")
  invoice.finalize(inv_id)

  local inv = invoice.get(inv_id)
  ctx.log("info", "Invoice amount: " .. inv.amount)
end
```

---

## Forms (fm/)

Forms capture user input through a web interface and trigger flows when submitted. Each `.yaml` file in the `fm/` directory defines a form.

### Form YAML Schema

```yaml
name: Payment Form
# Required. Human-readable name displayed at the top of the form.

stub: billing-payment
# Required. Unique identifier for this form. Used in:
#   - Event name: kf.{namespace}.{name}.{form-name}
#   - Form data access: ctx.fm["{stub}"]
#   - URL path: /kt/{ns}/{name}/fm/{stub}

description: Submit payment for an invoice
# Optional. Explanatory text displayed below the form title.

password: null
# Optional. If set, the form requires this password before displaying.
# Set to null or omit for no password protection.

fields:
  - name: invoice_id
    type: text
    label: Invoice ID
    placeholder: "INV-2026-001"
    required: true
    validation: "^INV-[0-9-]+$"
    help_text: "Enter the invoice number (format: INV-YYYY-NNN)"
    # Validation is a regex pattern. The field value must match this pattern
    # for the form to submit successfully.

  - name: amount
    type: number
    label: Amount to Pay
    required: true
    default: "0.00"
    # Default value pre-fills the field.

  - name: card_token
    type: text
    label: Card Token
    required: true
    help_text: "Use Stripe tokenized card reference"

  - name: email
    type: email
    label: Confirmation Email
    required: true
    # The email type validates that the input is a properly formatted email address.

  - name: notes
    type: textarea
    label: Additional Notes
    required: false
    # Textarea renders as a multi-line text input.

  - name: payment_method
    type: select
    label: Payment Method
    required: true
    options:
      - value: credit_card
        label: Credit Card
      - value: bank_transfer
        label: Bank Transfer
      - value: paypal
        label: PayPal
    # Select renders as a dropdown menu.

  - name: agree_terms
    type: checkbox
    label: I agree to the terms and conditions
    required: true
    # Checkbox renders as a single toggle. When required, it must be checked.

  - name: delivery_date
    type: date
    label: Preferred Delivery Date
    required: false
    # Date renders as a date picker.

  - name: attachments
    type: file
    label: Supporting Documents
    required: false
    # File renders as a file upload input.

  - name: categories
    type: multiselect
    label: Applicable Categories
    required: false
    options:
      - value: services
        label: Services
      - value: products
        label: Products
      - value: subscription
        label: Subscription
    # Multiselect allows choosing multiple options.

on_submit: confirmation.gohtml
# Optional. Template file (in tp/) to render after successful submission.
# If omitted, a default success message is shown.
```

### Available Field Types

| Type | Description | Rendered As |
|------|-------------|------------|
| `text` | Single-line text input | `<input type="text">` |
| `email` | Email address with validation | `<input type="email">` |
| `number` | Numeric input | `<input type="number">` |
| `textarea` | Multi-line text input | `<textarea>` |
| `select` | Single-choice dropdown | `<select>` with `<option>` elements |
| `checkbox` | Boolean toggle | `<input type="checkbox">` |
| `date` | Date picker | `<input type="date">` |
| `file` | File upload | `<input type="file">` |
| `multiselect` | Multiple-choice selection | Multi-select widget |

### Form Events

When a form is submitted, the harness automatically emits an event:

- Event name pattern: `kf.{namespace}.{name}.{form-name}`
- Example: Submitting the `payment` form in `acme.billing` emits `kf.acme.billing.payment`

Any flow that listens for this event is triggered with the form data available in `ctx.fm`:

```lua
triggers = {
  event("kf.acme.billing.payment")
}

function main(params)
  local data = ctx.fm["billing-payment"]  -- Keyed by the form's stub
  local invoice_id = data.invoice_id
  local amount = data.amount
  local email = data.email

  ctx.log("info", "Processing payment for " .. invoice_id)
  -- Business logic here
end
```

### Form Validation

Fields support these validation features:

- **`required: true`**: The field must have a non-empty value.
- **`validation: "regex"`**: The field value must match the provided regular expression.
- **`type` validation**: The `email` type checks for valid email format; `number` checks for numeric input.

Client-side validation provides immediate feedback. Server-side validation runs before the form event is emitted.

---

## Pages (pg/) and Templates (tp/)

Pages define web UI screens served by the kit. Each page is a YAML definition that references an HTML template.

### Page Definition (pg/*.yaml)

```yaml
name: dashboard
# Required. Unique name for this page within the kit.

path: /
# Required. URL path within the kit's route space.
# Full URL: /kt/{namespace}/{name}{path}
# Example: /kt/acme/billing/ for path: /

title: Billing Dashboard
# Required. Page title shown in the browser tab.

template: dashboard.gohtml
# Required. References a file in the tp/ directory.

layout: default
# Optional. Layout template to wrap this page.

requires_auth: true
# Optional (default: false). Whether authentication is required to view this page.
```

### Template Syntax

Templates use Go's `html/template` package. They receive data from the harness and from Lua flows (when a page is backed by a flow).

**Available variables in all templates:**

| Variable | Description |
|----------|-------------|
| `{{ .kit_name }}` | The kit identifier (e.g., `acme.billing`) |
| `{{ .page.name }}` | The page name from the YAML definition |
| `{{ .page.title }}` | The page title from the YAML definition |
| `{{ .user }}` | User information (if authenticated) |

**Custom data** from a backing Lua flow is merged into the template context. For example, if a flow returns `{ ok = true, invoices = {...} }`, the template can access `{{ .invoices }}`.

### Template Example

```html
<!-- acme.billing/tp/dashboard.gohtml -->
<!DOCTYPE html>
<html>
<head>
  <title>{{ .page.title }}</title>
  <link rel="stylesheet" href="/kt/acme/billing/pb/styles.css">
</head>
<body>
  <h1>{{ .page.title }}</h1>

  <div class="invoices">
    {{ range .invoices }}
    <div class="invoice">
      <h3>{{ .id }}</h3>
      <p>Amount: ${{ .amount }}</p>
      <p>Status: {{ .status }}</p>
    </div>
    {{ end }}
  </div>

  <script src="/kt/acme/billing/pb/app.js"></script>
</body>
</html>
```

### Template Helpers

Two special template functions are available for CMS rendering:

**querySelector(result, "slug-path")** -- Extracts a section's HTML from a CMS ParseResult. Navigate nested sections using dot notation.

```html
{{- $post := .post -}}
{{- if $post -}}
<!-- Extract top-level section by slug -->
<div class="intro">{{ querySelector $post "getting-started" }}</div>

<!-- Extract nested section via dot path -->
<div class="install">{{ querySelector $post "getting-started.installation" }}</div>
{{- end -}}
```

The function returns `template.HTML` (safe, no additional escaping). It returns an empty string for nil results, missing paths, or empty paths -- it never panics.

**safeHTML(str)** -- Marks a string as safe HTML, bypassing `html/template` auto-escaping. Use this only for HTML generated by the CMS parser (trusted content), never for user-supplied input.

```html
<article>
  {{ safeHTML .post.full_html }}
</article>
```

---

## Database

Each kit can have its own isolated SQLite database. Kit databases are stored at `.sentinel/data/{namespace}.{name}.db` and are completely separate from other kits' databases.

### Schema Definition (dd/schema.yaml)

Define your database schema in `dd/schema.yaml`. The harness creates tables on startup if they do not exist.

```yaml
tables:
  invoices:
    id:
      type: TEXT PRIMARY KEY
    customer_id:
      type: TEXT
    amount:
      type: REAL
    status:
      type: TEXT DEFAULT 'draft'
    created_at:
      type: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    updated_at:
      type: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

  payments:
    id:
      type: TEXT PRIMARY KEY
    invoice_id:
      type: TEXT
    amount:
      type: REAL
    status:
      type: TEXT
    created_at:
      type: TIMESTAMP DEFAULT CURRENT_TIMESTAMP

  indexes:
    - name: idx_invoices_customer
      table: invoices
      columns: [customer_id]
    - name: idx_payments_invoice
      table: payments
      columns: [invoice_id]
```

### Database Access in Lua

```lua
-- Create tables (alternative to dd/schema.yaml)
sn.db.exec("CREATE TABLE IF NOT EXISTS invoices (id TEXT PRIMARY KEY, amount REAL, status TEXT)")

-- Insert
sn.db.exec(
  "INSERT INTO invoices (id, amount, status) VALUES (?, ?, ?)",
  { "inv_001", 99.99, "draft" }
)

-- Query multiple rows
local invoices = sn.db.query(
  "SELECT * FROM invoices WHERE status = ?",
  { "draft" }
)
for _, inv in ipairs(invoices) do
  ctx.log("info", "Invoice: " .. inv.id .. " Amount: " .. inv.amount)
end

-- Query single row
local invoice = sn.db.query_one(
  "SELECT * FROM invoices WHERE id = ?",
  { "inv_001" }
)

-- Update
sn.db.exec(
  "UPDATE invoices SET status = ? WHERE id = ?",
  { "paid", "inv_001" }
)

-- Delete
sn.db.exec(
  "DELETE FROM invoices WHERE status = ? AND created_at < ?",
  { "draft", "2026-01-01" }
)

-- Transaction (multiple operations that succeed or fail together)
sn.db.transaction(function()
  sn.db.exec("UPDATE invoices SET status = ? WHERE id = ?", { "paid", "inv_001" })
  sn.db.exec("INSERT INTO payments (id, invoice_id, amount) VALUES (?, ?, ?)",
    { "pay_001", "inv_001", 99.99 })
end)
```

### Schema Design Patterns

**Use TEXT for IDs**: SQLite is typeless internally, but TEXT PRIMARY KEY with generated IDs (e.g., `inv_` prefix + random bytes) provides human-readable, unique identifiers.

**Use TIMESTAMP DEFAULT CURRENT_TIMESTAMP**: For audit trails and chronological queries.

**Create indexes for frequent queries**: If you frequently query by `customer_id`, create an index. Without it, SQLite does a full table scan.

**Use transactions for multi-step operations**: Any operation that modifies multiple tables or multiple rows should be wrapped in `sn.db.transaction()` to ensure atomicity.

### Cross-Kit Database Access

By default, each kit can only access its own database. To read from another kit's database, declare the import in `kit.yaml`:

```yaml
database:
  enabled: true
  imports:
    - shared    # Read access to {ns}.shared database
```

This allows read-only SELECT queries against the imported kit's tables. Write access is never granted across kits.

---

## Static Assets (pb/)

The `pb/` directory contains publicly accessible files: CSS stylesheets, JavaScript files, images, fonts, and any other static content needed by the kit's web UI.

**Asset URL format:**

```
/kt/{namespace}/{name}/pb/{filename}
```

**Examples:**

```
/kt/acme/billing/pb/styles.css
/kt/acme/billing/pb/app.js
/kt/acme/billing/pb/logo.png
/kt/acme/billing/pb/fonts/Inter.woff2
```

**Usage in templates:**

```html
<link rel="stylesheet" href="/kt/acme/billing/pb/styles.css">
<script src="/kt/acme/billing/pb/app.js"></script>
<img src="/kt/acme/billing/pb/logo.png" alt="Logo">
```

Assets are served with appropriate Content-Type headers based on file extension. They do not require authentication (they are public by design -- do not put sensitive content in `pb/`).

### Kit catalog images (optional)

Place branding files under `{namespace}.{name}/pb/` using **fixed basenames**. The harness picks the first existing extension per slot: **`.svg` → `.png` → `.jpg`**. No manifest or dashboard config entry is required — drop files on disk and reload the kit/SRE.

Authoritative dimensions and basenames: `system-specs/kits.yaml` → `branding.images`.

The harness does **not** validate pixel size. The dashboard (`/kits`, `/kitview`) uses `object-fit: fill` in fixed aspect slots; wrong dimensions look **warped** on purpose.

| Basename | Role | Target size | `GET /hl/kt` field |
|----------|------|-------------|-------------------|
| `kt.th` | Card thumbnail on `/kits` | **960×480** (2:1) | `th` (e.g. `kt.th.svg`) |
| `kt.ic` | Kit icon / avatar | **256×256** (square) | `ic` |
| `kt.hero` | Banner on `/kitview` | **1920×480** (4:1) | `hr` |

Example on-disk files (any one per row wins by priority):

```
pb/kt.th.svg
pb/kt.ic.png
pb/kt.hero.jpg
```

**URL pattern** (dashboard uses resolved filename from `GET /hl/kt`):

```
{public_url}/kt/{namespace}/{name}/pb/{th|ic|hr filename}
```

**Project public URL** — set in `sentinel.yaml` (returned on `GET /hl/runtime` as `public_url`):

```yaml
public_url: https://sn-harness.gandalf.lan
```

The dashboard **Instances** attach address remains the API endpoint the console can reach (often `localhost:8080`). `public_url` is for browser-facing kit images and **Launch** links (reverse proxies, TLS).

**List response** — each kit may include:

| Field | Meaning |
|-------|---------|
| `ic`, `th`, `hr` | Resolved filename under `pb/` |
| `has_icon`, `has_thumb`, `has_hero` | Legacy booleans (`true` when the matching field is set) |

#### Kit UI favicon (separate from catalog images)

For kits with a web UI (`pg/`), `kit.yaml` `branding.favicon` points at **`/pb/favicon.ico`** by convention. How the kit page emits `<link rel="icon">` is up to the kit templates; the harness only serves the file from `pb/`.

#### Optional design spec

`dc/DESIGN.md` (see `branding.design-spec` in `system-specs/kits.yaml`) can document colors, typography, and art direction for humans and agents authoring kit assets.

---

## fcms kits (file CMS)

Any kit with Markdown files (`.md`) in its `ct/` directory participates in the **fcms** plane. The harness discovers and parses all `.md` files at startup, building a bbolt-backed content cache. No additional configuration is needed -- just create the `ct/` directory and add Markdown files.

**Note:** fcms content lives in `ct/` so the `md/` directory remains reserved for Lua modules. Product language is **fcms**; Lua API remains `sn.cms.*` for compatibility. For Postgres collections use **ccms** (`forms/pub/`, `dd/`) — see [Content planes](/content-planes).

### ccms kits (collection CMS)

Kits may include:

| Path | Purpose |
|------|---------|
| `dd/*.sql` | Ordered SQL migrations (apply with `sentinel ccms migrate`) |
| `forms/pub/*.md` | Shippable collection forms (MD + frontmatter: `schema`, `table`, `fields[].column`) |
| `forms/draft/*.md` | Draft forms — **never** exposed as live editors |
| `tp/*.gohtml` | Optional white-label form templates |
| `fl/` | Not required for submit (zero-Lua default). After-save Lua plugins are out of MVP scope. |

Reference kit: `sentinel ccms install-refkit` installs embedded `sn.ccms-pages-posts`.

### Content Directory Structure

```
acme.blog/
  kit.yaml                   # Optional: cms_full_html: true
  ct/                        # CMS content (auto-discovered)
    hello-world.md           # Slug: "hello-world"
    about.md                 # Slug: "about"
    tutorials/
      getting-started.md     # Slug: "tutorials/getting-started"
      advanced-usage.md      # Slug: "tutorials/advanced-usage"
  assets.yaml                # Optional: asset URL rewriting
  fl/                        # Flows that serve content via sn.cms
  pg/                        # Pages with templates using querySelector/safeHTML
  tp/                        # Templates
```

### Slug Rules

The slug is the unique identifier for a piece of content within a kit:

- Default slug = filename without `.md`, relative to `ct/`, using `/` as separators.
- `ct/hello-world.md` becomes slug `hello-world`
- `ct/tutorials/getting-started.md` becomes slug `tutorials/getting-started`
- Override with `slug:` in frontmatter to use a custom slug.
- Slugs must be unique within a kit.

### Frontmatter

Each `.md` file supports an optional YAML frontmatter block delimited by `---`:

```yaml
---
title: "Hello World"
slug: "hello-world"
date: "2026-02-27"
description: "First post on the blog"
tags: ["intro", "blog"]
agent_context:
  purpose: "introductory post for new readers"
  tone: "friendly"
custom_field: "any value"
---

Content starts here in Markdown format...
```

**Field reference:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | Recommended | Document title. An advisory warning is logged if missing. |
| `slug` | string | No | Override the filename-derived slug. |
| `date` | string | No | Publication date in RFC3339 or YYYY-MM-DD format. |
| `description` | string | No | Short summary for listings and SEO. |
| `tags` | string[] | No | Tag list for categorization and filtering. |
| `agent_context` | object | No | AI agent metadata. **Never exposed via the REST API.** Available to Lua flows via `sn.cms.get()` but stripped from `/cm/*` API responses. Use for AI-specific context like tone instructions, content briefs, or editorial notes. |
| *(other fields)* | any | No | Any unknown fields are stored in a `meta{}` map. |

### cms_full_html Flag

In `kit.yaml`, set `cms_full_html: true` to have the CMS parser generate a `full_html` field on each entry. This field contains the entire Markdown document rendered as a single HTML string.

```yaml
name: Blog
cms_full_html: true
```

| Flag | Default | Description |
|------|---------|-------------|
| `cms_full_html` | `false` | When `true`, `sn.cms.get()` entries include `full_html`. Useful when templates need to render the whole document at once (using `{{ safeHTML .post.full_html }}`). **Important:** `full_html` is only populated on cold start (harness restart), not during hot-reload file watcher updates. |

### assets.yaml -- Asset URL Rewriting

Place `assets.yaml` at the kit root (same level as `kit.yaml`) to configure asset URL rewriting. This maps local file paths referenced in Markdown content to CDN or cloud storage URLs.

```yaml
bucket: "https://cdn.example.com/blog"
assets:
  "images/hero.jpg": "assets/hero.jpg"
  "images/logo.png": "assets/logo.png"
  "images/diagram.svg": "diagrams/arch.svg"
```

**How it works:**

- In rendered HTML, `src="images/hero.jpg"` becomes `src="https://cdn.example.com/blog/assets/hero.jpg"`
- Similarly, `href="images/logo.png"` becomes `href="https://cdn.example.com/blog/assets/logo.png"`
- Paths not in the `assets:` map pass through unchanged.
- Leading `/` is trimmed from local paths before lookup (both `/images/hero.jpg` and `images/hero.jpg` match).
- `bucket:` trailing slash is trimmed automatically.
- If `assets.yaml` is missing, the kit works normally -- rewriting is silently skipped.

### Accessing CMS Content in Lua

```lua
-- Get a single entry by slug
local entry, err = sn.cms.get("hello-world")
if err then
  ctx.log("error", "Content not found: " .. err)
  return
end

-- entry contains:
-- entry.frontmatter.title   -- "Hello World"
-- entry.frontmatter.date    -- "2026-02-27"
-- entry.frontmatter.tags    -- {"intro", "blog"}
-- entry.preamble            -- HTML of content before first heading
-- entry.sections            -- Table of headed sections
-- entry.full_html           -- Full HTML (only if cms_full_html: true)
-- entry.agent_context       -- AI metadata (available in Lua, stripped from API)
```

### CMS REST API

Content is also available via HTTP:

- `GET /cm` -- List all slugs across all CMS kits
- `GET /cm/{kitName}/{slug}` -- Get parsed content for a specific slug (agent_context is stripped)

### Complete CMS Template Example

**Lua flow** that fetches content and passes it to a template:

```lua
-- acme.blog/fl/post.lua
function main(params)
  local slug = params and params.slug or ""
  if slug == "" then
    return { ok = false, error = "slug required" }
  end

  local entry, err = sn.cms.get(slug)
  if err then
    ctx.log("info", "Post not found: " .. slug)
    return { ok = true }  -- post is nil in template
  end

  return { ok = true, post = entry }
end
```

**Template** that renders the content:

```html
<!-- acme.blog/tp/post.gohtml -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ if .post }}{{ .post.frontmatter.title }}{{ else }}Not Found{{ end }}</title>
  <link rel="stylesheet" href="/kt/acme/blog/pb/styles.css">
</head>
<body>
  {{- if .post -}}
  <article class="post">
    <header>
      <h1>{{ .post.frontmatter.title }}</h1>
      <time>{{ .post.frontmatter.date }}</time>
      <p>{{ .post.frontmatter.description }}</p>
      {{ range .post.frontmatter.tags }}
      <span class="tag">{{ . }}</span>
      {{ end }}
    </header>

    {{ if .post.preamble }}
    <div class="preamble">{{ safeHTML .post.preamble }}</div>
    {{ end }}

    <section class="overview">
      {{ querySelector .post "overview" }}
    </section>

    <section class="details">
      {{ querySelector .post "details" }}
      <div class="sub">{{ querySelector .post "details.examples" }}</div>
    </section>

    {{ if .post.full_html }}
    <div class="full-content">{{ safeHTML .post.full_html }}</div>
    {{ end }}
  </article>
  {{- else -}}
  <div class="not-found">
    <h1>Post Not Found</h1>
    <p><a href="/kt/acme/blog">Back to Blog</a></p>
  </div>
  {{- end -}}
</body>
</html>
```

### Hot-Reload

Changes to `.md` files are watched while the harness is running. When a Markdown file is saved, the content cache updates incrementally without requiring a restart. Note that hot-reload updates use the fast path, which means `full_html` is not re-generated during hot-reload -- it is only populated on cold start (harness restart).

---

## Skill Twins

Every code file in a kit can have a corresponding "skill twin" -- a `.md` file with the same name plus a `.md` suffix. For example, `process-payment.lua` has a skill twin at `process-payment.lua.md`.

Skill twins are **not CMS content**. They are documentation files designed to provide persistent context for AI agents (like Claude) that work with the code. The harness auto-spawns empty skill twins for new files.

### Purpose

When an AI agent needs to understand, modify, or debug a flow, the skill twin provides:

- **Purpose**: What the flow does and why it exists.
- **Dependencies**: What secrets, databases, connectors, and other flows it relies on.
- **Triggers**: How the flow is invoked (cron schedule, webhook path, event name).
- **Error handling**: What happens when things go wrong.
- **Recent changes**: A changelog of modifications for context.
- **Known issues**: Bugs, limitations, or areas that need attention.

### Pairing Rules

| Code File | Skill Twin |
|-----------|-----------|
| `fl/process-payment.lua` | `fl/process-payment.lua.md` |
| `cn/stripe.lua` | `cn/stripe.lua.md` |
| `md/invoice.lua` | `md/invoice.lua.md` |
| `fm/payment.yaml` | `fm/payment.yaml.md` |
| `pg/dashboard.yaml` | `pg/dashboard.yaml.md` |
| `tp/dashboard.gohtml` | `tp/dashboard.gohtml.md` |
| `pb/styles.css` | `pb/styles.css.md` |
| `kit.yaml` | `kit.yaml.md` |

### Example Skill Twin

```markdown
# Process Payment Flow

## Purpose
Processes payments via the Stripe API when triggered by form submission,
webhook, or direct API call.

## Triggers
- Webhook: /stripe-events (HMAC-signed with stripe_webhook_secret)
- Event: kf.acme.billing.payment (form submission)
- Manual: sentinel run acme-billing:process-payment

## Dependencies
- Secret: stripe_api_key (Stripe live/test API key)
- Connector: cn/stripe.lua
- Database: payments table, invoices table
- Module: md/invoice.lua (for invoice status updates)

## Data Flow
1. Receives invoice_id and amount from trigger
2. Retrieves Stripe API key from vault
3. Calls Stripe /v1/charges endpoint
4. Inserts payment record into payments table
5. Updates invoice status to "paid"
6. Emits payment.completed event

## Error Handling
- Stripe API errors: logged and returned to caller
- Database errors: transaction rollback, logged
- Timeout: 30 seconds (default)

## Recent Changes
- 2026-03-01: Added support for multiple payment methods
- 2026-02-28: Fixed race condition in concurrent payments
- 2026-02-15: Initial implementation
```

### Best Practices for Skill Twins

1. **Keep them current**: Update the skill twin whenever you change the code. Stale documentation is worse than no documentation.
2. **Focus on "why" not "what"**: The code shows what happens. The skill twin should explain why decisions were made.
3. **Document dependencies explicitly**: List every secret, database table, connector, and external service.
4. **Include examples**: Show example trigger payloads, expected outputs, and error scenarios.
5. **Use them for onboarding**: When a new team member (human or AI) needs to understand a flow, the skill twin should be sufficient.

---

## Testing

### Test File Convention

Test files must:
- Live in the same directory as the code they test
- End with `_test.lua`
- Contain functions prefixed with `test_`

Example: `acme.billing/fl/process-payment_test.lua` tests `acme.billing/fl/process-payment.lua`.

### Writing Tests

```lua
-- acme.billing/fl/process-payment_test.lua

function test_payment_success()
  local result = process_payment({
    invoice_id = "inv_test",
    amount = 1000
  })
  sn.test.ok(result.ok, "Payment should succeed")
  sn.test.eq(result.charge_id, "ch_test", "Should return charge ID")
end

function test_payment_invalid_amount()
  local result = process_payment({
    invoice_id = "inv_test",
    amount = -100  -- Invalid
  })
  sn.test.ok(not result.ok, "Should reject negative amount")
end

function test_payment_missing_invoice()
  local result = process_payment({
    amount = 1000
    -- invoice_id missing
  })
  sn.test.ok(not result.ok, "Should require invoice_id")
end
```

### Running Tests

```bash
# Run all tests in a kit
./sentinel sre test acme.billing

# Run only flow tests
./sentinel sre test acme.billing/fl

# Run with verbose output
./sentinel sre test acme.billing -v

# Filter by test name
./sentinel sre test acme.billing -v -f payment
```

---

## Kit Distribution

### Git Repository

The simplest distribution method. Share a kit by including it in a git repository:

```bash
# Clone a project that contains kits
git clone https://github.com/acme/automation-project.git
# Kits are already in the project root
```

### Git Submodules

Include a kit from another repository as a git submodule:

```bash
cd my-project
git submodule add https://github.com/acme/billing-kit.git acme.billing
```

This creates a `acme.billing/` directory linked to the external repository.

### Marketplace Publishing

For wider distribution, publish your kit to the Sentinel Kit Marketplace:

1. Authenticate: `sentinel login`
2. Ensure your `kit.yaml` has `name`, `version`, `description`, and `author` fields.
3. Publish through the marketplace dashboard or API.
4. Users install with: `sentinel sre kit install acme.billing`

Published kits are signed with Ed25519 keys for integrity verification.

### Version Management

Follow semantic versioning in `kit.yaml`:

```yaml
version: 2.1.0
# MAJOR.MINOR.PATCH
# MAJOR: Breaking changes (schema migration, API changes)
# MINOR: New features (new flows, new forms, new fields)
# PATCH: Bug fixes (flow logic fixes, template corrections)
```

---

## Building Reusable Services

If your kit needs to expose functionality via multiple interfaces (CLI, REST API, Lua flows), follow the [Triple-Access Pattern](/triple-access-pattern) guide. This ensures:

- **Shared business logic** across all three interfaces
- **Zero code duplication**
- **Agent-friendly automation** from flows
- **Consistent error handling and logging**

**Example:** The Sentinel library service (for managing API vendors and endpoints) is accessible via:
- **CLI:** `sentinel lib vendor list`
- **REST API:** `GET /lib`
- **Lua:** `local vendors = sn.lib.vendor_list({name="OpenAI"})`

**Learn more:** [Triple-Access Pattern Guide](/triple-access-pattern)

---

## Best Practices Summary

1. **Name kits consistently**: Always use `{namespace}.{name}` pattern with lowercase alphanumeric characters.
2. **Document everything with skill twins**: Every code file should have an up-to-date `.md` skill twin.
3. **Version semantically**: Follow semver in `kit.yaml` and bump versions on every meaningful change.
4. **Isolate databases**: Use kit-scoped databases. Import explicitly when cross-kit access is needed.
5. **Handle errors gracefully**: Use `pcall()` for risky operations and always implement the `failed(err)` callback.
6. **Log important events**: Use `ctx.log()` at appropriate levels for debugging and operational visibility.
7. **Test flows thoroughly**: Write `_test.lua` files for all critical business logic.
8. **Validate user input**: Check form data and webhook payloads before processing.
9. **Use transactions**: Wrap multi-step database operations in `sn.db.transaction()`.
10. **Keep connectors focused**: One connector per external service, with authentication handled internally.
11. **Keep kits small and focused**: A kit should do one thing well. Compose multiple kits for complex systems.
12. **Protect secrets**: Always use `ctx.secret()` to retrieve sensitive values. Never hardcode credentials.
