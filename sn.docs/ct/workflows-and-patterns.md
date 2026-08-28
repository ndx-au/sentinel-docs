---
title: "Workflows and Patterns Guide"
description: "This guide is a comprehensive collection of battle-tested patterns for building automation workflows with Sentinel."
---

# Workflows and Patterns Guide

This guide is a comprehensive collection of battle-tested patterns for building automation workflows with Sentinel. Each pattern addresses a specific real-world challenge that arises when orchestrating flows, integrating with external services, managing data, and coordinating across kits. Whether you are building your first webhook handler or designing a multi-kit event-driven architecture, these patterns provide a proven starting point.

The patterns are organized by category. Each one includes an explanation of when and why you would use it, followed by working code examples. You can mix and match patterns freely -- a single flow might combine webhook handling with exponential backoff retries and structured logging, for example.

All code examples use the current Sentinel Lua flow style with `function setup()`, `function main(params)`, `function cleanup()`, and `function failed(err)` as top-level functions. All trigger types pass data to `main(params)` as a Lua table argument. The `ctx` global is available for logging, secrets, and form data, but `ctx.get()` and `ctx.set()` are stubs (always return nil / do nothing). Use `params.*` or local variables instead.

---

## Webhook Patterns

Webhooks are the primary way external services communicate with Sentinel in real time. When a third-party service (Stripe, GitHub, Shopify, etc.) needs to notify your system of an event, it sends an HTTP POST to a webhook endpoint. Sentinel receives these at the `/wh/` prefix and routes them to the appropriate flow based on the registered trigger path.

Understanding webhook patterns is critical because webhooks are inherently unreliable -- services retry on failure, signatures must be verified to prevent spoofing, and high-traffic endpoints can overwhelm your system without rate limiting.

### Pattern: HMAC-Signed Webhook

**When to use:** Any time you receive webhooks from an external service that signs its payloads. This includes Stripe, GitHub, Shopify, Slack, and most modern SaaS platforms. HMAC verification ensures that the payload actually came from the claimed sender and was not tampered with in transit.

**Why this matters:** Without signature verification, anyone who discovers your webhook URL can send fake events to your system. This is a serious security vulnerability, especially for payment processing or account management flows. HMAC verification is your first line of defense.

**How it works:** The external service computes a hash (typically SHA-256) of the request body using a shared secret, then includes that hash in a request header. Sentinel's webhook trigger can automatically verify this signature before your flow code even runs, rejecting any request with an invalid or missing signature.

```lua
function setup()
  -- Register a webhook trigger with HMAC authentication.
  -- The 'key' parameter references a secret stored in the Sentinel vault.
  -- The 'sig_hdr' parameter tells Sentinel which HTTP header contains the signature.
  -- The 'alg' parameter specifies the HMAC algorithm to use for verification.
  webhook("/stripe", {
    auth = "hmac",
    key = "stripe_webhook_secret",
    alg = "sha256",
    sig_hdr = "Stripe-Signature"
  })
end

function main(params)
  -- By the time main() runs, signature verification has already succeeded.
  -- If the signature was invalid, the request was rejected with an error
  -- before your code executes. This means you can trust the payload.

  -- The webhook body is parsed by the harness; top-level JSON fields are
  -- merged into params as strings. For nested objects, values are
  -- JSON-stringified and must be decoded.
  ctx.log("info", "Stripe event received: " .. params.type)

  if params.type == "charge.succeeded" then
    -- params.data is a JSON string for nested objects; decode it
    local data = sn.json.dec(params.data)
    local amount_dollars = data.object.amount / 100
    ctx.log("info", "Payment received: $" .. amount_dollars)
    -- Process the payment: update database, send confirmation, etc.
  end

  return {ok = true}
end

function cleanup() end
function failed(err)
  ctx.log("error", "Stripe webhook processing failed: " .. tostring(err))
end
```

### Pattern: Header shared-secret webhook

**When to use:** Telegram Bot API `setWebhook` (`X-Telegram-Bot-Api-Secret-Token`) or any provider that sends a static secret in a named header rather than an HMAC of the body.

```lua
function setup()
  webhook("/telegram", {
    auth = "header",
    key = "telegram_webhook_secret",
    hdr = "X-Telegram-Bot-Api-Secret-Token",
  })
end
```

`auth = "bearer"` is the same check against `Authorization: Bearer <secret>`.

### Pattern: Rate-Limited Webhook

**When to use:** When your webhook endpoint might receive bursts of traffic that could overwhelm your system. This is common with services that send many events in rapid succession (e.g., bulk operations in Stripe, CI/CD pipelines in GitHub, or IoT device telemetry).

**Why this matters:** Without rate limiting, a flood of webhook requests can exhaust your database connections, fill up your execution queue, and cause legitimate requests to time out. Rate limiting with IP whitelisting gives you two layers of protection: you limit how fast requests can arrive, and you ensure they only come from known IP ranges.

**How it works:** You configure rate limits and allowed IP ranges in `sentinel.yaml`. Sentinel enforces these limits at the router level before your flow code runs.

```yaml
# sentinel.yaml
webhooks:
  /api/webhook:
    auth: hmac
    key: webhook_secret
    rps: 100              # Maximum 100 requests per second. Requests exceeding
                          # this rate receive an error response. The external
                          # service will typically retry later.
    cidrs:                # IP whitelist using CIDR notation. Only requests from
      - 35.184.0.0/16    # these IP ranges will be accepted. All other source
      - 35.185.0.0/16    # IPs receive an immediate rejection.
```

The `rps` (requests per second) value should be set based on your expected peak traffic with some headroom. If the external service documents their maximum event rate, use that as a starting point and add a 50% buffer. The `cidrs` list should come from the external service's documentation -- most providers publish their webhook source IP ranges.

### Pattern: Webhook Replay with Retry

**When to use:** When you need to handle webhook retries from external services that automatically resend failed deliveries. Stripe, for example, retries webhook deliveries for up to 72 hours if they do not receive a 2xx response. Your flow must handle receiving the same event multiple times without processing it twice.

**Why this matters:** Without idempotency, a retried webhook could charge a customer twice, send duplicate emails, or create duplicate records. Idempotent processing ensures that no matter how many times the same event is delivered, the outcome is the same as processing it once.

