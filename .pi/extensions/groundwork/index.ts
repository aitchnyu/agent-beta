/**
 * Groundwork kickoff — study the codebase immediately, in the background.
 *
 * On a fresh interactive session this injects one user message that tells
 * the agent to spawn the scout subagent with run_in_background and go
 * idle. Why each guard:
 *
 * - reason "startup" with NO previousSessionFile — a bare `pi` launch.
 *   `pi -c` and in-session /new, /resume, /fork fire other reasons (or
 *   carry previousSessionFile) and must never re-study. A transcript
 *   check CANNOT distinguish these: a fresh session already carries
 *   bootstrap entries at session_start (measured: 2).
 * - session file outside .../tasks/ — subagent children ALSO load project
 *   extensions and fire session_start in-process; injecting there races
 *   the child's real task prompt ("Agent is already processing" — the
 *   child errors at spawn). Measured with pi-subagents@22.
 * - stdout is a TTY — in headless `-p` runs the process exits after the
 *   final message and would kill the background study mid-flight.
 *
 * Behavior:
 * - The study overlaps whatever the operator does next, and the main agent
 *   idles at READY, so operator input is serviced immediately (pi queues
 *   follow-ups behind pending work — an agent busy studying would delay
 *   them).
 * - Configured launch: the kickoff fires at boot (model restore triggers
 *   model_change). Fresh VM: right after /model completes setup.
 * - The reviewer prewarm is deliberately NOT here — it only pays off
 *   inside a feature build, so agentconfig/steer.md's workflow triggers
 *   it at stage 4.
 * - Design record: prompts/20261009-prewarm-groundwork-and-reviewer.md
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const KICKOFF = [
	"[groundwork] Start the background study now — then go idle.",
	"",
	"1. Spawn ONE scout subagent in background (subagent tool, subagent_type \"scout\", run_in_background true) with this task:",
	'   "Build a MAP, not a copy: the feature workflow stages, scratch discipline, doc conventions, BaseModel save_plus/row_version, endpoints+Inertia pages pattern, test layout, and the ourapp/ + djangoapp/ + frontend/src/ours/ tree. Read-only. Treat everything as an orientation map that may go stale — never as evidence. Reply with the map."',
	'2. Reply with one line: "Groundwork running in background — READY."',
	"3. End your turn. Do not wait for the scout. When the operator sends a task, work it normally and pull the scout's map with get_subagent_result whenever it would save you orientation reads.",
	"If my first message is already a task, do not send a separate READY — spawn the scout, then do the task.",
].join("\n");

export default function (pi: ExtensionAPI) {
	// First launch on a fresh VM: /login and model/thinking selection happen
	// inside the first session, before any real prompt. So:
	// - defer here when no model exists yet;
	// - fire on model_change — at boot on configured launches (model
	//   restore), after /model on fresh ones;
	// - agent_start is the fallback for a prompt arriving before any
	//   model_change, queued as followUp — a "steer" delivery sent before
	//   the agent is streaming is silently dropped (measured).
	let deferredUntilConfigured = false;

	const isChildSession = (ctx: { sessionManager: { getSessionFile(): string } }) =>
		ctx.sessionManager.getSessionFile().includes("/tasks/");

	pi.on("session_start", async (event, ctx) => {
		if (event.reason !== "startup") return;
		if (event.previousSessionFile) return;
		if (!process.stdout.isTTY) return;
		if (isChildSession(ctx)) return;
		// ctx.model is undefined here even on configured launches (measured) —
		// model restore lands a moment later via model_change.
		deferredUntilConfigured = true;
	});

	pi.on("model_select", async (_event, ctx) => {
		// model_select (NOT model_change — pi has no such extension event) is
		// what fires when the model is restored at boot on configured
		// launches and when /model completes setup on a fresh VM.
		if (!deferredUntilConfigured) return;
		if (isChildSession(ctx)) return;
		if (ctx.model === undefined) return;
		deferredUntilConfigured = false;
		await pi.sendUserMessage(KICKOFF);
	});

	pi.on("agent_start", async (_event, ctx) => {
		if (!deferredUntilConfigured) return;
		if (isChildSession(ctx)) return;
		deferredUntilConfigured = false;
		await pi.sendUserMessage(KICKOFF, { deliverAs: "followUp" });
	});
}
