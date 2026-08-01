Yes — both are detectable from state the composable already tracks, and a desktop notification is the right channel (it works when you've tabbed away, which is exactly when you miss a permission prompt). Approach, no code:

Triggers (from existing state in useOpencodeChat):

Permission prompt — a permission block entering state "asked" (the permission.asked event already flows through pushPermission). Fire: "Agent needs approval: <command>".
Idle — streaming transitioning true → false at the end of a turn (the send finally). Fire: "Agent finished" (your move). A pending permission isn't "idle" — that's covered by #1 — so only notify idle when no "asked" card remains.
Channel/mechanism:

Browser Notification API — a real desktop notification (works backgrounded/minimized). Requires the user to grant permission once (Notification.requestPermission()).
Tab-title flash — flip document.title to 🔔 Agent needs approval / ✅ Agent finished (and back), so a backgrounded tab draws the eye.
Optional beep (Audio) for an audible cue.
Gate on document.hidden — only fire when the tab isn't visible, so it's silent while you're actively watching (and loud when you've stepped away). Make this configurable.
Opt-in: a toggle button next to Debug ("Notifications") that calls requestPermission() and stores the preference; off by default (browsers block notifications otherwise).

Where it lives:

A tiny notify(title, body) helper (Notification + title flash + optional sound).
Watchers in the composable (it already owns streaming and the permission blocks) — or in the page via watch.
The toggle button + preference in OpencodeChat.vue.
Two design questions before I code:

Idle meaning — "turn ended / awaiting your next message" (my read), or "no activity for N seconds" (a stuck/timeout detector)? They need different logic.
When to fire — only when the tab is hidden (recommended), or always (incl. a sound when visible)?
Answer those and I'll implement.

---------------
opencode can catch those redirects

./run djangomanage test ourapp.test_playwright --tag playwright
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

"filePath": "/Users/jesvin/dev/ourinstant/copy/frontend/src/main.scss",
  "oldString": "@use \"styles/users\";\n@use \"styles/opencode\";\n@use \"styles/files\";\n@use \"styles/git\";\n@use \"styles/variables\" as *;",
  "newString": "@use \"styles/users\";\n@use \"styles/opencode\";\n@use \"styles/files\";\n@use \"styles/git\";\n@use \"styles/todos\";\n@use \"styles/variables\" as *;"
}
content

{
  "command": "main/run mergescratch",
  "workdir": "/Users/jesvin/dev/ourinstant"
}

./run test ourapp --noinput 2>&1 | tail -n 40

Permissions at bottom

Example app should be a todo app

Vite 8 and Inertia 3 - how to upgrade?

Permission: external_directory - cant see dir sometimes
Permission: edit - cant see file sometimes

Run all tests in checkproject and merge coverage from both stages.
How to require rsync
Why do we need BaseModel?
----------
`./run djangomanage shell -c` - ban this?

Dont show full read output
Dont show full edit output
Reject overly long commands - like using cat instead of write
Parallel command prompts problems?

Readonly mode for whole system, disable get requests too if it mutates data. Do it at middleware level.

Page title for apps

os.environ.get("OPENCODE_BASE_URL", f"http://{_OPENCODE_HOST}:{_OPENCODE_PORT}")

## Error tracking
Log backend in json
Which analysis tool?
Send frontend errors to backend, make it easy to search/filter by line

## Notification center
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Cron and huey
Decorator for tasks

## Task center
Categories and tags

## Chatting
Upload files

### Request-response
Plan - gather requirements
Mention files - link to them
Mention code - show

Show source maps for main and sub apps? How to read errors from them?

How to make /prompt endpoint as stateless as possible?
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

logger = logging.getLogger(__name__) - agent added

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

Huey based background and scheduled tasks?
-----------
Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc

## Deployment
Async support for terminal
Long lived connections for notifications
Tool to analyse error logs and stacktraces
Opencode as service
Whitelist of services
Serve files in fs, accelerate using Caddy
Who is committing to git

## Future
keep login_for_test?
Offline workers and notifications
Error handling for frontend and backend
Whitelist services for outbound connections
Mermaid or D2 renderer for showing table relationships or other diagrams