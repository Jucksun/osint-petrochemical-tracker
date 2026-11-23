// Loads the static JSON that ships in /public/data and builds the search index once per isolate.
import { buildIndex } from "./search.js";

let cache = null;

export async function loadData(env, baseUrl) {
  if (cache) return cache;
  const get = async (name) => {
    const res = await env.ASSETS.fetch(new Request(new URL(`/data/${name}.json`, baseUrl)));
    if (!res.ok) throw new Error(`Could not load data/${name}.json (${res.status}). Run scripts/export_data.py.`);
    return res.json();
  };
  const [facilities, chunks, meta] = await Promise.all([get("facilities"), get("chunks"), get("meta")]);
  cache = { facilities, chunks, meta, index: buildIndex(chunks), byId: new Map(facilities.map((f) => [f.id, f])) };
  return cache;
}

export function resetCache() { cache = null; } // for tests
