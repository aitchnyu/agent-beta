# Instant app gen

We are making a Django app for users to manage mini apps with backend code, frontend code and individual sqlite dbs.

I will request some features which are present in prevproject. Do not use it for any other reason. Ensure its not covered by linters etc.

## USP
easy to use migrations - why not use Django migrations?
why have Model = generate_model('dir', 'model') instead of using the code?

## Why sqlite and modules?
Can copy apps around
Can replace data

## Examples
Maps and complaints

## Google OAuth (social login)

Credentials live in the database, not in settings or `.env`. After the first
`migrate`, register the Google app once:

```bash
./run djangomanage addgoogleoauth <client_id> <secret>
```

This creates (or updates) a `SocialApp` for `provider="google"` linked to the
current `SITE_ID`, with `scope=["profile","email"]` and
`auth_params={"access_type":"online"}` — the equivalent of the old
`SOCIALACCOUNT_PROVIDERS` block. Re-run it to rotate credentials; no duplicate
row is created.

## Promote a user to superuser

Social-login users can't be superuser at creation. Promote an existing user by
email (matched case-insensitively; sets both `is_superuser` and `is_staff` so
`/admin` works):

```bash
./run python manage.py makesuperuser alice@example.com
```

## Application collections, applications and tables

Mini-apps live in a three-level hierarchy: **collection → application →
table**. Each table is materialised as a real Postgres table named
`zz_<physical_name>`, where `physical_name` is an immutable, creation-time
identifier (`<tablename><unix-seconds>`, generated once). Names start with a
letter and are alphanumeric; the display **name** is the identity (used
directly in URLs), so there are no separate slugs. Because the physical table
is keyed by the immutable `physical_name` and not by the display name,
renaming a collection, application, or table is a plain row update with
**zero DDL** — no physical table is ever renamed.

