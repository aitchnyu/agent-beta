Build - can run on real db 
We cant create a context

Rollback - writes are rolled back
    todos - writes confirmed, not present
    create issue and redirect - created 100, redirect fails
    create family tree - 

----------

No. A browser-caused DB change is not rolled back by the savepoint.

The savepoint (transaction.savepoint()) lives on the command's DB connection (the main thread's, the one transaction.atomic() wraps). The browser doesn't write on that connection — it drives the server, which runs on its own separate connection with autocommit ON. So a click that triggers a write commits immediately on the server's connection, and that's a different connection than the one the savepoint controls. Transactions/savepoints are per-connection; the command's savepoint can't touch a commit on the server's connection.

So after the drive:

In-process writes (ORM on the command's connection, inside the savepoint) → rolled back. ✓ (that's the smoke probe)
Browser→server writes (the click's POST) → persist. ✗
This is exactly why write-then-verify-via-browser is impossible here, and why the buildapp guarantee is scoped to "in-process writes never commit" (buildapp.py docstring) — a @playwright_test that triggers a server write will leak it past the drive. App tests must stay read-only with respect to the server (or the test author owns cleaning up any server-side write).

-------------
aihere stuff

Setup must be idempotent using setup function names
Tests with failed browser

rename
    installorupdate - buildbackend
    buildapp - buildfrontend

--------
Have a table foreignkey type - target specific table
Does fk get automatic indexes?
Prevent deletes - find downstream

Relationships - detect and report cycles

Merge both inertia and json endpoints?

`/facts_page?k=v&k2=v2`
`/facts_page/-<rison>-`
- facts app - permalink

shared props - send collection and application name

Why abstract connection.schema_editor()?
out = row(fake_context()) - make something better

`./run djangomanage applications` - break into own commands 

How to review? File browser for python, vue, json etc
setup - what all code?
app - what all code?

Are readme instructions complete?
User management in readme
-----------

Playwright tests check errors are gone

Indexing for columns

## Chatting
Web terminals
https://github.com/butlerx/wetty

https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md
Command whitelist
Make a file browser?

Opencode with prompt
    whats an app
    Markup with links that open in file browser
    Two phases

Responses
    rich md with links
    request command
        git commit - confirm
    thinking traces

------
Pending:
post/inertia endpoints
Track setup runs - skip the completed ones

ensure dynamic functions are under savepoint
Test all api endpoints
get, post endpoint
/app/appname/get_endpoint/search_users/-query:anilk-
@test for test functions

_create_column_row - long function
NinjaAPI consistency - like error handlers etc

Command to list table ddl and class statement

Log changes to a table - dont make a page for that yet

-----------------

Dynamic modules that can run functions
Agent makes these modules
Vue apps
Agent can test apps and deploy

create 

FK later
Files too
Renames and null/not null later

type - 
    char - nope
    text - 
    int
    decimal
    date
    fk

SCHEMA_SERIALIZERS

Migration and schema evolution?

How to generate db and queries?

## Future
keep login_for_test?
Offline workers and notifications