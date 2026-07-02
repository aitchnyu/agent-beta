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
`delete_application_collection` refuses a non-empty collection.

```python
from djangoapp.models.dynamic import dynamic_models

dynamic_models.create_application_collection("Inv")
dynamic_models.create_application("Inv", "Orders", desc="...")

# One column spec per type — every field each type accepts is shown.
dynamic_models.create_application_table(
    "Inv", "Orders", "Items",
    columns=[
        {"name": "code", "type": "char", "default": "X", "max_length": 10, "choices": ["X", "Y"]},
        {"name": "note", "type": "text", "default": "", "min_length": 0, "max_length": 1000},
        {"name": "qty", "type": "integer", "default": 1, "nullable": True},
        {"name": "active", "type": "boolean", "default": False},
        {"name": "price", "type": "decimal", "default": "1.50", "nullable": False,
         "max_digits": 8, "decimal_places": 2},
        {"name": "due", "type": "datetime", "nullable": True},
        {"name": "owner", "type": "user", "nullable": True},
    ],
)

# add_application_table_columns takes the same spec shape (no duplicates, no
# existing names):
dynamic_models.add_application_table_columns(
    "Inv", "Orders", "Items",
    columns=[
        {"name": "region", "type": "char", "max_length": 5},
        {"name": "discount", "type": "decimal", "max_digits": 5, "decimal_places": 2},
    ],
)
dynamic_models.delete_application_table_columns("Inv", "Orders", "Items", ["region"])
dynamic_models.rename_application_table(table, "Products")
dynamic_models.delete_application_table("Inv", "Orders", "Products")
dynamic_models.delete_application(app)            # cascade-drops its tables
dynamic_models.delete_application_collection(collection)  # refuses if non-empty
```

### Registry methods

- Collections: `create_application_collection(name)` / `rename_application_collection(collection, new_name)` / `delete_application_collection(collection)` (refuses if non-empty)
- Applications: `create_application(appcollection, name, desc)` / `rename_application(appcollection, old_name, new_name)` / `delete_application(application)` (cascade-drops its tables)
- Tables: `create_application_table(appcollection, app, name, columns)` / `add_application_table_columns(...)` / `delete_application_table_columns(...)` / `rename_application_table(table, new_name)` / `delete_application_table(appcollection, app, table)`

### Read-only `applications` command

Listing/describe only (mutation is on the registry above):

```bash
./run djangomanage applications list_application_collections
./run djangomanage applications list_application_collection --name Inv
./run djangomanage applications describe_application_table --appcollection Inv --app Orders --name Products
```

- `list_application_collections` — list every collection name
- `list_application_collection --name` — list an app's contents
- `describe_application_table --appcollection --app --name` — print a table's columns (omits physical_name/db_table)

### Column types

`char` (default/choices/min_length/max_length), `text` (default/min_length/max_length),
`integer` (default/nullable), `boolean` (default), `decimal` (default/nullable/max_digits/decimal_places),
`datetime` (nullable), `user` (nullable FK to the project User). Column names must
start with a letter and contain only letters/digits.

### Superuser views

- `/apps/collections` — list collections
- `/apps/a/<collection_name>/list` — list apps in a collection
- `/apps/a/<collection_name>/<app_name>/manage` — list an app's tables with live row counts

All three require a superuser; anyone else gets a 404.

