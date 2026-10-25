---
title: "Edge Deployment Guide"
description: "How to deploy Sentinel behind a reverse proxy, configure TLS and edge security, and monitor production operation."
type: Guide
tags: [deployment]
status: stable
---

<!-- ndx-ste-mode: description -->

# Edge Deployment Guide

This guide explains production deployment with a reverse proxy and edge security. The primary architecture uses Cloudflare for CDN and DDoS protection. Caddy provides the origin reverse proxy. The guide also covers nginx and deployments without Cloudflare.

Production deployment of Sentinel requires careful attention to security, performance, and reliability. This guide covers each aspect in detail, from initial configuration through monitoring and backup strategies.

---

## Architecture Overview

```
Internet -> Cloudflare Edge (CDN + DDoS + SSL) -> Caddy Origin Server -> Sentinel Harness
              (Full Strict SSL, caching)            (TLS termination,    (localhost:8080)
                                                     reverse proxy)
```

**Why this three-layer architecture:**

- **Cloudflare** (outer layer) handles global CDN distribution, DDoS protection, bot mitigation, and TLS termination between the browser and Cloudflare's edge servers. This means malicious traffic is filtered before it even reaches your server, and static content is served from edge nodes close to your users.

- **Caddy** (middle layer) handles TLS between Cloudflare and your origin server using a Cloudflare origin certificate. This is required for Cloudflare's Full (Strict) SSL mode, which validates the origin certificate to prevent man-in-the-middle attacks between Cloudflare and your server. Caddy also acts as a reverse proxy, forwarding HTTP requests to Sentinel.

- **Sentinel** (inner layer) stays bound to `localhost:8080` and is never directly exposed to the internet. All external traffic is routed through Caddy. Sentinel handles the application logic: running flows, serving API responses, managing CMS content, and processing webhooks.

This dual-layer TLS architecture gives you edge performance and security without exposing Sentinel directly to the internet. Even if an attacker discovers your server's IP address, Sentinel is not accessible on any public port -- only Caddy listens on ports 80/443.

---

## Prerequisites

Before you start, make sure that you have:

