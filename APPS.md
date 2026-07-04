This will guide you, an agent to make apps and install them. These instructions have priority over AGENTS.md.  

Apps are in `apps/`.  

```
apps/
    collectionname/
        appname/
            app.py
```

We will add Vue apps in future in `appname/`.

When we ask to create an app, you should create the files in `collectioname/appname/`.   
Main entry is in app.py

```python
<imports>

# this, and other decorators tag the function
@setup
def setup_app():
    ...create_application(...., script='collectionname/appname/app.py')

@get_endpoint
def facts(request_context: RequestContext) -> APydanticSchema:
    model = ...get_model()
    facts = model.objects.filter()
    return APydanticSchema(facts=['...', '...'])

@backend_test
def test_facts():
    a = facts(fake_context()):
    assert len(a.facts) > 0, "We need facts"

```

We will run `./run setup collectionname/appname/app.py`. It will import the
module. It runs the `@setup` function and runs the functions marked
`@backend_test`. If they all pass, the app is installed. If any `@backend_test`
fails (or `@setup` raises), the whole script is rolled back: the setup's
database changes and DDL are reverted and the dynamic-model registry cache is
reset, so a failed install leaves nothing behind. An agent can use this as a
feedback loop.

# New changes
We will delete this section soon.

## Changed db methods

Change the signature of some existing methods to this. All arguments are
keyword-only. `description` is kept (rich text, sanitized on save). `script`
is a file path, not a dotted module path.

```python
.create_application(
    collection=coname,
    name=appname,
    description="...",
    tables={
        "tablename1": [
            CharColumn("name"),
            TextColumn("name"),
            IntegerColumn("name", nullable=True),
            BooleanColumn("name"),
            DecimalColumn("name", max_digits=8, decimal_places=2, nullable=True),
            DateTimeColumn("name"),
            UserColumn("name", nullable=True),
        ],
        "tablename2": [...],
    },
    script="collectionname/appname/app.py",
)

.create_application_table(
    collection=coname,
    application=appname,
    table=table,
    columns=[
        CharColumn("name"),
        TextColumn("name"),
        IntegerColumn("name", nullable=True),
        BooleanColumn("name"),
        DecimalColumn("name", max_digits=8, decimal_places=2, nullable=True),
        DateTimeColumn("name"),
        UserColumn("name", nullable=True),
    ],
)
```

Only `name` is positional on a column class; everything else is a keyword arg.
The column classes must validate everything and provide good type safety. The
old `{"name", "type", ...}` dict specs are removed entirely — column objects
are the only spec.

There is no CLI for creating tables (or apps); creation happens only through
the registry, i.e. inside a setup script. Mention all those classes and
dynamic-model methods in the README.

We have a `./run setup <path>` (see below).

## How to test
Ship an example app as a fixture under `djangoapp/tests/` (the `apps/` install
dir is gitignored, so the committed example lives in the test tree). It is the
"random fact" app: it calls `/apps/a/Facts/Animals/endpoint/get/random_fact`
and gets `{"fact": "Cats have 3 eyelids"}`; two runs tend to return different
facts. Assert assuming the randomness will not return the same thing twice.
Yes, use a table to store the facts.

Write enough `@backend_test` functions to cover all functionalities of endpoints.

## Endpoints
`@get_endpoint` needs a function that `def function_name(request_context: RequestContext) -> SomePydanticSchema:`.  

It can be accessed over http with `/apps/a/<collectionname>/<appname>/endpoint/get/<function_name>`.  

We will make Vue apps which utilize this


