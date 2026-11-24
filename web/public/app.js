import { esc, renderMarkdown, safeImage, safeUrl } from "./render.js";

const $ = (s) => document.querySelector(s);
const TIER_COLOR = { ex21_exact: "#33ff66", ex21_prefix: "#ffb000", token_only: "#ff5555" };
const TIER_LABEL = { ex21_exact: "exact", ex21_prefix: "prefix", token_only: "token only" };
const money = (n) => "$" + Math.round(n || 0).toLocaleString("en-US");
const S = { facs: [], byId: new Map(), meta: null, map: null, ready: false, tiers: new Set(["ex21_exact", "ex21_prefix"]),
  state: "", q: "", sel: null, hi: [], history: [], busy: false, cmds: [], ci: -1 };

/* ---------- data + filters ---------- */
const visible = () => {
  const q = S.q.trim().toLowerCase(), hi = new Set(S.hi);
  return S.facs.filter((f) => hi.has(f.id) || (S.tiers.has(f.tier) && (!S.state || f.state === S.state) &&
    (!q || `${f.name} ${f.city} ${f.entity || ""} ${f.id}`.toLowerCase().includes(q))))
    .sort((a, b) => b.pen - a.pen);
};
const geo = (list) => ({ type: "FeatureCollection", features: list.filter((f) => f.lat != null).map((f) => ({
  type: "Feature", properties: { id: f.id, pen: f.pen, tier: f.tier, name: f.name }, geometry: { type: "Point", coordinates: [f.lon, f.lat] } })) });

function refresh() {
  const list = visible();
  if (S.ready) S.map.getSource("fac").setData(geo(list));
  $("#count").textContent = `${list.length} shown (${list.filter((f) => f.lat != null).length} on map)`;
  $("#map-status").textContent = `${list.length} facilities`;
  $("#list").innerHTML = list.slice(0, 120).map((f) =>
    `<li data-id="${esc(f.id)}" class="${f.id === S.sel ? "sel" : ""}"><span class="n">${esc(f.name)}</span><span class="nm">${esc(f.state || "")}</span><span>${money(f.pen)}</span></li>`).join("") || '<li class="dim">No matches</li>';
}

function drawTiers() {
  $("#tiers").innerHTML = Object.keys(TIER_COLOR).map((t) => {
    const m = S.meta.tiers[t] || { facilities: 0, penalties: 0 };
    return `<label class="tier"><input type="checkbox" data-tier="${t}" ${S.tiers.has(t) ? "checked" : ""}><i style="background:${TIER_COLOR[t]}"></i><span>${TIER_LABEL[t]} (${m.facilities})</span><span>${money(m.penalties)}</span></label>`;
  }).join("");
}

/* ---------- map ---------- */
function initMap() {
  if (!window.maplibregl) { $("#map").innerHTML = '<div class="maperr">MAP LIBRARY COULD NOT LOAD (offline or blocked). The list, dossier and analyst still work.</div>'; return; }
  const map = S.map = new maplibregl.Map({ container: "map", center: [-96, 37.5], zoom: 3.3, attributionControl: { compact: true },
    style: { version: 8, sources: { base: { type: "raster", tileSize: 256, attribution: "© OpenStreetMap contributors © CARTO",
            tiles: ["https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=cb1_5ets_1_2da3e94b458f78a14e709fcb"] } },
      layers: [{ id: "base", type: "raster", source: "base" }] } });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  const color = ["match", ["get", "tier"], "ex21_exact", TIER_COLOR.ex21_exact, "ex21_prefix", TIER_COLOR.ex21_prefix, TIER_COLOR.token_only];
  const r = (a, b, c) => ["interpolate", ["linear"], ["sqrt", ["get", "pen"]], 0, a, 300, b, 1300, c];
  map.on("load", () => {
    map.addSource("fac", { type: "geojson", data: geo(visible()) });
    map.addLayer({ id: "fac-glow", type: "circle", source: "fac", paint: { "circle-radius": r(9, 14, 30), "circle-color": color, "circle-opacity": 0.16, "circle-blur": 0.7 } });
    map.addLayer({ id: "fac-dot", type: "circle", source: "fac", paint: { "circle-radius": r(4, 6, 14), "circle-color": color, "circle-opacity": 0.9, "circle-stroke-width": 1, "circle-stroke-color": "#000" } });
    map.addLayer({ id: "fac-hi", type: "circle", source: "fac", filter: ["match", ["get", "id"], ["__none__"], true, false],
      paint: { "circle-radius": 17, "circle-color": "rgba(0,0,0,0)", "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff" } });
    S.ready = true;
    const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
    map.on("click", "fac-dot", (e) => select(e.features[0].properties.id, { fly: false }));
    map.on("mouseenter", "fac-dot", (e) => { map.getCanvas().style.cursor = "pointer"; pop.setLngLat(e.features[0].geometry.coordinates).setText(e.features[0].properties.name).addTo(map); });
    map.on("mouseleave", "fac-dot", () => { map.getCanvas().style.cursor = ""; pop.remove(); });
    refresh();
    if (S.hi.length) applyHighlight(S.hi);
  });
}

