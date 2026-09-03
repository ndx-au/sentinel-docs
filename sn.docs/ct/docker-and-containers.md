---
title: "Docker And Container Deployment"
description: "This document explains how Sentinel uses Docker, how the harness detects Docker availability, what changes when Sentinel itself is running inside a container, and the security implications of mounting the Docker socket."
type: Guide
tags: [docker]
status: stable
---

# Docker And Container Deployment

This document explains how Sentinel uses Docker, how the harness detects Docker availability, what changes when Sentinel itself is running inside a container, and the security implications of mounting the Docker socket.

## Summary

Sentinel treats Docker as an optional **harness capability**, not as a baseline assumption.

That means:

- If the attached harness can talk to Docker, the Docker page is enabled.
- If the attached harness cannot talk to Docker, Docker-backed features are disabled cleanly.
- Manual infrastructure workflows still work. For example, you can still add an existing PostgreSQL connection even when Docker is unavailable.

The dashboard currently uses this capability for:

- the Docker page
- generated PostgreSQL instances from the Databases page
- managed RAG enablement from the RAG page
- any other Docker Compose stack management actions routed through the harness

## What Sentinel Checks

Sentinel does not guess based only on whether it is running bare-metal or inside a container.

Instead, the harness probes Docker directly:

1. Is the `docker` CLI available?
2. Can the harness reach the Docker daemon?

If either check fails, the harness reports Docker as unavailable.

The dashboard then disables Docker-backed actions and shows an operator-facing explanation such as:

> This harness does not have access to Docker. It may already be running inside a container without Docker socket access.

## When Docker Features Work

Docker-backed features work when all of the following are true:

- the `docker` binary is installed in the harness runtime
- the harness process can execute Docker commands
- the Docker daemon is reachable
- the harness has permission to use the Docker socket or remote daemon

When that is true, Sentinel can:

- list compose stacks
- save compose files
- start and stop stacks
- read stack logs
- generate and boot local PostgreSQL instances from the Databases page
- provision the managed single-instance RAG database automatically from the RAG page

## When Docker Features Are Disabled

Docker-backed features are disabled when the harness does not have usable Docker access.

Common cases:

- Docker is not installed on the host
- Docker is installed but the daemon is not running
- Docker socket permissions block the harness user
- Sentinel is running inside a container without `/var/run/docker.sock`
- Sentinel is running in an environment that intentionally has no Docker access

When Docker is unavailable:

- the Docker page shows a disabled-state message instead of pretending the feature is usable
- the Databases page disables `Generate PostgreSQL Instance`
- the RAG page disables `Enable Managed RAG`
- manual `Add Connection` still works
- RAG can still use an externally managed PostgreSQL database

## Managed RAG Database

Sentinel now treats RAG as a single harness-level subsystem.

If Docker is available, the recommended operator path is:

1. Open the RAG page
2. Click `Enable Managed RAG`
3. Let Sentinel provision and initialize the backing PostgreSQL stack
4. Configure an embedding-capable AI provider on the Agents page if semantic or multimodal retrieval is required
5. Return to `/rag` and choose the `Embedding Provider` and `Embedding Model`

That managed flow:

- creates a hardened local PostgreSQL stack specifically for RAG
- stores all generated credentials in the vault
- registers the resulting PostgreSQL connection with the harness
- initializes the `sentinel_rag` schema automatically

The managed RAG stack uses a `pgvector`-capable PostgreSQL 18 image so the vector and trigram extensions are available during initialization.

Important:
- managed RAG provisions the PostgreSQL retrieval backend, not the embedding provider
- semantic and multimodal indexing still require a configured AI provider with embedding support
- the RAG page makes this explicit through a dedicated `Embedding Provider` selector

## Sentinel Running Inside A Container

Sentinel can run inside a container. In that model, Docker-backed features only work if the container has explicit Docker access.

There are two broad modes:

### 1. Containerized Sentinel without Docker socket access