- **A Linux server** with systemd, such as Ubuntu 22.04+, Debian 12+, or Rocky Linux 9+. A basic deployment needs at least 1 CPU core and 512MB RAM. Heavy traffic needs more resources.
- **A domain name** managed in Cloudflare (the domain's DNS must be configured to use Cloudflare's nameservers).
- **Caddy installed** on the server. Install through package manager (`apt install caddy` on Debian/Ubuntu) or download from [caddyserver.com](https://caddyserver.com). Caddy version 2.x is required.
- **The Sentinel binary** deployed to `/usr/local/bin/sentinel`. Copy the release binary and set execute permissions: `chmod +x /usr/local/bin/sentinel`.
- **An SRE project** at `/opt/sentinel-sre`. This is the directory containing your `sentinel.yaml`, kits, and the `.sentinel/` configuration directory.

---

## Step 1: Configure Sentinel for Production

Create the `.sentinel/config.json` file in your SRE directory. This file is gitignored and contains infrastructure-specific configuration that varies between environments (development, staging, production).

```json
{
  "api": {
    "port": 8080,
    "tokens": ["<64-char-random-token>"],
    "debug_mode": false
  },
  "state": {
    "encrypt_db": true
  }
}
```

**Generating a strong API token:**
```bash
openssl rand -hex 32
```

This produces a 64-character hexadecimal string. Use this as the value in the `tokens` array. You can configure multiple tokens if different clients need different credentials (though they all have the same access level).

**Configuration details:**

- `api.port` -- The port Sentinel listens on. In this architecture, Sentinel only accepts connections from localhost (Caddy), so 8080 is fine. Do not expose this port in your firewall.
- **Content-plane ports (dedicated, not path-merged):** Graphile/ccms defaults to host **1880**. wpcms ingress stays on its own port (**8800** legacy default, target **1800**). If you expose Graphile publicly, add a separate reverse_proxy upstream — do not multiplex Graphile under the harness path for MVP. See [Content planes](/content-planes).
- `api.tokens` -- An array of bearer tokens that clients must provide in the `Authorization: Bearer <token>` header. In production, always configure at least one token. When tokens are configured, the harness runs in production mode and rejects unauthenticated requests.
- `api.debug_mode` -- Set this to `false` in production. Debug mode disables token authentication and enables more diagnostic endpoints. Keep these endpoints private.
- `state.encrypt_db` -- Encrypts the SQLite state database using SQLCipher (AES-256). Requires the `SENTINEL_STATE_PASSPHRASE` environment variable to be set.

**Important security note:** Sentinel listens on `localhost:8080` only in this architecture. Caddy proxies external HTTPS traffic to it. Do NOT enable Sentinel's built-in TLS (`tls.*` configuration options) when running behind Caddy -- Caddy owns TLS termination. Enabling both creates unnecessary complexity and can cause certificate conflicts.

---

## Step 2: Cloudflare SSL -- Full (Strict) Mode

Cloudflare offers four SSL modes. Understanding the differences is critical for security:

| Mode | Cloudflare to Origin | Certificate Validated | Security | Recommendation |
|------|---------------------|-----------------------|----------|----------------|
| Off | Plain HTTP | No | None | Never use |
| Flexible | Plain HTTP | No | Browser to CF only | Never use -- false sense of security |
| Full | HTTPS | No | Encrypted but MITM-vulnerable | Avoid -- does not verify origin cert |
| **Full (strict)** | HTTPS | **Yes, validated** | End-to-end verified | **Use this in production** |

**Why Full (Strict) is the only acceptable option:** In "Full" mode without "strict", Cloudflare uses HTTPS without verifying the origin certificate. An attacker between Cloudflare and the origin can present a fake certificate to intercept traffic. Full (Strict) mode makes sure that the origin certificate is valid.

### Enable Full (Strict)

1. Log into the Cloudflare Dashboard.
2. Select your domain.
3. Navigate to **SSL/TLS** > **Overview**.
4. Select **Full (strict)**.

### Generate a Cloudflare Origin Certificate

Cloudflare Origin Certificates are free certificates that Cloudflare trusts. They are only valid for connections from Cloudflare to your origin (they are not trusted by browsers directly). This is exactly what we need.

1. In the Cloudflare Dashboard, navigate to **SSL/TLS** > **Origin Server**.
2. Click **Create Certificate**.
3. Select your domain (for example `your-domain.com` and `*.your-domain.com` for wildcard coverage).
4. Choose the validity period (15 years is the default and is fine for origin certificates since they are only used between Cloudflare and your server).
5. Download the certificate (`origin.pem`) and private key (`origin.key`).

Place the certificate files on your server with appropriate permissions:

```bash
# Create a directory for certificates
sudo mkdir -p /etc/caddy/certs

# Copy the certificate and key
sudo cp origin.pem /etc/caddy/certs/origin.pem
sudo cp origin.key /etc/caddy/certs/origin.key

# Restrict permissions -- only the caddy user should read the private key
sudo chmod 600 /etc/caddy/certs/origin.key
sudo chown caddy:caddy /etc/caddy/certs/origin.pem /etc/caddy/certs/origin.key
```

**CAUTION:** Restrict `origin.key` to the Caddy process user with permissions 600. A compromised private key permits origin impersonation.

---

## Step 3: Caddyfile

Create or edit `/etc/caddy/Caddyfile`. The Caddyfile configures Caddy as a reverse proxy that terminates TLS using the Cloudflare origin certificate and forwards requests to Sentinel.

```
your-domain.com {
    tls /etc/caddy/certs/origin.pem /etc/caddy/certs/origin.key

    reverse_proxy localhost:8080 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

**Line-by-line explanation:**

- `your-domain.com { ... }` -- This block handles all requests for your domain. Replace `your-domain.com` with your actual domain name.
- `tls /etc/caddy/certs/origin.pem /etc/caddy/certs/origin.key` -- Tells Caddy to use the Cloudflare origin certificate for TLS instead of obtaining a Let's Encrypt certificate automatically. This is necessary because the Cloudflare origin certificate is what Cloudflare's Full (Strict) mode expects to see.
- `reverse_proxy localhost:8080` -- Forwards all requests to the Sentinel harness running on localhost port 8080.
- `header_up X-Real-IP {remote_host}` -- Adds the client's real IP address to the forwarded request. Sentinel uses this for access logging and IP-based access control.
- `header_up X-Forwarded-For {remote_host}` -- Standard proxy header that Sentinel uses to identify the original client IP.
- `header_up X-Forwarded-Proto {scheme}` -- Tells Sentinel whether the original request was HTTP or HTTPS.

**Alternative: Using Let's Encrypt instead of Cloudflare Origin Certificates:**

If you prefer Let's Encrypt certificates (which also satisfy Full (Strict) validation), replace the `tls` directive:

```
your-domain.com {
    tls your-email@example.com

    reverse_proxy localhost:8080 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

Caddy gets and renews Let's Encrypt certificates automatically when you provide an email address. HTTP-01 challenges need access to port 80. TLS-ALPN-01 challenges need access to port 443. Certificate renewal can occasionally fail.

**Reload Caddy after making changes:**

```bash
sudo systemctl reload caddy
```

Make sure that Caddy started correctly:

```bash
sudo systemctl status caddy
sudo journalctl -u caddy --since "5 minutes ago"
```

---

## Step 4: Cloudflare Caching for CMS

When using Sentinel's CMS system to serve web content, Cloudflare can cache pages at the edge for faster delivery. This section explains how to configure caching so that public content is cached but dynamic API responses are not.

### Cloudflare Settings (Dashboard > Caching)

- **Cache Level:** Standard -- this tells Cloudflare to respect `Cache-Control` headers from your origin. If your origin says a response is cacheable, Cloudflare caches it. If not, Cloudflare passes through.
- **Browser Cache TTL:** Respect Existing Headers -- this defers to the `Cache-Control` header set by Caddy or Sentinel.

### CMS Pages -- Enable Caching

For public CMS pages that need edge caching, set cache headers in the Caddyfile or your CMS render flow:

```lua
-- In your kit's render.lua page flow
function setup() end

function main(params)
    local slug = params and params.slug
    local entry = sn.cms.get(slug)
    if not entry then
        return {ok = false}
    end

    -- The Cache-Control header can be set at the Caddy layer
    -- using a Cloudflare Page Rule or Cache Rule, or in the
    -- response headers if your rendering system supports it.

    return {ok = true, page = entry}
end

function cleanup() end
function failed(err) end
```

### CMS API Endpoints -- Disable Caching

For dynamic API endpoints (anything under `/cm/*` that returns JSON), disable caching so clients get fresh data:

You can configure this in Cloudflare:
1. Navigate to **Caching** > **Cache Rules**.
2. Create a rule: If URL path starts with `/cm/`, then **Bypass Cache**.

Or use a response header in your flows:
```lua
ctx.response.headers["Cache-Control"] = "no-store"
```

### Cache Purging

After deploying new content, purge the Cloudflare cache so visitors see the latest version:
- **Manual:** Cloudflare Dashboard > Caching > Purge Everything.
- **API:** `curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache" -H "Authorization: Bearer {cf_token}" -d '{"purge_everything":true}'`.
- **Selective:** Purge specific URLs instead of everything: `-d '{"files":["https://your-domain.com/page"]}'`.

---

## Step 5: Systemd Service for Sentinel

Create a systemd service unit so Sentinel starts automatically on boot and restarts on failure. Create the file `/etc/systemd/system/sentinel.service`:

```ini
[Unit]
Description=Sentinel Harness
After=network.target
# If you depend on a database or other service, add:
# After=network.target postgresql.service

[Service]
Type=simple
User=sentinel
Group=sentinel
WorkingDirectory=/opt/sentinel-sre
ExecStart=/usr/local/bin/sentinel harness start -p /opt/sentinel-sre
Restart=on-failure
RestartSec=5

# Security: Set the vault and state passphrases
# Option 1: Inline (less secure -- visible in systemctl show)
Environment=SENTINEL_VAULT_PASSPHRASE=<passphrase>
Environment=SENTINEL_STATE_PASSPHRASE=<passphrase>

# Option 2: Environment file (more secure -- separate file with restricted permissions)
# EnvironmentFile=/etc/sentinel/env
# Create /etc/sentinel/env with:
#   SENTINEL_VAULT_PASSPHRASE=<passphrase>
#   SENTINEL_STATE_PASSPHRASE=<passphrase>
# chmod 600 /etc/sentinel/env
# chown sentinel:sentinel /etc/sentinel/env

# Resource limits (optional, adjust based on your workload)
LimitNOFILE=65535
MemoryMax=1G

[Install]
WantedBy=multi-user.target
```

**Set up the service user and directory:**

```bash
# Create a dedicated sentinel user (no login shell for security)
sudo useradd -r -s /usr/sbin/nologin sentinel

# Set ownership of the SRE directory
sudo chown -R sentinel:sentinel /opt/sentinel-sre

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable sentinel
sudo systemctl start sentinel

# Verify it is running
sudo systemctl status sentinel

# Check the logs
sudo journalctl -u sentinel -f
```

**Understanding the service configuration:**

- `Type=simple` -- systemd expects the process to stay in the foreground. Sentinel's `start` command does this by default.
- `User=sentinel` -- Runs the harness as a non-root, dedicated user. This limits the blast radius of any security vulnerability.
- `Restart=on-failure` -- If the harness crashes (non-zero exit), systemd automatically restarts it after 5 seconds.
- `LimitNOFILE=65535` -- Increases the file descriptor limit, which is necessary if the harness handles many concurrent connections.
- `MemoryMax=1G` -- Prevents the harness from consuming unlimited memory. Adjust based on your workload.

---

## Alternative: Nginx Instead of Caddy

If you prefer nginx or already have it installed, here is the equivalent configuration:

```nginx
# /etc/nginx/sites-available/sentinel
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/certs/origin.pem;
    ssl_certificate_key /etc/nginx/certs/origin.key;

    # Modern TLS settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (required for /ws endpoint)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Increase timeouts for long-running flow executions
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

Enable the site and reload:
```bash
sudo ln -s /etc/nginx/sites-available/sentinel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Key differences from Caddy:**
- You must explicitly configure TLS protocol versions and cipher suites.
- WebSocket proxying requires explicit `Upgrade` header forwarding.
- Certificate renewal (if using Let's Encrypt) requires a separate tool like `certbot`.
- HTTP-to-HTTPS redirect must be configured manually.

---

## Alternative: No Cloudflare (Direct Deployment)

If you do not use Cloudflare, you can deploy Sentinel directly behind Caddy or nginx with Let's Encrypt certificates:

```
# Caddyfile for direct deployment (no Cloudflare)
your-domain.com {
    tls your-email@example.com

    reverse_proxy localhost:8080 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

**What you lose without Cloudflare:**
- No CDN caching (content served from your server for all requests).
- No DDoS protection (your server directly absorbs attack traffic).
- No bot mitigation.
- No global anycast network (higher latency for distant users).
- No Cloudflare-specific features (such as Workers and Page Rules).

**What you gain:**
- Simpler architecture (one fewer layer to configure and debug).
- No dependency on Cloudflare's infrastructure.
- Direct control over all headers and caching behavior.
- No need for Cloudflare origin certificates.

For internal tools, staging environments, or low-traffic sites, this is a perfectly valid deployment pattern.

---

## Monitoring and Health Check Setup

Production deployments need monitoring to detect problems before users report them.

### Basic Health Check Script

Create a cron job that checks Sentinel's health endpoint:

```bash
#!/bin/bash
# /usr/local/bin/sentinel-health-check.sh

HEALTH_URL="http://localhost:8080/hl"
ALERT_EMAIL="admin@example.com"

response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL")

if [ "$response" != "200" ]; then
    echo "Sentinel health check failed (HTTP $response)" | \
        mail -s "ALERT: Sentinel Down" "$ALERT_EMAIL"
fi
```

Add to crontab:
```bash
# Check every minute
* * * * * /usr/local/bin/sentinel-health-check.sh
```

### Systemd Watchdog

Add a watchdog timeout to the systemd service to detect hangs:

```ini
# Add to [Service] section of sentinel.service
WatchdogSec=30
```

This tells systemd to expect a watchdog notification every 30 seconds. If the harness becomes unresponsive, systemd automatically restarts it.

### External Monitoring

In production, monitor your public health endpoint with an external service. Examples include UptimeRobot, Pingdom, and Better Uptime:

```
https://your-domain.com/hl
```

The health endpoint returns JSON with `{ok: true}` when the harness is healthy. Configure your monitoring service to alert when the response changes or the endpoint becomes unreachable.

---

## Log Aggregation Recommendations

In production, aggregate Sentinel logs for analysis and retention.

### Option 1: journald (Built-in)

If you use the systemd service, logs are automatically captured by journald:

```bash
# View recent logs
sudo journalctl -u sentinel --since "1 hour ago"

# Follow logs in real time
sudo journalctl -u sentinel -f

# Export logs for analysis
sudo journalctl -u sentinel --since today -o json > /var/log/sentinel-export.json
```

### Option 2: File-based logging

Redirect Sentinel's output to a log file with rotation:

```ini
# In sentinel.service
StandardOutput=append:/var/log/sentinel/harness.log
StandardError=append:/var/log/sentinel/harness-error.log
```

Set up log rotation:
```
# /etc/logrotate.d/sentinel
/var/log/sentinel/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 sentinel sentinel
}
```

### Option 3: Remote aggregation

For multi-server deployments, send logs to a centralized system:
- **Loki + Grafana** -- Lightweight, works well with journald through Promtail.
- **Elasticsearch + Kibana** -- Full-text search, powerful dashboards.
- **Managed logging services, such as Datadog and Splunk** -- Managed services with built-in alerting.

---

## Backup Strategy for Production

### What to Back Up

| Item | Location | Frequency | Method |
|------|----------|-----------|--------|
| SRE project files | `/opt/sentinel-sre/` | On every change | Git push (already versioned) |
| State database | `/opt/sentinel-sre/.sentinel/state.db` | Daily | File backup plan or SQLite backup API |
| Vault database | `/opt/sentinel-sre/.sentinel/vault.db` | After secret changes | File copy |
| Configuration file | `/opt/sentinel-sre/.sentinel/config.json` | After configuration changes | File copy |
| TLS certificates | `/etc/caddy/certs/` | After renewal | File copy |

### Automated Database Backup Script

```bash
#!/bin/bash
# /usr/local/bin/sentinel-backup.sh

BACKUP_DIR="/var/backups/sentinel"
SRE_DIR="/opt/sentinel-sre"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup the state database using SQLite's online backup
sqlite3 "$SRE_DIR/.sentinel/state.db" ".backup '$BACKUP_DIR/state_$TIMESTAMP.db'"

# Backup the vault database
cp "$SRE_DIR/.sentinel/vault.db" "$BACKUP_DIR/vault_$TIMESTAMP.db"

# Backup the config
cp "$SRE_DIR/.sentinel/config.json" "$BACKUP_DIR/config_$TIMESTAMP.json"

# Compress older backups
find "$BACKUP_DIR" -name "*.db" -mtime +1 -exec gzip {} \;

# Delete backups older than retention period
find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.json" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $TIMESTAMP"
```

Schedule in crontab:
```bash
# Daily backup at 1 AM
0 1 * * * /usr/local/bin/sentinel-backup.sh >> /var/log/sentinel-backup.log 2>&1
```

The state database backup uses SQLite's `.backup` command. It creates a consistent snapshot during harness operation.

**CAUTION:** Do not copy `state.db` during harness operation. A concurrent write can corrupt the backup.

---

## Scaling Considerations

Sentinel follows a 1:1 deployment model: one harness instance serves one SRE project. This section discusses how to handle growing workloads within this model.

### Vertical Scaling

The simplest scaling approach is to give the server more resources:

- **CPU:** More cores allow more concurrent flow executions. Each flow runs in its own Lua VM, so flows are naturally parallelized.
- **Memory:** More RAM supports more concurrent flows and larger datasets. Monitor with `systemctl status sentinel` and system tools.
- **Disk I/O:** SQLite performance is heavily influenced by disk speed. Use SSD storage for the SRE directory.

### Horizontal Scaling (Multiple SREs)

If a single SRE outgrows one server, split it into multiple focused SREs:

- **SRE per domain:** One SRE for your website CMS, another for your internal automation, a third for your monitoring.
- **SRE per team:** Each team manages their own SRE with their own kits and flows.
- **Load balancer:** If multiple SREs serve one domain, distribute traffic through nginx, HAProxy, or Cloudflare Load Balancing.

### Queue-Based Scaling

For workloads with bursty traffic (for example webhook floods), consider adding a message queue in front of Sentinel:

```
Webhook Source -> Message Queue (Redis, SQS) -> Consumer -> Sentinel API
```

The consumer reads from the queue at a controlled rate and submits work to Sentinel through the API. This smooths out traffic spikes and provides durability if Sentinel is temporarily unavailable.

---

## Deployment Checklist

Use this checklist before going live:

- [ ] `.sentinel/config.json`: `debug_mode: false`, strong tokens (64+ hex chars), `encrypt_db: true`.
- [ ] Vault passphrase set in environment (not in scripts or configuration files).
- [ ] Cloudflare SSL mode: **Full (strict)**.
- [ ] Cloudflare origin certificate generated and placed in `/etc/caddy/certs/` with correct permissions.
- [ ] Caddyfile configured with origin cert and `reverse_proxy localhost:8080`.
- [ ] Caddy reloaded and healthy: `systemctl status caddy`.
- [ ] Systemd service for Sentinel configured with auto-restart.
- [ ] Firewall: only ports 80 and 443 public (Caddy). Port 8080 localhost-only.
- [ ] Health monitoring configured (cron, external service, or both).
- [ ] Log aggregation configured (journald, file, or remote).
- [ ] Backup script scheduled and tested.
- [ ] Test end-to-end:
  ```bash
  curl -H "Authorization: Bearer <token>" https://your-domain.com/hl
  # Expected: {"ok":true,...}
  ```
- [ ] Verify WebSocket connectivity (if using dashboard or real-time features):
  ```bash
  # Using websocat or wscat
  wscat -c wss://your-domain.com/ws
  ```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| **525 SSL Handshake Failed** | Caddy cannot present TLS certificate to Cloudflare | Check certificate paths in Caddyfile. Run `systemctl status caddy` and `journalctl -u caddy` for details |
| **526 Invalid SSL Certificate** | Certificate does not match domain, or is self-signed without Cloudflare trust | Use a Cloudflare origin certificate (or a valid Let's Encrypt certificate) |
| **521 Web Server Down** | Caddy is not running or not listening on port 443 | Run `systemctl start caddy`. Check firewall allows port 443 |
| **524 Timeout** | Sentinel harness is not responding within Cloudflare's timeout (100 seconds) | Check `systemctl status sentinel`. Make sure that the SRE path in the service file is correct |
| **401 from Sentinel** | Missing or incorrect Bearer token in the request | Make sure that `Authorization: Bearer <token>` matches a token in `.sentinel/config.json` |
| **502 Bad Gateway** | Caddy cannot connect to Sentinel on localhost:8080 | Make sure that Sentinel responds: `curl http://localhost:8080/hl` |
| **Stale content after deploy** | Cloudflare is serving a cached version | Purge the cache: Cloudflare Dashboard > Caching > Purge Everything |
| **WebSocket connections fail** | Reverse proxy not forwarding upgrade headers | Make sure that nginx has `proxy_set_header Upgrade` and `proxy_set_header Connection "upgrade"` directives. Caddy handles this automatically |
