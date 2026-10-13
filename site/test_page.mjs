// Headless self-tests for the simulator page (Node 18+, no packages).
// Usage: node site/test_page.mjs site/index.new.html
import { readFileSync } from "node:fs";
import vm from "node:vm";

const file = process.argv[2] || "site/index.html";
const html = readFileSync(file, "utf8");
const cut = (a, b) => { const i = html.indexOf(a), j = html.indexOf(b); if (i < 0 || j < 0) throw new Error(`markers ${a} / ${b} not found`); return html.slice(i, j); };
const code = [cut("// ===== DATA =====", "// ===== END DATA ====="), cut("// ===== MATH =====", "// ===== END MATH ====="), cut("// ===== TESTS =====", "// ===== END TESTS ====="),
  "return runSelfTests(M, DATA);"].join("\n");
// Run in the main context (vm sandboxes slow global lookups ~10x and would distort the timing test).
const result = new Function(code)();
let fails = 0;
for (const r of result) { if (!r.ok) fails++; console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}  ·  ${r.detail}`); }
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
for (const s of scripts) new vm.Script(s, { filename: "inline-script" }); // syntax check of the whole page script
console.log(`${result.length - fails}/${result.length} passed; page script parses`);
process.exit(fails ? 1 : 0);