**How it works:** You store a record of processed event IDs in your database. Before processing any event, you check whether it has already been handled. If so, you return success immediately without re-processing. This pattern is sometimes called "at-least-once delivery with deduplication."

```lua
function setup()
  webhook("/stripe")
end

function main(params)
  -- params contains all parsed request fields as strings.
  -- For Stripe webhooks, top-level JSON body fields are merged into params.

  -- Check if we have already processed this event. Every webhook event
  -- from Stripe (and most other services) includes a unique event ID.
  -- We use this as our deduplication key.
  local existing = sn.db.query_one(
    "SELECT * FROM processed_events WHERE event_id = ?",
    {params.id})

  if existing then
    -- We have already processed this event. Return success so the external
    -- service stops retrying. Do NOT process the event again.
    ctx.log("info", "Duplicate event skipped: " .. params.id)
    return {ok = true}
  end

  -- Process the event. This is where your actual business logic goes.
  local result = process_event(params)

  -- Record that we processed this event. Use an INSERT so that if two
  -- concurrent deliveries of the same event arrive, one will fail the
  -- unique constraint and the other will succeed.
  sn.db.exec("INSERT INTO processed_events (event_id, processed_at) VALUES (?, ?)",
    {params.id, sn.time.now()})

  return {ok = result}
end

function cleanup() end
function failed(err)
  ctx.log("error", "Webhook processing failed: " .. tostring(err))
end
```

**Important implementation note:** Create the `processed_events` table with a UNIQUE constraint on `event_id`. This provides a second layer of protection against duplicate processing even under concurrent delivery. You should also periodically clean up old records from this table to prevent unbounded growth (see the Periodic Cleanup pattern later in this guide).

---

## Cron Patterns

Cron triggers execute flows on a schedule. They are essential for any task that needs to happen at regular intervals: generating reports, cleaning up old data, checking service health, synchronizing external systems, or sending notifications. Sentinel uses standard cron expressions with optional timezone support.

Cron jobs run within the harness process. If the harness is stopped, scheduled jobs do not run and are not retroactively executed when the harness restarts. For critical scheduled tasks, consider adding monitoring to detect missed executions.

### Pattern: Daily Digest

**When to use:** When you need to aggregate data over a time period and send a summary report. Common examples include daily sales reports, weekly error summaries, monitoring dashboards sent via email, or end-of-day reconciliation tasks.

**Why this matters:** Digest emails reduce alert fatigue by consolidating many individual events into a single actionable summary. They are also useful for stakeholders who need regular updates but do not monitor dashboards in real time.

```lua
function setup()
  -- Schedule for 9 AM Eastern every day. The timezone parameter ensures
  -- the job runs at the correct local time regardless of the server's
  -- system timezone, and correctly handles daylight saving time transitions.
  cron("0 9 * * *", {tz = "America/New_York"})
end

function main(params)
  ctx.log("info", "Generating daily digest...")

  -- Query data from the last 24 hours. Using SQLite's datetime function
  -- ensures timezone-aware comparisons against the created_at column.
  local metrics = sn.db.query(
    "SELECT * FROM metrics WHERE created_at > datetime('now', '-1 day')")

  if #metrics == 0 then
    ctx.log("info", "No metrics in the last 24 hours, skipping digest")
    return {ok = true, count = 0}
  end

  -- Build a summary from the raw metrics
  local summary = summarize_metrics(metrics)

  -- Send the digest via an email service (SendGrid in this example)
  send_digest_email(summary)

  return {ok = true, count = #metrics}
end

function summarize_metrics(metrics)
  local total = 0
  for _, m in ipairs(metrics) do
    total = total + m.value
  end
  return {total = total, count = #metrics, avg = total / #metrics}
end

function send_digest_email(summary)
  local token = ctx.secret("sendgrid_api_key")
  local resp = sn.http.post("https://api.sendgrid.com/v3/mail/send",
    sn.json.enc({
      personalizations = {{to = {{email = "admin@example.com"}}}},
      from = {email = "noreply@example.com"},
      subject = "Daily Digest",
      content = {{type = "text/plain", value = "Summary: " .. sn.json.enc(summary)}}
    }),
    {headers = {Authorization = "Bearer " .. token}})

  if resp.status ~= 202 then
    ctx.log("error", "Failed to send digest email, status: " .. resp.status)
  end
end

function cleanup() end
function failed(err)
  ctx.log("error", "Daily digest failed: " .. tostring(err))
end
```

### Pattern: Health Check Ping

**When to use:** When you need to verify that an external service (or your own API) is alive and responsive. Health checks are a fundamental monitoring pattern that helps you detect outages before your users do.

**Why this matters:** Proactive health checking means you can alert your team the moment a dependency becomes unavailable, rather than discovering the problem when users report errors. Combined with an alerting system, this pattern provides early warning for infrastructure issues.

```lua
function setup()
  -- Run every 5 minutes. This frequency balances timely detection with
  -- reasonable resource usage. For critical services, you might check
  -- every minute; for less critical ones, every 15 minutes may suffice.
  cron("*/5 * * * *")
end

function main(params)
  -- Set a 5-second timeout to distinguish between "slow" and "down".
  -- A healthy service should respond well within this window.
  local resp = sn.http.get("https://api.example.com/health", {timeout_ms = 5000})

  if resp.status == 200 then
    ctx.log("info", "Service healthy")
    return {ok = true, status = "healthy"}
  else
    ctx.log("error", "Service unhealthy, HTTP status: " .. resp.status)
    -- In a production setup, you would emit an event here to trigger
    -- an alert flow, send a notification to Slack/PagerDuty, or
    -- increment a failure counter for dead-man's-switch monitoring.
    return {ok = false, status = "unhealthy"}
  end
end

function cleanup() end
function failed(err)
  -- If the health check itself errors (e.g., DNS failure, network timeout),
  -- that is itself a signal that something is wrong.
  ctx.log("error", "Health check failed to execute: " .. tostring(err))
end
```

### Pattern: Periodic Cleanup

**When to use:** When your system accumulates data over time that needs to be purged periodically. This includes old log entries, expired sessions, completed execution records, temporary files, and processed event deduplication records.

