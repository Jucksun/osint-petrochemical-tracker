// Cheap automatic checks on the model's answer. They catch some mistakes, not all.
export const NO_ANSWER = "The records do not say.";

const MULT = { thousand: 1e3, k: 1e3, million: 1e6, m: 1e6, billion: 1e9, b: 1e9 };

export function dollarValues(text) {
  const out = [];
  for (const m of String(text).matchAll(/\$\s?([\d,]+(?:\.\d+)?)\s?(thousand|million|billion|k|m|b)?\b/gi)) {
    const v = parseFloat(m[1].replace(/,/g, ""));
    if (!Number.isNaN(v)) out.push({ raw: m[0].trim(), value: v * (MULT[(m[2] || "").toLowerCase()] || 1), rounded: !!m[2] });
  }
  return out;
}

export function checkAnswer(answer, { sources, corpus, facilityIds, toolsUsed }) {
  const warnings = [];
  if (answer.trim().replace(/\.$/, "") === NO_ANSWER.replace(/\.$/, "")) return warnings;
  const cited = [...answer.matchAll(/\[(\d{1,2})\]/g)].map((m) => +m[1]);
  if (cited.some((n) => n < 1 || n > sources.length)) warnings.push("The answer cites a source number that does not exist.");
  if (!toolsUsed.length && answer.length > 80) warnings.push("No records were consulted for this answer. Treat it as unverified.");
  const known = dollarValues(corpus).map((d) => d.value);
  for (const d of dollarValues(answer)) {
    const ok = known.some((k) => (d.rounded ? Math.abs(k - d.value) / (k || 1) <= 0.06 : k === d.value));
    if (!ok) warnings.push(`The dollar amount ${d.raw} does not appear in the records retrieved. It may be the model's arithmetic or a mistake.`);
  }
  for (const id of new Set(answer.match(/\b11\d{10}\b/g) || [])) {
    if (!facilityIds.has(id)) warnings.push(`RegistryID ${id} is not in the dataset.`);
  }
  return warnings;
}
