// Tools the AI analyst can call. Each returns { text } for the model plus optional UI effects
// (ctx.actions) and citable sources (ctx.sources). All numbers come from the exported data, never
// from the model's memory.
import { search } from "./search.js";

export const money = (n) => "$" + Math.round(Number(n) || 0).toLocaleString("en-US");
const lc = (s) => String(s ?? "").toLowerCase();
const TIERS = { exact: "ex21_exact", ex21_exact: "ex21_exact", strong: "ex21_exact", prefix: "ex21_prefix",
  ex21_prefix: "ex21_prefix", token: "token_only", token_only: "token_only", weak: "token_only" };
const FILTER_KEYS = ["state", "city", "name", "tier", "status", "min_penalties", "needs_review", "sort_by"];

export function filterFacilities(data, a = {}) {
  const tier = a.tier ? TIERS[lc(a.tier)] : null;
  const review = a.needs_review == null || a.needs_review === "" ? null : a.needs_review === true || lc(a.needs_review) === "true";
  const sorters = { penalties: (x, y) => y.pen - x.pen, actions: (x, y) => y.actions - x.actions,
    inspections: (x, y) => y.insp - x.insp, name: (x, y) => lc(x.name).localeCompare(lc(y.name)) };
  const out = data.facilities.filter((f) =>
    (!a.state || lc(f.state) === lc(a.state)) &&
    (!a.city || lc(f.city).includes(lc(a.city))) &&
    (!a.name || lc(`${f.name} ${f.entity || ""}`).includes(lc(a.name))) &&
    (!tier || f.tier === tier) &&
    (!a.status || lc(f.status).includes(lc(a.status))) &&
    (a.min_penalties == null || a.min_penalties === "" || f.pen >= Number(a.min_penalties)) &&
    (review === null || f.review === review));
  return out.sort(sorters[a.sort_by] || sorters.penalties);
}

function tierLine(list) {
  const t = {};
  for (const f of list) {
    t[f.tier] ||= { n: 0, pen: 0 };
    t[f.tier].n++;
    t[f.tier].pen += f.pen;
  }
  return Object.entries(t).map(([k, v]) => `${k}: ${v.n} facilities, ${money(v.pen)}`).join("; ") || "none";
}

const line = (f) => `${f.id} | ${f.name} | ${[f.city, f.state].filter(Boolean).join(", ") || "n/a"} | ${f.tier}` +
  ` | penalties ${money(f.pen)} | formal actions ${f.actions} | ${f.status || "status n/a"}`;

export function addSource(ctx, s) {
  let found = ctx.sources.find((x) => x.chunk === s.chunk && x.url === s.url);
  if (!found) {
    found = { n: ctx.sources.length + 1, ...s };
    ctx.sources.push(found);
  }
  return found.n;
}

export function satelliteUrl(f, zoom = "area") {
  const d = zoom === "close" ? 0.006 : 0.05, w = 640, h = 420, dy = (d * h) / w;
  return "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?" +
    `bbox=${f.lon - d},${f.lat - dy},${f.lon + d},${f.lat + dy}&bboxSR=4326&imageSR=4326&size=${w},${h}&format=jpg&f=image`;
}

function resolveFacility(data, ref) {
  const r = String(ref ?? "").trim();
  if (data.byId.has(r)) return { f: data.byId.get(r) };
  const hits = data.facilities.filter((f) => lc(f.name).includes(lc(r))).sort((a, b) => b.pen - a.pen);
  if (hits.length === 1) return { f: hits[0] };
  if (hits.length > 1) return { many: hits.slice(0, 6) };
  return {};
}

