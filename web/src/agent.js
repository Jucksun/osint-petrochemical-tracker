// The analyst: a small tool-calling loop that works with any chat model on Workers AI.
// Tool calls use a plain-text protocol (<tool>{...}</tool>) instead of model-specific function
// calling, so changing models in wrangler.toml never breaks it.
import { chat } from "./llm.js";
import { runTool, toolDocs } from "./tools.js";
import { checkAnswer, NO_ANSWER } from "./verify.js";

const MAX_ROUNDS = 4;
// Whole-question time budget. The browser gives up at 90s, so finish well before that.
const TIME_BUDGET_MS = 70_000;

export function systemPrompt(meta) {
  const t = meta.tiers || {};
  return `You are the JACKSONOS PETROCHEM ANALYST, a terminal assistant for an open-source-intelligence tracker of the ${meta.company} corporate family (Dow Inc., The Dow Chemical Company, Union Carbide).
DATA: ${meta.counts.facilities} EPA ECHO facilities linked to ${meta.company} by NAME MATCH against the SEC Exhibit 21 subsidiary list (as of ${meta.ex21_as_of}), plus the latest 10-K text. Link tiers: ex21_exact (strong), ex21_prefix (medium, needs review), token_only (weak, needs review; may be unrelated companies or even oil wells that merely contain the word "Dow"). Tier sizes: ${Object.entries(t).map(([k, v]) => `${k}=${v.facilities}`).join(", ")}. Map positions are ZIP-code centroids (approximate).
RULES:
1. Never state numbers, names or facts from memory. Get them from tools. If the tools return nothing relevant, reply exactly: ${NO_ANSWER}
2. Penalties and violations are agency-reported and may be alleged, pending, appealed or settled. Never say a company is guilty or committed wrongdoing.
3. Never give one blended total across link tiers. Report per tier and say when a match is uncertain.
4. Cite passages and facility records with the [n] numbers from tool results.
5. Be concise and plain, like a terminal. Markdown allowed: **bold**, "- " lists, [text](https://...) links, and images ![alt](url). Only use URLs that appeared in tool results. Never invent URLs.
TOOLS: To use tools, reply with ONLY lines of the form
<tool>{"name":"TOOL_NAME","args":{...}}</tool>
(up to 3 per reply, nothing else in that reply). You will receive the results. When you have enough, reply with the final answer and NO <tool> tags.
${toolDocs()}
Map highlights, images, file downloads and link buttons appear in the UI automatically when you call the matching tool; mention them briefly (for example: "Highlighted on the map.").`;
}

export function parseToolCalls(text) {
  const calls = [];
  for (const m of text.matchAll(/<tool>([\s\S]*?)<\/tool>/gi)) {
    const body = m[1].replace(/^\s*```(?:json)?|```\s*$/g, "").trim();
    try {
      const j = JSON.parse(body);
      const name = j.name || j.tool;
      if (name) calls.push({ name: String(name), args: j.args || j.arguments || j.parameters || {} });
    } catch { /* ignore malformed call */ }
  }
  return calls.slice(0, 3);
}

const strip = (t) => t.replace(/<\/?tool>/gi, "").replace(/^\s*TOOL RESULTS:?/i, "").trim();

export async function runAgent(env, data, history, userMessage) {
  const ctx = { sources: [], actions: [], toolsUsed: [], corpus: [] };
  const messages = [{ role: "system", content: systemPrompt(data.meta) }, ...history, { role: "user", content: userMessage }];
  let answer = "", model = "";
  const started = Date.now();
  for (let round = 0; round <= MAX_ROUNDS; round++) {
    const left = TIME_BUDGET_MS - (Date.now() - started);
    if (left < 8_000) { answer = "That question took too long to work through. Try a narrower question."; break; }
    const last = round === MAX_ROUNDS;
    if (last) messages.push({ role: "user", content: "Tool budget used. Give the final answer now using only the results above. Do not call tools." });
    const res = await chat(env, messages, { timeoutMs: Math.min(25_000, left) });
    model = res.model;
    const calls = last ? [] : parseToolCalls(res.text);
    if (last && /<tool>/i.test(res.text)) { answer = "I ran out of lookup steps before finishing. Try a narrower question."; break; }
    if (!calls.length) { answer = strip(res.text); break; }
    messages.push({ role: "assistant", content: res.text });
    const results = calls.map((c) => {
      ctx.toolsUsed.push(c.name);
      const r = runTool(c.name, c.args, data, ctx);
      ctx.corpus.push(r.text);
      return `<result tool="${c.name}">\n${r.text}\n</result>`;
    });
    messages.push({ role: "user", content: `TOOL RESULTS:\n${results.join("\n")}\nContinue: call another tool or give the final answer.` });
  }
  const warnings = checkAnswer(answer, { sources: ctx.sources, corpus: ctx.corpus.join("\n"), facilityIds: new Set(data.byId.keys()), toolsUsed: ctx.toolsUsed });
  return { answer: answer || NO_ANSWER, sources: ctx.sources, actions: ctx.actions, warnings, model, tools: ctx.toolsUsed };
}
