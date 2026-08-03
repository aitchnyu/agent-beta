// Pure stream → parsed SSE payloads. Extracted from the transport so it's
// unit-testable in isolation (no Vue/axios). Reads the fetch body, frames on
// `\n\n` (normalising CRLF/CR → LF so a proxy that rewrites line endings can't
// hang the spinner), joins multi-`data:` lines, and yields each frame's parsed
// JSON. Malformed frames are skipped. The reader lock is released in `finally`
// (also on an early `break` from the consumer). No Vue/state — the caller owns
// validation + dispatch.
export async function* parseSsePayloads(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<Record<string, unknown>> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  const drain = (): Record<string, unknown>[] => {
    const frames: Record<string, unknown>[] = []
    let idx: number
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const dataLines = frame.split("\n").filter((l) => l.startsWith("data:"))
      if (!dataLines.length) continue
      // SSE may split JSON across several `data:` lines; join them and skip a
      // frame that fails to parse so one bad frame can't kill the stream.
      // Strip exactly one leading space after `data:` (SSE spec; mirrors the
      // backend's `_iter_sse` in opencode.py).
      const payload = dataLines
        .map((l) => l.slice(5).replace(/^ /, ""))
        .join("\n")
      try {
        frames.push(JSON.parse(payload) as Record<string, unknown>)
      } catch {
        continue
      }
    }
    return frames
  }
  try {
    let chunk = await reader.read()
    while (!chunk.done) {
      buffer += decoder
        .decode(chunk.value, { stream: true })
        .replace(/\r\n|\r/g, "\n")
      for (const payload of drain()) yield payload
      chunk = await reader.read()
    }
    // Flush any final multi-byte sequence split across the last chunk boundary
    // — without this, a UTF-8 char split exactly on the boundary is dropped and
    // the containing JSON frame fails to parse.
    buffer += decoder.decode().replace(/\r\n|\r/g, "\n")
    for (const payload of drain()) yield payload
  } finally {
    // Release the reader's lock so the underlying fetch is torn down even when
    // the loop throws (abort, network drop). Without this the connection
    // lingers until GC.
    await reader.cancel().catch(() => {})
  }
}