Manage everything through the `dynamic_models` registry (`djangoapp/models/dynamic.py`),
the single home for all collection/app/table mutation. Each method runs in a
transaction; collection/app renames and table renames are display-name-only
updates with zero DDL. `delete_application` cascade-drops its tables;
`delete_application_collection` refuses a non-empty collection. All arguments
are keyword-only. There is no CLI for creating apps or tables — creation
happens only through the registry, inside a setup script (see
[App framework](#app-framework) below).

Columns are declared with typed column classes (positional `name`, everything
else keyword-only) from `djangoapp.models.columns`. The old `{"name", "type",
...}` dict spec is gone — column objects are the only spec.

```python
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    DateTimeColumn,
    DecimalColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)
from djangoapp.models.dynamic import dynamic_models

dynamic_models.create_application_collection("Inv")

# description is kept (rich text, sanitized on save); tables are created
# inline when given; script is a file path to the app's entry module.
dynamic_models.create_application(
    collection="Inv",
    name="Orders",
    description="...",
)

# create_application_table takes the same column objects (no duplicate or
# existing names):
dynamic_models.create_application_table(
    collection="Inv",
    application="Orders",
    table="Items",
    columns=[CharColumn("code", max_length=10), IntegerColumn("qty", nullable=True)],
)

# add_application_table_columns takes the same column objects too:
dynamic_models.add_application_table_columns(
    collection="Inv",
    application="Orders",
    table="Items",
    columns=[CharColumn("region", max_length=5), DecimalColumn("discount", max_digits=5, decimal_places=2)],
)
dynamic_models.delete_application_table_columns(collection="Inv", application="Orders", table="Items", names=["region"])
dynamic_models.rename_application_table(table, "Products")
dynamic_models.delete_application_table(collection="Inv", application="Orders", table="Products")
dynamic_models.delete_application(app)            # cascade-drops its tables
dynamic_models.delete_application_collection(collection)  # refuses if non-empty
```

### Registry methods

- Collections: `create_application_collection(name)` / `rename_application_collection(collection, new_name)` / `delete_application_collection(collection)` (refuses if non-empty)
- Applications: `create_application(*, collection, name, description="", tables=None)` / `rename_application(collection, old_name, new_name)` / `delete_application(application)` (cascade-drops its tables). The `app.py` path is derived from the apps root + collection/app names (not stored).
- Tables: `create_application_table(*, collection, application, table, columns)` / `add_application_table_columns(*, collection, application, table, columns)` / `delete_application_table_columns(*, collection, application, table, names)` / `rename_application_table(table, new_name)` / `delete_application_table(*, collection, application, table)`

### Read-only `applications` command

Listing/describe only (mutation is on the registry above; there is no CLI for
creating apps or tables):

```bash
./run djangomanage applications list_application_collections
./run djangomanage applications list_application_collection --name Inv
./run djangomanage applications describe_application_table --appcollection Inv --app Orders --name Products
```

- `list_application_collections` — list every collection name
- `list_application_collection --name` — list an app's contents
- `describe_application_table --appcollection --app --name` — print a table's columns (omits physical_name/db_table)

### Column classes

All live in `djangoapp.models.columns`; `name` is positional, every other
field is keyword-only. Column names must start with a letter and contain only
letters/digits.

- `CharColumn(name, *, default, max_length, min_length, choices, nullable)`
- `TextColumn(name, *, default, min_length, max_length, nullable)`
- `IntegerColumn(name, *, default, nullable)`
- `BooleanColumn(name, *, default, nullable)`
- `DecimalColumn(name, *, default, max_digits, decimal_places, nullable)`
- `DateTimeColumn(name, *, nullable)`
- `UserColumn(name, *, nullable)` — ForeignKey to the project `User`

### App framework

Apps are Python modules installed via a setup script. An app lives at
`apps/<collection>/<app>/app.py` (the install dir is gitignored; committed
example apps live under `djangoapp/tests/`). The entry module tags functions
with decorators from `djangoapp.apps`:

```python
from djangoapp.apps import setup, get_endpoint, backend_test, RequestContext

@setup
def setup_app():
    ...  # create_application(collection=..., name=..., tables=...)

@get_endpoint
def facts(request_context: RequestContext) -> SomePydanticSchema:
    model = ...  # get_model()
    return SomePydanticSchema(facts=[...])

@backend_test
def test_facts():
    a = facts(fake_context())
    assert len(a.facts) > 0, "We need facts"
```

Install (and self-test) an app with:

```bash
./run djangomanage installorupdate collectionname/appname
```

This imports the module, runs `@setup`, then runs every `@backend_test`. If
they all pass the app is installed; if `@setup` raises or any `@backend_test`
fails, the whole script is rolled back (DB changes + DDL reverted, dynamic-model
registry cache reset) so a failed install leaves nothing behind.

Build an app's frontend into its derived static folder with:

```bash
./run djangomanage buildapp collectionname/appname
```

This resolves the app, locates its `frontend/` dir (`<apps_root>/<collection>/<app>/frontend/`),
and runs `npm run build -- --emptyOutDir --outDir <static_folder>` so vite writes
`main.js`/`main.css` to `djangoapp/static/djangoapp/apps/<collection>/<app>/`
(gitignored build artifacts). Constant asset path; cache-busting is via the
`?cache_buster=<apps-generation>` the inertia view appends (no hashed filenames).
On success it bumps the apps generation, so a running server picks up the rebuilt
bundle without a restart.

### Endpoints

A `@get_endpoint` function `def name(request_context: RequestContext) -> SomePydanticSchema:`
is served as JSON at:

```
/apps/a/<collection>/<app>/endpoint/get/<function_name>
```

### Superuser views

- `/apps/collections` — list collections
- `/apps/a/<collection_name>/list` — list apps in a collection
- `/apps/a/<collection_name>/<app_name>/manage` — list an app's tables with live row counts

All three require a superuser; anyone else gets a 404.

