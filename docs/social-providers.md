# Social login providers

Google is the only enabled provider, and exactly **two lines** in
`djangoproject/settings.py` hardcode that. Everything else is
provider-agnostic: the login page renders its provider list from the
configured `SocialApp` rows in the database, the `addoauth` command upserts
any enabled provider, and the allauth templates never name a provider.

## The two hardcoded lines

1. **`djangoproject/settings.py` — `INSTALLED_APPS`**, the provider app:

   ```python
   "allauth.socialaccount.providers.google",
   ```

2. **`djangoproject/settings.py` — the `form-action` entry in `_CSP_COMMON`**,
   the enabled provider's authorize domain:

   ```python
   "form-action": [
       CSP.SELF,
       "https://accounts.google.com",
   ],
   ```

   The provider-login POST redirects to that domain, and Chromium enforces
   `form-action` across the post-submit redirect chain — a provider enabled
   without its domain here fails login *silently* (the redirect is
   CSP-blocked), which is why both lines carry change-me comments in
   settings.py.

## Adding a provider

1. Enable the provider app in `INSTALLED_APPS` (line 1 above), e.g.
   `"allauth.socialaccount.providers.github"`.
2. Add its authorize domain to `form-action` (line 2 above), e.g.
   `"https://github.com"` (github), `"https://login.microsoftonline.com"`
   (microsoft), `"https://appleid.apple.com"` (apple).
3. *(Optional)* Pin its scope/auth params: add an entry to
   `PROVIDER_DEFAULTS` in `djangoapp/management/commands/addoauth.py` —
   lowercase `scope`/`auth_params`, the keys allauth's `OAuth2Provider`
   reads. Without an entry, allauth's built-in provider defaults apply.
   Note some providers return no email without the right scopes and
   `SOCIALACCOUNT_EMAIL_REQUIRED = True` is set — e.g. github wants
   `{"scope": ["read:user", "user:email"]}`.
4. Register the app with the provider. The redirect (callback) URI is
   `/accounts/<provider>/login/callback/` on your host
   (`http://127.0.0.1:8000/accounts/...` in dev).
5. Store the credentials (idempotent; re-run to rotate):

   ```bash
   ./run djangomanage addoauth <provider> <client_id> <secret>
   ```

The provider's button then appears on `/accounts/login/` automatically —
no template or frontend change, and the generic "Sign in" links keep
working.

## Notes

- `addoauth` rejects provider ids that are not enabled in `INSTALLED_APPS`
  (allauth's registry only knows installed providers), naming the enabled
  ids in the error.
- Google's own setup — the worked example — is the
  [Google OAuth section](../README.md#google-oauth-social-login) of the README.
- On the test VM, the app is served at `https://localhost:8000/` via an ssh
  port forward — Google's localhost exception applies, so register
  `https://localhost:8000/accounts/google/login/callback/` there (or use the
  one-time `makeloginlink` flow; see the README's
  [VM (test server)](../README.md#vm-test-server) section).
