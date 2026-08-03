When agent is cut off, download latest message.

Run opencode under async worker?
ours/ in frontend - even for utils, configure vite
checkall vs checkcopy - run if anything outside of ours/ and ourapp/ is changed

useOpencodeChat - split into connection management and blocks 
Vite 8 and Inertia 3 - how to upgrade?
More tests in frontend?

Wait till explicitly asked
  Answer those three and I'll implement it in copy/, run ./run checkcopy to green, then deploy via mergescratch.

Base model - just created and updated 

Why do we need BaseModel?

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Example app should be a todo app

Run all tests in checkproject and merge coverage from both stages.

----------

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
Screen mux for dev

## Task center
Categories and tags
Huey based background and scheduled tasks?

## Chatting
Upload files

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

### Request-response
Plan - gather requirements
Mention files - link to them
Mention code - show

Show source maps for main and sub apps? How to read errors from them?

How to make /prompt endpoint as stateless as possible?
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

logger = logging.getLogger(__name__) - agent added
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
Who is committing to git'
Require rsync
Backup regularly - https://www.pghardstorage.org/examples

## Future
keep login_for_test?
Offline workers and notifications
Error handling for frontend and backend
Whitelist services for outbound connections
Mermaid or D2 renderer for showing table relationships or other diagrams