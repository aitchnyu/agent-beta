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
			"the open gate's menu survive; the next stage starts lean. Pass the next batch in " +
			"continue_with and execute it immediately when this tool returns — never end a " +
			"turn on compact.",
		promptSnippet: "compact — shed the finished stage's transcript between stages",
		promptGuidelines: [
			"Call compact({ continue_with }) at every stage boundary (after DocsGate approval, after CommitOffer) — pass the next batch and execute it the moment the tool returns.",
		],
		parameters: Type.Object({
			continue_with: Type.String({
				description:
					"One line: the next batch to execute immediately after compaction (it survives in the summary).",
			}),
		}),
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			ctx.compact({
				customInstructions:
					"Stage-boundary compaction: keep operator decisions verbatim, the feature " +
					"doc paths, reviewer agent IDs + their /tmp map paths, deploy/test state, " +
					"the open gate's menu options, and the NEXT BATCH verbatim: " +
					params.continue_with +
					". Drop probe transcripts, tool output dumps, and interleaved logs.",
			});
			return {
				content: [
					{
						type: "text",
						text:
							`compaction started — the next turn begins lean. Continue NOW with: ${params.continue_with} — do not end your turn.`,
					},
				],
				details: undefined,
			};
		},
	});
}
