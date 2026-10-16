# Test app

A small book-shelf model set the test suite runs against instead of the real
app: **authors** write **books**, every BaseModel row carries a full audit
history — who changed what, when — and a plain (non-BaseModel) **Shelf**
exercises the degrade-gracefully paths. The home route renders the landing
page with login-state props only; a superuser-only media API (no page, no
model) stores uploads under uuid names and streams them back through
`serve_file`.

It exists so the framework's tests can exercise real data flows — writes,
optimistic locking, audit logs, Inertia pages, file uploads — without
touching the actual user app. The gate overlays this app over `ourapp/` for
the project test stage; the VM's gate does the same for its own run.

The models-management screenshots need this overlay: regenerate with
`./run screenshots` under the project stage (`RUN_PROJECT_TESTS=1`) — see
[docs/screenshots/README.md](../../../../docs/screenshots/README.md).
