# Test app

A small book-shelf app the test suite runs against instead of the real one:
**authors** write **books**, the landing page lists the shelf, and every row
carries a full audit history — who changed what, when. A superuser-only
media API (no page, no model) stores uploads under uuid names and streams
them back through `serve_file`.

It exists so the framework's tests can exercise real data flows — writes,
optimistic locking, audit logs, Inertia pages, file uploads — without
touching the actual user app. The gate overlays this app over `ourapp/` for
the project test stage; the VM's gate does the same for its own run.

Screenshots of its pages are part of the suite: regenerate with
`./run screenshots` (the model shots need the project stage:
`RUN_PROJECT_TESTS=1`).
