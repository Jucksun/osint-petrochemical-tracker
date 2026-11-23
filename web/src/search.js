// Small BM25 keyword index over the text chunks (10-K passages + EPA facility records).
const STOP = new Set("a an and the of in on at to for is are was were by with or as it this that from be what which who how do does did about".split(" "));

export function tokens(s) {
  return (String(s).toLowerCase().match(/[a-z0-9]+/g) || [])
    .filter((w) => w.length > 1 && !STOP.has(w))
    .map((w) => (w.length > 3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w));
}

export function buildIndex(chunks) {
  const docs = chunks.map((c) => {
    const tf = new Map();
    for (const t of tokens(c.title + " " + c.text)) tf.set(t, (tf.get(t) || 0) + 1);
    let len = 0;
    for (const v of tf.values()) len += v;
    return { tf, len };
  });
  const df = new Map();
  for (const d of docs) for (const t of d.tf.keys()) df.set(t, (df.get(t) || 0) + 1);
  const avg = docs.reduce((a, d) => a + d.len, 0) / (docs.length || 1);
  return { chunks, docs, df, avg, n: docs.length };
}

export function search(index, query, { k = 5, type = null } = {}) {
  const q = [...new Set(tokens(query))];
  if (!q.length) return [];
  const k1 = 1.5, b = 0.75, out = [];
  index.docs.forEach((d, i) => {
    const c = index.chunks[i];
    if (type && c.type !== type) return;
    let score = 0, hit = 0;
    for (const t of q) {
      const f = d.tf.get(t);
      if (!f) continue;
      hit++;
      const n = index.df.get(t);
      const idf = Math.log(1 + (index.n - n + 0.5) / (n + 0.5));
      score += idf * ((f * (k1 + 1)) / (f + k1 * (1 - b + (b * d.len) / index.avg)));
    }
    if (hit) out.push({ chunk: c, score: score * (1 + 0.15 * hit) });
  });
  return out.sort((a, b2) => b2.score - a.score).slice(0, k).map((x) => x.chunk);
}