**Why this matters:** Without periodic cleanup, your database grows unboundedly. SQLite performance degrades as tables get very large, disk space fills up, and backups take longer. Regular cleanup keeps your system healthy and performant. Running cleanup during off-peak hours (like 3 AM on a Sunday) minimizes the impact on live traffic.

```lua
function setup()
  -- Run at 3 AM UTC every Sunday. This schedule avoids peak usage hours
  -- and gives the database a full week of data before each cleanup.
  cron("0 3 * * 0", {tz = "UTC"})
end

function main(params)
  ctx.log("info", "Starting periodic cleanup...")

  -- Delete log entries older than 90 days. Adjust the retention period
  -- based on your compliance requirements and storage capacity.
  local deleted = sn.db.exec(
    "DELETE FROM logs WHERE created_at < datetime('now', '-90 days')")

  ctx.log("info", "Deleted " .. deleted.rows_affected .. " log entries")

  -- VACUUM reclaims disk space freed by the DELETE operation.
  -- Without VACUUM, SQLite reuses deleted pages internally but does
  -- not shrink the database file. This operation can be slow on large
  -- databases, which is why we run it during off-peak hours.
  sn.db.exec("VACUUM")

  ctx.log("info", "Database vacuumed successfully")
  return {ok = true, rows_deleted = deleted.rows_affected}
end

function cleanup() end
function failed(err)
  ctx.log("error", "Periodic cleanup failed: " .. tostring(err))
end
```

---

## Event Patterns

Events are Sentinel's internal message bus for decoupling flows from each other. When one flow emits an event, any other flow that has registered a trigger for that event name will execute in response. Events are the backbone of event-driven architectures within Sentinel and are the recommended way to coordinate work across multiple flows and kits.

Events differ from webhooks in an important way: webhooks are triggered by external HTTP requests, while events are triggered internally by other flows (or by form submissions). This makes events ideal for breaking complex workflows into smaller, focused steps that are easier to test, debug, and maintain independently.

### Pattern: Event Cascade

**When to use:** When a single incoming action (like an order being placed) needs to trigger multiple independent follow-up tasks. Rather than putting all the logic in one monolithic flow, you break it into separate flows connected by events. Each flow handles one responsibility.

**Why this matters:** Event cascades provide loose coupling between workflow steps. The order processing flow does not need to know about email sending, inventory checking, or statistics updates. Each downstream flow can be developed, tested, and deployed independently. If the email service is down, the inventory check still runs. If you add a new follow-up task (like fraud detection), you just add a new flow that listens for the same event -- no changes needed to existing flows.

```lua
-- Flow 1: process-order.lua
-- This is the entry point that receives the external webhook.
-- It processes the order and then emits events for downstream flows.
function setup()
  webhook("/orders")
end

function main(params)
  -- params contains all parsed webhook request fields as strings.
  -- For a JSON POST body, top-level keys are merged into params.

  -- Store the order in the database
  sn.db.exec("INSERT INTO orders (id, status) VALUES (?, ?)",
    {params.id, "processing"})

  -- Emit events for downstream processing. Each event triggers
  -- independent flows that handle their own concerns.
  -- The second argument is a table of data that will be available
  -- to the triggered flow via its params argument.
  sentinel.emit("order.created", {order_id = params.id})
  sentinel.emit("inventory.check_needed", {sku = params.sku, qty = params.qty})

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

```lua
-- Flow 2: on-order-created.lua
-- Handles post-order tasks like email confirmation and statistics.
-- This flow is completely independent of the order processing flow.
function setup()
  event("order.created")
end

function main(params)
  -- Event data is available through the params argument to main().
  -- Fields match what was passed in the sentinel.emit() call.
  -- params.event_payload contains the emitted data as a Lua table.
  local payload = params.event_payload
  local order_id = payload.order_id
  ctx.log("info", "Order created: " .. order_id)

  -- Send confirmation email to the customer
  send_confirmation_email(order_id)

  -- Update aggregate statistics
  sn.db.exec("UPDATE stats SET total_orders = total_orders + 1")

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

```lua
-- Flow 3: check-inventory.lua
-- Handles inventory verification independently from order processing.
-- If stock is low, it emits another event for alerting.
function setup()
  event("inventory.check_needed")
end

function main(params)
  local payload = params.event_payload
  local sku = payload.sku
  local qty = payload.qty
  ctx.log("info", "Checking inventory for SKU: " .. sku)

  local stock = check_stock(sku)
  if stock < qty then
    -- Emit another event that could trigger a restocking flow,
    -- an alert notification, or a purchasing workflow.
    sentinel.emit("inventory.low", {sku = sku, qty = stock})
  end

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

### Pattern: Multi-Kit Coordination via Events

**When to use:** When you have multiple kits that need to communicate with each other without being tightly coupled. For example, a billing kit might need to notify a notifications kit when a payment fails, or a user management kit might need to tell an analytics kit when a new user signs up.

**Why this matters:** Kits are designed to be independent, reusable units of functionality. Direct function calls between kits would create tight coupling that defeats the purpose of the kit architecture. Events provide a clean boundary: a kit emits events about things it cares about, and other kits subscribe to the events they are interested in. You can add, remove, or replace kits without modifying others.

```lua
-- Kit: acme.billing / fl/payment-failed.lua
-- This flow lives in the billing kit. It processes payment failures
-- and emits a generic event that any other kit can listen for.
function setup()
  webhook("/payment-failed")
end

function main(params)
  -- params contains all parsed webhook request fields as strings.

  -- Update billing records in this kit's own database tables
  sn.db.exec("UPDATE invoices SET status = 'failed' WHERE payment_id = ?",
    {params.id})

  -- Emit an event that crosses kit boundaries. Any kit in the SRE
  -- can register a trigger for this event name. The billing kit does
  -- not need to know which kits are listening.
  sentinel.emit("billing.payment_failed", {
    customer_id = params.customer_id,
    amount = params.amount,
    invoice_id = params.invoice_id,
    failure_reason = params.failure_reason
  })

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

