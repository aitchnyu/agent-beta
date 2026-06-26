# Replace SOCIALACCOUNT_PROVIDERS with an `addgoogleoauth` command

## Goal
Drop the `SOCIALACCOUNT_PROVIDERS` block (and the `GOOGLE_OAUTH_*` env vars that
feed it) from settings, and instead store the Google OAuth app in the database via
a management command `addgoogleoauth`. The command must produce a `SocialApp` row
that is behaviourally identical to:

```python
"google": {
    "SCOPE": ["profile", "email"],
    "AUTH_PARAMS": {"access_type": "online"},
    "APP": {"client_id": "...", "secret": "...", "key": ""},
}
```

## Investigation findings (allauth 65.x source)

`allauth/socialaccount/providers/oauth2/provider.py`:

- `get_scope()` (line 72) reads `self.app.settings.get("scope")` **first**, then
  falls back to `SOCIALACCOUNT_PROVIDERS["..."]["SCOPE"]`.
- `get_auth_params()` (line 42) reads `self.app.settings.get("auth_params")`
  **first**, then falls back to `SOCIALACCOUNT_PROVIDERS["..."]["AUTH_PARAMS"]`.

So `SocialApp.settings` (a JSONField) **takes precedence** over
`SOCIALACCOUNT_PROVIDERS`. Storing `scope`/`auth_params` on the `SocialApp` fully
replaces the settings block.

**Key gotcha — key casing differs**: the settings dict uses uppercase
`SCOPE`/`AUTH_PARAMS`, but the `SocialApp.settings` JSONField uses **lowercase**
`scope`/`auth_params` (the exact keys `get_scope`/`get_auth_params` read).

`allauth/socialaccount/models.py`:

- `SocialApp` has `provider`, `provider_id` (blank for google), `name`, `client_id`,
  `secret`, `key` (blank), `settings = JSONField(default=dict)`, and
  `sites = ManyToManyField("sites.Site")` (SITES_ENABLED is True here).
- `SocialAppManager.on_site()` filters by `sites__id=current_site`, so the app must
  be linked to the current `Site` (SITE_ID) to be discovered at request time.

Conclusion: the command creates/updates one `SocialApp(provider="google")` with
`settings={"scope": ["profile", "email"], "auth_params": {"access_type": "online"}}`
and links it to `Site(SITE_ID)`. No secrets land in code or settings.

## Command design — `./run python manage.py addgoogleoauth <client_id> <secret>`

- Positional args: `client_id`, `secret`.
- Flags: `--key` (default `""`), `--name` (default `"Google"`), `--site` (default
  `settings.SITE_ID`).
- Idempotent: `get_or_create` on `provider="google"` (one app per provider); on
  re-run it updates `client_id`/`secret`/`key`/`name`/`settings` in place.
- Writes the fixed `settings` dict (lowercase keys) that reproduces the original
  SCOPE/AUTH_PARAMS.
- Links the app to the `Site` (create-or-use existing).
- Prints a confirmation including provider, site, and scope. Never echoes the
  secret.

## Decisions

- `scope`/`auth_params` are hardcoded in the command to match the original
  exactly. Google-specific (the command name is google-specific), so no flags.
- `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_SECRET` env vars become unused and are
  removed from `.env.example`; creds are passed to the command at runtime.
- `os` stays imported in settings (still used by SECRET_KEY/DEBUG/ALLOWED_HOSTS/
  TIME_ZONE); only the SOCIALACCOUNT_PROVIDERS block + its `os.environ.get` calls go.
- `prompts/20260626-foundation-scaffold.md` is historical — left untouched.

## Checklist

- [x] Management command
    - [x] create `djangoapp/management/__init__.py`, `djangoapp/management/commands/__init__.py`
    - [x] create `djangoapp/management/commands/addgoogleoauth.py`
    - [x] positional `client_id`/`secret`; flags `--key`/`--name`/`--site`
    - [x] idempotent upsert of `SocialApp(provider="google")` with the fixed `settings` dict (lowercase keys)
    - [x] link app to `Site(SITE_ID)`; create site row if missing
    - [x] confirmation output, secret not echoed
- [x] Settings
    - [x] remove the `SOCIALACCOUNT_PROVIDERS` block from `djangoproject/settings.py`
    - [x] drop the now-unused `os.environ.get("GOOGLE_OAUTH_CLIENT_ID"/"GOOGLE_OAUTH_SECRET")` refs
- [x] `.env.example` — remove `GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_SECRET` lines
- [x] README — document Google OAuth setup via `addgoogleoauth` (run order: migrate first, then the command)
- [x] Tests (`djangoapp/tests/management/test_addgoogleoauth.py`)
    - [x] creates a SocialApp with provider=google, matching client_id/secret/key, settings scope+auth_params, linked to SITE_ID
    - [x] re-running updates client_id/secret in place (no duplicate rows)
    - [x] scope/auth_params use lowercase keys (the keys allauth reads)
    - [x] creates the SITE_ID site row if missing (fresh DB)
- [x] Lint + verify (in order, per AGENTS.md)
    - [x] `./run lintfix`
    - [x] `./run typecheck`
    - [x] `./run test` (57 OK, incl. 4 new)
    - [x] `./run checkall`

## Risks / notes
- The app must exist before login works; README + command output make the run
  order explicit (`migrate` then `addgoogleoauth`).
- Secrets are passed as CLI args, so they may appear in shell history; that is
  inherent to a bootstrap command and acceptable here (single admin operation).
- `provider_id` left blank — correct for the plain google provider (subproviders
  like OIDC/SAML are the only ones needing it).
