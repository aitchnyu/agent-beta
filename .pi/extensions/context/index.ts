/**
 * steer.md injection — the one piece no catalog package provides.
 *
 * pi auto-loads AGENTS.md/CLAUDE.md as context; this repo deliberately
 * ships neither (.pi/steer.md is the only steering file, and it
 * must NOT become AGENTS.md — other agent tools would auto-read it).
 * This extension appends steer.md to the system prompt every turn.
 *
 * All permission policy lives in @gotgenes/pi-permission-system
 * (.pi/extensions/pi-permission-system/config.json); subagents and their
 * permission forwarding come from @gotgenes/pi-subagents. This extension
 * is intentionally ONLY the context wiring.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const REPO_ROOT = process.env.PI_REPO_ROOT ?? process.cwd();
const STEER_MD = path.join(REPO_ROOT, ".pi/steer.md");
const BEGIN = "<!-- steer-begin -->";
const END = "<!-- steer-end -->";

function stripSteer(prompt: string): string {
    const begin = prompt.indexOf(BEGIN);
    if (begin === -1) return prompt;
    const end = prompt.indexOf(END, begin);
    const tail = end === -1 ? "" : prompt.slice(end + END.length);
    return prompt.slice(0, begin) + tail;
}

export default function (pi: ExtensionAPI) {
    pi.on("before_agent_start", async (event) => {
        try {
            const steer = fs.readFileSync(STEER_MD, "utf-8");
            // A subagent's prompt is its agent file; strip any inherited
            // steer block so children run lean regardless of provider.
            if (event.systemPrompt.includes("<agent_instructions>")) {
                const stripped = stripSteer(event.systemPrompt);
                if (stripped === event.systemPrompt) return;
                return { systemPrompt: stripped };
            }
            if (event.systemPrompt.includes(BEGIN)) return;
            return { systemPrompt: `${event.systemPrompt}\n\n${BEGIN}\n${steer}\n${END}` };
        } catch {
            process.stderr.write(`steer.md missing at ${STEER_MD}\n`);
            return;
        }
    });
}
