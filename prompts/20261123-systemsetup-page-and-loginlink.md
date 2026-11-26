# First-run setup as three commands; no wizard, no /systemsetup

Nov 24, 2026. Supersedes the Nov 23 plan this file held (the
/systemsetup page, its helper and its socket units are dropped). Lands
as ONE uncommitted change; nothing commits. Rewrites the Textual wizard
in `ops/firstsetup/` into one standalone command.

## Decisions (operator, 2026-11-24)

- Three commands on debian's PATH, like `pi`: `desmosuperuserloginlink`
  (renamed from `desmologinlink`), `desmogoogleoauth`, `desmopiauth`.
  Only `desmopiauth` is a Textual app.
- They run once, at provisioning, in that order. Later logins start
  nothing; anything skipped waits for a manual run.
- No flags on any of them. An empty answer skips, with a friendly
  message that names the command and says what it does.
- `desmosuperuserloginlink` serves the first superuser only: it prints
  that one's first name, last name, email and link, and ignores the rest.
  "First" is the oldest (`listusers` orders by pk by default — marker).
- `desmopiauth` goes provider, authenticate, model, test. The model list
  is pi's live one, so it is read after sign-in.
- No thinking picker. A suggested model saves its own level; other models
  leave pi's default alone.
- No going back for any step (TODO.md): `desmopiauth` has no Back
  button; ctrl+q leaves from any screen with the skip message. The
  model table's column positions come from its header, never assumed.
- pi auth catches no error anywhere (operator, Nov 24). A failing step
  ends the app; one handler prints the traceback, then how to run the
  command again.
- Z.AI's suggested model is `glm-5.4` at thinking high (marker).
- No `/systemsetup` page, no helper, no socket units, no `next` param on
  the login link.
- Kept from Nov 23: the Home warning trim, the README docs, the 24-hour
  link.

## Probed facts (pi 1.5.2 on VM `desmo`)

- `pi auth` = login, logout, print-api-key, print-bearer-token, check —
  no way to hand pi a token. Credentials live in `~/.pi/agent/auth.json`.
- OAuth redirects are fixed to loopback on the browser's machine; pi
  also prompts for the pasted redirect URL and reads it from stdin.
- `--no-browser` gives a device code where one exists (Codex, Copilot,
  xAI); browser-only providers still run the browser flow + paste prompt.
- pi lists a provider's models only once it holds a credential. Its
  bundled catalog is a snapshot of the pinned version and can go stale.
- Startup default = settings.json keys `defaultProvider`, `defaultModel`,
  `defaultThinkingLevel` (what Ctrl+S writes; the file is pretty-printed).
- Registry auth kinds: oauth = openai, openai-codex, openrouter,
  anthropic, github-copilot, xai, meta, kimi-coding, radius; api_key =
  zai, google. Providers with OAuth often take API keys too.
- The operator is `debian` with passwordless sudo. `/usr/local/bin/pi`
  is a root-owned wrapper delegating to `./run pi`, installed by
  provisioning with `@PI_BIN@` baked in (`deploy/pi.sh`).
