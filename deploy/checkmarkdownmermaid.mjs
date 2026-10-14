// Validate every ```mermaid fence in the given markdown FILE(S): all fences
// parse → one "ok <file> (N blocks)" line per file, exit 0. The FIRST broken
// fence → print that block, then the parser's error, exit 1. Whole-file
// counterpart of checkmermaid.mjs (one diagram from stdin).
import fs from 'node:fs';
import { loadMermaid, FENCE } from './_mermaidenv.mjs';

let mermaid;
try {
  mermaid = await loadMermaid('checkmarkdownmermaid');
} catch (e) {
  console.error(
    `checkmarkdownmermaid: cannot load jsdom/mermaid (${String(e && e.message ? e.message : e).slice(0, 120)}) — run npm install in frontend/`,
  );
  process.exit(2);
}

const files = process.argv.slice(2);
if (!files.length) {
  console.error('usage: checkmarkdownmermaid.mjs <file.md>…');
  process.exit(2);
}

for (const f of files) {
  let text;
  try {
    text = fs.readFileSync(f, 'utf8');
  } catch (e) {
    console.error(`checkmarkdownmermaid: cannot read ${f} (${e.code})`);
    process.exit(2);
  }
  const blocks = [...text.matchAll(FENCE)];
  for (const [i, m] of blocks.entries()) {
    const line = text.slice(0, m.index).split('\n').length;
    try {
      await mermaid.parse(m[1]);
    } catch (e) {
      console.error(`${f}:${line} — block ${i + 1} of ${blocks.length} does not parse:\n`);
      console.error('```mermaid');
      console.error(m[1].trimEnd());
      console.error('```');
      console.error(String(e && e.message ? e.message : e).slice(0, 300));
      process.exit(1);
    }
  }
  console.log(`ok   ${f} (${blocks.length} block${blocks.length === 1 ? '' : 's'})`);
}
