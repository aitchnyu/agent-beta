# Home

The landing page — the app's single public route, owned by the app (not
the framework): today's Fact of the Day, the viewer's identity when signed
in, and links to the features.

## Who can do what

```mermaid
usecase-beta
direction TB
actor Visitor("Anonymous visitor")
actor Viewer("Signed-in viewer")
actor Cron("Huey cron (midnight)")
systemBoundary home["Home"]
  ReadPick("Read today's Fact of the Day")
  SignIn("Follow the sign-in link")
  SeeIdentity("See display_name + public_id")
  OpenFeature("Open a feature link")
end
Visitor --> ReadPick
Visitor --> OpenFeature
Visitor --> SignIn
Viewer --> SeeIdentity
Viewer --> OpenFeature
Cron --> ReadPick
note for Visitor "A plain sign-in link only — the full auth chrome lives in the framework navbar."
```

## Behaviour

- Nothing is stored here and nothing writes — the page only reads. The
  one changing input, today's pick, rotates nightly; see
  [facts.md](facts.md).
- The signed-in state adds the viewer's display name and public id (never
  the integer pk) to the page.

## What you see

Today's Fact of the Day. Anonymous visitors also get a "You are not signed
in." note with a plain sign-in link (the provider buttons live on the
allauth login page). Feature links show only what this viewer can open —
todos, a private feature, stays hidden from signed-out visitors.

![The landing page — today's pick with a sign-in note](screenshots/home.png)

## For developers

- View: `views/home.py` (`router`, mounted at `/`) — `GET /` → Inertia
  page `ours/Home`, props `{ is_authenticated, display_name, public_id,
  fact_of_day }` (`HomePropsSchema` in `ours/schemas.ts`; `fact_of_day`
  is `null` before the first cron run or with an empty fact pool).
- Frontend: `frontend/src/ours/pages/Home.vue`.
- Tests: `tests/test_home_views.py` (no e2e module of its own — the auth
  chrome lives in the framework navbar, covered by the framework suite);
  the capture is `tests/test_screenshots.py::test_home`.