```lua
-- Kit: acme.notify / fl/on-payment-failed.lua
-- This flow lives in a completely separate notifications kit.
-- It listens for billing events and sends alerts.
function setup()
  event("billing.payment_failed")
end

function main(params)
  local payload = params.event_payload
  local customer_id = payload.customer_id
  local amount = payload.amount
  local reason = payload.failure_reason

  -- Send notification via Slack, email, SMS, or any channel
  local slack_webhook = ctx.secret("slack_webhook_url")
  sn.http.post(slack_webhook, sn.json.enc({
    text = "Payment failed for customer " .. customer_id ..
           ": $" .. (amount / 100) .. " - " .. reason
  }))

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

```lua
-- Kit: acme.analytics / fl/track-payment-failure.lua
-- A third kit that also listens for the same event, tracking metrics.
function setup()
  event("billing.payment_failed")
end

function main(params)
  local payload = params.event_payload
  local reason = payload.failure_reason

  -- Track the failure in an analytics table for reporting
  sn.db.exec(
    "INSERT INTO payment_metrics (event, reason, recorded_at) VALUES (?, ?, ?)",
    {"failure", reason, sn.time.now()})

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

---

## Form Patterns

Forms provide a way for human users to submit structured data into Sentinel workflows. When a form is submitted, Sentinel emits a kit-scoped event (`kf.{namespace}.{kit}.{form-stub}`) that can trigger one or more flows. Forms are defined as YAML files in the `fm/` directory of a kit and are rendered by the dashboard or served via the API.

Forms are particularly useful for building approval workflows, data entry interfaces, configuration panels, and any interaction that requires structured input from a human operator.

### Pattern: Multi-Step Form Workflow

**When to use:** When a business process requires multiple stages of user input, such as an e-commerce checkout (cart review, then payment), an employee onboarding form (personal info, then department assignment, then equipment request), or any workflow where later steps depend on earlier input.

**Why this matters:** Multi-step workflows break complex processes into manageable chunks. Each step can validate its own input, store intermediate state, and trigger the next step only when ready. This approach also allows different team members to handle different steps, and provides natural checkpoints for auditing.

```lua
-- Step 1: Initial form submission (e.g., checkout form)
-- This flow triggers when the checkout form is submitted.
-- The form event name follows the pattern: kf.{namespace}.{kit}.{form-stub}
function setup()
  event("kf.acme.shop.checkout")
end

function main(params)
  -- Form field values are available through ctx.fm.{form_stub}.{field}.
  -- The field names match what is defined in the form YAML.
  local items = ctx.fm.checkout.items
  local email = ctx.fm.checkout.email

  -- Validate items against the inventory database
  local total = 0
  for _, item_id in ipairs(items) do
    local item = sn.db.query_one("SELECT * FROM inventory WHERE id = ?", {item_id})
    if not item then
      return {ok = false, error = "Item not found: " .. item_id}
    end
    total = total + item.price
  end

  -- Create a cart record to persist the state between form steps.
  -- This is the intermediate state that connects step 1 to step 2.
  local cart_id = sn.crypto.random_bytes(16)
  sn.db.exec(
    "INSERT INTO carts (id, email, items, total, status) VALUES (?, ?, ?, ?, ?)",
    {cart_id, email, sn.json.enc(items), total, "pending_payment"})

  -- Emit an event that tells the system this cart is ready for payment.
  -- A downstream flow or the UI can use this to present the payment form.
  sentinel.emit("checkout.ready_for_payment", {
    cart_id = cart_id,
    total = total,
    email = email
  })

  return {cart_id = cart_id, total = total}
end

function cleanup() end
function failed(err) end
```

```lua
-- Step 2: Payment form submission
-- This flow triggers when the payment form is submitted.
-- The payment form includes the cart_id from step 1 as a hidden field.
function setup()
  event("kf.acme.shop.payment")
end

function main(params)
  -- Form field values are available through ctx.fm.{form_stub}.{field}.
  local cart_id = ctx.fm.payment.cart_id
  local card = ctx.fm.payment.card_token
  local total = ctx.fm.payment.total

  -- Process payment through Stripe
  local stripe_key = ctx.secret("stripe_api_key")
  local resp = sn.http.post("https://api.stripe.com/v1/charges",
    "amount=" .. total .. "&source=" .. card,
    {headers = {Authorization = "Bearer " .. stripe_key}})

  if resp.status ~= 200 then
    return {ok = false, error = "Payment failed"}
  end

  local charge = sn.json.dec(resp.body)

  -- Update the cart status to reflect successful payment
  sn.db.exec("UPDATE carts SET status = ? WHERE id = ?",
    {"completed", cart_id})

  -- Emit a completion event that triggers order fulfillment,
  -- confirmation emails, inventory updates, etc.
  sentinel.emit("order.completed", {cart_id = cart_id, charge_id = charge.id})

  return {ok = true, charge_id = charge.id}
end

function cleanup() end
function failed(err) end
```

---

## WebSocket Patterns

Sentinel provides a WebSocket endpoint at `/ws` for real-time bidirectional communication between the harness and connected clients. WebSocket connections are managed by the WSManager and can be used from both the dashboard and custom clients. Flows can send messages to WebSocket clients using the `sn.ws.*` Lua API.

WebSockets are ideal for scenarios where you need to push data to clients in real time without them having to poll. This includes live monitoring dashboards, real-time log streaming, notification systems, and interactive control panels.

### Pattern: Real-Time Monitoring Dashboard

**When to use:** When you need a live dashboard that updates as events happen in your system. Rather than having the dashboard poll the API every few seconds (which wastes resources and introduces latency), WebSocket connections allow the harness to push updates to connected dashboards the instant something changes.

**Why this matters:** Real-time dashboards give operators immediate visibility into system behavior. They can watch flow executions as they happen, see errors the moment they occur, and monitor metrics without any delay. This is especially valuable during incident response, deployment rollouts, or when debugging production issues.

