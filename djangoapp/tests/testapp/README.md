# Test app

<!-- MAINTAIN-CONSISTENCY app-conventions — the layout/frontend rules here
     are restated in .pi/steer.md (Feature workflow) and
     docs/reference/README.md; change all three together. -->

The framework's own fixture app: a minimal `ourapp` that the project
tests overlay in place of the reference app. It proves the framework
works with any app of the documented shape — no feature code lives here.

```
djangoapp/tests/testapp/ourapp/
  models/     a couple of concrete BaseModel subclasses (books, filecleanup)
  views/      media (file serving) + home (the landing page)
  urls.py     the home page (plain Django view) then the app's ninja API
  migrations/ the fixture schema
```

What it demonstrates:

- **Pages are plain Django views.** `home_page` renders an Inertia page
  with no props; ninja routers carry JSON only (`.pi/steer.md`,
  "Feature workflow").
- **`GET /` resolves without the framework owning a home route** — the
  app is included first in `djangoapp/urls.py`, so its landing page wins.
- **No frontend assets**: the rendered component (`Home`) ships with the
  framework, and the app-facing e2e specs live in the reference app.
  There is no sdk here — nothing to generate for a python-only fixture.

Excluded from ruff/mypy (it is a fixture, not shipped code); overlaid by
`checkframework1` alongside the reference app.
