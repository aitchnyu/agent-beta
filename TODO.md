How to run opencode in server mode?
Communication endpoints that can forward messages and streaming stuff
Basic chat page
Configure the opencode, prompt and whitelist


## Chatting
Use opencode in daemon mode with custom config.
Continuous output - have async endpoint?

Web terminals

Command whitelist
Make a file browser, py, vue, json, images

Opencode with prompt
    whats an app
    Markup with links that open in file browser
    Two phases

Responses
    rich md with links
    request command
        git commit - confirm
    read file
    write file
    thinking traces
    show raw json?

How to test multi step write operations like creating a family tree?
Does Mypy lint application?

Remove collection - harder to organize shared modules?
shared props - send collection and application name

-----------
vue3-sfc-loader - try to avoid multiple apps
Ignore back button if its hard

Playwright tests check errors are gone

Indexing for columns

------
Track setup runs - skip the completed ones

NinjaAPI consistency - like error handlers etc

Command to list table ddl and class statement

Log changes to a table - dont make a page for that yet

-----------------

File fields
Renames and null/not null later

## Deployment
Async support for terminal
Long lived connections for notifications
Tool to analyse error logs and stacktraces
Opencode as service

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