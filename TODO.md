Install marked, then in RenderRawHtml: sanitizeHtml(marked.parse(text))

Show source maps?

How to make /prompt endpoint as stateless as possible?
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

logger = logging.getLogger(__name__) - agent added

Make a real app

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

## Chatting
Apps is not ignored in vcs
Make a file browser, py, vue, json, images
Available only to superruser, intended for /apps only
Diff and blame renderer?
Render images in md
Markup with links that open in file browser

Responses
    request command
        git commit - confirm
    read file
    write file
    thinking traces
    show raw json?

How to test multi step write operations like creating a family tree?
Does Mypy lint application?

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