```lua
-- fl/ws-monitor.lua
-- This flow runs on a schedule and pushes system metrics to all
-- connected WebSocket clients. The dashboard listens for these
-- messages and updates its display in real time.
function setup()
  cron("*/10 * * * * *")  -- Every 10 seconds
end

function main(params)
  -- Gather current system metrics
  local active_flows = sn.db.query_one(
    "SELECT COUNT(*) as cnt FROM executions WHERE status = 'running'")
  local recent_errors = sn.db.query_one(
    "SELECT COUNT(*) as cnt FROM executions WHERE status = 'failed' AND ended_at > datetime('now', '-5 minutes')")

  -- Broadcast metrics to all connected WebSocket clients.
  -- The topic string allows clients to filter messages they care about.
  sn.ws.broadcast("metrics", sn.json.enc({
    type = "system_metrics",
    active_flows = active_flows.cnt,
    recent_errors = recent_errors.cnt,
    timestamp = sn.time.now()
  }))

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

### Pattern: Live Event Stream

**When to use:** When operators or external systems need to observe events as they happen. This pattern pushes every emitted event to WebSocket clients, creating a live activity feed.

```lua
-- fl/event-broadcaster.lua
-- Listens for all events matching a pattern and forwards them
-- to WebSocket clients for real-time observation.
function setup()
  event("order.*")  -- Listen for all order-related events
end

function main(params)
  -- Event trigger params include event metadata fields.
  local event_pattern = params.event_pattern
  local event_payload = params.event_payload

  -- Forward the event to WebSocket clients on the "events" topic.
  -- Connected dashboards or monitoring tools receive this instantly.
  sn.ws.broadcast("events", sn.json.enc({
    type = "event",
    name = event_pattern,
    data = event_payload,
    timestamp = sn.time.now()
  }))

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

---

## fcms content workflow patterns

**fcms** (file CMS) stores content as markdown files in the `ct/` directory of a kit, managed through the `/fcms` API (legacy alias `/cm`). Workflows handle publishing, versioning, and rendering for technical writing and agent-authored docs. For Postgres collections use **ccms** ([Content planes](/content-planes)) — do not treat `ct/` files as collection rows.

### Pattern: Content Publishing Pipeline

**When to use:** When you need a structured content publishing process with draft, review, and publish stages. This is useful for team blogs, documentation sites, or any content that requires editorial review before going live.

**Why this matters:** A publishing pipeline prevents accidental publication of unfinished content, provides an audit trail of who approved what, and allows multiple team members to work on content without stepping on each other's changes.

```lua
-- fl/publish-content.lua
-- Triggered when an editor marks content as "ready for publish"
-- via a form submission in the dashboard.
function setup()
  event("kf.acme.cms.publish-request")
end

function main(params)
  -- Form field values are available through ctx.fm.{form_stub}.{field}.
  local slug = ctx.fm["publish-request"].slug
  local reviewer = ctx.fm["publish-request"].reviewer_email

  -- Fetch the content entry from CMS
  local entry = sn.cms.get(slug)
  if not entry then
    return {ok = false, error = "Content not found: " .. slug}
  end

  -- Update the content metadata to mark it as published.
  -- The CMS stores metadata in the frontmatter of markdown files.
  sn.cms.update(slug, {
    status = "published",
    published_at = sn.time.now(),
    published_by = reviewer
  })

  -- Emit an event so other flows can react to the publication.
  -- For example, a flow that purges the CDN cache, updates a sitemap,
  -- or sends a notification to subscribers.
  sentinel.emit("content.published", {
    slug = slug,
    title = entry.title,
    published_by = reviewer
  })

  ctx.log("info", "Published content: " .. slug)
  return {ok = true, slug = slug}
end

function cleanup() end
function failed(err) end
```

---

## Docker Stack Integration Patterns

Sentinel can manage Docker containers through the `/docker` API endpoints, enabling flows to start, stop, and monitor containers as part of automated workflows. This is particularly useful for managing development environments, running batch processing jobs in containers, or orchestrating microservice deployments.

### Pattern: Container Lifecycle Management

**When to use:** When a flow needs to spin up a container for a task (like running a data pipeline, executing a build, or provisioning a temporary service), wait for it to complete, and clean up afterward.

**Why this matters:** Containers provide isolated, reproducible environments for tasks that require specific dependencies or that should not affect the host system. By managing container lifecycles from flows, you can automate complex operational tasks that would otherwise require manual intervention or separate orchestration tools.

```lua
-- fl/run-data-pipeline.lua
-- Triggered on a schedule to run a data processing pipeline
-- inside a Docker container.
function setup()
  cron("0 2 * * *", {tz = "UTC"})  -- 2 AM UTC daily
end

function main(params)
  ctx.log("info", "Starting data pipeline container...")

  -- Start a container from a pre-built image
  local result = sn.docker.run({
    image = "myorg/data-pipeline:latest",
    env = {
      DATABASE_URL = ctx.secret("pipeline_db_url"),
      OUTPUT_BUCKET = "s3://my-bucket/output/"
    },
    volumes = {"/data/input:/input:ro"},
    timeout_ms = 300000  -- 5-minute timeout
  })

  if not result.ok then
    ctx.log("error", "Pipeline container failed: " .. result.error)
    sentinel.emit("pipeline.failed", {error = result.error})
    return {ok = false, error = result.error}
  end

  ctx.log("info", "Pipeline completed successfully, exit code: " .. result.exit_code)
  sentinel.emit("pipeline.completed", {duration_ms = result.duration_ms})

  return {ok = true, exit_code = result.exit_code}
end

function cleanup() end
function failed(err) end
```

---

## Database Patterns

Sentinel includes a built-in SQLite database for each SRE, accessible from flows via the `sn.db.*` API. These patterns address common data management challenges including transactional integrity, efficient pagination, and data migration.

### Pattern: Multi-Step Atomic Transaction

**When to use:** When a flow needs to perform multiple database operations that must either all succeed or all fail together. The classic example is a financial transfer: debiting one account and crediting another must be atomic. If the credit fails, the debit must be rolled back.

**Why this matters:** Without transactions, a failure between two related database operations leaves your data in an inconsistent state. Transactions guarantee atomicity (all-or-nothing), which is essential for maintaining data integrity in any workflow that modifies multiple records.

