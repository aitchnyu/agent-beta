RowLifecycleTests in test_row_views- for models. Do it for playwright too.

How to test the list and details with playwright?

createapp(columns, '/scriptpath') or createapp(tables={}, '/scriptpath') at create time itself
No need of json
ensure under savepoint


Command to list table ddl and class statement

Separate apps
--------

Have scripts/
Just use the methods? Remove some plumbing commands
Run script in transaction. Dont let it run plainly.
Ensure scripts/tests are reversible

Log changes to a table - dont make a page for that yet

-----------------

Dynamic modules that can run functions
Agent makes these modules
Vue apps
Agent can test apps and deploy

create 

FK later
Renames and null/not null later

type - 
    char - nope
    text - 
    int
    decimal
    date
    fk

SCHEMA_SERIALIZERS

ApplicationHistory
created ApplicationDirectory
renamed ApplicationDirectory
deleted ApplicationDirectory

ApplicationDirectory - name
App - name, desc - rich text

Have ApplicationDirectory and Application
Application user - role: admin etc

Creating app needs the fs state.

/app/folder/appname

app/
    functions.py
    db.sqlite3
    vue app (need to build something with entry.js)
    tests

Migration and schema evolution?

How to generate db and queries?

## Future
keep login_for_test?