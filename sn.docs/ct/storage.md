---
title: "Storage Points"
description: "Storage points provide a way to manage S3-compatible object storage endpoints for keeping binary files (images, video, documents, and other media assets) out of the SRE git repository."
---

# Storage Points

Storage points provide a way to manage S3-compatible object storage endpoints for keeping binary files (images, video, documents, and other media assets) out of the SRE git repository. Since git is designed for text files and source code, storing binary assets in git leads to repository bloat, slow clones, and merge conflicts. Storage points solve this by registering external object storage buckets that Sentinel's CMS system, dashboard, and Lua flows can reference.

## Overview

A storage point is a registration of an external S3-compatible storage endpoint with Sentinel. Each storage point has a unique short name called a "stub" that serves as a URL prefix in CMS templates. When the CMS template renderer encounters a stub-prefixed path in content, it automatically expands it to the full public URL of the asset.

Storage points serve two primary purposes:

1. **CMS URL Expansion** -- Each storage point has a stub (e.g., `img`, `vid`) that the CMS template renderer recognizes. At render time, a path like `/img/photo.jpg` is automatically expanded to the full public URL: `https://cdn.example.com/media/photo.jpg`. This means content authors write simple, portable paths in their markdown, and the system handles URL resolution.

2. **Storage Metadata Management** -- Storage points provide a centralized registry of bucket metadata accessible to the dashboard and to Lua flows via `sn.st.*`. This allows you to manage multiple storage backends (one for images, one for video, one for downloads) from a single interface, with credentials securely stored in the vault.

3. **Backup Upload Destinations** -- The backup subsystem can optionally upload completed folder archives and PostgreSQL dumps to a configured storage point after writing the local artifact under `.sentinel/backups`.

### Supported Providers

All three supported providers use the S3 API protocol, which means the same client code works with any of them. The differences are in how you configure the endpoint URL and credentials.

