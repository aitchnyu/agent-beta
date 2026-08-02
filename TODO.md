For write blocks, dont render it as json, include `filePath` in title. If content, render them as newlines. If oldString and newString, render as single column diff.
Try to make it a new component.
Here is an example response for write
"filePath": "/Users/jesvin/dev/ourinstant/copy/frontend/src/main.scss",
  "oldString": "@use \"styles/users\";\n@use \"styles/opencode\";\n@use \"styles/files\";\n@use \"styles/git\";\n@use \"styles/variables\" as *;",
  "newString": "@use \"styles/users\";\n@use \"styles/opencode\";\n@use \"styles/files\";\n@use \"styles/git\";\n@use \"styles/todos\";\n@use \"styles/variables\" as *;"
}

For bash, show command and title in title
Example:
{
  "command": "main/run mergescratch",
  "workdir": "/Users/jesvin/dev/ourinstant"
}

Have a max height with overflow for both. Scroll to bottom when content is being appended.

Permissions prompt should be rendered just above the text field.

./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Permissions at bottom

Example app should be a todo app

Vite 8 and Inertia 3 - how to upgrade?

Permission: external_directory - cant see dir sometimes
Permission: edit - cant see file sometimes

Run all tests in checkproject and merge coverage from both stages.
How to require rsync
Why do we need BaseModel?
----------

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
Who is committing to git

## Future
keep login_for_test?
Offline workers and notifications
Error handling for frontend and backend
Whitelist services for outbound connections
Mermaid or D2 renderer for showing table relationships or other diagrams