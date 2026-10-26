/**
 * Cap oversized bash results before they enter context.
 *
 * Measured on the 2026-10-25 session: 38 of 233 results over 6k chars
 * held 88% of 935KB of tool-result text (max 46KB ≈ 12k tokens for one
 * deploy/test log) — the driver of the mid-session compaction churn. A
 * result past MAX_CHARS is replaced by its first/last EDGE_LINES plus a
 * pointer to the full output parked on disk; the agent greps or reads
 * ranges of the parked file only when it needs the middle.
 *
 * Bash only — read/edit/write results are deliberate fetches and small
 * (p50 228 chars in the same session).
 */
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const MAX_CHARS = 6000;
const EDGE_LINES = 20;
const PARK_DIR = path.join(os.tmpdir(), "pi-tool-output");

// Clamp one edge (head or tail) to half the budget — a few huge lines
// must not slip the whole payload through.
function clampEdge(text: string): string {
	const budget = MAX_CHARS / 2;
	if (text.length <= budget) return text;
	return text.slice(0, budget) + "…[edge truncated]";
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_result", (event) => {
		if (event.toolName !== "bash") return;
		const text = event.content
			.filter((c): c is Extract<typeof c, { type: "text" }> => c.type === "text")
			.map((c) => c.text)
			.join("\n");
		if (text.length <= MAX_CHARS) return;

		let file: string | undefined;
		try {
			fs.mkdirSync(PARK_DIR, { recursive: true });
			file = path.join(
				PARK_DIR,
				`${event.toolCallId.replace(/[^a-zA-Z0-9_-]/g, "_")}.txt`,
			);
			fs.writeFileSync(file, text);
		} catch (err) {
			// Parking failed (full disk, unwritable tmp): still cap — the
			// pointer line is simply omitted.
			process.stderr.write(`tool-output-cap: parking failed: ${err}\n`);
			file = undefined;
		}

		const lines = text.split("\n");
		const middle =
			lines.length > EDGE_LINES * 2 ? "\n… [middle truncated] …\n" : "\n";
		const capped =
			clampEdge(lines.slice(0, EDGE_LINES).join("\n")) +
			middle +
			clampEdge(lines.slice(-EDGE_LINES).join("\n"));
		const note = file
			? `\n… [tool-output-cap] ${lines.length} lines, ${text.length} chars — full output parked at ${file} (grep it, or read with offset/limit)`
			: `\n… [tool-output-cap] ${lines.length} lines, ${text.length} chars — parking failed, middle omitted`;

		// structuredContent must ride along or pi drops it (bash exposes
		// {output, truncated, full_output_path, exit_code, …}); keep the
		// machine fields, but never repeat the full output there.
		const structured =
			event.structuredContent !== null &&
			typeof event.structuredContent === "object"
				? {
						...(event.structuredContent as Record<string, unknown>),
						output: capped + note,
						full_output_path: file,
					}
				: event.structuredContent;
		return {
			content: [{ type: "text" as const, text: capped + note }],
			structuredContent: structured,
		};
	});
}
