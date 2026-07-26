how is users pagination?
/git
/git/uncommitted
/git/commits (paginated, 25)
/git/commits/cid
/git/commits/cid/filename

Test in fakeapps/ dir

Render relationships in fe? Focus on table
Does readme tell how to render tables?

Shell command deleting app by itself?
`./run djangomanage shell -c` - ban this?
How to show networks of tables
Delete app commands
Dont mark something as done if network fails
Add a readme?
Dont commit before asking
Dont show full read output
Dont show full edit output
Reject overly long commands - like using cat instead of write
Ensure long commands have newlines

Readonly mode for whole system

Page title for apps

./run typecheck
uv run mypy apps/TodoList2App/app.py
playwright_test - it uses existing db, reverts

os.environ.get("OPENCODE_BASE_URL", f"http://{_OPENCODE_HOST}:{_OPENCODE_PORT}")

Tasks center - categories
Shared widgets and components, layout etc
Share error tracking in FE

## Notification center
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

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
Who is committing to git

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