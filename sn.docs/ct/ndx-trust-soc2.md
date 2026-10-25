---
title: "NDX Trust — SOC2 Type II preparation"
description: "Preparation for a SOC2 Type II observation period for hosted NDX systems."
type: Guide
tags: [trust]
status: stable
---

<!-- ndx-ste-mode: description -->

# NDX Trust — SOC2 Type II preparation

**Company:** NDX Pty Ltd  
**Public TLD:** ndx.au  
**GitHub:** ndx-au  

This document prepares hosted NDX systems for a SOC2 Type II observation period. It does **not** claim that Sentinel or NDX is SOC2 Type II certified.

## Language

| Surface | Allowed phrasing |
|---------|------------------|
| Sentinel harness (customer-deployed) | Product security controls and test evidence contributing to readiness |
| NDX hosted license / identity | SOC2 Type II **program** (in progress) |
| Marketing | Do not claim ISO certification or SOC 2 attestation without applicable independent assurance |

Customers operate customer-deployed instances.
The parties must agree on any future NDX SOC 2 system boundary for the actual engagement.
They must also agree on the treatment of telemetry and occupy data.
This guide asserts no attestation scope.

See [Security readiness and shared responsibility](/security-readiness) for
product limitations, secure deployment responsibilities and the SQLCipher
verification/migration boundary. Local tests are not operating-effectiveness
evidence for a hosted observation period.

## In-scope systems (NDX hosted)

- [ndxHQ](https://github.com/ndx-au/ndxHQ) at `https://license.ndx.au` (occupy, prepaid batches, CE telemetry, cloudless grants).
- Outbound tunnel broker / Cloudflare Tunnel tokens for org-license.
- Sentinel Kit Marketplace if it retains PII (`https://kits.ndx.au`).
- Identity: `https://id.ndx.au` (Authentik, formerly id.ndx.video).
- Stripe (prepaid slot Checkout), transactional email, admin endpoints, operator laptops.

## Control mapping (harness)

| Control | Implementation |
|---------|----------------|
| Encryption at rest | Vault: application-layer AES-256-GCM on SQLite. State: SQLCipher **opt-in**, default off. It needs a supported CGO build and tests of the file and key. Older files need assessment and a reviewed offline migration. |
| Auth | ED25519 dashboard signatures + bearer tokens. Auth failures emit `AUDIT[auth:…]` |
| Vault CRUD | SQLite `secret_access_log` plus `AUDIT[vault:secret:…]` |
| Occupy | `AUDIT[license:occupy:granted\|denied\|lapsed]` |
| Transport | TLS is optional (`tls.enabled`). In production, enable TLS |

## Type I → Type II clock

1. Policies: access control, change management, incident response, vendor, backup, encryption, privacy/retention, security awareness.
2. Evidence tooling (Vanta/Drata or equivalent) on HQ, IdP, Stripe, GitHub ndx-au.
3. Type I (design) then Type II (operating effectiveness, typically 3–12 months).
4. Pentest and access reviews during the observation window.

## Privacy (CE occupy)

CE instances must occupy. The payload includes instance identity and operational fields.
Kit and system telemetry follow the configured product behaviour.
This guide does not approve a default retention period or secondary marketing use.

Through NDX's privacy/ISMS process, establish the data inventory, purposes, legal basis, and contractual notices.
Define access and the retention schedule through the same process.