function setHiFilter(ids) {
  if (S.ready) S.map.setFilter("fac-hi", ["match", ["get", "id"], ids.length ? ids : ["__none__"], true, false]);
}

function applyHighlight(ids, label) {
  const fs = ids.map((i) => S.byId.get(String(i))).filter((f) => f && f.lat != null);
  S.hi = fs.map((f) => f.id);
  $("#btn-clear-hi").classList.toggle("hidden", !S.hi.length);
  refresh(); setHiFilter(S.hi);
  if (!S.ready || !fs.length) return;
  if (fs.length === 1) S.map.flyTo({ center: [fs[0].lon, fs[0].lat], zoom: 9, duration: 900 });
  else {
    const b = new maplibregl.LngLatBounds();
    fs.forEach((f) => b.extend([f.lon, f.lat]));
    S.map.fitBounds(b, { padding: 60, maxZoom: 8, duration: 900 });
  }
  if (label) $("#map-status").textContent = `highlight: ${label} (${fs.length})`;
}

/* ---------- dossier ---------- */
function select(id, { fly = true } = {}) {
  const f = S.byId.get(String(id));
  if (!f) return;
  S.sel = f.id;
  const row = (k, v) => (v == null || v === "" ? "" : `<tr><td>${k}</td><td>${v}</td></tr>`);
  const link = (u, t) => { const h = safeUrl(u); return h ? `<a href="${esc(h)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : ""; };
  $("#dossier").innerHTML = `<h3>${esc(f.name)}</h3><span class="badge b-${esc(f.tier)}">${esc(TIER_LABEL[f.tier] || f.tier)}</span>
    ${f.review ? '<div class="alert"><b>Needs review.</b> This link is a name match, not a confirmed ownership record.</div>' : ""}
    <table>${row("Registry ID", esc(f.id))}${row("Matched entity", esc(f.entity))}${row("Address", esc([f.street, f.city, f.state, f.zip].filter(Boolean).join(", ")))}
    ${row("Compliance", esc(f.status))}${row("Penalties", `${money(f.pen)} <span class="dim">(agency-reported)</span>`)}${row("Formal actions", f.actions)}
    ${row("Inspections", f.insp)}${row("Last inspection", esc(f.last_insp))}${row("Last penalty", esc(f.last_pen))}${row("Industry", esc(f.sic))}
    ${row("Position", f.lat == null ? "unmapped (no valid ZIP)" : f.geo === "zip" ? "approximate (ZIP centroid)" : "ECHO coordinates")}</table>
    <div class="actions"><button class="btn" data-ask="${esc(f.id)}">Ask the analyst</button>${f.lat != null ? `<button class="btn" data-aerial="${esc(f.id)}">Aerial view</button>` : ""}</div>
    <p>${link(f.echo_url, "EPA ECHO report")} ${f.ex21_url ? " · " + link(f.ex21_url, `SEC Exhibit 21 (${f.as_of})`) : ""}</p><div id="aerial"></div>`;
  document.querySelectorAll("#list li").forEach((li) => li.classList.toggle("sel", li.dataset.id === f.id));
  if (fly && S.ready && f.lat != null) S.map.flyTo({ center: [f.lon, f.lat], zoom: 9, duration: 800 });
}

const aerial = (f) => { const d = 0.05, dy = d * 420 / 640;
  return `https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?bbox=${f.lon - d},${f.lat - dy},${f.lon + d},${f.lat + dy}&bboxSR=4326&imageSR=4326&size=640,420&format=jpg&f=image`; };

/* ---------- terminal ---------- */
const log = () => $("#log");
const scroll = () => { log().scrollTop = log().scrollHeight; };
function addMsg(cls, who, html) {
  const d = document.createElement("div");
  d.className = `msg ${cls}`;
  d.innerHTML = `<div class="who">${who}</div><div class="t">${html}</div>`;
  log().appendChild(d); scroll();
  return d;
}

function attachments(actions, sources, warnings) {
  const wrap = document.createElement("div");
  const att = document.createElement("div");
  att.className = "att";
  for (const a of actions || []) {
    if (a.type === "map" && Array.isArray(a.ids)) {
      const b = document.createElement("button");
      b.className = "maplink"; b.type = "button"; b.dataset.ids = a.ids.join(","); b.dataset.label = a.label || "";
      b.textContent = `Show on map: ${a.label || a.ids.length + " facilities"}`;
      att.appendChild(b);
    } else if (a.type === "link" && safeUrl(a.url)) {
      att.insertAdjacentHTML("beforeend", `<a class="chip" href="${esc(safeUrl(a.url))}" target="_blank" rel="noopener noreferrer">${esc(a.title || a.url)}</a>`);
    } else if (a.type === "file" && safeUrl(a.url)) {
      att.insertAdjacentHTML("beforeend", `<a class="filecard" href="${esc(safeUrl(a.url))}" download="${esc(a.name || "file.csv")}">${esc(a.name || "file")} (${+a.rows || 0} rows)</a>`);
    } else if (a.type === "image" && safeImage(a.url)) {
      const fig = document.createElement("figure");
      fig.className = "shot";
      const img = new Image();
      img.alt = a.alt || ""; img.loading = "lazy"; img.referrerPolicy = "no-referrer"; img.src = safeImage(a.url);
      img.onerror = () => { fig.innerHTML = '<figcaption class="err">[image failed to load]</figcaption>'; };
      const cap = document.createElement("figcaption");
      cap.textContent = a.caption || "";
      fig.append(img, cap); att.appendChild(fig);
    }
  }
  if (att.childElementCount) wrap.appendChild(att);
  if (sources && sources.length) {
    const s = document.createElement("div");
    s.className = "sources";
    s.innerHTML = "SOURCES:" + sources.map((x) => { const h = safeUrl(x.url);
      return `<div>[${x.n}] ${h ? `<a href="${esc(h)}" target="_blank" rel="noopener noreferrer">${esc(x.title)}</a>` : esc(x.title)}</div>`; }).join("");
    wrap.appendChild(s);
  }
  for (const w of warnings || []) wrap.insertAdjacentHTML("beforeend", `<div class="warn">! ${esc(w)}</div>`);
  return wrap;
}

function reveal(el, text, sources) {
  const done = () => { el.innerHTML = renderMarkdown(text, { sources }); scroll(); };
  if (text.length > 1400 || matchMedia("(prefers-reduced-motion: reduce)").matches) { done(); return Promise.resolve(); }
  return new Promise((res) => {
    let n = 0;
    const id = setInterval(() => {
      n += 10;
      if (n >= text.length) { clearInterval(id); done(); res(); } else { el.innerHTML = renderMarkdown(text.slice(0, n), { sources }); scroll(); }
    }, 14);
  });
}

async function send(text) {
  text = text.trim();
  if (!text || S.busy) return;
  S.cmds.push(text); S.ci = S.cmds.length;
  addMsg("user", "YOU", esc(text));
  const low = text.toLowerCase();
  if (low === "clear") { log().innerHTML = ""; return; }
  if (low === "help") {
    addMsg("bot", "ANALYST", renderMarkdown("Ask anything about the Dow-linked facilities or the 10-K. Examples:\n- Which Texas facilities have the most penalties?\n- Show Michigan facilities on the map\n- Give me an aerial view and dossier for a facility by name\n- What does the 10-K say about wastewater?\n- Export the exact-match facilities as CSV\n\nCommands: `help`, `clear`. The AI can place map highlights, show images, link sources and create files."));
    return;
  }
  S.busy = true; $("#send").disabled = true;
  const t0 = Date.now();
  const wait = addMsg("bot", "ANALYST", '<span class="thinking">PROCESSING</span>');
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text, history: S.history.slice(-6) }) });
    const j = await r.json().catch(() => ({}));
    wait.remove();
    if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
    if (j.model) $("#model").textContent = "MODEL: " + j.model.split("/").pop().toUpperCase();
    const m = addMsg("bot", `ANALYST <span class="dim">(${((Date.now() - t0) / 1000).toFixed(1)}s${j.tools?.length ? ", tools: " + esc([...new Set(j.tools)].join(", ")) : ""})</span>`, "");
    const body = m.querySelector(".t");
    await reveal(body, j.answer || "", j.sources || []);
    body.appendChild(attachments(j.actions, j.sources, j.warnings));
    const first = (j.actions || []).find((a) => a.type === "map" && Array.isArray(a.ids));
    if (first) applyHighlight(first.ids, first.label);
    S.history.push({ role: "user", content: text }, { role: "assistant", content: (j.answer || "").slice(0, 1200) });
    scroll();
  } catch (e) {
    wait.remove();
    addMsg("bot", "ANALYST", `<span class="err">ERR: ${esc(e.message)}</span>`);
  } finally {
    S.busy = false; $("#send").disabled = false; $("#prompt").focus();
  }
}

/* ---------- csv ---------- */
function csvOfVisible() {
  const cols = [["RegistryID", "id"], ["Name", "name"], ["City", "city"], ["State", "state"], ["LinkTier", "tier"], ["MatchedEntity", "entity"], ["NeedsReview", "review"], ["Status", "status"], ["PenaltiesUSD", "pen"], ["FormalActions", "actions"], ["Inspections", "insp"], ["EchoUrl", "echo_url"]];
  const cell = (v) => { let s = v == null ? "" : String(v); if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const text = [cols.map((c) => c[0]).join(","), ...visible().map((f) => cols.map(([, k]) => cell(f[k])).join(","))].join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" })); a.download = "dow-facilities-filtered.csv"; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ---------- wiring ---------- */
async function boot() {
  try {
    const [facs, meta] = await Promise.all([fetch("/data/facilities.json").then((r) => r.json()), fetch("/data/meta.json").then((r) => r.json())]);
    S.facs = facs; S.meta = meta; S.byId = new Map(facs.map((f) => [f.id, f]));
  } catch {
    addMsg("bot", "SYSTEM", '<span class="err">ERR: could not load the data files.</span>'); return;
  }
  $("#asof").textContent = `Exhibit 21 as of ${S.meta.ex21_as_of || "n/a"} · data built ${S.meta.generated_at.slice(0, 10)}`;
  $("#state").innerHTML += [...new Set(S.facs.map((f) => f.state).filter(Boolean))].sort().map((s) => `<option>${esc(s)}</option>`).join("");
  drawTiers(); refresh(); initMap();

  $("#tiers").addEventListener("change", (e) => { const t = e.target.dataset.tier; if (!t) return; e.target.checked ? S.tiers.add(t) : S.tiers.delete(t); refresh(); });
  $("#state").addEventListener("change", (e) => { S.state = e.target.value; refresh(); });
  $("#q").addEventListener("input", (e) => { S.q = e.target.value; refresh(); });
  $("#list").addEventListener("click", (e) => { const li = e.target.closest("li[data-id]"); if (li) select(li.dataset.id); });
  $("#btn-csv").addEventListener("click", csvOfVisible);
  $("#btn-clear-hi").addEventListener("click", () => { S.hi = []; $("#btn-clear-hi").classList.add("hidden"); setHiFilter([]); refresh(); });
  $("#btn-method").addEventListener("click", () => $("#method").showModal());
  $("#method-close").addEventListener("click", () => $("#method").close());
  $("#dossier").addEventListener("click", (e) => {
    const ask = e.target.closest("[data-ask]"), ae = e.target.closest("[data-aerial]");
    if (ask) { const f = S.byId.get(ask.dataset.ask); send(`Give me a dossier on ${f.name} (RegistryID ${f.id}) and what we know about the link confidence.`); }
    if (ae) { const f = S.byId.get(ae.dataset.aerial), u = safeImage(aerial(f));
      $("#aerial").innerHTML = `<img alt="Aerial view near ${esc(f.name)}" src="${esc(u)}" referrerpolicy="no-referrer" onerror="this.replaceWith(document.createTextNode('[image failed to load]'))"><div class="dim">Around the ZIP centroid; approximate. Imagery: Esri, Maxar, Earthstar Geographics</div>`; }
  });
  log().addEventListener("click", (e) => {
    const b = e.target.closest(".maplink");
    if (b) applyHighlight(b.dataset.ids.split(","), b.dataset.label);
    const s = e.target.closest(".suggest button");
    if (s) send(s.textContent);
  });
  $("#form").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#prompt").value; $("#prompt").value = ""; send(v); });
  $("#prompt").addEventListener("keydown", (e) => {
    if (e.key === "ArrowUp" && S.cmds.length) { S.ci = Math.max(0, S.ci - 1); e.target.value = S.cmds[S.ci] || ""; e.preventDefault(); }
    if (e.key === "ArrowDown" && S.cmds.length) { S.ci = Math.min(S.cmds.length, S.ci + 1); e.target.value = S.cmds[S.ci] || ""; e.preventDefault(); }
  });

  const c = S.meta.counts;
  const m = addMsg("bot", "SYSTEM", renderMarkdown(`**JACKSONOS V2.1 - PETROCHEM ANALYST**\nTracking ${c.facilities} EPA facilities linked to the ${S.meta.company} family through SEC filings (${c.mapped} on the map). Penalties are agency-reported and links are name matches, so confidence is shown everywhere. Type a question or pick one:`));
  m.querySelector(".t").insertAdjacentHTML("beforeend", '<div class="suggest">' + [
    "Which facilities have the highest penalties, broken down by link tier?",
    "Show Michigan facilities on the map",
    "What does the 10-K say about environmental proceedings?",
    "Which token_only matches look unrelated to Dow?",
    "Export the exact-match facilities as CSV"].map((q) => `<button type="button">${esc(q)}</button>`).join("") + "</div>");
}
boot();
