# Session index + sliding idle timeout + login log

## Goal

- Re-add the removed details-page admin features on an indexed foundation:
  **session count** and **logout all sessions** for a user.
- Sessions expire **2 weeks after the user's last request** (configurable),
  not 2 weeks after login — sliding idle expiry.
- **Log all logins** (Google OAuth included) to UserHistory + structlog.
- Reuse Django's session machinery as-is: stock
  ``django.contrib.sessions.backends.db`` engine, no custom SessionStore.

## Investigation findings (this session's research)

1. **The scan is out.** ``User.session_keys`` (decode-and-match over the
   whole ``django_session`` table) was removed as O(all sessions) per call —
   cost dominated by transferring every session blob.
2. **Django sessions have no user column**; the only mapping is inside the
   base64/pickled payload. An index table is the schema-change-free… no —
   the minimal-schema answer is ONE index table keyed by FKs.
3. **Double CASCADE closes the registry's classic upkeep gaps.** With
   ``index.session FK → django_session ON DELETE CASCADE``: logout,
   ``clearsessions``, our logout-all, ANY row deletion auto-cleans index
   rows — at the ORM collector *and* DB-DDL level. The registry cannot
   point at dead sessions; only expiry needs a ``> now`` filter.
4. **Sliding expiry needs a writer.** Default Django saves sessions only
   when modified → expiry is absolute (2 weeks after the last write, i.e.
   effectively login). ``SESSION_SAVE_EVERY_REQUEST = True`` is the
   pure-stock sliding switch but pays a full-row UPDATE per request.
   The amortized alternative: touch only when more than half the window
   has elapsed (≈ one write per user per week at daily use).
5. **``user_logged_in`` is the one signal every login path fires** — our
   ``User.login``, allauth Google logins, admin, tests' ``force_login`` —
   because they all call ``django.contrib.auth.login``. It is the single
   hook for index insertion AND login logging (today only login-key
   redemptions are logged, because recording lives inside ``User.login``).
6. ``SessionMiddleware.process_response`` re-saves the session and re-issues
   the cookie exactly when ``request.session.modified`` is set — a
   middleware registered AFTER ``SessionMiddleware`` sees its
   ``process_response`` run EARLIER (bottom-up), so it can flip the flag
   and let stock Django do both writes.

## Decisions

- Stock db session engine stays; no custom SessionStore (reuse Django's
  persistence, key cycling, race handling — we own none of it).
- ``UserSessionIndex`` model with double CASCADE (user + session FKs).
- Amortized sliding expiry: half-life touch middleware (NOT
  ``SESSION_SAVE_EVERY_REQUEST``).
- Login logging + index insertion live in ONE ``user_logged_in`` receiver;
  ``User.login`` slims to a plain ``auth.login`` wrapper (recording moves
  to the receiver so allauth logins are logged too — no double-record).