```lua
function setup() end

function main(params)
  -- sn.db.transaction() wraps all enclosed operations in a database
  -- transaction. If any operation throws an error (via error()), the
  -- entire transaction is rolled back. If all operations succeed, the
  -- transaction is committed.
  local amount = params.amount
  local from_account = params.from_account
  local to_account = params.to_account

  sn.db.transaction(function()
    -- Step 1: Debit the source account
    sn.db.exec("UPDATE accounts SET balance = balance - ? WHERE id = ?",
      {amount, from_account})

    -- Step 2: Verify the source account has sufficient funds.
    -- This check happens INSIDE the transaction, so no other transaction
    -- can modify the balance between our UPDATE and this SELECT.
    local account_a = sn.db.query_one("SELECT * FROM accounts WHERE id = ?",
      {from_account})
    if account_a.balance < 0 then
      -- Calling error() inside a transaction triggers a rollback.
      -- The debit from Step 1 is undone, and the flow receives an error.
      error("Insufficient funds")
    end

    -- Step 3: Credit the destination account
    sn.db.exec("UPDATE accounts SET balance = balance + ? WHERE id = ?",
      {amount, to_account})

    -- Step 4: Create an audit trail
    sn.db.exec("INSERT INTO transactions (from_id, to_id, amount) VALUES (?, ?, ?)",
      {from_account, to_account, amount})
  end)

  ctx.log("info", "Transfer complete")
  return {ok = true}
end

function cleanup() end
function failed(err) end
```

### Pattern: Pagination with Cursor

**When to use:** When you need to return large result sets in manageable pages. This pattern is essential for any API endpoint that lists records, and is the recommended approach for flows that process large datasets incrementally.

**Why this matters:** Returning thousands of records in a single response is slow, memory-intensive, and often unnecessary. Cursor-based pagination is more efficient than offset-based pagination for large datasets because it does not degrade in performance as you page deeper into the results. The cursor approach also handles insertions and deletions between pages correctly.

```lua
function setup() end

function main(params)
  local page_size = 50
  local cursor = params.cursor or "0"

  -- Query page_size + 1 rows. If we get more rows than page_size,
  -- there are additional pages. The extra row tells us this without
  -- needing a separate COUNT(*) query.
  local rows = sn.db.query(
    "SELECT * FROM orders WHERE id > ? ORDER BY id LIMIT ?",
    {cursor, page_size + 1})

  local has_more = #rows > page_size
  if has_more then
    table.remove(rows)  -- Remove the sentinel row (not returned to caller)
  end

  -- The next cursor is the ID of the last row in the current page.
  -- The caller passes this back as the cursor for the next page.
  local next_cursor = nil
  if has_more and #rows > 0 then
    next_cursor = rows[#rows].id
  end

  return {
    orders = rows,
    next_cursor = next_cursor,
    has_more = has_more
  }
end

function cleanup() end
function failed(err) end
```

---

## Error Handling Patterns

Error handling is one of the most important aspects of building reliable automation workflows. External services fail, networks are unreliable, databases lock up, and inputs contain unexpected data. These patterns help you build flows that handle failures gracefully, recover when possible, and provide useful diagnostic information when they cannot.

### Pattern: Graceful Degradation

**When to use:** When your flow depends on an external service that might be unavailable, and you can provide a useful (if reduced) result using cached or default data. This pattern is appropriate when partial results are better than a complete failure.

**Why this matters:** Hard failures in one dependency should not cascade into failures across your entire system. By falling back to cached data or default values, your flow can continue providing value even during outages. This is especially important for user-facing flows where an error message is a much worse experience than slightly stale data.

```lua
function setup() end

function main(params)
  -- Attempt to fetch fresh data from the external API.
  -- The timeout prevents the flow from hanging if the API is unresponsive.
  local resp = sn.http.get("https://api.example.com/data", {timeout_ms = 5000})

  local data
  if resp.status == 200 then
    -- API is healthy. Use the fresh data and also cache it for future
    -- fallback use. This keeps the cache up to date during normal operation.
    data = sn.json.dec(resp.body)
    sn.db.exec("INSERT OR REPLACE INTO data_cache (id, data, created_at) VALUES (?, ?, ?)",
      {"latest", sn.json.enc(data), sn.time.now()})
  else
    -- API is unavailable. Log a warning (not an error, since we can recover)
    -- and fall back to the most recent cached data.
    ctx.log("warn", "API unavailable (HTTP " .. resp.status .. "), using cached data")
    local cached = sn.db.query_one("SELECT * FROM data_cache ORDER BY created_at DESC")
    if cached then
      data = sn.json.dec(cached.data)
    else
      -- No cache available either. Use a safe default.
      data = {status = "unavailable", note = "No cached data available"}
    end
  end

  return data
end

function cleanup() end
function failed(err) end
```

### Pattern: Exponential Backoff Retry

**When to use:** When your flow needs to make an HTTP request or external call that might fail transiently. Transient failures include network timeouts, HTTP 502/503/504 errors, rate limiting, and brief service outages. Retrying with exponential backoff gives the external service time to recover without overwhelming it with rapid retries.

**Why this matters:** Simple immediate retries can make problems worse by flooding a struggling service with additional requests. Exponential backoff (doubling the delay between each attempt) is a widely adopted best practice that balances recovery speed with system health. Many API providers explicitly recommend or require this pattern.

```lua
function setup() end

-- This is a reusable utility function you can include in any flow.
-- It wraps a function call with retry logic using exponential backoff.
-- The 'fn' parameter should be a function that returns a result on success
-- or calls error() on failure.
function retry_with_backoff(fn, max_attempts)
  for attempt = 1, max_attempts do
    local ok, result = pcall(fn)

    if ok then
      return result  -- Success on this attempt
    end

    if attempt < max_attempts then
      -- Calculate delay: 1s, 2s, 4s, 8s, etc.
      local delay = 2 ^ (attempt - 1)
      ctx.log("warn", "Attempt " .. attempt .. " of " .. max_attempts ..
        " failed: " .. tostring(result) .. ". Retrying in " .. delay .. "s")
      sn.sleep(delay)
    else
      -- All attempts exhausted. Re-raise the error for the caller to handle.
      ctx.log("error", "All " .. max_attempts .. " retry attempts failed")
      error(result)
    end
  end
end

function main(params)
  local result = retry_with_backoff(function()
    local resp = sn.http.post("https://api.example.com/submit",
      sn.json.enc(params.data),
      {headers = {["Content-Type"] = "application/json"}})
    if resp.status ~= 200 then
      error("Request failed with HTTP " .. resp.status)
    end
    return sn.json.dec(resp.body)
  end, 3)  -- Try up to 3 times

  return {ok = true, result = result}
end

function cleanup() end
function failed(err) end
```

---

## Logging Patterns

