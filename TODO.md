Base model - just created and updated 
Just log stuff. .save_with_logs(user, updated=True) and .delete_with_logs
How to test it?
Test git and file manager too without mocks
Avoid some linting errors

Split models and views as separate files. Same for tests.
Git page for copy

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99

Page title for apps - as component

Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc

When agent is cut off due to redeployment, download latest message to show to user?

How to configure provider and model for Opencode?

docs/ for llm. Have feature catalog.
Models and views are multi-file modules.
ours/ in frontend - even for utils, configure vite
checkall vs checkcopy - run if anything outside of ours/ and ourapp/ is changed

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Example app should be bigger
Include logging, including storing in db

Run all tests in checkproject and merge coverage from both stages.

Readonly mode for whole system, disable get requests too if it mutates data. Do it at middleware level.

## Error tracking
Log backend in json
Which analysis tool?
Send frontend errors to backend, make it easy to search/filter by line
Show source maps for main and sub apps? How to read errors from them?

## Task center
Categories and tags

## Notification center
Service worker and PWA?
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Cron and huey
Huey based background and scheduled tasks?
Decorator for tasks
Screen mux for dev

## Chatting
Upload files

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

logger = logging.getLogger(__name__) - agent added

## Deployment
Tool to analyse error logs and stacktraces
Opencode as service
Whitelist of services
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections

## Future
keep login_for_test?
Mermaid or D2 renderer for showing table relationships or other diagrams