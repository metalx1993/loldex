/**
 * loldex API — Cloudflare Worker
 *
 * A thin, read-only HTTP API over the loldex index. It fetches the same
 * data.json the static site uses, caches it in memory, and serves filtered
 * JSON so machine consumers (SIEM/SOAR/detection pipelines, other tools) can
 * query the index programmatically.
 *
 * Endpoints:
 *   GET /api/stats
 *   GET /api/search?q=&os=&platform=&priv=&cap=&phase=&type=&limit=&offset=
 *   GET /api/entries?limit=&offset=
 *   GET /api/entry/<id...>          (id may contain slashes)
 *
 * Deploy: see api/README.md
 */

const DATA_URL = "https://loldex.sh/data.json";
const TTL_MS = 5 * 60 * 1000; // re-fetch data at most every 5 min
const MAX_LIMIT = 200;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

let CACHE = null;
let CACHE_AT = 0;

async function loadEntries() {
  const now = Date.now();
  if (CACHE && now - CACHE_AT < TTL_MS) return CACHE;
  const res = await fetch(DATA_URL, { cf: { cacheTtl: 300 } });
  if (!res.ok) throw new Error(`data fetch ${res.status}`);
  const json = await res.json();
  CACHE = json.entries || [];
  CACHE_AT = now;
  return CACHE;
}

function normPlatform(v) {
  if (!v) return v;
  const m = { win: "windows", ad: "active-directory" };
  return m[v] || v;
}

function matches(e, p) {
  if (p.q) {
    const hay = `${e.name} ${e.id} ${(e.aliases || []).join(" ")}`.toLowerCase();
    if (!hay.includes(p.q.toLowerCase())) return false;
  }
  if (p.platform && e.platform !== p.platform) return false;
  if (p.priv && e.privilege_required !== p.priv) return false;
  if (p.cap && !(e.capabilities || []).includes(p.cap)) return false;
  if (p.phase && !(e.phases || []).includes(p.phase)) return false;
  if (p.type && e.type !== p.type) return false;
  return true;
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS },
  });
}

function clampInt(v, def, max) {
  const n = parseInt(v, 10);
  if (Number.isNaN(n) || n < 0) return def;
  return max ? Math.min(n, max) : n;
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (request.method !== "GET") return json({ error: "method not allowed" }, 405);

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "");
    let entries;
    try {
      entries = await loadEntries();
    } catch (err) {
      return json({ error: "index unavailable", detail: String(err) }, 502);
    }

    if (path === "" || path === "/" || path === "/api") {
      return json({
        name: "loldex API",
        version: 0,
        endpoints: ["/api/stats", "/api/search", "/api/entries", "/api/entry/<id>"],
        count: entries.length,
      });
    }

    if (path === "/api/stats") {
      const byPlatform = {}, byCap = {}, byPriv = {};
      for (const e of entries) {
        byPlatform[e.platform] = (byPlatform[e.platform] || 0) + 1;
        byPriv[e.privilege_required] = (byPriv[e.privilege_required] || 0) + 1;
        for (const c of e.capabilities || []) byCap[c] = (byCap[c] || 0) + 1;
      }
      return json({ count: entries.length, byPlatform, byPriv, byCapability: byCap });
    }

    if (path === "/api/search" || path === "/api/entries") {
      const p = {
        q: url.searchParams.get("q") || "",
        platform: normPlatform(url.searchParams.get("platform") || url.searchParams.get("os")),
        priv: url.searchParams.get("priv"),
        cap: url.searchParams.get("cap"),
        phase: url.searchParams.get("phase"),
        type: url.searchParams.get("type"),
      };
      const limit = clampInt(url.searchParams.get("limit"), 50, MAX_LIMIT);
      const offset = clampInt(url.searchParams.get("offset"), 0);
      const hits = entries.filter((e) => matches(e, p));
      return json({
        count: hits.length,
        limit,
        offset,
        results: hits.slice(offset, offset + limit),
      });
    }

    if (path.startsWith("/api/entry/")) {
      const id = decodeURIComponent(path.slice("/api/entry/".length));
      const e = entries.find((x) => x.id === id);
      return e ? json(e) : json({ error: "not found", id }, 404);
    }

    return json({ error: "not found", path }, 404);
  },
};
