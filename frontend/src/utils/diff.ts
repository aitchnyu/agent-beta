// Unified-diff helper backed by jsdiff. jsdiff is lazy-imported HERE — the only
// consumer is the opencode edit-diff card (DiffBody), which renders inside the
// SSE-driven chat, NOT during an Inertia page swap, so the lazy load is
// swap-safe and stays out of the host bundle. Callers import this module
// normally; the lazy machinery is confined here, not orchestrated at the call
// site.

/** Build a unified diff of `oldStr` → `newStr` and return it from the first
 *  `@@` hunk, or `null` when the inputs are identical (no hunk to render).
 *  Throws on non-string input (malformed wire data) — the caller surfaces it. */
export async function unifiedHunk(
  oldStr: string,
  newStr: string,
): Promise<string | null> {
  const { createPatch } = await import("diff")
  const patch = createPatch("file", oldStr, newStr, "", "", { context: 3 })
  const at = patch.indexOf("@@")
  return at < 0 ? null : patch.slice(at)
}
