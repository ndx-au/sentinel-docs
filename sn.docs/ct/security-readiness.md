---
title: "Security readiness and shared responsibility"
description: "Sentinel product security boundaries, responsibilities for deployment, and limits of assurance."
type: Guide
tags: [security, trust, operations]
status: draft
---

<!-- ndx-ste-mode: description -->

# Security readiness and shared responsibility

Sentinel and NDX develop evidence for future ISO/IEC 27001 and SOC 2 assurance.
This guide does not claim ISO/IEC 27001 certification or SOC 2 attestation for Sentinel or NDX.
Product tests contribute evidence.
Assurance also needs controls across the organisation and an independent assessment.

## Deployment boundary

One harness instance administers one Sentinel Runtime Environment (SRE).
Kit namespaces do not provide separate customer tenants.
Shared administrators, Docker access, database owners, or dashboard credentials can cross the boundary between instances.

For instances that need separation, use distinct OS or service identities.
Use separate SRE directories, credentials, database roles, volumes, and network rules.

For self-hosted Sentinel, the customer owns host hardening, authenticated ingress, TLS, and user access reviews.
The customer also owns backups, restores, monitoring, retention, and trust in installed kits.
NDX owns product engineering and release fixes.
For an NDX-operated service, NDX must operate the corresponding infrastructure controls and retain evidence.
The actual deployment needs evidence of isolation and availability.

## Management and browser access

Keep harness management, the dashboard, and the MCP sidecar behind restricted, authenticated ingress.
Use a production build.
Disable debug authentication.
Provision unique credentials.
Protect all traffic with TLS and make sure that certificates are valid.

The dashboard stores privileged harness credentials and relies on trusted ingress.
It does not provide a general login or role-based access system for end users.

The harness can listen on all interfaces. The security closure fixes the dashboard listener to IPv4 loopback. It has no public bind flag. For remote access, use authenticated ingress or a controlled tunnel that can reach loopback in the dashboard network namespace. A separate container cannot reach this listener through the usual container address.
An empty dashboard whitelist allows all peers.
A production build does not automatically enable TLS or make these listeners private.
Apply explicit firewall rules and authenticated ingress.

The security baseline removes wildcard dashboard CORS and rejects browser mutations from other origins.
WebSocket origins must match the dashboard authority.
Desktop pages navigate to the dashboard origin.
Native actions use the launcher's separately authenticated bridge.

Do not restore wildcard CORS to resolve a deployment problem.
Do not disable browser protections.

MCP defaults to read/validate permissions.
Loopback binding limits reachability but does not authenticate the caller.
In the baseline implementation, all MCP HTTP paths need credentials.
The signing proxy has privileged access.

Restrict the MCP listener.
Configure the smallest necessary risk ceiling.
Limit client permissions for tools, resources, and prompts.
Restrict the signing proxy to trusted local clients.

## Kits and agents

Lua's restricted libraries, module loading within kits, and clean VM lifecycle reduce risk.
Host APIs still provide configured access to the vault, databases, networks, events, and connectors.

Treat installed kits as trusted automation code.
Do not use kit names or AI instructions as a tenant sandbox.
Use external credentials with narrow permissions for connectors.
Review permitted network egress.

Before a target executes, the harness examines each provider batch for tools outside its declared scope.
Model fallback follows the scoped policy.
Dispatch examines the operator pause state.
Retrieved documents, tool results, persistent memory, and skill twins remain untrusted data.
Their instructions cannot grant authority.
These controls do not guarantee resistance to prompt injection or the safety of an allowed action.
The harness has no general mechanism that binds a specific action to human approval.
Recovery hooks have independent five-second limits.
Host calls must honour cancellation.
Deployment controls must enforce quotas for running jobs, heap use, and networks.

For workflows with major effects, require explicit human review.
Grant only the necessary permissions.

## Secrets and storage

Vault values use AES-256-GCM with random nonces for each encryption and an Argon2id-derived key.
Some secret names and metadata remain unencrypted.
Exact-value redaction in logs and AI traces adds protection.
It does not cover all encoded, split, short, or unregistered values.

Store connector and provider credentials in the vault.
Protect the master passphrase and recovery material separately.

State encryption is optional.
It needs a SQLCipher build with CGO support.
The baseline corrects ignored SQLCipher key parameters.
Before use, it makes sure that the database format and key are correct.
Whether an older database remained plaintext after an encryption request is unknown until assessment.
Portable builds without CGO cannot provide SQLCipher coverage.
The dashboard's fixed embedded database key does not replace access controls for the OS, files, or volumes.

Preserve existing database files and backups.
Plan an offline migration with review.
Test the restore and make sure that the restored files have the required encryption.
Do not delete a database to make startup succeed.
Do not disable encryption verification.