Effective logging is essential for understanding what your flows do, diagnosing problems when they occur, and auditing system behavior over time. Sentinel stores execution logs per-flow and makes them available through the `/lg` and `/ex/{id}/lg` API endpoints, as well as through the dashboard's log viewer. These patterns help you produce logs that are useful both during development and in production.

### Pattern: Structured Logging

**When to use:** Always. Every flow should include structured log messages at key decision points. Structured logging means including relevant identifiers and values in every log message so that you can trace a specific execution through the system without ambiguity.

**Why this matters:** Log messages like "Processing order" are nearly useless when you have hundreds of concurrent executions. Structured messages like "Processing order ord_12345 for customer cust_678" let you quickly filter and trace a specific workflow instance. Including the execution ID in logs allows you to correlate messages across flows that are part of the same logical operation.

```lua
function setup() end

function main(params)
  -- Always include the relevant business identifiers in log messages.
  -- These identifiers let you search and filter logs effectively.
  ctx.log("info", "Processing order " .. params.order_id ..
    " for customer " .. params.customer_id)

  local result = sn.json.dec(sn.http.post("https://api.example.com/process",
    sn.json.enc({order_id = params.order_id})).body)

  -- Log the outcome with specific values, not just "success" or "failure".
  -- Include the execution_id so this log entry can be correlated with
  -- the execution record in the /ex API.
  ctx.log("info", "Order status: " .. result.status ..
    ", amount: $" .. result.amount / 100 ..
    ", execution_id: " .. ctx.execution_id)

  return {ok = true}
end

function cleanup() end
function failed(err) end
```

### Pattern: Error Logging with Context

**When to use:** Whenever your flow calls external services, processes user input, or performs operations that might fail. Wrapping risky operations in pcall() and logging the full context on failure gives you the information you need to diagnose problems without having to reproduce them.

**Why this matters:** When a flow fails in production, the error message alone is often not enough to understand what went wrong. By logging the full context (which parameters were being processed, which step failed, what the execution ID was), you create a breadcrumb trail that makes debugging much faster.

```lua
function setup() end

function main(params)
  local ok, result = pcall(function()
    return process_order(params.order_id)
  end)

  if not ok then
    -- Log the error with all available context. This information
    -- will appear in the execution logs accessible via /ex/{id}/lg
    -- and in the dashboard's log viewer.
    ctx.log("error", "Order processing failed: " .. tostring(result) ..
      " (execution: " .. ctx.execution_id ..
      ", order: " .. params.order_id .. ")")

    -- Optionally emit an event for an alerting flow to pick up
    sentinel.emit("flow.error", {
      flow = "process-order",
      error = tostring(result),
      order_id = params.order_id
    })

    return {ok = false, error = result}
  end

  return result
end

function cleanup() end
function failed(err) end
```

---

## State Management Patterns

Sentinel provides persistent state in the SQLite database that survives across executions, and all trigger types pass data to `main(params)` as a Lua table argument. Note that `ctx.set()` and `ctx.get()` are stubs (no-op / always return nil), so use local variables for within-execution state and the database for cross-execution state.

### Pattern: Execution State

**When to use:** When you want to track the progress of a flow execution through its stages. Use local variables to track the current step within an execution and log the step on failure. For state visible via the API, store progress in the database.

**Why this matters:** When a flow fails, knowing which step it was on is the first question you need answered. By tracking the step in a local variable and logging it in the `failed()` handler, you get this information automatically.

```lua
function setup() end

-- Track the current step in a module-level local so failed() can access it.
local current_step = "init"

function main(params)
  -- Use a local variable to track execution progress. Update it
  -- before each step so the failed() handler knows where it stopped.

  current_step = "1_data_fetch"
  local data = sn.http.get("https://api.example.com/data")

  current_step = "2_validation"
  validate_data(data)

  current_step = "3_storage"
  store_data(data)

  current_step = "4_completion"
  return {ok = true}
end

function cleanup() end
function failed(err)
  -- The current_step local tells you exactly which stage the flow
  -- was in when the error occurred.
  ctx.log("error", "Flow failed at step: " .. current_step ..
    ", error: " .. tostring(err))
end
```

### Pattern: Session Management

**When to use:** When you have a multi-flow workflow where separate flow executions need to share state. For example, a user login flow creates a session, and subsequent action flows need to reference that session. Since each flow execution gets its own `ctx`, you need a persistent mechanism (the database) to share state across executions.

**Why this matters:** Real-world workflows often span multiple flow executions. A user might log in (flow 1), browse products (flow 2), add items to cart (flow 3), and check out (flow 4). The session concept ties these separate executions together into a coherent user journey.

```lua
-- Flow 1: Start session
function setup()
  event("user.login")
end

function main(params)
  local session_id = sn.crypto.random_bytes(16)
  local payload = params.event_payload

  -- Persist the session in the database so other flows can find it.
  -- The database is the only state that persists across flow executions.
  sn.db.exec("INSERT INTO sessions (id, user_id, started_at) VALUES (?, ?, ?)",
    {session_id, payload.user_id, sn.time.now()})

  return {session_id = session_id}
end

function cleanup() end
function failed(err) end
```

```lua
-- Flow 2: Use session
function setup()
  event("user.action")
end

function main(params)
  -- Look up the session from the database using the user_id
  -- passed in the event payload.
  local payload = params.event_payload
  local session = sn.db.query_one("SELECT * FROM sessions WHERE user_id = ?",
    {payload.user_id})

  if not session then
    return {ok = false, error = "No active session"}
  end

  -- Update last activity timestamp for session timeout tracking
  sn.db.exec("UPDATE sessions SET last_activity = ? WHERE id = ?",
    {sn.time.now(), session.id})

  -- Continue with the workflow using the session context
  return {ok = true}
end

function cleanup() end
function failed(err) end
```

---

## Testing Patterns

Testing your flows before deploying them to production is essential for reliability. These patterns cover techniques for isolating your flows from external dependencies during testing and for setting up reproducible test scenarios.

### Pattern: Mock External Services

**When to use:** When you want to test your flow logic without making real API calls. This is important during development (to avoid consuming API quotas), in CI/CD pipelines (where external services may not be accessible), and when testing error handling paths (where you need to simulate failures).

