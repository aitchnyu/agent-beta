# Allauth page templates + provider-agnostic OAuth (stay Google-only)

## Goal

- Style allauth's server-rendered pages (`/accounts/login/`, the provider
  confirm interstitial, logout confirm, social signup, auth error) with
  project template overrides. Today they render allauth's bare built-ins —
  the repo ships only `inertia/base.html` and `404.html`.
- Remove every Google-specific hardcoding so a future provider is two
  adjacent config lines, not a code hunt (TODO.md: "Templates for Allauth",
  "Buttons and stuff may be hardcoded for Google").
- **Non-goal: enabling other providers now.** Google stays the only one in
  `INSTALLED_APPS`; everything else is mechanism only.

## Investigation findings (allauth 65.18)

1. **Loader-order trap.** allauth ships *all* its templates (`account/`,
   `socialaccount/`, `allauth/layouts/`, `allauth/elements/`, …) from the
   single `allauth` app package, and `allauth` is listed **before**
   `djangoapp` in `INSTALLED_APPS`. With `APP_DIRS: True` the first app wins,
   so overrides dropped into `djangoapp/templates/` are silently ignored.
   Fix: add `BASE_DIR / "djangoapp" / "templates"` to `TEMPLATES["DIRS"]`
   (the filesystem loader runs before app dirs). Moving `djangoapp` above
   allauth in `INSTALLED_APPS` also works; DIRS is the chosen fix.
2. **Reachable pages under our config** (`SOCIALACCOUNT_ONLY = True`, no
   mfa/usersessions/headless/idp apps): `account/login.html` (reduced to the
   provider list), `account/logout.html` (GET confirm), `socialaccount/
   login.html` (provider confirm interstitial), `socialaccount/signup.html`
   (email collision between providers), `socialaccount/authentication_error.
   html`. They all extend `allauth/layouts/base.html` — **one layout override
   styles everything**; no per-page overrides needed.
3. **The provider list is DB-driven.** `get_providers` returns providers that
   are registry-registered (`INSTALLED_APPS`) *and* have a `SocialApp` row on
   the current site. The login page auto-adapts; nothing in templates may
   hardcode "Google".
4. **CSP `form-action`.** The provider login POST returns a redirect to the
   provider's authorize URL, and Chromium enforces `form-action` across the
   post-submit redirect chain — every enabled provider's authorize domain
   must be listed. The hardcoded `https://accounts.google.com`
   (settings.py:222) becomes a derived list. Derivation **cannot** use
   allauth's registry (it populates during app loading, after settings
   import) — scan our own `INSTALLED_APPS` prefix instead.
5. allauth's default layout menu (Change Email / Change Password /
   Connections / Sessions) links pages that are dead ends for social-only
   accounts — the override drops the menu.

## Decisions

- No new providers. `INSTALLED_APPS` keeps google only, plus one commented
  affordance line (e.g. github) next to it.
- `addoauth <provider> <client_id> <secret>` is the generalized upsert; the
  earlier decision to keep `addgoogleoauth` as a wrapper was reversed on
  review — the google-specific command is removed and the README keeps Google
  as the worked example via `addoauth google …`.
- Final simplification (post-review): the derived CSP machinery
  (`_enabled_social_providers`/`_PROVIDER_CSP_DOMAINS` + the fail-fast raise)
  was replaced by a hardcoded google `form-action`; both google-hardcoded
  lines carry change-me comments and the add-a-provider recipe lives in
  `docs/social-providers.md`, linked from the README. The `--name`/`--site`
  flags were dropped with them — display name derives from the provider
  class, site from `SITE_ID` (single-site setup).
- Frontend links become generic **"Sign in" → `/accounts/login/`**
  (`Home.vue`, `Layout.vue`, and the `docs/reference` mirror). No
  shared-props provider buttons — a single provider doesn't justify a
  `SocialApp` query on every anonymous request.
- Overrides live in `djangoapp/templates/`, activated by the DIRS entry.
- Stylesheet is a plain static file `djangoapp/static/djangoapp/allauth.css`
  (stable URL, collectstatic-friendly; NOT a Vite-hashed entry —
  `hashed_entry` is for the inertia bundle only).

## Design

### Templates

- `djangoapp/templates/allauth/layouts/base.html` — minimal skeleton:
  `{% load static %}` + the CSS link, `{% block head_title %}`,
  messages block, `{% block content %}`. No allauth menu. A stable marker
  for tests (e.g. `data-allauth-layout` on `<body>`).
- `djangoapp/templates/allauth/elements/provider.html` — the provider link
  as a button; label from `attrs.name`, at most a generic
  `provider-{{ attrs.provider_id }}` class. Never a hardcoded Google label.
- `djangoapp/static/djangoapp/allauth.css` — styles the plain elements the
  layouts emit (h1/p/form/button/ul/lists) plus the provider button.

### Command