Other stores include execution state, traces, kit databases, memory, documents, uploads, caches, and content planes.
SQLite WAL and free pages, backups, snapshots, and Go garbage collection limit secure deletion.

Protect each store and backup according to its data.
Define retention for every store and external provider.
Define credential rotation and revocation.

## Content, backups and evidence

fcms raw HTML is for trusted authored content.
Local development templates do not establish minimum database permissions or isolation between rows in production.
Kit SQL migrations need explicit review and execution.

Separate public content from management origins.
Do not treat arbitrary uploaded Markdown as safe content.
Restrict Graphile/PostgreSQL and WordPress management.
Use unique secrets.
Use separate database roles for bootstrap, migration, and runtime access.

Local SQLite and stdout logs do not provide a tamper-resistant audit store.

Export security events to a restricted, durable logging system.
Synchronise clocks.
Test alerts.
Retain evidence under your policy.
Define recovery objectives.
Keep encrypted offsite backups.
Test restores in an isolated environment, including the encryption keys.

SBOM and provenance workflows and automated scanners support release review.
They do not prove that a release or deployment is secure.
The installed version's release notes and verification determine which security changes apply.
This draft is not evidence of deployment.
The installer needs a checksum verifier.

Use reviewed, versioned releases and kits.
Make sure that release checksums match.

If the repository has private vulnerability reporting, use that facility.
Otherwise, use your established NDX support relationship to arrange a private channel.
Send a minimal reproduction with fake data.
Never publish customer data or credentials.

Related guide: [NDX Trust preparation](/ndx-trust-soc2).


## Offline SQLCipher conversion

The reviewed copy converter preserves fail-closed startup. Follow the
[offline migration runbook](/sqlcipher-offline-migration) and separate
[rollout checklist](/sqlcipher-rollout-checklist). Conversion does not approve
installation. Native CGO/SQLCipher release validation and matching runtime keys
are required. The security closure also binds MCP sessions to authenticated
identity and permission profile and extends scoped AI checks to streaming and retries.
Native AI stream callbacks wait for full validation, with 4 MiB and 16,384-chunk
limits. Kit and host APIs still require trusted operators and deployment isolation.

## First-release security branch: management and file controls

The following applies to the unreleased security remediation branch; upgrade all
participating clients before rollout. It is not a statement about older releases.

The dashboard accepts a local Host authority (`localhost`, a loopback IP, and the
actual port), rejects foreign browser origins and does not grant CORS access.
Use an authenticated operator tunnel with a local browser URL. An ingress that
connects to dashboard loopback must share or explicitly reach its network namespace
and preserve the supported local authority. Do not publish its port as an unauthenticated
service. Authentication at the ingress and local OS user trust remain operator controls;
the dashboard has no general end-user login/RBAC. Each hosted instance needs separate
credentials, storage and administrative access.

The signing proxy is restricted to loopback and trusted native clients. It rejects
browser Origin headers, cross-site fetch metadata and non-local Host values before
signing or forwarding. A local process can still use its authority: protect the host
and key store. The MCP sidecar retains harness credential verification and SDK
origin/rebinding protection. An unauthenticated sidecar cannot bind publicly.

FS Control uses pinned directory handles for actual reads/writes/deletes. Managed
file connectors carry per-execution grants, including form entry paths; missing
enforcement denies access. Symlink components are refused even when their targets
are inside the root, because they can bypass a more-specific deny. Use ordinary
paths in policies. Reads and writes are capped at 16 MiB. Hardlinks, bind mounts,
host administrators and changes to operator-owned root directories remain host
security responsibilities; FS Control is not a hostile-tenant kernel sandbox.

Servers cap active handlers at 32 and body-bearing handlers at four, with a 32 MiB
request read limit and no unbounded admission queue. Request body read deadlines
are 15 seconds for dashboard, harness and MCP; streaming responses retain no write
timeout. Workflow registration, asynchronous execution and both form entry paths
share a 32-active-execution cap per manager, including recovery. Saturation rejects
work before creating a job. Accepted asynchronous jobs retain their existing execution
lifetime rather than being canceled when an HTTP request ends. These are engineering
bounds, not a distributed user quota or complete network denial-of-service protection.
Enforce connection/rate limits and OS resource budgets at deployment ingress too.


## First-release branch: metadata and native HTTP

Flow inspection has no execution host APIs. Keep metadata and top-level declarations
free of network, files, secrets and model calls; perform work in execution hooks.
Inspection uses a 100 ms evaluation budget, a 1 MiB regular source-file limit inside
the SRE and the shared manager admission limit. Host-dependent or invalid metadata
falls back to a default manifest. Source symlinks and named pipes are refused.

Native `sn.http.*` and the HTTP connector now inherit the Lua deadline and
cancellation. Their timeout is capped at 30 seconds and responses at 16 MiB. Supply
credentials in headers, not URL userinfo; URL fragments are rejected. HTTP connector
logs retain only the target origin and fixed error classes, not private URL paths
or query values.