export const TOOLS = {
  find_facilities: {
    doc: 'find_facilities {state?:"TX", city?, name?, tier?:ex21_exact|ex21_prefix|token_only, status?:"violation", min_penalties?:number, needs_review?:bool, sort_by?:penalties|actions|inspections|name, limit?:<=15} -> matching facilities, with totals per tier',
    run(a, data) {
      const list = filterFacilities(data, a), lim = Math.min(Math.max(Number(a.limit) || 8, 1), 15);
      if (!list.length) return { text: "No facilities matched." };
      return { text: `Matched ${list.length} facilities. By tier: ${tierLine(list)}.\nTop ${Math.min(lim, list.length)} sorted by ${a.sort_by || "penalties"}:\n` +
        list.slice(0, lim).map(line).join("\n") };
    },
  },
  aggregate: {
    doc: 'aggregate {group_by:state|tier|entity|status|city, state?, tier?, name?, status?, limit?:<=15} -> facility counts, penalties and formal actions per group',
    run(a, data) {
      const key = { state: "state", tier: "tier", entity: "entity", status: "status", city: "city" }[a.group_by] || "state";
      const groups = new Map();
      for (const f of filterFacilities(data, { ...a, sort_by: "name" })) {
        const k = f[key] || "(none)";
        const g = groups.get(k) || { n: 0, pen: 0, act: 0, mix: {} };
        g.n++; g.pen += f.pen; g.act += f.actions; g.mix[f.tier] = (g.mix[f.tier] || 0) + 1;
        groups.set(k, g);
      }
      const rows = [...groups].sort((x, y) => y[1].pen - x[1].pen).slice(0, Math.min(Number(a.limit) || 10, 15));
      if (!rows.length) return { text: "No facilities matched." };
      return { text: `Grouped by ${key}, sorted by penalties (agency-reported). Groups mix link tiers unless filtered; the tier mix is shown.\n` +
        rows.map(([k, g]) => `${k}: ${g.n} facilities, ${money(g.pen)}, ${g.act} formal actions (tiers ${Object.entries(g.mix).map(([t, c]) => `${t}=${c}`).join(" ")})`).join("\n") };
    },
  },
  facility_detail: {
    doc: "facility_detail {id: RegistryID or facility name} -> full record; also highlights it on the map and adds source links",
    run(a, data, ctx) {
      const { f, many } = resolveFacility(data, a.id ?? a.name);
      if (many) return { text: "Several facilities match. Ask which one, or call again with a RegistryID:\n" + many.map(line).join("\n") };
      if (!f) return { text: "No facility found for that id or name." };
      const n = addSource(ctx, { title: `EPA ECHO: ${f.name}`, url: f.echo_url, type: "facility", chunk: f.id });
      if (f.lat != null) ctx.actions.push({ type: "map", ids: [f.id], label: f.name });
      ctx.actions.push({ type: "link", title: "EPA ECHO detailed facility report", url: f.echo_url });
      if (f.ex21_url) ctx.actions.push({ type: "link", title: `SEC Exhibit 21 (as of ${f.as_of})`, url: f.ex21_url });
      return { text: `[${n}] ${f.name} (RegistryID ${f.id})\nAddress: ${[f.street, f.city, f.state, f.zip].filter(Boolean).join(", ") || "n/a"}${f.county ? ` (${f.county} County)` : ""}\n` +
        `Link tier: ${f.tier}${f.entity ? ` via Exhibit 21 entity "${f.entity}"` : " (name token only)"}${f.review ? " - NEEDS REVIEW" : ""}\n` +
        `Compliance status: ${f.status || "n/a"}; quarters with non-compliance: ${f.nc_qtrs ?? "n/a"}\n` +
        `Penalties recorded: ${money(f.pen)} (agency-reported; may be alleged, pending, appealed or settled); formal actions: ${f.actions}; inspections: ${f.insp}; last inspection: ${f.last_insp || "n/a"}; last penalty: ${f.last_pen || "n/a"}\n` +
        `Industry: ${f.sic || "n/a"}\nLocation: ${f.lat != null ? `approximate (${f.geo === "zip" ? "ZIP centroid" : "ECHO coordinates"})` : "unmapped (no ZIP)"}` };
    },
  },
  search_documents: {
    doc: 'search_documents {query, doc_type?:"10-K"|"facility"} -> relevant passages from the Dow 10-K filing and EPA facility records, numbered for citation',
    run(a, data, ctx) {
      const type = { "10-k": "10-K", "10k": "10-K", facility: "echo_facility_fact", epa: "echo_facility_fact" }[lc(a.doc_type)] || null;
      const hits = search(data.index, a.query || "", { k: 5, type });
      if (!hits.length) return { text: "No passages matched." };
      return { text: hits.map((c) => {
        const n = addSource(ctx, { title: c.title, url: c.url, type: c.type === "10-K" ? "10-K" : "facility", chunk: c.id, excerpt: c.text.slice(0, 160) });
        return `[${n}] (${c.title})\n${c.text.slice(0, 700)}`;
      }).join("\n\n") };
    },
  },
  show_on_map: {
    doc: "show_on_map {ids?:[RegistryID], state?, tier?, name?, city?} -> highlights facilities on the map",
    run(a, data, ctx) {
      const list = Array.isArray(a.ids) && a.ids.length ? a.ids.map((i) => data.byId.get(String(i))).filter(Boolean) : filterFacilities(data, a);
      const mapped = list.filter((f) => f.lat != null);
      if (!mapped.length) return { text: "Nothing to show: no matching facilities have map coordinates." };
      ctx.actions.push({ type: "map", ids: mapped.map((f) => f.id), label: a.state ? `${a.state} facilities` : `${mapped.length} facilities` });
      return { text: `Highlighted ${mapped.length} facilities on the map${list.length > mapped.length ? ` (${list.length - mapped.length} have no coordinates)` : ""}.` };
    },
  },
  show_satellite: {
    doc: 'show_satellite {id, zoom?:"area"|"close"} -> shows an aerial image (location is approximate, from the ZIP code)',
    run(a, data, ctx) {
      const { f, many } = resolveFacility(data, a.id ?? a.name);
      if (many) return { text: "Several facilities match; use a RegistryID:\n" + many.map(line).join("\n") };
      if (!f || f.lat == null) return { text: "No coordinates available for that facility." };
      const zip = f.geo === "zip";
      ctx.actions.push({ type: "image", url: satelliteUrl(f, a.zoom), alt: `Aerial view near ${f.name}`,
        caption: zip ? `Aerial view around ZIP ${f.zip} centroid. Approximate; may not show the facility itself. Imagery: Esri, Maxar, Earthstar Geographics` : `Aerial view of ${f.name}. Imagery: Esri, Maxar, Earthstar Geographics` });
      return { text: `Aerial image shown for ${f.name}. ${zip ? "Position is the ZIP code centroid, so it is approximate." : ""}` };
    },
  },
  export_csv: {
    doc: "export_csv {state?, tier?, name?, city?, status?, min_penalties?, needs_review?, sort_by?} -> creates a downloadable CSV of matching facilities",
    run(a, data, ctx) {
      const list = filterFacilities(data, a);
      if (!list.length) return { text: "No facilities matched, so no file was created." };
      const qs = new URLSearchParams();
      for (const k of FILTER_KEYS) if (a[k] != null && a[k] !== "") qs.set(k, String(a[k]));
      const tag = [a.state, a.tier && TIERS[lc(a.tier)]].filter(Boolean).join("-").toLowerCase();
      ctx.actions.push({ type: "file", name: `dow-facilities${tag ? "-" + tag : ""}.csv`, url: `/api/export.csv?${qs}`, rows: list.length });
      return { text: `CSV file created with ${list.length} rows (tiers: ${tierLine(list)}).` };
    },
  },
};

