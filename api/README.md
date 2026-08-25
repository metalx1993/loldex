# loldex API

A thin, read-only HTTP API over the loldex index, running on a Cloudflare
Worker. It fetches the same `data.json` the static site serves, caches it, and
returns filtered JSON. No database, no server.

## Endpoints

| Method + path | Returns |
|---|---|
| `GET /api/stats` | counts by platform, privilege, capability |
| `GET /api/search?q=&os=&platform=&priv=&cap=&phase=&type=&limit=&offset=` | matching entries |
| `GET /api/entries?limit=&offset=` | all entries, paginated |
| `GET /api/entry/<id>` | one entry by id (id may contain slashes) |

`os` accepts shorthands: `win` → windows, `ad` → active-directory.
`limit` caps at 200. All responses send `Access-Control-Allow-Origin: *`.

### Examples

```
/api/search?q=tar&os=linux&priv=sudo
/api/search?cap=file-download            # cross-platform pivot
/api/search?platform=active-directory
/api/entry/gtfobins/tar/shell/sudo
/api/stats
```

## Deploy

Two ways.

### A. Dashboard (no local tools)

1. In the Cloudflare dashboard: Workers & Pages → Create → **Worker** (this
   time you DO want a Worker, not Pages).
2. Name it `loldex-api`, deploy the starter, then open **Edit code**.
3. Paste the contents of `worker.js`, save, deploy.
4. In the Worker's Settings → Domains & Routes, add a custom domain
   `api.loldex.sh` (or a route). HTTPS is automatic.

### B. Wrangler (CLI)

```bash
npm install -g wrangler
wrangler login
cd api
wrangler deploy
```

Then attach the route in `wrangler.toml` (uncomment the `routes` block) and
`wrangler deploy` again, or add `api.loldex.sh` from the dashboard.

## Notes

- The Worker reads `DATA_URL` (default `https://loldex.sh/data.json`). If your
  site lives elsewhere, edit that constant.
- Data is cached in memory for 5 minutes, so a fresh site deploy shows up in the
  API within a few minutes automatically.
- Read-only by design. There is no write path.
