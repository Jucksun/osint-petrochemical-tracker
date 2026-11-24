// Calls Workers AI with a model fallback chain. Written to tolerate the different response shapes
// Workers AI models return, so swapping models in wrangler.toml needs no code change.

const DEFAULT_MODELS = "@cf/zai-org/glm-4.7-flash,@cf/qwen/qwen3-30b-a3b-fp8,@cf/meta/llama-3.3-70b-instruct-fp8-fast";

export function extractText(res) {
  if (res == null) return "";
  if (typeof res === "string") return res;
  const cands = [res.response, res.result?.response, res.output_text, res.choices?.[0]?.message?.content,
    res.choices?.[0]?.text];
  for (const c of cands) {
    if (typeof c === "string" && c.trim()) return c;
    if (Array.isArray(c)) {
      const t = c.map((p) => (typeof p === "string" ? p : p?.text || "")).join("");
      if (t.trim()) return t;
    }
  }
  return "";
}

export function clean(text) {
  return text.replace(/<think>[\s\S]*?<\/think>/gi, "").replace(/<think>[\s\S]*$/i, "").trim();
}

// Give up on a model that has not answered in time and try the next one.
function withTimeout(promise, ms, label) {
  let t;
  const timer = new Promise((_, reject) => { t = setTimeout(() => reject(new Error(`timed out after ${Math.round(ms / 1000)}s`)), ms); });
  return Promise.race([promise, timer]).finally(() => clearTimeout(t));
}

export async function chat(env, messages, { maxTokens = 1200, timeoutMs = 25_000 } = {}) {
  const models = String(env.CHAT_MODELS || DEFAULT_MODELS).split(",").map((s) => s.trim()).filter(Boolean);
  const opts = env.AI_GATEWAY ? { gateway: { id: env.AI_GATEWAY } } : undefined;
  const errors = [];
  for (const model of models) {
    try {
      const res = await withTimeout(env.AI.run(model, { messages, max_tokens: maxTokens, temperature: 0.1 }, opts), timeoutMs);
      const text = clean(extractText(res));
      if (text) return { text, model };
      errors.push(`${model}: empty response`);
    } catch (e) {
      errors.push(`${model}: ${e?.message || e}`);
    }
  }
  const err = new Error("All models failed. " + errors.join(" | "));
  err.details = errors;
  throw err;
}
