# Debugging a failing test

A failing test debugs from inside its frame: rerun the same label with
`--pdb`. All commands and outputs below are real, captured from a
deliberately failing test pair. Unit runs and Playwright runs both stay
allowlisted — the debugger commands ride along without a prompt.

## Unit tests — commands in a here-string

```bash
./run test ourapp.tests.test_debug_demo --pdb <<< 'pp sorted(body)
pp body["open_due_on"]
q'
```

pdb lands in the failing test frame; every local is inspectable as-is.
Worked example — a test that guessed a JSON key (`body["next_due_on"]`):

```python
# ourapp/tests/test_debug_demo.py (illustrative example)
from djangoapp.tests._base import BaseTestCase

class CompletePayloadGuessTests(BaseTestCase):
    def test_complete_response_carries_next_due(self) -> None:
        ...seed a 3-day interval chore due yesterday...
        resp = self.client.post(
            f"/chores/{chore.public_id}/complete",
            data={"expected_row_version": chore.row_version},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertEqual(body["next_due_on"], str(_today() + dt.timedelta(days=3)))
```

Fails with `KeyError: 'next_due_on'` — nested? renamed? missing? The pdb
run answers in one command:

```
(Pdb) ['archived', 'first_due_on', 'name', 'open_due_on', 'public_id',
       'repeat_every', 'repeat_unit', 'row_version', 'schedule_kind',
       'schedule_summary', 'weekday_picks']
(Pdb) '2026-11-01'
```

The payload is flat; the key is `open_due_on` and already holds the
`+3 days` value the test wanted.

## Playwright tests — feed pdb from an rc under /tmp/desmo

Playwright's node driver takes over the process's stdin. Commands piped
to pdb never arrive — observed: the prompt prints, hits EOF, and quits.
Feed pdb from an rc file in a throwaway HOME instead (random dir under
/tmp/desmo, so nothing collides with a later session):

```
# write tool → /tmp/desmo/pdb-debug7/.pdbrc   (random name each time)
u
u
u
u
u
p page.url
p row.inner_text()
q
```

```bash
HOME=/tmp/desmo/pdb-debug7 ./run playwrighttest ourapp.tests.test_debug_demo_playwright --pdb
```

- An assignment prefix (`HOME=… cmd`) is stripped before the allowlist
  matches, so the command still rides `./run playwrighttest *`. Do NOT
  write `env HOME=…` — the `env` command is an indirection wrapper and
  prompts.
- Keep the rc out of the repo root: a repo-root `.pdbrc` executes on
  **every** later pdb session — including unit runs — and its `q` ends
  them early.
- A failed `expect()` raises inside Playwright's own code — `u` up to the
  test frame first (`w` shows the stack). Unit-test post-mortems already
  land in the test frame.
- The harness's shared page is deliberately never closed between tests,
  so the prompt sits on the failing page:

```
'http://localhost:39635/chores'
'Water the plants\nevery 3 days\nOverdue · Oct 29\nDone\nArchive'
```

What the live page can show at the prompt:

- `p row.inner_text()`, `p row.inner_html()` — the exact string a
  `to_contain_text` assertion matched against; text answers "wrong copy",
  html answers "wrong nesting".
- `!print(page.content()[:1000])` — the serialized DOM is huge; slice it
  or the transcript drowns in it.
- `!page.evaluate("() => JSON.stringify(x)")` — state with no DOM face:
  Inertia's page object, stores, localStorage. `JSON.stringify` so it
  prints instead of returning an opaque handle.
- `!_ = page.screenshot(path="/tmp/desmo/debug.png")` — for layout and
  geometry text can't show; `_ =` swallows the returned PNG bytes pdb
  would otherwise echo.
- `p self.console_errors` — the harness's already-collected error sink;
  `[]` clears the page itself of suspicion.
- `!page.on("console", lambda m: print("CONSOLE:", m.type, m.text))` then
  any action — the sink only holds what happened **before** the stop;
  output from new actions needs a handler registered before they fire.
- `!page.get_by_role("button", name="Done").click()` then re-probe — the
  page is live mid-test; driving it directly beats a rerun
  (`./run playwrighttest` rebuilds the frontend every time).

## Breakpoint at a line (not on error)

`--pdb` fires only on failure — the final frame. Reach for a real
breakpoint when the failing assert is far from the cause: the value was
already wrong by the time the test checked it. Use it to catch the
function that broke it mid-run.

```bash
./run python -m pdb -c "b ourapp/x.py:88" -c "c" -c "p thing" -c "q" \
  manage.py test <label>
```

Runs as `./run python …`, not a test command — and `./run python` is not
allowlisted (arbitrary code), so it prompts. The `--pdb` post-mortem
covers the common case anyway: the test already failed, you want the scene
of the crime.
