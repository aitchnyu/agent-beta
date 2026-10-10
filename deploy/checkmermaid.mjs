// Validate one mermaid diagram from stdin: the ENTIRE input must parse as a
// single diagram — "ok" and exit 0, or the parser's error and exit 1. An
// optional ```mermaid / ``` wrapper around the source is stripped.
//
// jsdom is required: mermaid assumes a browser, and parsing some diagram
// types (stateDiagram-v2) initializes DOMPurify, which needs a real
// window/document or it throws "addHook is not a function". Rejected
// alternatives: @mermaid-js/parser is pure JS but covers only the
// langium-era diagrams (pie, gitgraph, radar, treemap, …) — not er/state/
// usecase; mermaid-cli needs puppeteer + bundled Chromium.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const REPO = path.resolve(import.meta.dirname, '..');
let JSDOM, mermaid;
try {
  const jsdom = await import(
    pathToFileURL(path.join(REPO, 'frontend/node_modules/jsdom/lib/api.js')).href
  );
  JSDOM = jsdom.JSDOM;
  mermaid = (
    await import(
      pathToFileURL(path.join(REPO, 'frontend/node_modules/mermaid/dist/mermaid.esm.min.mjs')).href
    )
  ).default;
} catch (e) {
  console.error(
    `checkmermaid: cannot load jsdom/mermaid (${String(e && e.message ? e.message : e).slice(0, 120)}) — run npm install in frontend/`,
  );
  process.exit(2);
}
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
mermaid.initialize?.({ startOnLoad: false });

let bad = 0;
// No file args and a TTY stdin would block on read(0) forever — the doc
// scan is the only sensible no-arg behavior in that case.
if (process.stdin.isTTY && process.argv.length === 2) {
  for (const f of [
    ...fs.readdirSync(path.join(REPO, 'ourapp/docs')).map((f) => path.join(REPO, 'ourapp/docs', f)),
    path.join(REPO, 'ourapp/README.md'),
    path.join(REPO, 'docs/mermaid.md'),
    path.join(REPO, 'agentconfig/steer.md'),
  ]) {
    const text = fs.readFileSync(f, 'utf8');
    for (const m of text.matchAll(/```mermaid\b\n([\s\S]*?)```/g)) {
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
