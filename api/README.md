# Historical Worker API

This directory retains an optional, read-only Cloudflare Worker implementation.
Its presence and offline tests do not establish that a Worker is deployed or
active. LOLDEX's implemented public contract is [API v1](openapi-v1.json), served
by the site's PHP API; see [the v1 design](../docs/phase7-design.md).

The historical Worker reads the public catalogue and returns filtered JSON.
It has no write path, database, or authentication credentials.

## Historical endpoints

| Method + path | Returns |
|---|---|
| `GET /api/stats` | counts by platform, privilege, capability |
| `GET /api/search?q=&os=&platform=&priv=&cap=&phase=&type=&limit=&offset=` | matching entries |
| `GET /api/entries?limit=&offset=` | all entries, paginated |
| `GET /api/entry/<id>` | one entry by id (id may contain slashes) |

`os` accepts `win` → `windows` and `ad` → `active-directory`. Supply either
`platform` or `os`. Parameters must be unique scalars; unknown parameters,
malformed encodings, control characters and noncanonical integers fail with 400.
`q` accepts up to 256 UTF-16 code units; other filters accept up to 64. `limit`
ranges from 0 to 200 (default 50), and `offset` from 0 to 100000 (default 0).
Entry identifiers accept up to 512 UTF-16 code units, and request URLs up to 8192.

JSON responses send `Access-Control-Allow-Origin: *`, `X-Content-Type-Options:
nosniff` and `Cache-Control: no-store`. The catalogue cache is internal to the
Worker and expires after five minutes. Concurrent cache misses share one
upstream request; failures clear the in-flight request and return a generic 502.

Catalogue acquisition has a ten-second deadline covering fetch and body reading,
a 16 MiB streamed body limit and structural validation. The fixed upstream is
`https://loldex.sh/data.json`. A single A2 redirect is accepted only to
`https://loldex.sh/releases/r-<64 lowercase hex digits>/data.json`, without URL
credentials, a query or a fragment. Other destinations and redirect chains are
rejected. These bounds do not constitute a deployment or a hosting-level abuse
control.

## Offline verification

From the repository root, run:

```bash
node tests/test_worker_security.cjs
```

The tests mock upstream requests, deadlines, redirect responses and concurrent
loads. They also check the committed catalogue. They require no Cloudflare
account and never publish the Worker.

## Gate before any future deployment

The historical Worker is outside the current SiteGround publication path.
`wrangler.toml` retains its explicit compatibility date and commented routes;
this hardening does not activate them.

There is deliberately no floating global install, unversioned `npx` command or
dashboard paste-and-deploy recipe here. A future Worker activation must first
provide all of the following in a separately reviewed change:

1. Confirm whether this historical interface is still required alongside API
   v1, and document the intended hostname, routes and public contract.
2. Select an exact Wrangler version from the official npm registry, verify its
   supported Node runtime, and commit an API-local `package.json` with
   `"private": true` plus a complete `package-lock.json` with registry URLs and
   package integrity hashes. Review the resulting dependency graph. No
   reproducible Wrangler toolchain is committed at present.
3. Install that reviewed toolchain with `npm ci` and use only its local Wrangler
   executable. Do not substitute a global installation or a floating download.
4. Re-run offline regressions and validate the Worker in an isolated Cloudflare
   staging environment, including the real A2 redirect, deadline/body limits,
   CORS and error responses. Review the compatibility date and required platform
   abuse controls for that environment.
5. Obtain authorization for that specific production hostname and activation,
   then publish the reviewed revision and verify the live behavior.

Until that gate is completed, no Worker deployment is part of the LOLDEX upload
or cronjob procedure. SiteGround continues to use the PHP API and its documented
publication process.