This is the safer and simpler default.

Characteristics:

- the harness runs inside a container
- Docker CLI and daemon access are not exposed inside that container
- Docker-backed features are disabled
- external services such as PostgreSQL must be provided separately

This is a good fit when:

- you only want Sentinel as an orchestration/API runtime
- infrastructure is managed elsewhere
- you do not want the app container to control the host

### 2. Containerized Sentinel with Docker socket access

This is a privileged deployment mode.

Typical setup:

- mount `/var/run/docker.sock` into the Sentinel container
- ensure the container user can access the socket
- ensure the `docker` CLI exists in the container image

In that mode, Sentinel can manage host Docker resources even though Sentinel itself is containerized.

This enables:

- the Docker page
- compose stack management
- generated PostgreSQL instances

But it also means the Sentinel container effectively has host-level Docker control.

## Security Implications Of Mounting The Docker Socket

Mounting the Docker socket is operationally convenient, but it is a high-trust decision.

In practice, Docker socket access is close to host-level control because a process that can control Docker can usually:

- start privileged containers
- mount host paths
- inspect other containers
- reach secrets available to the Docker host
- alter or replace running workloads

Treat Docker socket access as equivalent to giving the harness strong infrastructure control.

Recommended policy:

- use Docker socket mounting only when you explicitly want Sentinel to manage Docker on that host
- do not mount the socket by default
- keep this mode for trusted operator environments
- prefer external PostgreSQL and manual connections when you do not want host Docker control

## Example: Running Sentinel In A Container Without Docker Access

This is the simplest containerized deployment pattern.

```yaml
services:
  sentinel:
    image: your-sentinel-image
    ports:
      - "8085:8080"
    volumes:
      - ./sre:/app/sre
    command: ["./sentinel", "start", "-p", "/app/sre", "--port", "8080", "--no-input"]
```

In this mode:

- Sentinel runs normally
- Docker page is disabled
- generated PostgreSQL is disabled
- you should use externally managed services

## Example: Running Sentinel In A Container With Docker Socket Access

This is the explicit opt-in mode for host Docker management.

```yaml
services:
  sentinel:
    image: your-sentinel-image
    ports:
      - "8085:8080"
    volumes:
      - ./sre:/app/sre
      - /var/run/docker.sock:/var/run/docker.sock
    command: ["./sentinel", "start", "-p", "/app/sre", "--port", "8080", "--no-input"]
```

Additional requirements:

- the image must include the `docker` CLI
- the process user inside the container must be able to use the socket

Use this only if you intentionally want Sentinel to manage host Docker stacks.

## Operational Guidance

Choose one of these models deliberately:

### Model A: Sentinel manages Docker locally

Use when:

- you want one-click stack management
- you want Sentinel-generated PostgreSQL instances
- the host is trusted for operator-driven automation

Requirements:

- Docker installed
- daemon reachable
- harness user can use Docker

### Model B: Sentinel uses external infrastructure

Use when:

- Sentinel runs in restricted environments
- your platform team provides PostgreSQL separately
- Docker control from the application layer is undesirable

Requirements:

- provide PostgreSQL separately
- add connections manually from the Databases page or CLI

## Dashboard Behavior

The dashboard now reflects Docker capability explicitly.

### Docker Page

If Docker is available:

- stack management UI is shown

If Docker is unavailable:

- the page shows a disabled-state message
- create/start/stop actions are not exposed

### Databases Page

If Docker is available:

- `Generate PostgreSQL Instance` is enabled

If Docker is unavailable:

- that button is disabled
- the page explains why
- `Add Connection` remains available

## Recommended Default

For most production deployments:

- do **not** assume Docker access
- treat Docker-backed workflows as optional convenience features
- keep manual and external infrastructure paths first-class

That gives Sentinel a clean degradation path:

- Docker-capable harnesses get stack management
- restricted harnesses remain fully usable for orchestration, flows, CMS, AI, and external databases
