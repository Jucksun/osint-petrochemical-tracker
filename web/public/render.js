// Renders AI-written text into safe HTML. The model's output is untrusted (it can be influenced by
// text inside SEC filings), so everything is escaped first and only a small whitelist is allowed:
// bold, code, lists, https links, images from approved hosts, and [n] citation chips.
export const IMAGE_HOSTS = ["services.arcgisonline.com", "echo.epa.gov", "www.epa.gov", "www.sec.gov"];

const ENT = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ENT[c]);

export function safeUrl(u) {
  const s = String(u || "").trim();
  if (/^\/(?![\/\\])/.test(s)) return s; // same-site path
  try {
    const url = new URL(s);
    return url.protocol === "https:" ? url.href : null;
  } catch { return null; }
}

export function safeImage(u) {
  const s = safeUrl(u);
  if (!s) return null;
  if (s.startsWith("/")) return s;
  return IMAGE_HOSTS.includes(new URL(s).hostname) ? s : null;
}

function inline(raw, ctx) {
  const re = /!\[([^\]]*)\]\(([^)\s]+)\)|\[([^\]]+)\]\(([^)\s]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\[(\d{1,2})\]/g;
  let out = "", last = 0, m;
  while ((m = re.exec(raw))) {
    out += esc(raw.slice(last, m.index));
    last = re.lastIndex;
    if (m[2] !== undefined) {
      const src = safeImage(m[2]);
      out += src ? `<img class="inline-img" src="${esc(src)}" alt="${esc(m[1])}" loading="lazy" referrerpolicy="no-referrer">`
        : `<span class="blocked">[image blocked: ${esc(m[1] || "unapproved source")}]</span>`;
    } else if (m[4] !== undefined) {
      const href = safeUrl(m[4]);
      out += href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(m[3])}</a>` : esc(m[3]);
    } else if (m[5] !== undefined) out += `<code>${esc(m[5])}</code>`;
    else if (m[6] !== undefined) out += `<strong>${esc(m[6])}</strong>`;
    else {
      const s = ctx.sources.find((x) => x.n === +m[7]);
      const href = s && safeUrl(s.url);
      out += href ? `<a class="cite" href="${esc(href)}" target="_blank" rel="noopener noreferrer" title="${esc(s.title)}">[${m[7]}]</a>` : esc(m[0]);
    }
  }
  return out + esc(raw.slice(last));
}

export function renderMarkdown(text, { sources = [] } = {}) {
  const ctx = { sources };
  let html = "", list = null, code = null, para = [];
  const flushPara = () => { if (para.length) { html += `<p>${para.map((l) => inline(l, ctx)).join("<br>")}</p>`; para = []; } };
  const flushList = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const line of String(text ?? "").replace(/\r/g, "").split("\n")) {
    if (line.trim().startsWith("```")) {
      if (code === null) { flushPara(); flushList(); code = []; } else { html += `<pre>${esc(code.join("\n"))}</pre>`; code = null; }
      continue;
    }
    if (code !== null) { code.push(line); continue; }
    const ul = /^\s*[-*]\s+(.*)$/.exec(line), ol = /^\s*\d+[.)]\s+(.*)$/.exec(line), h = /^#{1,4}\s+(.*)$/.exec(line);
    if (ul || ol) {
      flushPara();
      const tag = ul ? "ul" : "ol";
      if (list !== tag) { flushList(); html += `<${tag}>`; list = tag; }
      html += `<li>${inline((ul || ol)[1], ctx)}</li>`;
      continue;
    }
    flushList();
    if (h) { flushPara(); html += `<p class="h">${inline(h[1], ctx)}</p>`; continue; }
    if (!line.trim()) { flushPara(); continue; }
    para.push(line);
  }
  if (code !== null) html += `<pre>${esc(code.join("\n"))}</pre>`;
  flushPara(); flushList();
  return html;
}
