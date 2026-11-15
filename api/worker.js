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
 * Historical compatibility implementation; deployment is not implied.
 * Deploy: see api/README.md
 */

const DATA_URL = "https://loldex.sh/data.json";
const TTL_MS = 5 * 60 * 1000; // re-fetch data at most every 5 min
const MAX_LIMIT = 200;
const MAX_OFFSET = 100000;
const MAX_URL_BYTES = 8192;
const MAX_INDEX_BYTES = 16 * 1024 * 1024;
const LOAD_TIMEOUT_MS = 10000;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

let CACHE = null;
let CACHE_AT = 0;

let IN_FLIGHT = null;

async function fetchEntries() {
  const controller = new AbortController();
  let reader;
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      if (reader) reader.cancel().catch(() => {});
      reject(new Error("index deadline"));
    }, LOAD_TIMEOUT_MS);
  });
  const read = async () => {
    let destination = DATA_URL;
    let res;
    for (let redirects = 0; ; redirects++) {
      res = await fetch(destination, {
        cf: { cacheTtl: 300 }, signal: controller.signal, redirect: "manual",
      });
      if (controller.signal.aborted) {
        if (res.body) res.body.cancel().catch(() => {});
        throw new Error("index deadline");
      }
      if (![301, 302, 303, 307, 308].includes(res.status)) break;
      if (res.body) res.body.cancel().catch(() => {});
      // A2 redirects the stable catalogue once to its immutable release. Never
      // let a redirect expand the fixed upstream origin or endpoint allowlist.
      const location = res.headers.get("Location");
      if (redirects !== 0 || !location) throw new Error("index redirect");
      const next = new URL(location, destination);
      if (next.origin !== new URL(DATA_URL).origin || next.username || next.password ||
          next.search || next.hash || !/^\/releases\/r-[0-9a-f]{64}\/data\.json$/.test(next.pathname)) {
        throw new Error("index redirect");
      }
      destination = next.href;
    }
    if (!res.ok || !res.body) throw new Error("index response");
    const length = res.headers.get("Content-Length");
    if (length !== null && (!/^[0-9]+$/.test(length) || Number(length) > MAX_INDEX_BYTES)) {
      await res.body.cancel();
      throw new Error("index size");
    }
    reader = res.body.getReader();
    const chunks = [];
    let size = 0;
    for (;;) {
      const part = await reader.read();
      if (controller.signal.aborted) throw new Error("index deadline");
      if (part.done) break;
      size += part.value.byteLength;
      if (size > MAX_INDEX_BYTES) throw new Error("index size");
      chunks.push(part.value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const data = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!data || !Array.isArray(data.entries) || data.entries.length > 100000) {
      throw new Error("index shape");
    }
    for (const entry of data.entries) {
      if (!entry || typeof entry !== "object" || Array.isArray(entry) ||
          typeof entry.id !== "string" || typeof entry.name !== "string" ||
          typeof entry.platform !== "string" || typeof entry.privilege_required !== "string" ||
          ["aliases", "capabilities", "phases"].some((key) => entry[key] !== undefined &&
            (!Array.isArray(entry[key]) || entry[key].some((item) => typeof item !== "string")))) {
        throw new Error("index shape");
      }
    }
    return data.entries;
  };
  try {
    return await Promise.race([read(), deadline]);
  } finally {
    clearTimeout(timer);
    controller.abort();
    if (reader) reader.cancel().catch(() => {});
  }
}

async function loadEntries() {
  if (CACHE && Date.now() - CACHE_AT < TTL_MS) return CACHE;
  if (!IN_FLIGHT) {
    IN_FLIGHT = fetchEntries().then((entries) => {
      CACHE = entries;
      CACHE_AT = Date.now();
      return entries;
    }).finally(() => { IN_FLIGHT = null; });
  }
  return IN_FLIGHT;
}

function parameters(url) {
  const caps = { q: 256, platform: 64, os: 64, priv: 64, cap: 64, phase: 64, type: 64, limit: 3, offset: 6 };
  const result = Object.create(null);
  for (const [key, value] of url.searchParams) {
    if (!Object.hasOwn(caps, key) || Object.hasOwn(result, key) || value.length > caps[key] ||
        /[\x00-\x1f\x7f]/.test(value)) throw new Error("query");
    result[key] = value;
  }
  if (result.platform !== undefined && result.os !== undefined) throw new Error("query");
  return result;
}

function boundedInt(value, fallback, max) {
  if (value === undefined) return fallback;
  if (!/^(0|[1-9][0-9]*)$/.test(value) || Number(value) > max) throw new Error("query");
  return Number(value);
}

function normPlatform(v) {
  if (!v) return v;
  const m = { win: "windows", ad: "active-directory" };
  return Object.hasOwn(m, v) ? m[v] : v;
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
    headers: { "Content-Type": "application/json; charset=utf-8", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store", ...CORS },
  });
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (request.method !== "GET") return json({ error: "method not allowed" }, 405);

    let url, path, params, limit, offset, id;
    try {
      if (request.url.length > MAX_URL_BYTES) throw new Error("URL size");
      url = new URL(request.url);
      // Decode before parsing: URLSearchParams otherwise silently repairs bad escapes.
      decodeURIComponent(url.pathname);
      decodeURIComponent(url.search.replace(/\+/g, " "));
      path = url.pathname;
      while (path.endsWith("/")) path = path.slice(0, -1);
      params = parameters(url);
      limit = boundedInt(params.limit, 50, MAX_LIMIT);
      offset = boundedInt(params.offset, 0, MAX_OFFSET);
      if (path.startsWith("/api/entry/")) {
        id = decodeURIComponent(path.slice("/api/entry/".length));
        if (!id || id.length > 512 || /[\x00-\x1f\x7f]/.test(id)) throw new Error("id");
      }
    } catch {
      return json({ error: "invalid request" }, 400);
    }
    if (!["", "/api", "/api/stats", "/api/search", "/api/entries"].includes(path) && id === undefined) {
      return json({ error: "not found" }, 404);
    }
    let entries;
    try {
      entries = await loadEntries();
    } catch (err) {
      return json({ error: "index unavailable" }, 502);
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
      const byPlatform = Object.create(null), byCap = Object.create(null), byPriv = Object.create(null);
      for (const e of entries) {
        byPlatform[e.platform] = (byPlatform[e.platform] || 0) + 1;
        byPriv[e.privilege_required] = (byPriv[e.privilege_required] || 0) + 1;
        for (const c of e.capabilities || []) byCap[c] = (byCap[c] || 0) + 1;
      }
      return json({ count: entries.length, byPlatform, byPriv, byCapability: byCap });
    }

    if (path === "/api/search" || path === "/api/entries") {
      const p = {
        q: params.q || "",
        platform: normPlatform(params.platform || params.os),
        priv: params.priv, cap: params.cap, phase: params.phase, type: params.type,
      };
      const hits = entries.filter((e) => matches(e, p));
      return json({
        count: hits.length,
        limit,
        offset,
        results: hits.slice(offset, offset + limit),
      });
    }

    if (path.startsWith("/api/entry/")) {
      const e = entries.find((x) => x.id === id);
      return e ? json(e) : json({ error: "not found", id }, 404);
    }

    return json({ error: "not found" }, 404);
  },
};
