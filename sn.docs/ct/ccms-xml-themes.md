---
title: "CCMS XML views and XSLT themes"
description: "Versioned presentation XML and kit-local XSLT themes for Sentinel collection CMS."
type: Guide
tags: [cms, ccms, themes]
status: draft
---

<!-- ndx-ste-mode: description -->

# CCMS XML views and XSLT themes

CCMS presents authorized collection data through a stable XML envelope and optional
kit-local XSLT themes. PostgreSQL and Graphile remain the data authority. There is
no per-collection XSD or DTD.

## Presentation contract

- Namespace: `urn:ndx:sentinel:ccms:1`
- Root: `{urn:ndx:sentinel:ccms:1}document` with `version="1"`, `view`, and `audience` (the prefix is not significant)
- Views: `list`, `detail`, `new`, `edit`, `saved`, `error`
- Field names are XML attribute values (spaces and odd identifiers stay intact)
- Field metadata may include `column` for form control names (HTTP posts use columns)
- Collection-level `actions` carry `submit` and `list` hrefs for editors
- Distinct states: value, empty string, null (`<cc:null/>`), omitted
- Exact numeric lexemes are retained on reads; booleans are `true`/`false`
- XML-illegal text is reversibly base64 encoded with `encoding="utf8-b64"`; byte values use `encoding="base64"`
- Add `xmlns:cc="urn:ndx:sentinel:ccms:1"` to XSLT and use explicit `cc:` paths, such as `//cc:collection/cc:rows/cc:row`

XML is internal. Public and editor HTML pages do not require clients to fetch XML.

## Kit configuration

```yaml
# kit.yaml
ccms_theme: catalog
```

```yaml
# themes/catalog/theme.yaml
templates:
  ccms.list: list.xsl
  ccms.detail: detail.xsl
  ccms.form: form.xsl
  ccms.saved: saved.xsl
```

If `ccms_theme` is unset, legacy Go templates / built-in HTML remain. If it is set
and broken, rendering fails with a visible theme error (no silent layout fallback).

Reference kit `sn.ccms-pages-posts` ships two themes: `catalog` (default) and
`cards`. Switch with `ccms_theme: cards` after `sentinel ccms install-refkit`.

## Collection bindings

Prefer kit `collections/*.yaml` for source identity, keys, exposure and optional
GraphQL overrides. Forms may still declare `schema`/`table`; the adapter maps them
without auto-publishing. Publication for anonymous browse requires
`publication.public: true` plus `data_plane.public_graphile_url`.

## Publication boundary

Anonymous browse uses only:

- `GET /ccms/{ns}/{name}/collections/{collection}`
- `GET /ccms/{ns}/{name}/collections/{collection}/{key}`

Requirements: `collections/*.yaml` with `publication.public: true`, kit enabled,
`data_plane.enabled: true`, and `data_plane.public_graphile_url` configured.
Editor, status, and forms catalog routes stay authenticated.

## Protected editors

Authenticated editors stay on:

- `GET+POST /ccms/{ns}/{name}/forms/{form}`
- `GET /ccms/{ns}/{name}/forms/{form}/list`

Themed editors round-trip through the same XML model. Validation and Graphile
failures re-render the form with submitted values and `data-ccms-error` markers.
A missing row on update surfaces as `CCMS.STALE` (no generic optimistic locking).
Dashboard Collections deep-links to the harness origin. These links require harness
authentication; the dashboard session is not forwarded to that origin. Dedicated
`/collections/edit/...` BFF routes are deferred.

## Verified scope and remaining work

Acceptance on 2026-11-10 used fresh PostgreSQL 17 and digest-pinned PostGraphile
v4, production gateway authentication, both reference themes, and real Chromium
create/edit/validation/navigation checks. A 125-record fixture traversed cursor
pages without duplicates or truncation. Migration repeated as a skip; JSON CLI
output is machine-readable.

Public lists accept `limit=1..100` (default 20) and an opaque `cursor`; editors
use cursor pages of up to 100 records. Follow the rendered Next action.
Publication filtering occurs in Graphile before pagination, with stable primary-key
ordering. A separately configured URL must still use a database role with the
intended read-only grants and row policy; URL configuration does not create them.

The proven runtime slice is the pages/posts refkit with a single `id` key, text
fields and checkboxes. The wider #37 contract remains open: schema-derived
GraphQL metadata/custom mappings, non-id/compound-key execution, fully typed
nullable/default/JSON/array editor controls and complete relation support still
need implementation and acceptance. Descriptor/type helpers alone do not prove
those end-to-end capabilities.

## Known limits

- No file uploads, delete/bulk edit, or public XML export in v1
- Declared relation expansion remains unverified; no arbitrary joins
- List-template Gohtml path remains for kits without `ccms_theme`

Related: [Content planes](/content-planes), [Harness HTTP routes](/harness-http-routes).
