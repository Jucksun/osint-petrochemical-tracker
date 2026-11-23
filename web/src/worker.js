// Cloudflare Worker: /api/chat (AI analyst), /api/export.csv, /api/health. Everything else is static.
import { runAgent } from "./agent.js";
import { loadData } from "./data.js";
import { facilitiesToCsv, filterFacilities } from "./tools.js";

const json = (obj, status = 200, extra = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra } });

// Soft per-isolate limiter. For real protection also add a Cloudflare rate-limiting rule on /api/chat (see DEPLOY.md).
const hits = new Map();
export function limited(ip, now = Date.now(), max = 15, windowMs = 60_000) {
  const arr = (hits.get(ip) || []).filter((t) => now - t < windowMs);
  arr.push(now);
  hits.set(ip, arr);
  if (hits.size > 5000) hits.clear();
  return arr.length > max;
}

function sameOrigin(req, url) {
  const o = req.headers.get("origin");
  if (!o) return true;
  try { return new URL(o).host === url.host; } catch { return false; }
}

function cleanHistory(h) {
  if (!Array.isArray(h)) return [];
  return h.filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
    .slice(-6).map((m) => ({ role: m.role, content: m.content.slice(0, 1500) }));
}

async function chat(req, env, url) {
  if (!sameOrigin(req, url)) return json({ error: "Cross-origin requests are not allowed." }, 403);
  if (limited(req.headers.get("cf-connecting-ip") || "anon")) return json({ error: "Too many requests. Wait a minute and try again." }, 429);
  const raw = await req.text();
  if (raw.length > 12_000) return json({ error: "Request too large." }, 413);
  let body;
  try { body = JSON.parse(raw); } catch { return json({ error: "Invalid JSON." }, 400); }
  const message = typeof body.message === "string" ? body.message.trim().slice(0, 800) : "";
  if (!message) return json({ error: "Empty message." }, 400);
  try {
    const data = await loadData(env, req.url);
    return json(await runAgent(env, data, cleanHistory(body.history), message));
  } catch (e) {
    console.error("chat failed", e?.message);
    return json({ error: "The AI service is unavailable right now. The map and tables still work.", detail: String(e?.message || e).slice(0, 400) }, 502);
  }
}

async function csv(req, env, url) {
  const data = await loadData(env, req.url);
  const args = Object.fromEntries(url.searchParams);
  const list = filterFacilities(data, args);
  return new Response(facilitiesToCsv(list), { headers: {
    "content-type": "text/csv; charset=utf-8", "content-disposition": 'attachment; filename="dow-facilities.csv"',
    "x-rows": String(list.length), "cache-control": "no-store" } });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    try {
      if (url.pathname === "/api/chat") return req.method === "POST" ? await chat(req, env, url) : json({ error: "Use POST." }, 405, { allow: "POST" });
      if (url.pathname === "/api/export.csv") return await csv(req, env, url);
      if (url.pathname === "/api/health") { const d = await loadData(env, req.url); return json({ ok: true, ...d.meta.counts, models: env.CHAT_MODELS }); }
      if (url.pathname.startsWith("/api/")) return json({ error: "Not found." }, 404);
    } catch (e) {
      return json({ error: "Server error.", detail: String(e?.message || e).slice(0, 300) }, 500);
    }
    return env.ASSETS.fetch(req);
  },
};