- `./run djangomanage addoauth <provider> <client_id> <secret>` — flags
  `--key` (default `""`), `--name` (default: provider id capitalized),
  `--site` (default `settings.SITE_ID`).
- `PROVIDER_DEFAULTS: dict[str, dict[str, Any]]` keyed by provider id;
  google entry verbatim from today's `GOOGLE_SETTINGS` (lowercase
  `scope`/`auth_params` — the keys `OAuth2Provider` reads; see
  prompts/20260628-google-oauth-command.md). New providers = new entry.
- Validate the provider id against
  `allauth.socialaccount.providers.registry` — an unknown *or*
  known-but-not-installed id raises `CommandError` listing the enabled
  provider ids (exactly right while google-only).
- `addgoogleoauth.py` becomes a wrapper that forwards to the shared upsert
  (shared helper module, e.g. `_socialapp.py`, so both commands stay thin);
  output and defaults byte-identical to today.

### Settings / CSP

- Next to the (commented) provider affordance lines:
  `PROVIDER_CSP_DOMAINS = {"google": "accounts.google.com", "github":
  "github.com", "microsoft": "login.microsoftonline.com", "apple":
  "appleid.apple.com"}`.
- `_SOCIAL_PROVIDERS` = prefix-scan of `INSTALLED_APPS` for
  `allauth.socialaccount.providers.*`; `form-action` = `[CSP.SELF]` + the
  domains of enabled providers. **Raise at import** naming the provider when
  an enabled one lacks a map entry — deliberate fail-fast so the two
  adjacent lines stay in sync in this template repo.
- Update the comments at settings.py:199-202 (`addgoogleoauth` →
  `addoauth`, wrapper noted) and drop the `# For Google login` comment.

### Frontend

- `frontend/src/ours/pages/Home.vue:35-42` — label "Sign in", href
  `/accounts/login/`, keep the `.home-login-link` class (styles + tests).
- `frontend/src/components/Layout.vue:50-56` — same generic link, keep the
  bootstrap-ish button classes.
- Update the `docs/reference/frontend/src/ours/pages/Home.vue` mirror (no
  Layout.vue mirror exists). Home props/zod schema unchanged.

### Tests

- New `djangoapp/tests/management/test_addoauth.py`: idempotent
  create/update, google defaults applied, unknown provider rejected,
  not-installed provider rejected listing enabled ids, wrapper path
  equivalent.
- Existing `test_addgoogleoauth.py` passes **unchanged** — that is the
  wrapper's proof.
- New template/CSP tests (e.g. `djangoapp/tests/test_allauth_templates.py`):
  seed the google SocialApp → `GET /accounts/login/` is 200, contains
  "Google" (from the provider list) and the layout marker + CSS link;
  `GET /accounts/logout/` renders the confirm; the response CSP header
  lists `accounts.google.com` and not `github.com`.
- Playwright: `ourapp/tests/test_home_playwright.py` assertions keep using
  `.home-login-link` (not Google-specific); update the class docstring's
  "Google login link" bullets, add an href assertion for `/accounts/login/`;
  mirror in `docs/reference/ourapp/tests/`.

### Docs

- README: update lines 52-53, 126, 265-266 to `addoauth` with
  `addgoogleoauth` noted as the Google alias; the Google OAuth section
  keeps working as the worked example.
- `.env.example:68` comment → `addoauth`.

## Checklist

- [ ] Loader precedence — `TEMPLATES["DIRS"] += [BASE_DIR / "djangoapp" / "templates"]`
- [ ] Layout override + provider element override + `allauth.css`
- [ ] `addoauth` command (registry validation, `PROVIDER_DEFAULTS`);
      `addgoogleoauth` removed (README keeps Google as the example via
      `addoauth google …`)
- [ ] Derived CSP `form-action` + fail-fast domain-map check + commented
      INSTALLED_APPS provider affordance
- [ ] Frontend "Sign in" links (`Home.vue` ours + reference mirror,
      `Layout.vue`)
- [ ] Tests: command, template/CSP, playwright docstring/href updates
- [ ] Docs: README, `.env.example`, settings comments
- [ ] Verify (framework-wide change — full battery): `./run lintfix`,
      `./run typecheck`, `./run test`, `./run checkproject`

## Risks / notes

- Login now has two local hops (login page → provider confirm → provider).
  Accepted — once styled, the login page is the chooser; the extra hop
  disappears in feel, and `SOCIALACCOUNT_LOGIN_ON_GET` (which would drop the
  confirm) stays off (allauth discourages login-on-GET).
- The DIRS entry double-registers `djangoapp/templates` (also APP_DIRS
  scanned) — harmless; DIRS is searched first, so overrides win
  deterministically without reshuffling `INSTALLED_APPS`.
- The settings-import raise on an unmapped provider is intentional: boot
  fails with a clear message instead of a login silently blocked by CSP.
- Secrets as CLI args may land in shell history — unchanged from the
  `addgoogleoauth` prompt's note (single admin bootstrap operation).
- `prompts/2026*` files are historical — left untouched.