| Provider | Description | Endpoint Configuration | Typical Use Case |
|----------|-------------|----------------------|------------------|
| **AWS S3** (`s3`) | Amazon Simple Storage Service, the original S3 implementation | Leave the endpoint field blank -- the S3 client uses AWS defaults based on the region | Production workloads, CloudFront CDN integration, wide ecosystem support |
| **Backblaze B2** (`b2`) | Backblaze's S3-compatible API, significantly cheaper than AWS S3 for storage | Set endpoint to `s3.{region}.backblazeb2.com` (e.g., `s3.us-west-004.backblazeb2.com`) | Cost-effective storage for large media files, video archives |
| **Garage** (`garage`) | Self-hosted S3-compatible storage ([Garage project](https://git.deuxfleurs.fr/Deuxfleurs/garage)) | Set endpoint to your Garage server's address | Self-hosted environments, data sovereignty requirements, air-gapped deployments |

---

## Concepts

### Stubs

A **stub** is a short, unique string assigned to each storage point. It acts as a URL path prefix in CMS templates, creating a simple and memorable way to reference assets from a specific storage backend.

**How stubs work in practice:**
- You create a storage point with stub `img` that points to your image bucket on S3
- In your CMS content, you write image paths as `/img/hero-banner.jpg`
- The CMS template renderer sees the `/img/` prefix, looks up the storage point with stub `img`, and expands the path to the full public URL: `https://cdn.example.com/media/hero-banner.jpg`

**Stub naming conventions:**
- `img` -- Images (photos, illustrations, icons)
- `vid` -- Video files
- `dl` -- Downloadable files (PDFs, archives)
- `assets` -- General static assets (CSS, fonts, etc.)
- `docs` -- Documentation attachments

**Stub validation rules:**
- Length: 1 to 32 characters
- Characters: Lowercase alphanumeric and hyphens only
- Must start and end with an alphanumeric character (not a hyphen)
- Regex pattern: `^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$`
- Must be unique across all storage points in the SRE

The stub appears at the root of the CMS base URL, making it easy to grep for references in templates. If you search for `/img/` in your CMS content files, you find every reference to the image storage point.

### URL Expansion

URL expansion is the process by which the CMS template renderer converts a stub-prefixed path into a full public URL. Understanding this process helps you configure storage points correctly.

**Expansion formula:**
```
Template path:  /{stub}/{filename}
Expanded URL:   {public_url}{path_prefix}{filename}

Concrete example:
  stub:        img
  public_url:  https://cdn.example.com/
  path_prefix: media/
  Template:    /img/photo.jpg
  Result:      https://cdn.example.com/media/photo.jpg
```

**Why public URL and endpoint are separate fields:**

The **endpoint** is the S3 API URL that would be used for authenticated bucket operations. For AWS S3, this is something like `s3.us-east-1.amazonaws.com`. Today Sentinel stores this as part of the bucket registration and uses it for configuration and future connectivity/object access work; it is not exposed to end users.

The **public URL** is the URL that end users' browsers use to fetch the content. This is often a CDN domain (like `https://d1234567890.cloudfront.net/`) or a custom domain (like `https://cdn.example.com/`). The public URL must be accessible from the internet (or your users' network) without authentication.

These are different URLs because:
- The S3 API endpoint may require authentication and is designed for programmatic access
- The public URL is optimized for fast, unauthenticated content delivery
- Using a CDN as the public URL provides edge caching and reduced latency
- You might change CDN providers without changing your S3 bucket

### Credential Storage

Storage point credentials (S3 access key and secret key) are stored in the Sentinel **vault** (encrypted with AES-256-GCM), not in the database or configuration files. This ensures that credentials are never exposed in database dumps, backups, or configuration file leaks.

The vault stores credentials using a naming convention:
- Access key: `st:{id}:ak` (where `{id}` is the storage point's UUID)
- Secret key: `st:{id}:sk`

When you create a storage point, both credentials are written to the vault atomically. When you delete a storage point, both credentials are removed. When you edit a storage point and leave the credential fields blank, the existing credentials are preserved.

---

## Dashboard User Guide

The Storage page is available at `http://localhost:9090/storage` in the Sentinel dashboard. It appears in the left sidebar between "Databases" and "Docker", identified by a `cloud_upload` icon.

The Backups page can use any storage point listed here as an optional upload target for:
- PostgreSQL `pg_dump` artifacts
- folder archives for non-repo artifacts and generated assets

### Page Layout

The page has three sections:

1. **Header bar** -- Contains the page title ("Storage Points"), a **Refresh** link that reloads data from the harness, and a green **Add Storage Point** button in the top-right corner.

2. **Info banner** -- A brief explanation of how stubs and URL expansion work. This banner is always visible at the top of the page and serves as a quick reference for the expansion formula.

3. **Storage points table** -- Lists all registered storage points in a table format. When no storage points have been created yet, an empty state message is displayed with a prompt to add the first one.

The table columns are:

| Column | Description |
|--------|-------------|
| **Name** | The storage point's human-readable label, shown alongside a `cloud_upload` icon |
| **Stub** | The URL prefix, displayed as a monospace code badge (e.g., `/img/`). This is what appears in CMS template paths. |
| **Provider** | Color-coded pill showing the provider type: orange for AWS S3, blue for Backblaze B2, purple for Garage |
| **Bucket** | The S3 bucket name. If a path prefix is configured, it appears in muted text after the bucket name (e.g., `my-bucket / media/`) |
| **Public URL** | The public base URL used for stub expansion. Long URLs are truncated with the full URL visible on hover. |
| **Actions** | Three icon buttons: Test connectivity (bolt icon), Edit (pencil icon), Delete (trash icon) |

### Adding a Storage Point

1. Click the green **Add Storage Point** button in the top-right corner of the page.

2. A modal dialog opens with configuration fields. At the top is a **Provider selector** with radio buttons:

   - **AWS S3** (selected by default) -- The endpoint field shows a hint: "Leave blank for default AWS S3". The region placeholder shows `us-east-1`.
   - **Backblaze B2** -- The endpoint field shows: "Backblaze S3-compatible endpoint" with placeholder `s3.us-west-004.backblazeb2.com`. The region placeholder shows `us-west-004`.
   - **Garage** -- The endpoint field shows: "Your Garage S3 endpoint (e.g. garage.example.com)". The region placeholder shows `garage`.

   Switching between providers updates the hints and placeholders to guide you toward the correct values for each provider.

3. Fill in the required fields:

   | Field | Required | Description | Example |
   |-------|----------|-------------|---------|
   | **Name** | Yes | A unique human-readable label for this storage point | `production-media` |
   | **Stub** | Yes | URL prefix for CMS expansion, shown between `/` markers | `img` |
   | **Bucket** | Yes | The S3 bucket name | `my-media-bucket` |
   | **Public URL** | Yes | Public base URL used for stub expansion | `https://cdn.example.com/` |

4. Fill in the optional fields as needed:

   | Field | Required | Description | Example |
   |-------|----------|-------------|---------|
   | **Endpoint** | No (required for B2 and Garage) | Custom S3 API endpoint. Leave blank for AWS S3. | `s3.us-west-004.backblazeb2.com` |
   | **Region** | No | AWS region or provider-specific region identifier | `us-east-1` |
   | **Path Prefix** | No | Path prefix within the bucket. Files are stored under this prefix. | `media/` |

5. Fill in the credential fields (required when creating):

   | Field | Description |
   |-------|-------------|
   | **Access Key** | S3 access key ID. Format varies by provider: `AKIA...` for AWS, `004...` for B2, `GK...` for Garage |
   | **Secret Key** | S3 secret access key (displayed as a masked/password input) |

   Credentials are stored in the encrypted vault, never in the database.

6. Click **Add Storage Point** to save. On success, the page reloads and the new entry appears in the table. On failure, a toast notification displays the error message.

### Editing a Storage Point

1. Click the **pencil icon** in the Actions column of the storage point you want to modify.

2. The same modal opens, pre-filled with all current values. The title changes to "Edit Storage Point" and the submit button reads "Update Storage Point".

3. Modify any fields as needed. You can change the name, stub, provider, bucket, public URL, endpoint, region, or path prefix.

4. **Credentials are optional when editing.** The credential fields appear empty and the "required" asterisks are hidden. A hint reads: "Leave blank to keep existing credentials." Only fill in the credential fields if you want to rotate (replace) the keys. If you leave them blank, the existing credentials in the vault remain unchanged.

5. Click **Update Storage Point** to save.

### Testing Connectivity

1. Click the **bolt icon** in the Actions column of the storage point you want to test.
2. A toast notification appears: "Testing connection..."
3. **On success:** A green toast shows "Connection test passed" with details about the provider, endpoint, and bucket.
4. **On failure:** A red toast shows the error message (e.g., "access key not found in vault").

**Note about the current test scope:** The connectivity test currently verifies that credentials exist in the vault and that the storage point configuration is valid. It does not perform an actual S3 `ListBucket` call to verify that the credentials work with the remote provider. Full S3 connectivity testing (actual bucket access verification) is planned for a future release when the S3 SDK is added to the harness.

### Deleting a Storage Point

1. Click the **trash icon** in the Actions column.
2. A browser confirmation dialog appears: `Delete storage point "{name}"? This will also remove vault credentials.`
3. Click **OK** to confirm. The storage point record is deleted from the database, and both vault credentials (`st:{id}:ak` and `st:{id}:sk`) are removed.
4. The page reloads automatically.

**Warning:** Deletion is permanent. If you have CMS content referencing this storage point's stub, those references will stop expanding correctly. Make sure to update any content that references the stub before deleting the storage point.

### Closing the Modal

The Add/Edit modal can be closed by:
- Clicking the **X** button in the top-right corner of the modal
- Clicking the **Cancel** button at the bottom
- Clicking the dark backdrop area outside the modal

Any unsaved changes are discarded when the modal is closed.

### Tips for Effective Use

- **Choose stubs carefully.** Stubs appear in every CMS template URL that references the storage point. Pick short, memorable names that are unlikely to change. Common conventions: `img` for images, `vid` for video, `dl` for downloads, `assets` for general static files.

- **Include trailing slashes.** When entering the public URL, include a trailing slash (e.g., `https://cdn.example.com/`). Similarly, if using a path prefix, include a trailing slash (e.g., `media/`). The expansion concatenates `public_url + path_prefix + filename` directly, so missing slashes produce malformed URLs like `https://cdn.example.commedia/photo.jpg`.

- **Rotate credentials safely.** To rotate credentials, edit the storage point and fill in both the new access key and secret key. The old credentials are overwritten in the vault. Make sure the new credentials are active on the provider side before rotating in Sentinel.

- **Use multiple storage points.** Register as many storage points as needed, each with a unique name and stub. For example, one for images (`img`), another for videos (`vid`), and a third for documents (`docs`). This allows different content types to be stored on different providers or in different buckets.

---

## CLI Import / Export

Storage-point registrations can be exported to a local JSON bundle and later re-imported. The bundle includes bucket metadata and vault-backed credentials so you can recover local development projects after state resets without re-entering provider settings by hand.

### Export All Storage Points

```bash
sentinel -p ./my-project storage export ./my-project/storage-points.local.json
```

The output file is written with `0600` permissions because it contains live credentials.

### Export One Storage Point

```bash
sentinel -p ./my-project storage export ./my-project/storage-points.local.json --stub img
```

You can also filter by UUID with `--id`.

### Import a Bundle

```bash
sentinel --no-input -p ./my-project storage import ./my-project/storage-points.local.json
```

Import preserves storage point IDs when possible. If a point with the same stub or name already exists under a different ID, Sentinel updates that existing record instead of creating a duplicate.

### Local Development Convention

The helper startup scripts `start-dev.sh` and `start-dev.ps1` automatically import `storage-points.local.json` from the project root before starting the harness. New projects created with `sentinel sre init` ignore this file by default so it stays out of git.

---

## Lua API

Storage point metadata is available to Lua flows through the `sn.st.*` namespace.

### Available Functions

| Function | Description |
|----------|-------------|
| `sn.st.list()` | Returns all registered storage points |
| `sn.st.get(id)` | Returns a single storage point by UUID |
| `sn.st.get_by_stub(stub)` | Returns a storage point by stub |
| `sn.st.resolve(stub, path)` | Resolves a stub plus object path to a full public URL |

### Example Usage

```lua
local points, err = sn.st.list()
if not err then
  for _, point in ipairs(points) do
    print(point.name, point.bucket)
  end
end

local img, err = sn.st.get_by_stub("img")
if not err then
  print(img.public_url)
end

local url, err = sn.st.resolve("img", "hero-banner.jpg")
if not err then
  print(url)
end
```

### Important Scope Note

The current Lua API is intentionally limited to storage point metadata lookup and URL resolution. It does not currently upload, download, list, or delete objects in the configured bucket.

The backup subsystem is the current harness-side exception: it can upload completed backup artifacts to a storage point after local artifact creation, but that path is server-owned rather than part of the Lua storage API.

---

## Provider Setup Guides

### AWS S3 Step-by-Step

1. **Create an S3 bucket:**
   - Sign in to the AWS Console
   - Navigate to S3 > Create Bucket
   - Choose a bucket name (e.g., `mysite-media`) and region (e.g., `us-east-1`)
   - For public content, uncheck "Block all public access" and acknowledge the warning
   - Create the bucket

2. **Configure bucket policy for public read access** (if serving public content):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": "*",
       "Action": "s3:GetObject",
       "Resource": "arn:aws:s3:::mysite-media/*"
     }]
   }
   ```

3. **Create an IAM user for programmatic access:**
   - Navigate to IAM > Users > Add User
   - Attach a policy that allows `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on your bucket
   - Create access keys and save the Access Key ID and Secret Access Key

