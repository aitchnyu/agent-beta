/**
 * Reviewer-manager — prewarmed reviewers that cannot silently rot.
 *
 * Two Oct 28 sessions prewarmed reviewers that expired before the review
 * round (pi-subagents releases idle background agents; a busy main agent
 * cannot ping them). This extension tracks every background REVIEWER
 * spawn (the prewarms — scout and other non-reviewer agents are ignored)
 * and exposes the `reviewers` tool: status for each held prewarm, plus a
 * refresh that resumes each with a keepalive via nested subagent calls.
 * A resume that fails (the retention window already lapsed) respawns the
 * prewarm fresh with its original prompt, so a refresh call can never
 * end with a dead reviewer.
 *
 * steer.md calls reviewers({refresh: true}) at the checkpoints where
 * staleness bites: DocsGate, code-stage start, and the FinalReport.
 * (v2 idea, not expressible today: a timer-driven keepalive — pi exposes
 * no tool execution outside a tool call, so refresh stays agent-initiated.)
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

interface Prewarm {
	agentId: string;
	agentType: string;
	sprompt: string;
	spawnedAt: number;
	lastRefreshAt: number;
}

/** Minutes since the prewarm's last (spawn or refresh). */
function idleMinutes(pre: Prewarm): number {
	return Math.round((Date.now() - pre.lastRefreshAt) / 60_000);
}

const SPAWN_ID = /Agent started in background\.\s*Agent ID:\s*(\S+)/;

export default function (pi: ExtensionAPI) {
	const prewarms = new Map<string, Prewarm>();
	// toolCallId -> spawn args, joined to the agent id on execution end.
	const pendingSpawns = new Map<string, { agentType: string; sprompt: string }>();

	// Capture reviewer prewarm SPAWNS from their call args.
	pi.on("tool_call", (event) => {
		const call = event as { toolName?: string; input?: Record<string, unknown>; parentToolCallId?: string };
		if (call.toolName !== "subagent" || call.parentToolCallId) return; // not ours, not a fresh spawn
		const input = call.input ?? {};
		if (input.run_in_background !== true) return;
		const agentType = String(input.subagent_type ?? "");
		if (!agentType.startsWith("reviewer")) return; // scouts and friends are not prewarms
		pendingSpawns.set(event.toolCallId, { agentType, sprompt: String(input.prompt ?? "") });
	});

	// Join the spawn's agent id from its result text.
	pi.on("tool_execution_end", (event) => {
		if (event.toolName !== "subagent" || event.isError) return;
		const spawn = pendingSpawns.get(event.toolCallId);
		if (!spawn) return;
		pendingSpawns.delete(event.toolCallId);
		const result = event.result as { output?: Array<{ text?: string }>; text?: string } | undefined;
		const text = result?.output?.map((part) => part.text ?? "").join("\n") ?? result?.text ?? "";
		const match = text.match(SPAWN_ID);
		if (!match) return;
		const now = Date.now();
		prewarms.set(match[1], {
			agentId: match[1],
			agentType: spawn.agentType,
			sprompt: spawn.sprompt,
			spawnedAt: now,
			lastRefreshAt: now,
		});
	});

	pi.registerTool({
		name: "reviewers",
		label: "Prewarmed reviewer status + keepalive",
		description:
			"Status of every prewarmed reviewer subagent, and optionally a keepalive refresh " +
			"that resumes each one (nested subagent calls) so the pi-subagents retention window " +
			"never expires them mid-feature. A resume that already expired respawns the prewarm " +
			"fresh with its original prompt. Call with refresh=true at DocsGate, at code-stage " +
			"start, and with the FinalReport — the same checkpoints where staleness bites.",
		promptSnippet: "reviewers — prewarm status; refresh=true keeps reviewers from aging out",
		promptGuidelines: [
			"Call reviewers({refresh: true}) at DocsGate, at code-stage start, and when the FinalReport lands — it keepalives every prewarmed reviewer (respawning any that expired).",
		],
		parameters: Type.Object({
			refresh: Type.Optional(
				Type.Boolean({ description: "Resume each prewarm with a keepalive ping (default false)." }),
			),
		}),
		async execute(_toolCallId, params, signal, _onUpdate, ctx) {
			const held = [...prewarms.values()];
			if (held.length === 0) {
				return { content: [{ type: "text", text: "no prewarmed reviewers held" }], details: undefined };
			}
			const lines: string[] = [];
			for (const pre of held) {
				const ageMin = Math.round((Date.now() - pre.spawnedAt) / 60_000);
				if (params.refresh !== true) {
					lines.push(`${pre.agentType} ${pre.agentId}: held ${ageMin}m, idle ${idleMinutes(pre)}m`);
					continue;
				}
				const outcome = await ctx.executeTool(
					"subagent",
					{
						resume: pre.agentId,
						prompt:
							"[reviewer-manager keepalive] holding for the review round — " +
							"no new work. Reply with exactly: STORED",
					},
					{ signal },
				);
				const failed = (outcome as { isError?: boolean }).isError === true;
				if (!failed) {
					pre.lastRefreshAt = Date.now();
					lines.push(`${pre.agentType} ${pre.agentId}: refreshed (held ${ageMin}m)`);
					continue;
				}
				// The retention window already lapsed — respawn with the original prompt.
				const respawn = await ctx.executeTool(
					"subagent",
					{ subagent_type: pre.agentType, run_in_background: true, prompt: pre.sprompt },
					{ signal },
				);
				const text = JSON.stringify(respawn);
				const newId = text.match(SPAWN_ID)?.[1];
				if (newId) {
					const now = Date.now();
					prewarms.delete(pre.agentId);
					prewarms.set(newId, { ...pre, agentId: newId, spawnedAt: now, lastRefreshAt: now });
					lines.push(`${pre.agentType} ${pre.agentId}: expired → respawned as ${newId}`);
				} else {
					lines.push(`${pre.agentType} ${pre.agentId}: expired → RESPAWN FAILED (spawn fresh yourself)`);
				}
			}
			return { content: [{ type: "text", text: lines.join("\n") }], details: undefined };
		},
	});
}
