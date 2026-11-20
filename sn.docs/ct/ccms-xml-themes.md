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
- Root: `cc:document` with `version="1"`, `view`, and `audience`
- Views: `list`, `detail`, `new`, `edit`, `saved`, `error`
- Field names are XML attribute values (spaces and odd identifiers stay intact)
- Field metadata may include `column` for form control names (HTTP posts use columns)
- Collection-level `actions` carry `submit` and `list` hrefs for editors
- Distinct states: value, empty string, null (`<cc:null/>`), omitted
- Exact integer/decimal lexemes; UUIDs are opaque; booleans are `true`/`false`

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
Dashboard Collections deep-links to the harness origin; dedicated
`/collections/edit/...` BFF routes are deferred.

## Known limits

- No file uploads, delete/bulk edit, or public XML export in v1
- Relations are declared and bounded; no arbitrary joins
- List-template Gohtml path remains for kits without `ccms_theme`

Related: [Content planes](/content-planes), [Harness HTTP routes](/harness-http-routes).
