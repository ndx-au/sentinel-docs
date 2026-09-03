---
okf_version: "0.2"
---

# Overview

* [Sentinel Documentation](../sn.docs/ct/index.md) - Sentinel is a git-native orchestration harness -- a single Go binary that discovers, manages, and executes Lua-based workflows from a plain folder of files.

# Guide

* [Getting Started with Sentinel](../sn.docs/ct/getting-started.md) - Welcome to Sentinel. This guide is your starting point -- whether you are a developer who wants to automate workflows, an operations engineer evaluating orchestration tools, or an AI agent consuming this documentation programmatically.
* [Configuration Guide](../sn.docs/ct/configuration-guide.md) - Comprehensive guide to Sentinel configuration, security, deployment, and performance tuning.
* [Kit Development Guide](../sn.docs/ct/kit-development.md) - Complete guide to building kits -- the fundamental unit of organization in Sentinel -- with flows, connectors, modules, forms, pages, databases, CMS content, and templates.
* [Workflows and Patterns Guide](../sn.docs/ct/workflows-and-patterns.md) - This guide is a comprehensive collection of battle-tested patterns for building automation workflows with Sentinel.
* [Triple-Access Pattern for Sentinel Services](../sn.docs/ct/triple-access-pattern.md) - The Triple-Access Pattern is a core internal architecture principle used throughout the Sentinel codebase.
* [Edge Deployment Guide](../sn.docs/ct/edge-deployment.md) - This guide walks you through deploying Sentinel in a production environment behind a reverse proxy with edge security.
* [Adversarial Testing & Probe Runner](../sn.docs/ct/adversarial-testing.md) - Adversarial testing is the practice of deliberately trying to break your system to find bugs before your users do.
* [Storage Points](../sn.docs/ct/storage.md) - Storage points provide a way to manage S3-compatible object storage endpoints for keeping binary files (images, video, documents, and other media assets) out of the SRE git repository.
* [Registration, occupy, and editions](../sn.docs/ct/licensing.md) - Sentinel is proprietary software of NDX Pty Ltd (GitHub org ndx-au, public sites on ndx.au). Every production harness must register and occupy a live slot while it is online. There is no business grace: if occupy fails past the lease TTL (~180s), flows do not start.
* [Docker And Container Deployment](../sn.docs/ct/docker-and-containers.md) - This document explains how Sentinel uses Docker, how the harness detects Docker availability, what changes when Sentinel itself is running inside a container, and the security implications of mounting the Docker socket.
* [WordPress with Sentinel](../sn.docs/ct/wordpress.md) - This document describes the WordPress platform architecture for Sentinel, covering the central origin, preview rendering, and edge content delivery.
* [fcms (file CMS) — Operator Guide](../sn.docs/ct/sentinel-cms.md) - Git-native file content in Sentinel: Markdown files in a kit’s ct/ directory are the source of truth.
* [MCP Agent Integration](../sn.docs/ct/mcp-agent-integration.md) - Connect AI coding agents (Cursor, Claude Desktop, Hermes, custom MCP clients) to a running Sentinel harness so they can inspect SREs, validate kits, run executions, reload kits, read source, and scaffold components — without round-tripping through the HTTP API.
* [RAG retrieval evaluation](../sn.docs/ct/rag-evaluation.md) - Offline, fixture-driven retrieval benchmarks for the harness RAG stack. Live PG-backed eval against a running SRE is optional; CI gates on embedded fixtures in internal/rag/testdata/retrieval_eval_fixtures.json.
* [AI provider extension guide](../sn.docs/ct/ai-provider-extension.md) - How to add a Go runtime adapter for a new meta.runtime.provider value in API Library. Operators register vendors in the dashboard; the harness wires adapters at bootstrap via BuildClientFromLibrary.
* [Content planes — fcms, ccms, wpcms](../sn.docs/ct/content-planes.md) - Sentinel is pluralistic: orchestration always works without a content plane. When you publish content, pick one primary public plane per site origin (dual-primary on the same origin is unsupported).
* [NDX Trust — SOC2 Type II preparation](../sn.docs/ct/ndx-trust-soc2.md) - This document prepares hosted NDX systems for a SOC2 Type II observation period.

# Reference

* [HTTP API Reference](../sn.docs/ct/api-reference.md) - Complete reference for every Sentinel HTTP endpoint. This document covers request formats, response structures, authentication, error handling, pagination, streaming, and WebSocket protocols.
* [Lua API Reference](../sn.docs/ct/lua-api.md) - Complete reference for the Lua API available inside Sentinel flows. This document covers the sandboxed execution environment, the flow lifecycle, every available API function, and common patterns for building robust automation flows.
* [CLI Reference](../sn.docs/ct/cli-reference.md) - Complete reference for the sentinel command-line interface, covering every command, flag, environment variable, and common workflow.
* [Harness HTTP route reference](../sn.docs/ct/harness-http-routes.md) - This document is the canonical catalog of HTTP paths the Sentinel harness exposes on api.port (default 8080).
* [The `.sentinel/` Directory](../sn.docs/ct/sentinel-directory.md) - Machine-local harness state for one SRE. Gitignored (see repo .gitignore).
* [Harness Internals — Code Architecture](../sn.docs/ct/internals.md) - Contributor reference for the Sentinel harness Go codebase.

# Playbook

* [Troubleshooting & FAQ](../sn.docs/ct/troubleshooting-faq.md) - This guide is your comprehensive reference for diagnosing and resolving problems with Sentinel.
* [Agentic AI — operator guide](../sn.docs/ct/agentic-ai-operator.md) - End-to-end path for enabling LLM flows in an SRE: API Library + Vault → Agents validate → release controls → flow (sn.ai.chat) → trace in dashboard.
* [Agentic AI — UAT trail](../sn.docs/ct/agentic-ai-uat.md) - Hands-on acceptance trail for M1 — Agentic AI completion. Work through each section in order; sample payloads are copy-paste ready.

# Generated

* [Sentinel Documentation](sentinel-docs.md) - Hierarchical concatenation of the sentinel-docs OKF bundle for NotebookLM.
