// Validate one mermaid diagram from stdin: the ENTIRE input must parse as a
// single diagram — "ok" and exit 0, or the parser's error and exit 1. An
// optional ```mermaid / ``` wrapper around the source is stripped.
// No args on a TTY: scan every ```mermaid fence in the default docs
// (ourapp/docs/, ourapp/README.md, docs/mermaid.md, agentconfig/steer.md).
import fs from 'node:fs';
import path from 'node:path';
import { loadMermaid, FENCE } from './_mermaidenv.mjs';

let mermaid;
try {
  mermaid = await loadMermaid('checkmermaid');
} catch (e) {
  console.error(
    `checkmermaid: cannot load jsdom/mermaid (${String(e && e.message ? e.message : e).slice(0, 120)}) — run npm install in frontend/`,
  );
  process.exit(2);
}

let bad = 0;
// No file args and a TTY stdin would block on read(0) forever — the doc
// scan is the only sensible no-arg behavior in that case.
if (process.stdin.isTTY && process.argv.length === 2) {
  const REPO = path.resolve(import.meta.dirname, '..');
  for (const f of [
    ...fs.readdirSync(path.join(REPO, 'ourapp/docs')).map((f) => path.join(REPO, 'ourapp/docs', f)),
    path.join(REPO, 'ourapp/README.md'),
    path.join(REPO, 'docs/mermaid.md'),
    path.join(REPO, 'agentconfig/steer.md'),
  ]) {
    const text = fs.readFileSync(f, 'utf8');
    for (const m of text.matchAll(FENCE)) {
      const line = text.slice(0, m.index).split('\n').length;
      try {
        await mermaid.parse(m[1]);
        console.log(`ok   ${path.relative(REPO, f)}:${line}`);
      } catch (e) {
        bad += 1;
        console.log(`FAIL ${path.relative(REPO, f)}:${line} — ${String(e && e.message ? e.message : e).slice(0, 200)}`);
      }
    }
  }
  process.exit(bad ? 1 : 0);
}

const lines = fs.readFileSync(0, 'utf8').trim().split('\n');
if (lines[0]?.trim().startsWith('```mermaid')) lines.shift();
if (lines.length && lines[lines.length - 1].trim() === '```') lines.pop();

try {
  await mermaid.parse(lines.join('\n'));
  console.log('ok');
} catch (e) {
  console.error(String(e && e.message ? e.message : e).slice(0, 300));
  process.exit(1);
}