export function toolDocs() { return Object.values(TOOLS).map((t) => "- " + t.doc).join("\n"); }

export function runTool(name, args, data, ctx) {
  const t = TOOLS[name];
  if (!t) return { text: `Unknown tool "${name}". Available: ${Object.keys(TOOLS).join(", ")}.` };
  try {
    return t.run(args && typeof args === "object" ? args : {}, data, ctx);
  } catch (e) {
    return { text: `Tool ${name} failed: ${e.message}` };
  }
}

const COLS = [["RegistryID", "id"], ["Name", "name"], ["Street", "street"], ["City", "city"], ["State", "state"], ["ZIP", "zip"],
  ["County", "county"], ["LinkTier", "tier"], ["MatchedExhibit21Entity", "entity"], ["NeedsReview", "review"],
  ["ComplianceStatus", "status"], ["PenaltiesUSD", "pen"], ["FormalActions", "actions"], ["Inspections", "insp"],
  ["LastInspection", "last_insp"], ["LastPenalty", "last_pen"], ["LocationPrecision", "geo"], ["Lat", "lat"], ["Lon", "lon"],
  ["EchoUrl", "echo_url"], ["Exhibit21Url", "ex21_url"]];

export function facilitiesToCsv(list) {
  const cell = (v) => {
    let s = v == null ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // stop spreadsheet formula injection
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [COLS.map((c) => c[0]).join(","), ...list.map((f) => COLS.map(([, k]) => cell(f[k])).join(","))].join("\r\n") + "\r\n";
}
