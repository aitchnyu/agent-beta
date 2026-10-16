// Validate every ```d2 fence in the given markdown FILE(S): all fences
// compile → one "ok <file> (N blocks)" line per file, exit 0. The FIRST
// broken fence → print that block, then the compiler's error, exit 1.
// No args on a TTY: scan every ```d2 fence in the default docs
// (ourapp/docs/, ourapp/README.md, docs/d2.md, docs/reference/ourapp/docs/,
// agentconfig/steer.md) and report ok/FAIL per fence.
//
// The engine is @d2lang/d2's isomorphic node build from frontend/node_modules
// — the exact version the /files viewer renders with. The WASM engine is
// DOM-free: no jsdom/DOMPurify shim to get wrong.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const REPO = path.resolve(import.meta.dirname, '..');

// The pinned viewer build, or exit 2 with the fix hint (a bare
// module-not-found stack would read like a broken diagram).
async function loadD2() {
  try {
    const { D2 } = await import(
      pathToFileURL(path.join(REPO, 'frontend/node_modules/@d2lang/d2/dist/node-esm/index.js')).href
    );
    return new D2();
  } catch (e) {
    console.error(
      `checkmarkdownd2: cannot load @d2lang/d2 (${String(e && e.code ? e.code : e).slice(0, 80)}) — run npm install in frontend/`,
    );
    process.exit(2);
  }
}

// What counts as a d2 fence is decided by marked — the SAME parser (and
// pinned build) the viewer uses — walked from its lexer token stream.
// - whatever marked emits as a `code` token with language `d2` is
//   exactly what RichTextViewer renders, and nothing else
// - regex-free by construction: tilde fences, 4-backtick runs,
//   blockquotes, indent bounds, case, CRLF all match the viewer
// - `token.text` is the dedented source the viewer compiles
async function loadMarked() {
  const { marked } = await import(
    pathToFileURL(path.join(REPO, 'frontend/node_modules/marked/lib/marked.esm.js')).href
  );
  return marked;
}

async function collectD2Blocks(text, marked) {
  const blocks = [];
  const seen = new Set();
  const walk = (tokens) => {
    for (const token of tokens ?? []) {
      if (seen.has(token)) continue;
      seen.add(token);
      if (token.type === 'code' && token.lang === 'd2') {
        blocks.push(token);
      } else if (token.type === 'list') {
        for (const item of token.items ?? []) walk(item.tokens);
        // list.tokens can mirror item tokens on loose lists — seen-set
        // dedupes, but skip the mirror entirely for clarity.
        for (const token2 of token.tokens ?? []) {
          if (token2.type === 'list') walk([token2]);
        }
      } else {
        walk(token.tokens);
      }
    }
  };
  walk(marked.lexer(text));
  // Line numbers: each token's raw appears in document order; a running
  // search offset keeps duplicate-looking blocks indexed correctly.
  let lastIdx = 0;
  for (const token of blocks) {
    const idx = text.indexOf(token.raw, lastIdx);
    lastIdx = idx + token.raw.length;
    token.fenceLine = text.slice(0, idx).split('\n').length;
  }
  return blocks;
}

const d2 = await loadD2();
const marked = await loadMarked();

// d2 compile errors arrive as Error messages holding a JSON array of
// {range, errmsg}; return the first human-readable errmsg (fallback: the
// raw message).
function firstD2Error(e) {
  const raw = String(e && e.message ? e.message : e);
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed[0] && parsed[0].errmsg) {
      return parsed[0].errmsg;
    }
  } catch {
    // not JSON — fall through
  }
  return raw.slice(0, 300);
}

const files = process.argv.slice(2);

// No file args and a TTY stdin: the doc scan. (Without the TTY check, a
// piped no-arg run would block on read(0) forever.)
if (!files.length && process.stdin.isTTY) {
  let bad = 0;
  for (const f of [
    ...fs.readdirSync(path.join(REPO, 'ourapp/docs')).map((f) => path.join(REPO, 'ourapp/docs', f)),
    path.join(REPO, 'ourapp/README.md'),
    path.join(REPO, 'docs/d2.md'),
    ...fs.readdirSync(path.join(REPO, 'docs/reference/ourapp/docs')).map((f) => path.join(REPO, 'docs/reference/ourapp/docs', f)),
    path.join(REPO, 'agentconfig/steer.md'),
  ]) {
    const text = fs.readFileSync(f, 'utf8');
    for (const block of await collectD2Blocks(text, marked)) {
      try {
        await d2.compile(block.text);
        console.log(`ok   ${path.relative(REPO, f)}:${block.fenceLine}`);
      } catch (e) {
        bad += 1;
        console.log(`FAIL ${path.relative(REPO, f)}:${block.fenceLine} — ${firstD2Error(e)}`);
      }
    }
  }
  // The WASM worker keeps node alive past main — shut it down explicitly.
  await d2.dispose();
  process.exit(bad ? 1 : 0);
}

if (!files.length) {
  console.error('usage: checkmarkdownd2.mjs <file.md>… (no args on a TTY: scan the default docs)');
  process.exit(2);
}

for (const f of files) {
  let text;
  try {
    text = fs.readFileSync(f, 'utf8');
  } catch (e) {
    console.error(`checkmarkdownd2: cannot read ${f} (${e.code})`);
    process.exit(2);
  }
  const blocks = await collectD2Blocks(text, marked);
  for (const [i, block] of blocks.entries()) {
    try {
      await d2.compile(block.text);
    } catch (e) {
      console.error(`${f}:${block.fenceLine} — block ${i + 1} of ${blocks.length} does not compile:\n`);
      console.error('```d2');
      console.error(block.text.trimEnd());
      console.error('```');
      console.error(firstD2Error(e));
      process.exit(1);
    }
  }
  console.log(`ok   ${f} (${blocks.length} block${blocks.length === 1 ? '' : 's'})`);
}
// The WASM worker keeps node alive past main — shut it down explicitly.
await d2.dispose();
process.exit(0);