4. **Optional: Set up CloudFront CDN:**
   - Create a CloudFront distribution pointing to your S3 bucket
   - Use the CloudFront URL as the public_url (e.g., `https://d1234567890.cloudfront.net/`)

5. **Register in Sentinel:**
   ```json
   {
     "name": "aws-media",
     "stub": "img",
     "provider": "s3",
     "endpoint": "",
     "region": "us-east-1",
     "bucket": "mysite-media",
     "path_prefix": "",
     "public_url": "https://mysite-media.s3.amazonaws.com/",
     "access_key": "AKIA...",
     "secret_key": "wJal..."
   }
   ```

   With CloudFront:
   ```json
   {
     "public_url": "https://d1234567890.cloudfront.net/"
   }
   ```

### Backblaze B2 Step-by-Step

1. **Create a B2 bucket:**
   - Sign in to the Backblaze Dashboard
   - Navigate to B2 Cloud Storage > Buckets > Create a Bucket
   - Choose a bucket name and set it to "Public" if serving public content
   - Note the bucket's region (e.g., `us-west-004`)

2. **Create application keys:**
   - Navigate to Application Keys > Add a New Application Key
   - Restrict the key to your specific bucket for security
   - Save the Key ID (access key) and Application Key (secret key)

3. **Determine the S3-compatible endpoint:**
   - The endpoint format is `s3.{region}.backblazeb2.com`
   - For region `us-west-004`, the endpoint is `s3.us-west-004.backblazeb2.com`