- Window knob: ``SESSION_COOKIE_AGE`` derived from a new
  ``SESSION_IDLE_DAYS`` env var (default 14). One knob; everything
  (Django's expiry math, the touch, the cookie max-age) derives from it.
- Lazy index backfill instead of a data migration: sessions created before
  this change get indexed on their first authenticated request.

## Design

### Model (``djangoapp/models/`` or base.py — follow existing layout)

```
UserSessionIndex:
    user        FK → User,           on_delete=CASCADE
    session     FK → Session (django.contrib.sessions.models),
                                    on_delete=CASCADE, unique
    expire_date DateTimeField       (copy of the session row's)
    Meta: unique_together / constraints on (user, session),
          index on (user, expire_date)
```

- ``expire_date`` is denormalized (also on the session row). Writers rule:
  login insert, lazy backfill, touch — and CASCADE for deletion. The
  ``expire_date__gt=now`` filter tolerates drift either way.
- No admin/TTL sweep needed: CASCADE removes rows at deletion; expired
  rows are filtered and ``clearsessions`` cascades them away.

### ``user_logged_in`` receiver

- ``get_or_create`` the index row: user from the signal, key from
  ``request.session.session_key`` (``auth.login`` cycles + saves before
  the signal fires), ``expire_date=request.session.get_expiry_date()``.
- ``UserHistory.record_login(user)`` + structlog ``"user logged in"``
  (no "via login key" anymore — the receiver does not know the path;
  acceptable loss, or read ``request.path`` for a hint).
- ``User.login()`` loses its recording lines (wrapper only). This also
  fixes the latent gap where allauth logins were never recorded.

### Touch middleware (``djangoapp/middleware.py``)

- Registered after ``SessionMiddleware`` (its ``process_response`` runs
  earlier, bottom-up — see finding 6).
- ``process_request`` (or ``__call__`` pre-view): skip anonymous sessions.
  Load the index row for ``(request.session.session_key)``:
  - missing → lazy backfill: decode ``_auth_user_id``, read the session
    row's ``expire_date``, create the index row.
  - present and ``now > expire_date - SESSION_COOKIE_AGE/2`` → due.
- ``process_response``: if due → single-column
  ``UserSessionIndex.objects.filter(...).update(expire_date=now+window)``
  and set ``request.session.modified = True``; stock SessionMiddleware
  then re-saves the session row (full save, fine at ~weekly cadence) and
  re-issues the cookie with the fresh max-age.

### Endpoint + UI (restore what 821efdf's parent removed)

- ``UserDetailsProps.session_count`` (superuser branch, one indexed
  count) + "Sessions" table row.
- ``POST /users/api/{public_id}/logout`` → delete
  ``Session.objects.filter(pk__in=index(user=target))``; CASCADE cleans
  the index; return the count. UI: "Log out everywhere" button + confirm
  (sweetalert) + toast — same as before removal.
- Both under the existing superuser gating; CSRF covered by the default
  ``csrf_guard``.

### Settings + env

- ``SESSION_COOKIE_AGE = int(os.environ.get("SESSION_IDLE_DAYS", "14")) * 86400``
  (documented in ``.env.example`` and ``.env.vm.example``).

## Checklist

- [x] ``UserSessionIndex`` model + migration (schema only; no data step)
- [x] ``user_logged_in`` receiver (UserHistory login + log; index rows
      come from the middleware's lazy backfill — at signal time the final
      session key is not knowable: auth.login may flush or not-yet-save)
- [x] ``User.login`` slims to wrapper (no duplicate recording)
- [x] Touch middleware: lazy backfill + half-life touch + cookie re-issue
- [x] ``SESSION_IDLE_DAYS`` knob in settings + both env examples
- [x] Details page: session_count prop + Sessions row + logout-all
      endpoint/button/toast
- [x] Tests: receiver fires for force_login (history + log line);
      lazy backfill; touch policy; count + logout-all API tests with
      annotated query budgets; e2e restored: issue link → redeem in 2nd
      browser → logout-all kills it; docstrings first, bullet lists per
      conventions
- [x] ``makemigrations --check`` clean; full battery
      (``lintfix`` → ``typecheck`` → ``test`` → ``checkproject``)

## As-built updates (2026-09-14 review follow-up)

- **Logout-all is audited** like the sibling admin action: a
  ``UserHistory`` entry (action ``logout_all``, carrying the ended-session
  count) + a ``user sessions ended`` log line — destructive security
  actions stay visible in the target's timeline and server logs.
- **Index insertion lives in the middleware, not the receiver** (see the
  checklist note above).

## Risks / notes

- Index row insert failing fails the login (receiver raises) — accepted:
  a DB failure during login is a broken login anyway.
- The session FK couples the index to the db session engine; if
  ``SESSION_ENGINE`` ever changes, the index design must change with it
  (the custom-store variant was the alternative — revisit then).
- ``SESSION_COOKIE_AGE`` shrink applies to NEW expiries only; existing
  sessions keep their old deadlines until touched/expired.
- VM deploy needs ``migrate`` (new table) — the deploy flow already runs it.
