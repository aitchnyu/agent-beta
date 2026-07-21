Remove collections. Apps will be in one namespace. You can clean the db if moving files around does not work out.

Instead of http://127.0.0.1:8000/apps/a/collection/Page/e, it will be http://127.0.0.1:8000/apps/Page for homepage. No collection in paths. Other endpoints will be under /e.

Propose me the endpoint changes.

-----------------

New prompt:

We will have multiple @setup decorators. It will collect into a list of functions. We must execute them in order. Store the last completed step in application in a new column.

Test by having different versions of an app in different folders as mock. One app will have setup1. Another will have setup1 and setup2. Run first app, verify its installed. Mock path to second app, then verify build will run only second step. 

-------------------

How to make /prompt endpoint as stateless as possible?

shared props - send collection and application name

↑ Back to Trivia Open Facts - should be at top
./run djangomanage buildbackend - allow all the time

Render with css - mention that css has to be rendered

logger = logging.getLogger(__name__) - agent added

Make a real app
Test reset

Give chat to end users?

## Chatting
Make a file browser, py, vue, json, images
Markup with links that open in file browser
Two phases

Responses
    request command
        git commit - confirm
    read file
    write file
    thinking traces
    show raw json?

How to test multi step write operations like creating a family tree?
Does Mypy lint application?

Remove collection - harder to organize shared modules?

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

## Agents and terminals
https://github.com/butlerx/wetty
https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md
https://github.com/tsl0922/ttyd
https://github.com/xtermjs/xterm.js#browser-support
https://xtermjs.org/ - lots of users, including clouds. Plugins for images and links/rich text
https://github.com/open-webui/open-terminal - agent stuff

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