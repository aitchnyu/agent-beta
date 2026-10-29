/**
 * The compact tool — agent-callable compaction between stages.
 *
 * Context is rent: every turn re-sends the transcript. steer.md tells the
 * agent to call `compact` at stage boundaries (after DocsGate approval,
 * after CommitOffer) so the next stage starts from pi's own compaction
 * instead of the full history. Operator decisions survive compaction
 * like every /compact; the custom instructions keep the essentials.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export default function (pi: ExtensionAPI) {
	pi.registerTool({
		name: "compact",
		label: "Compact the session",
		description:
			"Compact this session NOW. Call it at stage boundaries (after DocsGate approval, " +
			"after CommitOffer) or whenever the transcript holds a finished stage's probes, " +
			"deploys, and tool dumps. Operator decisions, doc paths, reviewer agent IDs, and " +
			"the open gate's menu survive; the next stage starts lean. Takes no arguments.",
		promptSnippet: "compact — shed the finished stage's transcript between stages",
		promptGuidelines: [
			"Call compact() at every stage boundary (after DocsGate approval, after CommitOffer) — before starting the next stage's work.",
		],
		parameters: Type.Object({}),
		async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
			ctx.compact({
				customInstructions:
					"Stage-boundary compaction: keep operator decisions verbatim, the feature " +
					"doc paths, reviewer agent IDs + their /tmp map paths, deploy/test state, " +
					"and the open gate's menu options. Drop probe transcripts, tool output " +
					"dumps, and interleaved logs.",
			});
			return {
				content: [{ type: "text", text: "compaction started — the next turn begins lean" }],
				details: undefined,
			};
		},
	});
}
