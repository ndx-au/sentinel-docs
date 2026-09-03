---
title: "Registration, occupy, and editions"
description: "Sentinel is proprietary software of NDX Pty Ltd (GitHub org ndx-au, public sites on ndx.au). Every production harness must register and occupy a live slot while it is online. There is no business grace: if occupy fails past the lease TTL (~180s), flows do not start."
type: Guide
tags: [licensing]
status: stable
---

# Registration, occupy, and editions

Sentinel is proprietary software of **NDX Pty Ltd** (GitHub org [`ndx-au`](https://github.com/ndx-au), public sites on **ndx.au**). Every production harness must **register** and **occupy a live slot** while it is online. There is no business grace: if occupy fails past the lease TTL (~180s), **flows do not start**.

## Editions

| Edition | Name | Eligibility | Slots |
|---------|------|-------------|-------|
| **CE** | Sentinel CE | Orgs attesting **under $1M USD** annual revenue | Unlimited concurrent while occupy succeeds. HQ records usage for R&D and customer relations. |
| **Enterprise** | Sentinel Enterprise | Above threshold, or any cloudless/on-prem org | **USD 100 per slot per month**, prepaid as dated batches of N concurrent slots × M months. |

Cloudless / on-prem org-license is **always paid** at the Enterprise rate, including sub-$1M orgs. Application and vetting are required.

## Phone home (occupy)

| Item | Value |
|------|--------|
| HQ | `https://license.ndx.au` (`marketplace.license_url`) |
| Kit catalog / device login | `https://kits.ndx.au` (`marketplace.url`) |
| Heartbeat | ~60 seconds |
| Lease TTL | ~180 seconds (protocol TTL, not a grace window) |
| Identity | `{sre}/.sentinel/marketplace-instance.json` Ed25519 + signed heartbeat |

`POST /v1/occupy` grants or denies a lease. CE still occupies. Paid orgs are refused with `NO_SLOT` or `ENTITLEMENT_EXPIRED` when concurrent online instances exceed unexpired prepaid batches.

Register binds **identity**. Occupy binds the **seat**. Offline instances free paid slots when the lease expires.

## Credentials

| Prefix | Edition |
|--------|---------|
| `sk_ce_*` | Sentinel CE |
| `sk_free_*` | Legacy CE |
| `sk_ent_*` | Enterprise |

Stored in `.sentinel/config.json` as `marketplace.license_key`.

## First-run

```bash
sentinel login          # device code against kits.ndx.au
sentinel register       # org profile + instance bind against license.ndx.au
sentinel harness start -p ./my-sre
```

Manual: `sentinel license activate sk_ent_...`

## Enforcement

| State | Flows |
|-------|-------|
| Unregistered (prod) | Blocked |
| Registered, live occupy lease | Run |
| Expired credential | Blocked |
| Occupy denied / lease lapsed | Blocked |
| SMTP configured | License deny/lapse emails |

Dev builds (`-tags dev`) are not gated. Public `snprod` binaries set `PrereleaseRegistrationBypass=false`.

## Notices

Occupy deny appears in harness logs (`AUDIT[license:occupy:…]`), dashboard header, `/mk/license`, `/hl` `marketplace`, and optional SMTP (`smtp.*` in `.sentinel/config.json`).

## Cloudless

Vetted paid orgs run **org-license** from [ndx-au/ndxHQ](https://github.com/ndx-au/ndxHQ) on their network. Sentinels occupy the local broker only. org-license syncs a signed entitlement blob to HQ over **outbound** HTTPS (optional Cloudflare Tunnel). Cached blob remains valid until `term_end`.

## Configuration

```json
{
  "marketplace": {
    "url": "https://kits.ndx.au",
    "license_url": "https://license.ndx.au",
    "license_key": "sk_ce_...",
    "registration_enabled": true,
    "telemetry_enabled": true
  },
  "smtp": {
    "enabled": false,
    "host": "",
    "port": 587,
    "from": "",
    "to": [],
    "license_notices": true
  }
}
```

`SENTINEL_LICENSE_URL` overrides `marketplace.license_url`. `SENTINEL_MARKETPLACE_URL` overrides kit catalog URL.

## Reserved rights

NDX Pty Ltd may add edition-specific code paths without changing the credential prefix format.
