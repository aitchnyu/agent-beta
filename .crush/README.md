# Why this directory is tracked

The empty `init` file pre-answers crush's "Would you like to initialize
this project?" first-open dialog (it fires when neither this flag nor a
`CRUSH.md` exists). We ship no `CRUSH.md` — instructions live in
`agentconfig/steer.md` via `context-path` in `.crushrc`. Everything else
here (sessions, crush.db, logs) is machine-local and gitignored.