4. **Determine the public URL:**
   - B2 public bucket URL format: `https://f{cluster}.backblazeb2.com/file/{bucket-name}/`
   - Alternatively, use Cloudflare or a CDN in front of B2

5. **Register in Sentinel:**
   ```json
   {
     "name": "b2-media",
     "stub": "vid",
     "provider": "b2",
     "endpoint": "s3.us-west-004.backblazeb2.com",
     "region": "us-west-004",
     "bucket": "my-b2-bucket",
     "path_prefix": "video/",
     "public_url": "https://f004.backblazeb2.com/file/my-b2-bucket/",
     "access_key": "004...",
     "secret_key": "K004..."
   }
   ```

### Garage (Self-Hosted) Step-by-Step

1. **Install and configure Garage:**
   - Follow the Garage documentation at [garagehq.deuxfleurs.fr](https://garagehq.deuxfleurs.fr)
   - Set up a Garage cluster (minimum 1 node for development, 3 for production)
   - Configure the S3 API endpoint (typically port 3900)

2. **Create a bucket:**
   ```bash
   garage bucket create my-garage-bucket
   ```

3. **Create API keys:**
   ```bash
   garage key create my-sentinel-key
   garage bucket allow --read --write my-garage-bucket --key my-sentinel-key
   ```

4. **Determine the public URL:**
   - If Garage is behind a reverse proxy with a public domain: `https://garage.example.com/my-garage-bucket/`
   - If using Garage's web endpoint: configure the web endpoint in Garage and use that URL

5. **Register in Sentinel:**
   ```json
   {
     "name": "garage-assets",
     "stub": "assets",
     "provider": "garage",
     "endpoint": "garage.example.com",
     "region": "garage",
     "bucket": "my-garage-bucket",
     "path_prefix": "",
     "public_url": "https://garage.example.com/my-garage-bucket/",
     "access_key": "GK...",
     "secret_key": "..."
   }
   ```

---

## API Reference

All storage point endpoints use the `/st` brevity prefix. All responses are HTTP 200 with errors in the body as `{ok: false, err: "CODE", msg: "..."}`.

### List Storage Points

```
GET /st
```

Returns all registered storage points. Credentials are never included in the response.

**Response:**
```json
{
  "ok": true,
  "points": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "production-media",
      "stub": "img",
      "provider": "s3",
      "endpoint": "",
      "region": "us-east-1",
      "bucket": "my-media-bucket",
      "path_prefix": "media/",
      "public_url": "https://cdn.example.com/",
      "created_at": "2026-02-28T10:00:00Z",
      "updated_at": "2026-02-28T10:00:00Z"
    }
  ]
}
```

### Get Storage Point

```
GET /st/{id}
```

Returns a single storage point by its UUID.

**Response:**
```json
{
  "ok": true,
  "point": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "production-media",
    "stub": "img",
    "provider": "s3",
    "endpoint": "",
    "region": "us-east-1",
    "bucket": "my-media-bucket",
    "path_prefix": "media/",
    "public_url": "https://cdn.example.com/",
    "created_at": "2026-02-28T10:00:00Z",
    "updated_at": "2026-02-28T10:00:00Z"
  }
}
```

### Create Storage Point

```
POST /st
```

Creates a new storage point. Credentials are required on creation and are stored in the vault.

**Request Body:**
```json
{
  "name": "production-media",
  "stub": "img",
  "provider": "s3",
  "endpoint": "",
  "region": "us-east-1",
  "bucket": "my-media-bucket",
  "path_prefix": "media/",
  "public_url": "https://cdn.example.com/",
  "access_key": "AKIAIOSFODNN7EXAMPLE",
  "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique human-readable label |
| `stub` | Yes | URL stub for CMS expansion (must be unique, follow stub validation rules) |
| `provider` | Yes | `s3`, `b2`, or `garage` |
| `endpoint` | No | Custom S3 endpoint URL. Leave blank for AWS S3. Required for B2 and Garage. |
| `region` | No | AWS region or equivalent. Used by the S3 client for request signing. |
| `bucket` | Yes | S3 bucket name |
| `path_prefix` | No | Optional prefix within the bucket. Include trailing slash if used. |
| `public_url` | Yes | Public base URL for stub expansion. Include trailing slash. |
| `access_key` | Yes | S3 access key ID (stored in vault, not in database) |
| `secret_key` | Yes | S3 secret access key (stored in vault, not in database) |

**Response:**
```json
{
  "ok": true,
  "point": { ... }
}
```

**Possible errors:**
- `REQUEST.MISSING` -- A required field is missing
- `REQUEST.INVALID` -- Invalid provider value or stub format
- `SYSTEM.ERROR` -- Database or vault failure (creation is rolled back on failure)

### Update Storage Point

```
PUT /st/{id}
```

Updates an existing storage point. Same body format as create, except `access_key` and `secret_key` are optional. If credential fields are empty or omitted, existing vault credentials are preserved.

**Response:**
```json
{
  "ok": true,
  "point": { ... }
}
```

### Delete Storage Point

```
DELETE /st/{id}
```

Deletes a storage point and removes its vault credentials. Credential deletion is best-effort (if the vault delete fails, the storage point record is still deleted).

**Response:**
```json
{
  "ok": true
}
```

### Test Connection

```
POST /st/{id}/test
```

Tests a storage point by verifying that credentials exist in the vault and returning the configured provider metadata.

**Success response:**
```json
{
  "ok": true,
  "msg": "credentials found, S3 connectivity test not yet implemented",
  "provider": "s3",
  "endpoint": "",
  "bucket": "my-media-bucket",
  "region": "us-east-1"
}
```

**Failure response:**
```json
{
  "ok": false,
  "msg": "access key not found in vault"
}
```

---

## Migration Patterns

### Migrating Between Providers

To migrate from one storage provider to another (e.g., from AWS S3 to Backblaze B2):

1. **Create the new storage point** with a temporary stub (e.g., `img-new`)
2. **Copy all files** from the old bucket to the new bucket using a tool like `rclone`, `aws s3 sync`, or the provider's migration tool
3. **Test the new storage point** by verifying files are accessible at the new public URL
4. **Update the stubs:** Delete the old storage point, then edit the new one to use the original stub (`img`)
5. **Verify CMS content** renders correctly with the new storage point

### Migrating from Local Files to Storage Points

If you currently have binary files committed in your SRE git repository:

1. **Create a storage point** for each type of content (images, documents, etc.)
2. **Upload files** to the appropriate S3 buckets
3. **Update CMS content** to use stub-prefixed paths instead of relative file paths
4. **Remove the binary files** from the git repository: `git rm --cached path/to/files/`
5. **Add the paths to .gitignore** to prevent re-adding

---

## Data Model

Storage point metadata is stored in the SRE state database in the `storage_points` table (created by migration v6). Credentials are stored separately in the vault.

| Field | Type | Notes |
|-------|------|-------|
| `id` | TEXT PK | UUID, auto-generated on creation |
| `name` | TEXT UNIQUE | User-chosen label, must be unique |
| `stub` | TEXT UNIQUE | URL stub for CMS expansion, must be unique |
| `provider` | TEXT | One of: `s3`, `b2`, `garage` |
| `endpoint` | TEXT | S3 endpoint URL (empty for AWS defaults) |
| `region` | TEXT | Region identifier |
| `bucket` | TEXT | Bucket name |
| `path_prefix` | TEXT | Optional path prefix within bucket |
| `public_url` | TEXT | Public base URL for stub expansion |
| `created_at` | DATETIME | Auto-set on creation |
| `updated_at` | DATETIME | Auto-updated on modification |

---

## Limitations

- **No file upload/browse** -- Storage points are metadata registrations only. File management (upload, list, delete objects in the bucket) is not yet available through the dashboard or API. You must use provider-specific tools (AWS CLI, B2 CLI, Garage CLI) or third-party S3 clients to manage files.

- **Connectivity test is partial** -- The test endpoint verifies that vault credentials exist but does not perform an actual S3 `ListBucket` call. Full S3 connectivity testing requires adding an S3 SDK dependency, which is planned for a future release.

- **Lua API is metadata-only** -- Storage points are exposed to Lua via `sn.st.*`, but only for listing points, looking them up by ID/stub, and resolving public URLs. Object I/O is not implemented yet.

- **Single-region only** -- Each storage point maps to one bucket in one region. Cross-region replication must be configured at the provider level (e.g., AWS S3 Cross-Region Replication, B2 replication).

---

## Architecture Notes

Understanding the architecture helps with troubleshooting and customization:

- **Storage metadata** lives in the SRE state database (`storage_points` table), not in any dashboard-specific database. This means storage points are part of the SRE state and are backed up with the state database.

- **Credentials** live in the vault (AES-256-GCM encrypted), completely separate from the metadata. This separation ensures that a database dump or backup never contains credentials.

- **The dashboard proxies** all storage requests through the harness API. The dashboard never accesses the vault or state database directly. Dashboard requests go to `/api/dashboard/storage/*`, and the dashboard BFF layer proxies those operations to the harness's `/st/*` endpoints.

- **Route prefix** follows the brevity regime: `/st` for the harness API, `/api/dashboard/storage` for the dashboard BFF path.
