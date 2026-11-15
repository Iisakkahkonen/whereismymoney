// EN/FI parity check: every UI text key must exist in both languages, with the
// same {placeholders}. Run with `npm run check:i18n`; CI runs it before the build.
import { readFileSync } from "node:fs";

const src = readFileSync(new URL("../src/i18n.ts", import.meta.url), "utf8");

function block(name) {
  const start = src.indexOf(`  ${name}: {`);
  if (start < 0) throw new Error(`language block ${name} not found`);
  const end = src.indexOf("\n  },", start);
  const entries = {};
  for (const m of src.slice(start, end).matchAll(/^\s+"([^"]+)":\s*"((?:[^"\\]|\\.)*)",?$/gm)) entries[m[1]] = m[2];
  return entries;
}

const en = block("en");
const fi = block("fi");
const problems = [];
for (const k of Object.keys(en)) if (!(k in fi)) problems.push(`missing in fi: ${k}`);
for (const k of Object.keys(fi)) if (!(k in en)) problems.push(`missing in en: ${k}`);
const vars = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
for (const k of Object.keys(en)) if (k in fi && vars(en[k]) !== vars(fi[k])) problems.push(`placeholders differ: ${k}`);
for (const k of Object.keys(fi)) if (!fi[k].trim()) problems.push(`empty fi text: ${k}`);

if (problems.length) {
  console.error(problems.join("\n"));
  process.exit(1);
}
console.log(`i18n ok: ${Object.keys(en).length} keys in both languages`);
