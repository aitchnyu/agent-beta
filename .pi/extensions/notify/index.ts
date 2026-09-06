/**
 * Turn-end + question bell — a single real BEL (\x07) per event via
 * process.stdout.write, exactly like the bell channels of packaged
 * notify extensions (@diegopetrucci/pi-notify's ringBell, @2008muyu/
 * pi-notify's bell). VS Code's xterm.js and Termius ring it; OSC
 * notification sequences are unsupported there, so no banner payload.
 *
 * Hard-won constraints (do not regress):
 * - \a is NOT an escape in JS/TS — "\a" is the letter 'a'. A stray
 *   printable byte between pi-tui's control sequences desyncs its
 *   renderer (dead cursor, stuck TUI). Only \x07 ever.
 * - No child processes, no /dev/tty: out-of-band pty writes corrupted
 *   rendering during debugging. The plain stdout write is the proven
 *   path — it reaches the pty and is what the packages above ship.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
	// Double ring, separated: consecutive BELs coalesce into one sound
	// in VS Code, so the second comes 300ms later — after the settle
	// frame finishes, on a static screen. Both are plain stdout writes
	// of a real BEL (the historical corruption was a stray printable
	// byte, never the write timing).
	const ring = () => {
		process.stdout.write("\x07");
		const encore = setTimeout(() => process.stdout.write("\x07"), 300);
		encore.unref();
	};

	// The agent is fully done — retries, compaction retries, and queued
	// follow-ups all drained. This, not agent_end/turn_end, is the moment
	// it is really waiting on the operator.
	pi.on("agent_settled", async (_event, ctx) => {
		if (ctx.hasUI) ring();
	});

	// A blocking question is on screen: the permission system's asks and
	// any extension select/confirm/input prompt. pi coalesces nested
	// prompts into one outer waiting span, so no double-fires there.
	pi.on("ui_prompt_start", async (_event, ctx) => {
		if (ctx.hasUI) ring();
	});
}
