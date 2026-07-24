Whats next app? A todo app?

os.environ.get("OPENCODE_BASE_URL", f"http://{_OPENCODE_HOST}:{_OPENCODE_PORT}")
Log them properly
Playwright tests - `expect(page.get_by_text(_ENTRY_DIR)).to_be_visible()`

Shared widgets and components, layout etc
Tasks center - categories

## Chatting
Diff and blame renderer?
Upload files

### Request-response
Plan - gather requirements
Mention files - link to them
Mention code - show 
Mermaid or d2?

Install marked, then in RenderRawHtml: sanitizeHtml(marked.parse(text)) - since model is apparently rendering md in spite of instructions

Show source maps for main and sub apps? How to read errors from them?

How to make /prompt endpoint as stateless as possible?
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

logger = logging.getLogger(__name__) - agent added

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

How to test multi step write operations like creating a family tree?
Does Mypy lint application?

Huey based background and scheduled tasks?
-----------
Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc

vue3-sfc-loader - try to avoid multiple apps
Ignore back button if its hard

Playwright tests check errors are gone

Indexing for columns

------
Command to list table ddl and class statement

Log changes to a table - dont make a page for that yet, can query from commandline
-----------------

File fields
Renames and null/not null later

## Deployment
Async support for terminal
Long lived connections for notifications
Tool to analyse error logs and stacktraces
Opencode as service
Whitelist of services
Serve files in fs, accelerate using Caddy

## Separate frontends
Very easy to build individually, can add new libraries etc

Challenges
How to add common behavior and style? Like a notification dropdown
Each app has to be kept updated separately, need to compile
Command to audit all apps at once?

## Future
keep login_for_test?
Offline workers and notifications
Error handling for frontend and backend
Whitelist services for outbound connections
Mermaid or D2 renderer for showing table relationships or other diagrams