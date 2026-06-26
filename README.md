# Instant app gen

We are making a Django app for users to manage mini apps with backend code, frontend code and individual sqlite dbs.

I will request some features which are present in prevproject. Do not use it for any other reason. Ensure its not covered by linters etc.

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