**Why this matters:** Tests that depend on external services are slow, unreliable, and often expensive. By pointing your flows at a mock server during testing, you get fast, deterministic tests that you can run anywhere. You can also simulate error conditions (timeouts, 500 errors, rate limits) that are difficult to trigger with real services.

```lua
-- The API_URL is configurable via environment variable, defaulting to
-- the production URL. During testing, set the MOCK_API environment
-- variable to point at a local mock server.
local API_URL = os.getenv("MOCK_API") or "https://api.example.com"

function setup() end

function main(params)
  local resp = sn.http.get(API_URL .. "/status")
  return sn.json.dec(resp.body)
end

function cleanup() end
function failed(err) end
```

**Running tests with a mock:**
```bash
# Start a mock server (e.g., using a tool like mockoon, wiremock, or a simple HTTP server)
# Then run Sentinel with the MOCK_API variable set:
MOCK_API="http://localhost:8081" ./sentinel harness start -p ./test-sre
```

### Pattern: Database Fixtures

**When to use:** When your flow depends on specific data being present in the database. Fixtures create a known starting state so that your tests are deterministic and reproducible.

**Why this matters:** Tests that depend on previous test runs or on manually-created data are fragile and hard to debug. Fixtures ensure that each test starts from a known state and cleans up after itself, preventing test pollution where one test's data affects another test's outcome.

```lua
function test_process_order()
  -- Setup: Create the exact data this test needs. Do not rely on
  -- data from other tests or previous runs.
  sn.db.exec("INSERT INTO customers (id, name) VALUES (?, ?)",
    {"cust_test", "Test Customer"})

  sn.db.exec("INSERT INTO orders (id, customer_id, status) VALUES (?, ?, ?)",
    {"ord_test", "cust_test", "pending"})

  -- Execute: Run the function under test with known inputs
  local result = process_order({order_id = "ord_test"})

  -- Verify: Check that the result matches expectations
  sn.test.ok(result.ok, "Should process order successfully")

  -- Cleanup: Remove test data so it does not affect other tests.
  -- In a transaction-based test framework, you could wrap the entire
  -- test in a transaction and roll it back instead.
  sn.db.exec("DELETE FROM orders WHERE id = ?", {"ord_test"})
  sn.db.exec("DELETE FROM customers WHERE id = ?", {"cust_test"})
end
```

---

## Performance Patterns

When your flows process large datasets or make many external calls, performance becomes a concern. These patterns help you handle high-volume workloads efficiently within Sentinel's execution model.

### Pattern: Batch Processing

**When to use:** When your flow needs to process a large number of items (hundreds or thousands). Rather than inserting or processing items one at a time, batch processing groups them into chunks and processes each chunk in a transaction. This is dramatically faster for database operations because it reduces the number of transaction commits.

**Why this matters:** SQLite (and most databases) have significant per-transaction overhead. Inserting 10,000 rows one at a time means 10,000 separate transactions, each with its own disk sync. Inserting them in batches of 100 means only 100 transactions, which can be 10-50x faster. Batching also reduces memory pressure because you only hold one batch in memory at a time.

```lua
function setup() end

function main(params)
  local items = params.items or {}
  local batch_size = 100

  -- Process items in batches of 100
  for i = 1, #items, batch_size do
    local batch = {}
    for j = i, math.min(i + batch_size - 1, #items) do
      table.insert(batch, items[j])
    end

    process_batch(batch)

    -- Log progress for long-running batch jobs
    ctx.log("info", "Processed " .. math.min(i + batch_size - 1, #items) ..
      " of " .. #items .. " items")
  end

  return {ok = true, total = #items}
end

function process_batch(batch)
  -- Wrap the entire batch in a single transaction for performance.
  -- All inserts in this batch either succeed together or fail together.
  sn.db.transaction(function()
    for _, item in ipairs(batch) do
      sn.db.exec("INSERT INTO processed (id, data) VALUES (?, ?)",
        {item.id, sn.json.enc(item)})
    end
  end)
end

function cleanup() end
function failed(err) end
```

### Pattern: Connection Pooling

**When to use:** When your flow makes multiple HTTP requests to the same service in a loop. By reusing the same headers object and relying on HTTP keep-alive, you avoid the overhead of establishing a new TCP connection for each request.

**Why this matters:** TCP connection setup (especially with TLS) adds significant latency to each request. Reusing connections via keep-alive can reduce per-request latency by 50-200ms. For a flow that makes 100 requests, that adds up to 5-20 seconds of saved time.

```lua
function setup() end

function main(params)
  -- Prepare shared headers once. The Connection: keep-alive header
  -- tells the HTTP client to reuse the TCP connection across requests.
  local headers = {
    Authorization = "Bearer " .. ctx.secret("api_token"),
    ["Content-Type"] = "application/json",
    ["Connection"] = "keep-alive"
  }

  local ids = params.ids or {}
  local results = {}

  for _, id in ipairs(ids) do
    local resp = sn.http.get("https://api.example.com/items/" .. id,
      {headers = headers})
    if resp.status == 200 then
      table.insert(results, sn.json.dec(resp.body))
    else
      ctx.log("warn", "Failed to fetch item " .. id .. ": HTTP " .. resp.status)
    end
  end

  return {ok = true, results = results}
end

function cleanup() end
function failed(err) end
```

---

## Summary

These patterns cover the most common scenarios you will encounter when building automation workflows with Sentinel. The key principles across all patterns are:

1. **Decouple with events.** Use events to connect flows rather than direct calls. This makes your system more modular and resilient.
2. **Handle failures explicitly.** Every external call can fail. Use retries, fallbacks, and structured error logging to handle failures gracefully.
3. **Use transactions for data integrity.** When multiple database operations must succeed together, wrap them in a transaction.
4. **Log with context.** Include business identifiers, execution IDs, and step indicators in every log message.
5. **Test in isolation.** Use mock services and database fixtures to make your tests fast, deterministic, and independent.
6. **Batch for performance.** When processing large datasets, batch operations reduce transaction overhead dramatically.
7. **Leverage WebSockets for real-time needs.** Push data to connected clients instead of having them poll.

As your SRE grows, you will likely combine multiple patterns within a single flow. A webhook handler might use HMAC verification, exponential backoff retries for downstream calls, structured logging throughout, and batch processing for bulk operations. The patterns compose naturally because they each address a different concern.
