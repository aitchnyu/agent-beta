# Single Sign-in button with provider dropdown + google email login

Planned/as-built 2026-09-14 (emerged from live review on the VM, so no
handwritten TODO line precedes this record).

## Goal

- The anonymous navbar shows ONE Sign-in control; the configured login
  providers (allauth SocialApps, current site) drop down from it as links.
- A Google login whose VERIFIED email matches an existing local account
  (e.g. created via createuser) logs into that account — no allauth
  "already exists, connect it first" wall at /accounts/3rdparty/signup/.

## Decisions

- **Native `<details>`, not a bootstrap dropdown component** — the app
  imports bootstrap SCSS modules only, no bootstrap JS; details is native
  and keyboard-accessible. Layout.vue closes it on outside clicks.
- **Providers reach the navbar via shared props** —
  `SharedPropsMiddleware.login_providers` (id/name/url only — no
  client_id/secret). Signed-in requests share `None` (the dropdown never
  renders and no SocialApp SELECT runs — query budgets are per-test);
  anonymous requests share the list, `[]` when nothing is configured
  (navbar falls back to a plain `/accounts/login/` link).
- **Stale/duplicate SocialApp rows are safe** — `registry.get_class`
  pre-check skips rows for uninstalled provider modules (the TypeError
  path); `distinct("provider")` (order provider, pk — deterministic)
  collapses duplicate rows to one entry.
- **Email-is-identity is google-scoped** —
  `SOCIALACCOUNT_PROVIDERS["google"]["EMAIL_AUTHENTICATION"] = True`;
  allauth's rule: only fully-trusted providers may authenticate by email
  claim, and only provider-VERIFIED emails match.

## Checklist

- [x] settings: SOCIALACCOUNT_PROVIDERS google EMAIL_AUTHENTICATION
- [x] middleware: login_providers shared (None signed-in), stale-row
      pre-check, distinct collapse
- [x] Layout.vue dropdown + outside-click close + [] fallback plain link
- [x] .layout-signin styles in main.scss (no bootstrap dropdown JS)
- [x] zod: login_providers nullable array of {id,name,url}
- [x] tests: middleware (list/empty/stale/duplicate/None-gate), playwright
      dropdown e2e (open/close)

## Notes

- The google email-authentication semantics themselves ride on allauth's
  adapter (upstream-tested); the scoping choice is pinned by the settings
  block + docs, not a dedicated test (config-only surface).
