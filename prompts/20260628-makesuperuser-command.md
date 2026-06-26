# `makesuperuser` command — promote an existing user by email

## Goal
A management command that finds an existing `User` by email and promotes it to a
superuser (mirroring `createsuperuser` but for users created via social login,
who can't be superuser at creation time).

```
./run python manage.py makesuperuser <email>
```

## Decisions
- Look up by `email__iexact` so case variants of the same address match.
- The project's `User.email` is **not** unique (inherited from `AbstractUser`,
  no override). Handle 0 / >1 matches explicitly with a `CommandError` rather
  than relying on `get()`.
- Set both `is_superuser=True` and `is_staff=True`: Django admin (`/admin`)
  requires `is_staff` to even render the admin, and a superuser that can't reach
  admin is useless. `createsuperuser` does the same.
- Idempotent: if already a superuser, just report it; no error.
- Confirm the target's `username`/`public_id` in output (never email to avoid
  PII in logs); do not print anything sensitive.

## Checklist

- [x] Command `djangoapp/management/commands/makesuperuser.py`
    - [x] positional `email`
    - [x] `email__iexact` lookup; `CommandError` on 0 or >1 matches
    - [x] promote via `User.update(..., is_staff=True, is_superuser=True, user=user)` so it is audited in `UserHistory`; idempotent (early-return if already)
    - [x] confirmation output with username (no email echoed)
    - [x] imports `djangoapp.User` directly (no `get_user_model`)
- [x] Tests `djangoapp/tests/management/test_makesuperuser.py`
    - [x] promotes a matching user to superuser+staff
    - [x] case-insensitive email match
    - [x] unknown email -> CommandError
    - [x] already-superuser is a no-op (no history row)
    - [x] promotion records an edited UserHistory row with the flag diff
- [x] README — "Promote a user to superuser" section
- [x] Lint + verify
    - [x] `./run lintfix`
    - [x] `./run typecheck`
    - [x] `./run test` (62 OK)
    - [x] `./run checkall`

## Risks / notes
- `email__iexact` could promote the wrong user if two accounts share an email;
  the >1 check guards that with an explicit error.
- Promotion does not grant Django admin *login ability* if the user has no
  usable password and `ModelBackend` is the only backend; here allauth's
  `AuthenticationBackend` + social login handles identity, so this is only for
  the `/admin` *authorization* (`is_staff`/`is_superuser`).
