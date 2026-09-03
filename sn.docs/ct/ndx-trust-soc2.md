---
title: "NDX Trust — SOC2 Type II preparation"
description: "This document prepares hosted NDX systems for a SOC2 Type II observation period."
type: Guide
tags: [trust]
status: stable
---

# NDX Trust — SOC2 Type II preparation

**Company:** NDX Pty Ltd  
**Public TLD:** ndx.au  
**GitHub:** ndx-au  

This document prepares hosted NDX systems for a SOC2 Type II observation period. It does **not** claim that Sentinel or NDX is SOC2 Type II certified.

## Language

| Surface | Allowed phrasing |
|---------|------------------|
| Sentinel harness (customer-deployed) | SOC2-ready controls (audit, encryption, occupy evidence) |
| NDX hosted license / identity | SOC2 Type II **program** (in progress) |
| Marketing | Do not say “Sentinel is SOC2 Type II certified” until an independent report exists |

Customer-deployed Sentinel is **out of NDX attestation scope** except for telemetry and occupy data NDX receives at `license.ndx.au`.

## In-scope systems (NDX hosted)

- [ndxHQ](https://github.com/ndx-au/ndxHQ) at `https://license.ndx.au` (occupy, prepaid batches, CE telemetry, cloudless grants)
- Outbound tunnel broker / Cloudflare Tunnel tokens for org-license
- Sentinel Kit Marketplace if it retains PII (`https://kits.ndx.au`)
- Identity: `https://id.ndx.au` (Authentik; formerly id.ndx.video)
- Stripe (prepaid slot Checkout), transactional email, admin endpoints, operator laptops

## Control mapping (harness)

| Control | Implementation |
|---------|----------------|
| Encryption at rest | Vault: application-layer AES-256-GCM on SQLite. State: SQLCipher **opt-in**, default off. |
| Auth | ED25519 dashboard signatures + bearer tokens; auth failures emit `AUDIT[auth:…]` |
| Vault CRUD | SQLite `secret_access_log` plus `AUDIT[vault:secret:…]` |
| Occupy | `AUDIT[license:occupy:granted\|denied\|lapsed]` |
| Transport | TLS optional (`tls.enabled`); production operators should enable TLS |

## Type I → Type II clock

1. Policies: access control, change management, incident response, vendor, backup, encryption, privacy/retention, security awareness.
2. Evidence tooling (Vanta/Drata or equivalent) on HQ, IdP, Stripe, GitHub ndx-au.
3. Type I (design) then Type II (operating effectiveness, typically 3–12 months).
4. Pentest and access reviews during the observation window.

## Privacy (CE occupy)

CE instances must occupy. Payload always includes instance id, harness version, uptime. Kit list and system info follow `marketplace.telemetry_enabled`. Retain occupy rows under a documented retention period (default 24 months) for R&D and prospecting.