- `ops/firstsetup/` (committed in 7eca13a) holds the old wizard:
  flow.py (verbs), providers.py (catalog, recommendations), pistore.py
  (pi's files), screens.py + app.py (TUI).
- Left in the tree from the dropped plan: an untracked `ops/piauth.py`
  written for the socket protocol — rewrite it.

## A. The commands

Each is an `ops/` module behind `./run <name>`, imported at the top of
its file like every other module. A skip prints its message and exits 0,
so the provisioning sequence continues.

- [x] `ops/superuserloginlink.py` behind `./run desmosuperuserloginlink`
      — plain prompts.
  - [x] No superuser: ask first name, last name, email (the old form's
        validation); `createuser --superuser --if-absent`.
  - [x] An empty first name skips with the message below.
  - [x] Superusers exist: the oldest one's link, with first name, last
        name and email printed above it. Other superusers are ignored.
  - [x] `listusers --superusers` lists superusers; the command reads its
        first row. `listusers` orders by pk (creation order) by default
        — marker, Nov 24.
  - [x] Then `makeloginlink --minutes 1440`; print the link.
- [x] `ops/googleoauth.py` behind `./run desmogoogleoauth` — plain prompts.
  - [x] First run `djangomanage oauthstatus google`. When Google sign-in
        is already set up, say so and quit (no replace, no `./run` hint
        — operator, Nov 24).
  - [x] Ask for the client id, then the secret (hidden input).
  - [x] An empty client id skips with the message below.
  - [x] Validate as the old Google form did; store through
        `djangomanage addoauth google <id> <secret>`.
  - [x] New management command `oauthstatus <provider>`: one JSON line
        with `configured` and `client_id`.
- [x] `ops/piauth.py` behind `./run desmopiauth` — Textual.
  - [x] Engine beside the app, tested without Textual: provider
        catalog, key storage, OAuth sign-in start, live models, test call,
        default save.
  - [x] Provider: a dropdown of the providers pi lists.
  - [x] Authenticate: an API-key field. Providers pi registers as OAuth
        also get "Sign in": the TUI steps aside (`app.suspend()`), pi's
        login owns the terminal, and the code only waits for it to exit
        — no pipes, no relay (operator, Nov 24: "without interacting
        with a process"). Success is judged by the credential file.
  - [x] Model: pi's live list, the suggested model focused and its
        description shown; a suggestion missing from the list is not
        offered.
  - [x] Layout (operator, Nov 25): the panel is as wide as the
        terminal; a field's label sits on its own line above the input.
        Inputs keep Textual's standard look — a rule that shrinks or
        borders the input loses to Textual's focused-input rule and the
        field ends up with no row for its text (that bug shipped).
  - [x] Test: one real call with `--no-session`. On a reply, save the
        model as the startup default (plus the suggestion's thinking
        level) and quit with "pi is ready: type pi".
  - [x] No `try`/`except` in `ops/piauth.py` or `ops/piauth_app.py`.
        A failing step ends the app; `report()` is the one handler: it
        prints the traceback, then the failed message below.
  - [x] Leaving the TUI early quits with the skip message below.
  - [x] Name the typed-app accessor clearly — the marker in
        `screens.py` says `_setup_app` is an unclear name.
- [x] Wrappers: one file per command in `deploy/`, modeled on
      `deploy/pi.sh`, installed by provisioning to `/usr/local/bin/`.

### The messages

Each ends with the command to run, on its own line — never a `./run`
form (operator, Nov 24). The README quotes them verbatim.

- `desmosuperuserloginlink`, skipped:
  "Skipped. To sign in to the site later, run:
    desmosuperuserloginlink
  It creates the first superuser and prints a login link."
- `desmogoogleoauth`, skipped:
  "Skipped. Run this with your client id and secret:
    desmogoogleoauth"
- `desmogoogleoauth`, already set up (no replace — operator, Nov 24):
  "Google sign-in is already set up." then quit; nothing is asked.
- `desmopiauth`, left early:
  "Skipped. The `pi` agent has no model yet. Run this when a provider
  key or account is ready:
    desmopiauth"
- `desmopiauth`, failed test:
  "That did not work, so `pi` is not set up yet. Run this again when
  the provider is ready:
    desmopiauth"

## B. Provisioning

- [x] Installer tail (interactive `[ -t 1 ]` only) runs the three as
      debian, in order, replacing the `firstsetup` step.
- [x] `deploy/inside-vm.sh` installs the wrappers; its `firstsetup`
      comments go.

## C. Remove

- [x] Delete `ops/firstsetup/`, its two test files, the `firstsetup`
      verb and help line, and `pyproject.toml`'s per-file ignore for
      `ops/firstsetup/app.py`. Textual itself stays.
- [x] Sweep the mentions in README, `run`, `deploy/template.env`,
      `INSTRUCTIONS.md`.

## D. Defaults chosen — correct any that are wrong

- Already set up at provisioning: `desmosuperuserloginlink` prints a link for the
  existing superuser; `desmogoogleoauth` quits with its message;
  `desmopiauth` runs anyway, since choosing a model is a fresh decision.
- `Home.vue`: drop the "Ask your agent…" paragraph; add one line telling
  the reader to run `desmosuperuserloginlink` on the machine.

## E. Docs

- [x] README: the three commands after provision, each with an example
      of filling it in — the prompts, example answers, and what gets
      printed. The two text commands as terminal transcripts;
      `desmopiauth`'s screens rendered in plaintext with the example
      values filled in. Every example uses fake values
      (`jane@example.com`, a placeholder client id, dots for secrets).
- [x] README: `desmosuperuserloginlink` in the first-user section, replacing the
      raw `djangomanage` pair.
- [x] README: Pi setup rewritten around `desmopiauth`; the old wizard
      render replaced.

## Tests — where each script runs

Unit tests run locally through `python3 -m unittest discover -s ops/tests`
and `./run test`, inside the gate. Real runs happen where the script's
dependencies exist.

- [x] `superuserloginlink` and `googleoauth`: `ops/tests/test_superuserloginlink.py`,
      `ops/tests/test_googleoauth.py` — `djangomanage` calls scripted;
      validation, the superuser pick, both skip paths, the already-set-up
      exit.
- [x] `oauthstatus`: its management test beside the other commands'
      (`djangoapp/tests/management`).
- [x] `piauth` engine: `ops/tests/test_piauth.py` — subprocess seam
      scripted; catalog parsing, key storage, settings merge, the test
      call's verdicts, argument refusals.
- [x] VM `desmo` by hand:
  - [x] `desmosuperuserloginlink`: the oldest-superuser branch only (prints a link, creates
        no user).
  - [x] `desmogoogleoauth`: stops at the already-set-up check, or skips
        at the client id — the VM's stored Google credentials stay.
  - [x] `desmopiauth`: a real run against zai; restore pi's
        settings.json afterwards and remove stray test sessions.
- [ ] Installer tail: only a real provision exercises it — a throwaway
      local container, `desmo` untouched.

## Limits (accepted)

- Real sign-ins (OpenAI, Anthropic, OpenRouter) are not testable here.
  Confirm only that pi's prompts reach the TUI and that a cancelled
  login returns cleanly.
- The engine calls `./run djangomanage` and pi as the operator who runs
  the command — no helper, so no privilege boundary to review.

## F. One command: `desmosetup` (operator, Nov 25)

Supersedes A–E wherever they name three commands. `desmosetup` replaces
`desmogoogleoauth` and `desmopiauth`; `desmosuperuserloginlink` stays for
printing a fresh link.

### Decisions (operator, 2026-11-25)

- The installer's tail (interactive installs only) runs `desmosetup`.
- One Textual screen collects the domain, the first superuser, Google and
  the pi provider.
  - The domain, the superuser details and the provider cannot be skipped.
  - Google can be skipped.
- The TUI exits; the terminal takes over — superuser, Google, pi's own
  login, the test.
- The report prints in parts:
  - the login link and the homepage link;
  - Google: set, with the redirect URL, or not set;
  - pi: enabled, as provider / model / thinking, or failed, with the
    command to run.
- The domain is asked after provision; a `set-domain` provisioner step
  applies it.
- The model is Z.AI `glm-5.4` at thinking high when pi lists it, else the
  provider's first listed model.
- Providers with both a key and a sign-in start with `--api-key`.
- No replace flow for Google: both fields empty leaves what the machine
  holds.

### Code

- [x] `ops/piauth.py`, the engine: catalog, login command, models, test
      call, default save. `store_key`, `start_oauth_login` and
      `ModelOption` go.
- [x] `ops/googleoauth.py`: `status`, `check_values`, `store` — no
      prompts, no command.
- [x] `ops/superuserloginlink.py`: `first_superuser`, `create_first`,
      `ensure_superuser`, `login_link`.
- [x] `ops/setup_app.py`, the screen:
  - [x] Set applies the domain at once; its line, or the refusal, shows
        under the panel.
  - [x] An existing first superuser fills the three fields.
  - [x] A failing load ends the app and keeps the error.
- [x] `ops/setup.py`: `run_steps`, `google_step`, `pi_step`,
      `login_on_terminal`, `format_report`, `main`.
  - [x] Google and pi refusals are report parts; anything else is a
        traceback.
  - [x] The command exits 0 whenever the report printed.
  - [x] ctrl+c during pi's login reaches pi alone: the report still
        prints (under the installer's `su -l … -c`, su ends the session
        instead — the banner names the command).
- [x] `deploy/inside-vm.sh`: `set_domain` and the `set-domain` dispatch.
  - [x] It waits, bounded, until the app answers again before it says
        "domain set".
- [x] `deploy/desmosetup.sh`; `deploy/desmogoogleoauth.sh` and
      `deploy/desmopiauth.sh` removed.
- [x] `run`: the `desmosetup` verb and help line; the two old verbs go.
- [x] `deploy/install.sh`: the tail runs `desmosetup` once.
- [x] `deploy/pi-notice.sh`: "run desmosetup".
- [x] `ops/checkframework2.py`: assert 5 names `desmosetup`.

### Docs

- [x] README: "First-run setup (`desmosetup`)", the screen and the
      reports rendered from the code.
- [x] README: the Google OAuth, Sign in, Commands, Layout and VM
      sections.
- [x] `INSTRUCTIONS.md`, `deploy/template.env`, `localvm`.

### Tests

- [x] `ops/tests/test_piauth.py` — `pick_model`, `login_command`, pi's
      files, the catalog, the models, the test call.
- [x] `ops/tests/test_googleoauth.py` — `status`, `check_values`,
      `store`.
- [x] `ops/tests/test_superuserloginlink.py` — `EnsureSuperuserTests`.
- [x] `ops/tests/test_setup.py` — the steps, the report, `main`,
      validation, the origin, `apply_domain`, SIGINT around pi's login.
- [x] VM `desmo` by hand: `set-domain`, then a real `desmosetup` in a
      pseudo-terminal.
  - [x] Through the installer's own `su -l debian -c`: screen, report,
        exit 0 — once by keyboard, once with mouse clicks on Set and
        Save.
  - [x] From debian's shell: pi's device-code prompt, ctrl+c, report.
  - [x] Three refused origins: non-zero exit, env file unchanged.
  - [x] pi's own files byte-identical afterwards.
- [ ] Installer tail: only a real provision exercises it.

### Seen on the VM (Nov 26)

- pi 1.5.2's catalog lists no `glm-5.4` for zai: seven models, `glm-4.7`
  first. The rule as written then picks `glm-4.7`, with no thinking
  level — the operator's call whether that fallback should change.
- The VM's stored zai key is refused by Z.AI (`401`, authentication
  failed) for every model, so the report's pi part failed as designed:
  the command to run, then pi's own line.
- Under `su -l debian -c`, one ctrl+c ends the whole session (util-linux
  su kills it) — true for any command started that way.

## G. One shot, first run: no presence checks, no quitting (operator, Nov 26)

Markers found on the `aihere` check, written down before any change:

- `ops/setup_app.py:91` — only one shot at completing this command; never
  endorse running it again; first run only.
- `ops/superuserloginlink.py:144` — we will run it exactly once.
- `ops/setup.py:154` — ensure the command returns JSON, so it is easier
  to parse.
- `TODO.md:1` — we still have `pick_model`; `TODO.md:2` — previous
  commands checked what was present; `TODO.md:3` — quitting allows a
  redo, which is not endorsed; `TODO.md:52` — why not 5.4?

### Decisions (operator, 2026-11-26)

- Superuser, domain and Google are this repo's own code: assume they are
  correct and follow the happy path.
- Report whenever a report is available.
- If pi's login fails, the report says how to continue.
- Google left empty: the report names the by-hand `addoauth` line.
- Under the installer, only pi's own prompt cancels on ctrl+c.
- pi picks the model itself (operator: option "c", Nov 26): the setup
  saves nothing about models, and the report names the provider only.
- `desmosuperuserloginlink` prints a link only: it has no business
  creating a superuser.
- No Set button. The form takes a domain, a subdomain, or literally
  `https://localhost:8443` — required, with no suggestion; a typed domain
  is set after the screen, first of the terminal steps.
- The button is `Next`.
- API-key providers get a masked key field on the screen; the key is
  saved in pi's own file, and pi's key prompt is not used.
- A sign-in-only provider starts `pi auth login <provider> --no-browser`
  the moment it is chosen; the screen is suspended meanwhile.
- Success is pi's model list: a non-empty list is the whole test, and no
  model call is made. The pick is saved as pi's startup default.
- A refusal shows under its field and in a toast at the bottom, and the
  view goes to the first refusal; the status line names them all.
- Report headings in the operator's wording: Login stuff, Google stuff,
  Pi. No `--prefill-localhost`.

### Code

- [x] No presence checks:
  - [x] `ensure_superuser` is gone; the setup calls `create_first`.
  - [x] The screen's `_load` no longer asks `listusers` to prefill.
  - [x] Google left empty is simply not set; no verb runs.
  - [x] pi's login always runs; a credential on file skips nothing.
- [x] pi is 1.6.1 (the provisioner's pin).
- [x] pi picks its own model; the setup chooses and saves nothing about
      models. `pick_model`, `RECOMMENDED_MODELS`, `Recommendation` and
      `Choice` are gone; `set_default` became `opt_out_of_analytics`.
      Grounded on the VM: pi's own default for Z.AI is `glm-5.3` at
      `high` (its `defaultModelPerProvider` table lags its catalog, which
      lists `glm-5.4`).
- [x] The report's pi part names the provider only: "Pi is enabled with
      zai. Just run `pi`" — pi's footer shows the model. pi has no
      supported way to report its choice, so printing it was dropped.
- [x] The provider catalog is one node call on pi's registry: the
      unknown-provider error-line workaround and its parser are gone.
      pi's CLI gained nothing in 1.6.1 (same commands and flags as 1.5.2),
      so the table parser, the key write and the terminal login stay as
      they are.
- [x] `opt_out_of_analytics` writes `enableAnalytics: false` into pi's
      settings file, creating it. pi's first-time dialog asks about
      analytics only with no settings file and under experimental
      features, so that file ends it for good.
- [x] `SetupScreen.compose` — four titled boxes tell the sections apart:
      Domain, First superuser details, Google login (can skip), Pi
      provider; Next and the status line sit below them.
- [x] The provider choice shows the masked API key row, or starts pi's
      sign-in with the screen suspended.
- [x] `validate` returns every (field, message) in screen order; the
      screen writes each under its input, toasts them at the bottom, and
      scrolls to the first.
- [x] `piauth.store_key` writes pi's own `{type: "api_key", key}` shape,
      the directory 0700 and the file 0600.
- [x] `auth_check` and `call_model` are gone: a fetched model list is the
      whole test. The report says "Pi is enabled with …".
- [x] The report has bold headings: Login stuff, Google stuff, Pi.
- [x] No Set button: `typed_origin` maps a domain name to its https
      origin and takes the local origin literally; `run_steps` sets the
      domain first when it differs.
- [x] Past the screen, SIGTSTP and SIGCONT get their defaults. Textual's
      driver keeps its own handlers, and a stop and a continue at pi's
      prompt crashed the run in the installer (reproduced).
- [x] pi's other calls run in a session of their own, so ctrl+c reaches
      pi's login prompt alone.
- [x] `desmosuperuserloginlink` creates nothing: its prompts and
      `create_superuser` are gone. With no superuser it prints the
      by-hand `createuser` line and exits 1. `create_first` stays as the
      verb `desmosetup` calls.
- [x] No quitting:
  - [x] `SetupApp.BINDINGS` replaces ctrl+q and ctrl+c with a no-op.
  - [x] No leave hint; the status line says "Fill the fields, then press Next".
  - [x] No skip message and no failure handler: a crash is Python's or
        Textual's own traceback, exit 1.
  - [x] SIGINT is ignored from Save to the report; pi's login child gets
        the default back.
  - [x] The installer starts the command through
        `sudo -n -u debian -i`, not `su -l … -c`: su kills the session on
        ctrl+c (probed), sudo leaves the command standing. The banner
        names no command.
- [x] `deploy/pi-notice.sh`: "run pi, then /login <provider> and /model".
- [x] `addoauth` prints one JSON line — `message`, `provider`,
      `client_id`, `redirect_uri`, `created`; `store` reads it in one
      call. `oauthstatus` and its test are removed.

### Docs

- [x] README: the section rewritten; every "run it again" sentence gone;
      `oauthstatus` out of the command list and the layout tree.
- [x] `.pi/steer.md`: `addoauth`'s JSON line; `oauthstatus` gone.

### Tests

- [x] `ops/tests/test_setup.py` — no skip, no handler, SIGINT through
      the steps, the by-hand Google line, `create_first` without a
      lookup.
- [x] `ops/tests/test_googleoauth.py`, `test_superuserloginlink.py`.
- [x] `ops/tests/test_piauth.py` — `test_pick_is_one_pi_lists` pins the
      pick against the captured table.
- [x] `djangoapp/tests/management/test_addoauth.py` — the JSON line;
      `test_oauthstatus.py` removed.
- [x] VM `desmo` by hand, through the installer's `sudo -n -u debian -i`:
  - [x] ctrl+q and ctrl+c on the screen change nothing.
  - [x] ctrl+c at pi's prompt alone: "Login cancelled", then the report,
        exit 0 — once with a device-code prompt, once with a key prompt.
  - [x] pi's login runs although a credential is on file; the call goes
        out as `glm-5.3`.
  - [x] pi's own files byte-identical afterwards; the test superuser
        removed again.
- [x] `addoauth`'s line: its Django tests, locally and on the VM (a
      real run would overwrite the VM's stored Google credentials).
- [ ] Installer tail: only a real provision exercises it.
