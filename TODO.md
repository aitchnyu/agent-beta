How to make /prompt endpoint as stateless as possible?

Track setup runs - skip the completed ones
shared props - send collection and application name

↑ Back to Trivia Open Facts - should be at top
./run djangomanage buildbackend - allow all the time

Render with css - mention that css has to be rendered

Can we reset session or kill agent?

Have checkpoint for running setup repeatedly?
```python
if savepoint('')
```

logger = logging.getLogger(__name__) - agent added

Make a real app

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