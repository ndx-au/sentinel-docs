---
okf_version: "0.2"
---

# Overview

* [Sentinel Documentation](../sn.docs/ct/index.md) - Sentinel uses one Go binary to discover, manage, and execute Lua workflows from a folder of plain files.

# Guide

* [Getting Started with Sentinel](../sn.docs/ct/getting-started.md) - How to install Sentinel, create a project, run your first flow, and use the core components.
* [Configuration Guide](../sn.docs/ct/configuration-guide.md) - Reference for shared project configuration, local infrastructure configuration, security, backups, and deployment.
* [Kit Development Guide](../sn.docs/ct/kit-development.md) - How to build Sentinel kits with flows, connectors, modules, forms, pages, templates, assets, and skill twins.
* [Workflows and Patterns Guide](../sn.docs/ct/workflows-and-patterns.md) - Workflow patterns for webhooks, schedules, events, forms, content, containers, errors, logs, and tests.
* [Triple-Access Pattern for Sentinel Services](../sn.docs/ct/triple-access-pattern.md) - How to share Sentinel business logic across REST API, CLI, and Lua interfaces.
* [Edge Deployment Guide](../sn.docs/ct/edge-deployment.md) - How to deploy Sentinel behind a reverse proxy, configure TLS and edge security, and monitor production operation.
* [Adversarial Testing & Probe Runner](../sn.docs/ct/adversarial-testing.md) - How to probe Sentinel APIs, test their contracts, find security vulnerabilities, and test the harness under load.
* [Storage Points](../sn.docs/ct/storage.md) - How to register S3-compatible storage points, resolve public URLs, and use them for content and backups.
* [Registration, occupy, and editions](../sn.docs/ct/licensing.md) - Sentinel registration, occupy leases, editions, credentials, and license enforcement.
* [Docker And Container Deployment](../sn.docs/ct/docker-and-containers.md) - How Sentinel detects Docker access, runs in containers, and manages the privileges from Docker socket access.
* [WordPress with Sentinel](../sn.docs/ct/wordpress.md) - Sentinel WordPress architecture, central origin, preview rendering, and delivery at the edge.
* [fcms (file CMS) — Operator Guide](../sn.docs/ct/sentinel-cms.md) - How to manage Markdown content, use fcms APIs, render HTML, and configure content access.
* [MCP Agent Integration](../sn.docs/ct/mcp-agent-integration.md) - How to connect MCP clients to Sentinel and configure authentication, permissions, tools, resources, and prompts.
* [RAG retrieval evaluation](../sn.docs/ct/rag-evaluation.md) - Offline retrieval benchmarks, fixture tests, dashboard results, and optional tests against a live SRE.
* [AI provider extension guide](../sn.docs/ct/ai-provider-extension.md) - How to add a Go runtime adapter and connect it to API Library vendors, credential validation, and the dashboard.
* [Content planes — fcms, ccms, wpcms](../sn.docs/ct/content-planes.md) - Sentinel content planes: fcms for files, ccms for collections, and wpcms for WordPress.
* [NDX Trust — SOC2 Type II preparation](../sn.docs/ct/ndx-trust-soc2.md) - Preparation for a SOC2 Type II observation period for hosted NDX systems.
* [Security readiness and shared responsibility](../sn.docs/ct/security-readiness.md) - Sentinel product security boundaries, responsibilities for deployment, and limits of assurance.

# Reference

* [HTTP API Reference](../sn.docs/ct/api-reference.md) - Reference for Sentinel HTTP endpoints, authentication, request and response data, pagination, event streams, and WebSockets.
* [Lua API Reference](../sn.docs/ct/lua-api.md) - Reference for Lua flow APIs, context, HTTP, WebSockets, databases, secrets, AI, memory, and retrieval.
* [CLI Reference](../sn.docs/ct/cli-reference.md) - Reference for Sentinel commands, flags, environment variables, and common operator procedures.
* [Harness HTTP route reference](../sn.docs/ct/harness-http-routes.md) - Reference for harness HTTP route prefixes, default kit behavior, keyhole configuration, and dashboard proxy mappings.
* [The `.sentinel/` Directory](../sn.docs/ct/sentinel-directory.md) - Reference for local harness files, their storage engines, dependencies, backups, and proposed changes.
* [Harness Internals — Code Architecture](../sn.docs/ct/internals.md) - Reference for harness packages, startup, subsystem connections, and flow execution.

# Playbook

* [Troubleshooting & FAQ](../sn.docs/ct/troubleshooting-faq.md) - Causes and corrective procedures for Sentinel startup, flows, databases, APIs, security, and Lua errors.
* [Agentic AI — operator guide](../sn.docs/ct/agentic-ai-operator.md) - How to configure the API Library, vault, release controls, flows, and dashboard traces for LLM workflows.
* [Agentic AI — UAT trail](../sn.docs/ct/agentic-ai-uat.md) - Acceptance procedures for Agentic AI completion, with example payloads and expected results.

# Generated

* [Sentinel Documentation](sentinel-docs.md) - Hierarchical concatenation of the sentinel-docs OKF bundle for NotebookLM.
