import { describe, expect, it } from "vitest"
import { parseSsePayloads } from "./parseSse"

// Build a ReadableStream from string chunks (optionally splitting a frame).
function stream(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(new TextEncoder().encode(c))
      controller.close()
    },
  })
}

async function collect(body: ReadableStream<Uint8Array>) {
  const out: Record<string, unknown>[] = []
  for await (const p of parseSsePayloads(body)) out.push(p)
  return out
}

describe("parseSsePayloads", () => {
  it("parses a single data: frame", async () => {
    const body = stream(['data: {"type":"a"}\n\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "a" }])
  })

  it("joins multi-line data: into one payload", async () => {
    const body = stream(['data: {"type":\ndata: "b"}\n\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "b" }])
  })

  it("strips one leading space after data: (SSE spec)", async () => {
    const body = stream(['data: {"type":"c"}\n\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "c" }])
  })

  it("normalizes CRLF frame separators", async () => {
    const body = stream(['data: {"type":"d"}\r\n\r\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "d" }])
  })

  it("skips malformed JSON frames without throwing", async () => {
    const body = stream(['data: not-json\n\ndata: {"type":"e"}\n\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "e" }])
  })

  it("ignores frames with no data: line", async () => {
    const body = stream(['event: ping\n\ndata: {"type":"f"}\n\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "f" }])
  })

  it("reassembles a frame split across chunks", async () => {
    const body = stream(['data: {"ty', 'pe":"g"}\n\n'])
    await expect(collect(body)).resolves.toEqual([{ type: "g" }])
  })
})
