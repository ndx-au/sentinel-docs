---
title: "Docker And Container Deployment"
description: "How Sentinel detects Docker access, runs in containers, and manages the privileges from Docker socket access."
type: Guide
tags: [docker]
status: stable
---

<!-- ndx-ste-mode: description -->

# Docker And Container Deployment

This guide explains Docker access in Sentinel and how the harness detects it. It covers Sentinel containers and the privileges from Docker socket access.

## Summary

Sentinel treats Docker as an optional **harness capability**, not as a baseline assumption.

That means:

- If the attached harness can talk to Docker, the Docker page is enabled.
- If the attached harness cannot talk to Docker, Docker-backed features are disabled cleanly.
- Manual infrastructure workflows still work. For example, you can still add an existing PostgreSQL connection even when Docker is unavailable.

The dashboard currently uses this capability for:

- The Docker page.
- Generated PostgreSQL instances from the Databases page.
- Managed RAG enablement from the RAG page.
- Any other Docker Compose stack management actions routed through the harness.

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

- The `docker` binary is installed in the harness runtime.
- The harness process can execute Docker commands.
- The Docker daemon is reachable.
- The harness has permission to use the Docker socket or remote daemon.

When that is true, Sentinel can:

- List compose stacks.
- Save compose files.
- Start and stop stacks.
- Read stack logs.
- Generate and boot local PostgreSQL instances from the Databases page.
- Provision the managed single-instance RAG database automatically from the RAG page.

## When Docker Features Are Disabled

Docker-backed features are disabled when the harness does not have usable Docker access.

Common cases:

- Docker is not installed on the host.
- Docker is installed but the daemon is not running.
- Docker socket permissions block the harness user.
- Sentinel is running inside a container without `/var/run/docker.sock`.
- Sentinel is running in an environment that intentionally has no Docker access.

When Docker is unavailable:

- The Docker page shows a disabled-state message instead of pretending the feature is usable.
- The Databases page disables `Generate PostgreSQL Instance`.
- The RAG page disables `Enable Managed RAG`.
- Manual `Add Connection` still works.
- RAG can still use an externally managed PostgreSQL database.

## Managed RAG Database

Sentinel now treats RAG as a single harness-level subsystem.

If Docker is available, the recommended operator path is:

1. Open the RAG page.
2. Click `Enable Managed RAG`.
3. Let Sentinel provision and initialize the backing PostgreSQL stack.
4. Configure an embedding-capable AI provider on the Agents page if semantic or multimodal retrieval is required.
5. Return to `/rag` and choose the `Embedding Provider` and `Embedding Model`.

That managed flow:

- Creates a hardened local PostgreSQL stack specifically for RAG.
- Stores all generated credentials in the vault.
- Registers the resulting PostgreSQL connection with the harness.
- Initializes the `sentinel_rag` schema automatically.

The managed RAG stack uses a `pgvector`-capable PostgreSQL 18 image so the vector and trigram extensions are available during initialization.

Important:
- Managed RAG provisions the PostgreSQL retrieval backend, not the embedding provider.
- Semantic and multimodal indexing still require a configured AI provider with embedding support.
- The RAG page makes this explicit through a dedicated `Embedding Provider` selector.

## Sentinel Running Inside A Container

Sentinel can run inside a container. In that model, Docker-backed features only work if the container has explicit Docker access.

There are two broad modes:

### 1. Containerized Sentinel without Docker socket access

This is the safer and simpler default.

Characteristics:

- The harness runs inside a container.
- Docker CLI and daemon access are not exposed inside that container.
- Docker-backed features are disabled.
- External services such as PostgreSQL must be provided separately.

This is a good fit when:

- You only want Sentinel as an orchestration/API runtime.
- Infrastructure is managed elsewhere.
- You do not want the app container to control the host.

### 2. Containerized Sentinel with Docker socket access

This is a privileged deployment mode.

Typical setup:

- Mount `/var/run/docker.sock` into the Sentinel container.
- Make sure that the container user can access the socket.
- Make sure that the `docker` CLI exists in the container image.

In that mode, Sentinel can manage host Docker resources even though Sentinel itself is containerized.

This enables:

- The Docker page.
- Compose stack management.
- Generated PostgreSQL instances.

But it also means the Sentinel container effectively has host-level Docker control.

## Security Implications Of Mounting The Docker Socket

Mounting the Docker socket is operationally convenient, but it is a high-trust decision.

In practice, Docker socket access is close to host-level control because a process that can control Docker can usually:

- Start privileged containers.
- Mount host paths.
- Inspect other containers.
- Reach secrets available to the Docker host.
- Alter or replace running workloads.

Treat Docker socket access as equivalent to giving the harness strong infrastructure control.

Recommended policy:

- Use Docker socket mounting only when you explicitly want Sentinel to manage Docker on that host.
- Do not mount the socket by default.
- Keep this mode for trusted operator environments.
- Prefer external PostgreSQL and manual connections when you do not want host Docker control.

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

- Sentinel runs normally.
- Docker page is disabled.
- Generated PostgreSQL is disabled.
- Use externally managed services.

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

More requirements:

- The image must include the `docker` CLI.
- The process user inside the container must be able to use the socket.

Use this only if you intentionally want Sentinel to manage host Docker stacks.

## Operational Guidance

Choose one of these models deliberately:

### Model A: Sentinel manages Docker locally

Use when:

- You want one-click stack management.
- You want Sentinel-generated PostgreSQL instances.
- The host is trusted for operator-driven automation.

Requirements:

- Docker installed.
- Daemon reachable.
- Harness user can use Docker.

### Model B: Sentinel uses external infrastructure

Use when:

- Sentinel runs in restricted environments.
- Your platform team provides PostgreSQL separately.
- Docker control from the application layer is undesirable.

Requirements:

- Provide PostgreSQL separately.
- Add connections manually from the Databases page or CLI.

## Dashboard Behavior

The dashboard now reflects Docker capability explicitly.

### Docker Page

If Docker is available:

- Stack management UI is shown.

If Docker is unavailable:

- The page shows a disabled-state message.
- Create/start/stop actions are not exposed.

### Databases Page

If Docker is available:

- `Generate PostgreSQL Instance` is enabled.

If Docker is unavailable:

- That button is disabled.
- The page explains why.
- `Add Connection` remains available.

## Recommended Default

For most production deployments:

- Do **not** assume Docker access.
- Treat Docker-backed workflows as optional convenience features.
- Keep manual and external infrastructure paths first-class.

That gives Sentinel a clean degradation path:

- Docker-capable harnesses get stack management.
- Restricted harnesses remain fully usable for orchestration, flows, CMS, AI, and external databases.
