import test from "node:test";
import assert from "node:assert/strict";
import { renderMarkdown, safeUrl, safeImage, esc } from "../public/render.js";

const R = (t, sources = []) => renderMarkdown(t, { sources });

test("html and script injection is escaped", () => {
  const h = R('<script>alert(1)</script> <img src=x onerror=alert(1)> **<b>x</b>**');
  assert.ok(!/<script|<img src=x|<b>/.test(h)); assert.match(h, /&lt;script&gt;/);
});

test("only https and same-site links survive", () => {
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("data:text/html,<script>1</script>"), null);
  assert.equal(safeUrl("http://insecure.example/"), null);
  assert.equal(safeUrl("//evil.example/x"), null);
  assert.equal(safeUrl("/\\evil.example"), null);
  assert.equal(safeUrl("/api/export.csv?state=TX"), "/api/export.csv?state=TX");
  assert.match(safeUrl("https://echo.epa.gov/x"), /^https:\/\/echo\.epa\.gov/);
  const h = R("[click](javascript:alert(1)) and [ok](https://www.sec.gov/a)");
  assert.ok(!h.includes("javascript:")); assert.match(h, /href="https:\/\/www\.sec\.gov\/a"/); assert.match(h, /rel="noopener noreferrer"/);
});

test("images only from approved hosts; attribute breakout is escaped", () => {
  assert.ok(safeImage("https://services.arcgisonline.com/x.jpg"));
  assert.equal(safeImage("https://evil.example/pixel.gif"), null);
  assert.equal(safeImage("https://services.arcgisonline.com.evil.example/x"), null);
  const bad = R("![x](https://evil.example/track.png)");
  assert.ok(!bad.includes("<img")); assert.match(bad, /image blocked/);
  const good = R('![a"onerror="alert(1)](https://echo.epa.gov/p.png)');
  assert.ok(!/onerror="alert/.test(good)); assert.match(good, /<img class="inline-img" src="https:\/\/echo\.epa\.gov\/p\.png"/);
});

test("citation chips link to known sources and stay plain otherwise", () => {
  const src = [{ n: 1, title: "10-K", url: "https://www.sec.gov/doc" }];
  const h = R("Said so [1] but not [2].", src);
  assert.match(h, /<a class="cite" href="https:\/\/www\.sec\.gov\/doc"[^>]*>\[1\]<\/a>/); assert.match(h, /not \[2\]\./);
});

test("lists, bold, code fences and headings render", () => {
  const h = R("# Title\n- one\n- **two**\n\n1. a\n2. b\n```\n<b>raw</b>\n```");
  assert.match(h, /<p class="h">Title/); assert.match(h, /<ul><li>one<\/li><li><strong>two<\/strong><\/li><\/ul>/);
  assert.match(h, /<ol><li>a<\/li><li>b<\/li><\/ol>/); assert.match(h, /<pre>&lt;b&gt;raw&lt;\/b&gt;<\/pre>/);
});

test("esc handles all five characters and non-strings", () => {
  assert.equal(esc(`&<>"'`), "&amp;&lt;&gt;&quot;&#39;"); assert.equal(esc(null), ""); assert.equal(esc(5), "5");
});