The developing agent authority mechanism keeps model observation restricted across
an execution and its delegated children, including actions after plain model output.
When authority is bound, filesystem and native HTTP effects consult those grants.
Restricted HTTP requests refuse redirects, private/loopback destinations and common
address-translation ranges; they pin checked public DNS answers and inherit neither
proxy settings nor a cookie jar. Custom network routing still requires deployment
egress controls. Private-service automation remains an operator responsibility.

The unreleased branch now initializes an approval runtime and binds private
execution identity before registration, asynchronous execution and both form entry
paths. MCP-started flows begin with agent restrictions. Model calls during trigger
registration are refused before the provider. Remaining SQL resource identity,
credential audience, persistent code and final end-to-end assurance work is open;
this is not a release approval or a complete security boundary claim.

Events accept bounded JSON data, reject cycles and unsupported values, and give each
subscriber a frozen copy. The bus reserves an entire batch before creating dispatch
goroutines, with 64 active dispatches and no partial dispatch on saturation. This is
separate from the 32 active workflow limit. Split larger fanout deliberately and
handle `EVENT.BUSY`. Tool argument batches validate before any callback; native Lua
results reject unbounded or cyclic values.


Native sleep and PostgreSQL calls preserve the Lua deadline and cancellation.
SMTP sends are capped at 30 seconds, or the earlier caller deadline, with a 1 MiB
message limit and 100 recipients. Use bare email addresses and a single-line
subject. Provide both `username` and `password`, or neither; configured credentials
require verified STARTTLS with TLS 1.2 or newer. Never disable certificate checking
to make authentication succeed. Plain unauthenticated relay traffic still requires
an appropriately protected deployment network. Server acceptance of DATA does not
prove inbox delivery; reconcile uncertain results before retrying.

When agent authority is bound, SMTP needs a complete `connector.smtp` grant before
dialing and uses checked public destinations. An isolated network-namespace test
covers an authorized send and denied recipient mutation. This does not establish
real relay configuration, live delivery or operational confidentiality.


## First-release branch: execution policy and operator approval

An optional owner-managed `.sentinel/execution-policy.json` is read at startup.
Keep it a regular file, at most 1 MiB, writable only by the owner on Unix. Invalid,
unreadable, duplicate-key or unknown-field policies prevent startup. Policy changes
require a controlled restart. Without this file, ordinary trusted operator flows
retain their existing permissions; model-derived actions and MCP-started flows have
no native grants by default. One harness still administers one trusted-operator SRE.

Profiles may restrict canonical SRE-relative flow paths and authenticated actor IDs.
Exact operation grants explicitly select `automatic` or `required` approval, with
argument constraints or an explicit any-arguments choice. Actor, flow and ancestor
grants intersect. Model observation permanently narrows an execution origin,
including cached handles, parents and siblings. Generic native operations without
a matching restricted grant deny. Broad automatic grants need careful review;
persistent code and control-plane effects remain under assessment.

A required native action waits up to five minutes, or the earlier synchronous
caller deadline, for a local operator's exact approval. Use the local `approvals
runtime`, `approvals grant` and `approvals revoke` CLI commands against the existing
instance state and key configuration. Review the complete action file, canonical
source, authenticated actor and execution ID before granting. Tickets are single
use and bind the runtime, actor, execution, source digest, operation, arguments and
handle acquisition. An unrelated ticket cannot release the action. Restart
invalidates outstanding tickets. Storage, audit or clock failure denies dispatch.
The CLI provides no remote approval mode or automatic database initialization.

Native HTTP starts its bounded network timer after approval; total work still
inherits its caller deadline. Asynchronous root jobs retain their independent
workflow lifetime. Delegation is limited to depth 16 and 2,048 descendant attempts
per origin, shared across children; failed dispatch does not refund attempts.
Rejected delegation creates no workflow execution record. Event fanout and the
32-active-workflow limit apply separately.

Ordinary large or binary operator arguments may be explicitly omitted from general
audit records. Such an omission is never an approvable restricted-agent action.
Audit records avoid raw action payloads; retain private action files under operator
access controls. Native callback regions cannot call a model, and restricted
native callback-bearing arguments are currently unsupported. Real SQL handles,
delegated budget accounting and the final agent scenario suite still need proof.


Native SQLite execution, queries, transactions and schema inspection now inherit
the Lua caller's cancellation with a 30-second ceiling. Cancellation before a call
prevents database acquisition; cancellation during a transaction rolls back its
uncommitted writes. Schema names are single portable database labels, not paths;
quoted SQL identifiers are escaped. These checks do not make arbitrary SQL a kit
isolation boundary. Do not grant unrestricted raw SQL to an agent as a substitute
for reviewed operations and database permissions; backend/file-access review remains
open on the first-release branch.
