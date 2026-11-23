// End-to-end smoke test: real index.html + app.js in jsdom, real data, real Worker, fake AI and map.
// Skipped automatically if jsdom is not installed (npm i --no-save jsdom).
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

let JSDOM = null;
try { ({ JSDOM } = await import("jsdom")); } catch { /* optional */ }
const skip = !JSDOM && "jsdom not installed";

const PUB = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public");
const { default: worker } = await import("../src/worker.js");
const { resetCache } = await import("../src/data.js");

const ASSETS = { async fetch(req) {
  try { return new Response(await readFile(path.join(PUB, new URL(req.url).pathname))); } catch { return new Response("", { status: 404 }); }
} };
const tool = (name, args) => `<tool>${JSON.stringify({ name, args })}</tool>`;

async function makePage(replies) {
  resetCache();
  const calls = { filter: [], fly: 0, bounds: 0, data: 0 };
  const ai = { run: async () => { const r = replies.shift(); if (r instanceof Error) throw r; return { response: r }; } };
  const env = { ASSETS, AI: ai, CHAT_MODELS: "@cf/test/model-a" };
  const html = (await readFile(path.join(PUB, "index.html"), "utf8")).replace(/<script[\s\S]*?<\/script>/g, "");
  const dom = new JSDOM(html, { url: "https://petrochemicals.jacksonsobservatory.com/", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  w.matchMedia = () => ({ matches: true });
  w.HTMLElement.prototype.scrollTo = () => {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function () { this.open = false; };
  class Fake { constructor() { this.h = {}; } on(ev, a, b) { if (ev === "load") setTimeout(a, 0); } addControl() {} addSource() {} addLayer() {}
    getSource() { return { setData: () => calls.data++ }; } setFilter(id, f) { calls.filter.push(f); } flyTo() { calls.fly++; } fitBounds() { calls.bounds++; }
    getCanvas() { return { style: {} }; } }
  w.maplibregl = { Map: Fake, NavigationControl: class {}, Popup: class { setLngLat() { return this; } setText() { return this; } addTo() { return this; } remove() {} },
    LngLatBounds: class { extend() {} } };
  w.fetch = async (url, opts) => {
    const u = new URL(url, "https://petrochemicals.jacksonsobservatory.com/");
    if (u.pathname.startsWith("/api/")) return worker.fetch(new Request(u, { ...opts, headers: { ...(opts?.headers || {}), "cf-connecting-ip": "p" + Math.random() } }), env);
    return new Response(await readFile(path.join(PUB, u.pathname)));
  };
  const render = (await readFile(path.join(PUB, "render.js"), "utf8")).replace(/^export /gm, "");
  const app = (await readFile(path.join(PUB, "app.js"), "utf8")).replace(/^import .*$/m, "");
  w.eval(render + "\n" + app);
  const until = async (fn, ms = 4000) => { const t = Date.now(); while (Date.now() - t < ms) { const v = fn(); if (v) return v; await new Promise((r) => setTimeout(r, 20)); } throw new Error("timeout waiting for UI"); };
  const ask = (text) => { w.document.querySelector("#prompt").value = text; w.document.querySelector("#form").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true })); };
  await until(() => w.document.querySelector(".suggest button"));
  return { w, d: w.document, calls, until, ask };
}

test("page boots: filters, list, tiers, suggestions", { skip }, async () => {
  const { d } = await makePage([]);
  assert.match(d.querySelector("#count").textContent, /^146 shown/);
  assert.equal(d.querySelectorAll("#tiers input").length, 3);
  assert.ok(d.querySelectorAll("#list li").length > 50);
  assert.ok(d.querySelector("#state").options.length > 5);
  assert.match(d.querySelector("#asof").textContent, /Exhibit 21 as of/);
});

test("tier toggle, state filter and search update the list; selecting shows the dossier", { skip }, async () => {
  const { d, w } = await makePage([]);
  const tok = d.querySelector('input[data-tier="token_only"]');
  tok.checked = true; tok.dispatchEvent(new w.Event("change", { bubbles: true }));
  assert.match(d.querySelector("#count").textContent, /^292 shown/);
  const st = d.querySelector("#state"); st.value = "MI"; st.dispatchEvent(new w.Event("change"));
  assert.match(d.querySelector("#count").textContent, /^\d+ shown/);
  d.querySelector("#list li").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  assert.ok(d.querySelector("#dossier h3")); assert.match(d.querySelector("#dossier").textContent, /Registry ID/);
});

test("AI answer renders with citations, map action highlights the map, file + link + image attach", { skip }, async () => {
  const { d, calls, until, ask } = await makePage([
    [tool("show_on_map", { state: "MI" }), tool("export_csv", { state: "MI" })].join("\n"),
    "Michigan facilities are highlighted on the map. **Done.**"]);
  ask("Show Michigan facilities on the map");
  await until(() => d.querySelector(".maplink"));
  await until(() => /Done\./.test(d.querySelector("#log").textContent));
  assert.ok(d.querySelector(".filecard").getAttribute("href").startsWith("/api/export.csv?state=MI"));
  assert.ok(calls.filter.some((f) => Array.isArray(f) && f[2] && f[2][0] !== "__none__"), "map highlight filter applied");
  assert.ok(calls.bounds + calls.fly > 0, "map moved");
  assert.ok(!d.querySelector("#btn-clear-hi").classList.contains("hidden"));
  assert.match(d.querySelector("#model").textContent, /MODEL-A/);
  assert.equal(d.querySelector("#send").disabled, false);
});

test("malicious model output cannot inject script, tracking images or javascript: links", { skip }, async () => {
  const evil = 'Click [here](javascript:alert(1)) <script>window.pwned=1</script> ![t](https://evil.example/p.gif) <img src=x onerror="window.pwned=2">';
  const { d, w, until, ask } = await makePage([tool("find_facilities", { state: "TX" }), evil]);
  ask("anything");
  await until(() => /Click/.test(d.querySelector("#log").textContent));
  await new Promise((r) => setTimeout(r, 50));
  const log = d.querySelector("#log");
  assert.equal(w.pwned, undefined); assert.equal(log.querySelectorAll("script").length, 0);
  assert.ok(![...log.querySelectorAll("img")].some((i) => /evil|^x$/.test(i.getAttribute("src") || "")));
  assert.ok(![...log.querySelectorAll("a")].some((a) => /^javascript:/i.test(a.getAttribute("href") || "")));
});

test("AI outage shows a readable error and re-enables input", { skip }, async () => {
  const { d, until, ask } = await makePage([new Error("boom")]);
  ask("hello");
  await until(() => d.querySelector(".err"));
  assert.match(d.querySelector("#log").textContent, /ERR: .*unavailable/);
  assert.equal(d.querySelector("#send").disabled, false);
});

test("help and clear commands work without calling the AI", { skip }, async () => {
  const { d, until, ask } = await makePage([]);
  ask("help"); await until(() => /Commands:/.test(d.querySelector("#log").textContent));
  ask("clear"); await until(() => d.querySelector("#log").children.length === 0);
});
