Have ForeignKeyColumn(name, *, target=(collection, app), nullable) - it uses collection, app to resolve table.

The column will refer to the table.

Use a graph library to ensure no cycles, when creating a table that refers to another, or adding a column that refers another table. Report the cycle.

Have a command to export tables as nodes and fk columns as edges. Which graph format can be readily opened?

Prevent deletes to avoid breaking foreign key relationships.

Update readme

How to test multi step write operations like creating a family tree?

--------
Merge both inertia and json endpoints?

`/facts_page?k=v&k2=v2`
`/facts_page/-<rison>-`
- facts app - permalink

shared props - send collection and application name

out = row(fake_context()) - make something better

`./run djangomanage applications` - break into own commands 

How to review? File browser for python, vue, json etc
setup - what all code?
app - what all code?

Are readme instructions complete?
-----------
vue3-sfc-loader - try to avoid multiple apps
Ignore back button if its hard

Playwright tests check errors are gone

Indexing for columns

## Chatting
Web terminals
https://github.com/butlerx/wetty

https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md
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