// Shared bootstrap for the mermaid validators (checkmermaid,
// checkmarkdownmermaid): loads mermaid with a jsdom browser environment.
//
// jsdom is required: mermaid assumes a browser, and parsing some diagram
// types (stateDiagram-v2) initializes DOMPurify. The globals must exist
// BEFORE importing mermaid — DOMPurify binds window at import time;
// import-first order leaves stateDiagram-v2 crashing with
// "Pt.addHook is not a function". Rejected alternatives: @mermaid-js/parser
// is pure JS but covers only the langium-era diagrams (pie, gitgraph,
// radar, treemap, …) — not er/state/usecase; mermaid-cli needs puppeteer +
// bundled Chromium.
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const REPO = path.resolve(import.meta.dirname, '..');

export async function loadMermaid(label) {
  const jsdom = await import(
    pathToFileURL(path.join(REPO, 'frontend/node_modules/jsdom/lib/api.js')).href
  );
  const dom = new jsdom.JSDOM('<!doctype html><html><body></body></html>');
  globalThis.window = dom.window;
  globalThis.document = dom.window.document;
  const mermaid = (
    await import(
      pathToFileURL(path.join(REPO, 'frontend/node_modules/mermaid/dist/mermaid.esm.min.mjs')).href
    )
  ).default;
  mermaid.initialize?.({ startOnLoad: false });
  return mermaid;
}

// What the /files viewer renders as a diagram fence — the ground truth both
// validators check against.
export const FENCE = /```mermaid\b\n([\s\S]*?)```/g;
