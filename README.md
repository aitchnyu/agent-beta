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

Manage everything through the `applications` management command (agent-driven;
inputs are validated by Pydantic, each subcommand runs in a transaction, exit
0 on success or non-zero with a printed error):

```bash
./run djangomanage applications create_application_collection --name Inv
./run djangomanage applications create_application --appcollection Inv --name Orders

# Tables take a JSON payload via --json-payload.
./run djangomanage applications create_application_table --json-payload '{"appcollection":"Inv","app":"Orders","name":"Items","columns":[{"name":"code","type":"char","max_length":10},{"name":"qty","type":"integer","default":1,"nullable":true}]}'
./run djangomanage applications add_application_table_columns --json-payload '{"appcollection":"Inv","app":"Orders","table":"Items","columns":[{"name":"region","type":"char","max_length":5}]}'
./run djangomanage applications delete_application_table_columns --json-payload '{"appcollection":"Inv","app":"Orders","table":"Items","columns":["region"]}'

./run djangomanage applications rename_application_table --appcollection Inv --app Orders --name Items --new-name Products
./run djangomanage applications describe_application_table --appcollection Inv --app Orders --name Products
./run djangomanage applications delete_application_table --appcollection Inv --app Orders --name Products
```

### Subcommands

- `create_application_collection --name` / `rename_application_collection --old-name --new-name` / `delete_application_collection --name` (refuses if non-empty)
- `list_application_collections` / `list_application_collection --name`
- `create_application --appcollection --name [--desc]` / `rename_application --old-appcollection --old-name --new-appcollection --new-name` / `delete_application --appcollection --name` (refuses if non-empty)
- `create_application_table --json-payload '<json>'` / `add_application_table_columns --json-payload '<json>'` / `delete_application_table_columns --json-payload '<json>'`
- `rename_application_table --appcollection --app --name --new-name` / `describe_application_table --appcollection --app --name` / `delete_application_table --appcollection --app --name`

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

