#!/usr/bin/env node
// decode-stack.mjs — resolve a minified bundle position back to original
// source through the CURRENT build's vite sourcemaps
// (djangoapp/static/djangoapp/, never served; read from disk).
//
//   node scripts/decode-stack.mjs <file.js-or-url> <line> <col>
//
// Only the current dist is searched; if the bundle hash in the position
// doesn't exist there (the log predates a rebuild), it complains — the
// map for an old hash is gone. For deeper frames, rerun with the next
// file:line:col from the logged stack text. No dependencies:
// node:module.SourceMap.
import { SourceMap } from "node:module"
import fs from "node:fs"
import path from "node:path"

const DIST = path.resolve(
  import.meta.dirname,
  "..",
  "..",
  "djangoapp/static/djangoapp",
)

// Find <basename>.js.map anywhere under the dist (vite nests chunks under
// assets/; the entry sits at the root).
function findMap(ref) {
  const wanted = `${path.basename(ref.split("?")[0], ".map")}.map`
  const stack = [DIST]
  while (stack.length) {
    const dir = stack.pop()
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) stack.push(full)
      else if (entry.name === wanted) return full
    }
  }
  return null
}

// Browser line/col are 1-based; SourceMap.findEntry takes 0-based offsets and
// returns 0-based originals — normalize both ways here.
function decode(file, line, col) {
  const mapPath = findMap(file)
  if (!mapPath) {
    console.error(
      `map not found for ${path.basename(file)} in ${DIST} — log older than the current build?`,
    )
    process.exit(1)
  }
  const sm = new SourceMap(JSON.parse(fs.readFileSync(mapPath, "utf8")))
  const entry = sm.findEntry(line - 1, col - 1)
  if (!entry || entry.originalSource === undefined) return null
  return {
    source: entry.originalSource.replace(/^(\.\.\/)+/, ""),
    line: entry.originalLine + 1,
    col: entry.originalColumn + 1,
    name: entry.name ?? null,
  }
}

const [file, line, col] = process.argv.slice(2)
if (
  !file ||
  !line ||
  !col ||
  !Number.isInteger(Number(line)) ||
  !Number.isInteger(Number(col))
) {
  console.error(
    "usage: decode-stack.mjs <file-or-url> <line> <col>  (line/col are 1-based integers)",
  )
  process.exit(1)
}
const d = decode(file, Number(line), Number(col))
console.log(`${path.basename(file)}:${line}:${col}`)
const where = d
  ? `${d.source}:${d.line}:${d.col}${d.name ? ` (${d.name})` : ""}`
  : "unmapped"
console.log(`  → ${where}`)
