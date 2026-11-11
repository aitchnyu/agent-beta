gantt
line numbers for highlight.
review of our changes, squash
update repo-map
provision, does its behave as old after much of code gone?

Dont read .env except as direct user request

Move all coder requests to main?

The message before approval for operator should look like this:

```
# geeky stuff

# Conclusion

link to mockup
link to design doc

1 correct mockups and docs
2 approve
```

ie, user should be presented links and important info in the last few lines.

✓ Coder groundwork: chore tracker completed
  ↻7 · 12 tool uses · 15.6k token · 53.2s
  ⎿  GROUNDWORK DONE + preliminary plan (models-first, holding for the gate):
  transcript:
sessions/2026-11-11T13-36-51-466Z_01a1cad3-5b08-7048-9354-a32c9b844716/tasks/2026-11-11T13-42-26-143Z_01a1cad8-765f-7048-9354-a330d
10db4c2.jsonl

 The groundwork is done — the coder holds with a preliminary plan. This is a background notification landing while the
 DesignQuestions ask is open. Per "An ask is terminal": absorb silently, never echo as a new message. The notification says the
 plan is stored; I'll use it in the gate message after the operator answers.

 But wait — I'm in a turn now (the notification triggered a turn). The rule: "Once a message closes with numbered choices +
 Choose... it is the LAST word until the operator picks. Background notifications landing meanwhile — a reviewer finishing, a
 subagent completing — are absorbed silently: steer, collect, triage, but never echo them as new messages."

 So this turn should NOT produce a user-facing message. I should just absorb it. But I need to output something minimal or
 nothing? The notification turn — I can collect the full result so it's banked for the gate message. Let me get the full result
 quietly (a tool call, not a user message), and then end with... hmm. Any output I produce is a user-facing message in this TUI?
 The steer says never echo them as new messages. I should collect the result (so I have the plan when the gate comes) and end the
 turn with essentially no new content — or a single terse line acknowledging nothing needed.

 Actually — "GROUNDWORK is never reported in any form — not its completion, not its progress — the plan surfaces in the gate
 message and nowhere else."

 So: collect the result silently, end the turn with nothing that re-acks the open menu. But I have to write SOMETHING in my reply.
 The safest is an extremely terse line that doesn't report the groundwork and doesn't re-ask: maybe just "(working — your picks
 above still needed)". Hmm, that re-acks the open menu ("never re-ack the open menu").

 Honestly the cleanest: just collect the result and output a minimal no-op line like "Noted — waiting on your picks." That IS
 re-acking. Alternatively output nothing but the tool call... The turn requires a final text response though. I'll keep it to one
 short line that adds no information and reopens nothing. Actually per the spirit: notifications are absorbed silently — the ideal
 response is near-empty. I'll do the get_subagent_result call and reply with a single line like "…" — no. Let me think.

 The notification handling: I'll fetch the full plan now (banking it for the gate message), and my visible reply should be minimal
 — not reporting the groundwork. Something like a single sentence that doesn't mention it. But any sentence risks being noise. The
 guidance for watched-state lines: "Speak when state the operator is watching changes" — groundwork is explicitly excluded from
 reporting.

 I'll reply with a minimal line: "(quiet turn — design picks above are still open; nothing else needed from you)". Hmm, that
 re-acks.

 The absolute minimum that doesn't violate: reply with a single period or "—". That seems weird but matches "absorb silently".
 Maybe better: no text at all after the tool call — just the tool call and end. Can I end a turn with only a tool call and no
 text? The harness usually wants some text, but a turn can end after tool results with an empty-ish reply. I'll output something
 extremely short like "(nothing needed — picks above still open)" — no, re-ack.

 I'll just say nothing meaningful: output "…" Actually let me look at the rule once more: "never echo them as new messages, and
 never re-ack the open menu ('still waiting on your pick'). While the ask is open, watched-state lines (a batch going green,
 verdicts landing) wait too — they ride the turn after the pick."

 So the correct behavior: silent absorption. The turn's visible content should be nothing. I'll emit just the tool call and then a
 bare minimal response. I think a single word like "Noted." is acceptable as non-echoing (it doesn't report groundwork, doesn't
 re-ack the menu). Fine.


 ▸ Get Agent Result  232b4e34-f774-4bf
 ✓ coder · zai/glm-5.3-flash · 12 tool uses · 15.6k token · 2% · 53.2s
   ⎿  Coder groundwork: chore tracker
   ⎿  GROUNDWORK DONE + preliminary plan (models-first, holding for the gate):


 Noted.
```

Show Line numbers for files in plain text mode in file view mode
Dont show diff for new files. Dont link to deleted files in diff, but we can see current version.

--

Permission prompts

19:21:59	cd ../scratch && python3 - <<'EOF' … inline python rewriting ourapp/models/chores.py	raw python3 heredoc
19:24:47	cd ../scratch && python - <<'EOF' … line-splice script on chores/tests	                raw python heredoc
19:30:06	cd ../scratch && rg … settings.py; ./run djangomanage shell -c "…"	                    djangomanage shell -c
19:39:53	cd ../scratch && cat ourapp/docs/home.md | head -3 >/dev/null; python3 -c "print(open(...).count(...))"	python3 -c
19:42:35	cd ../scratch && python - <<'EOF' … writing ChoresPage.vue/ChorePage.vue	            raw python heredoc
19:44:32	cd ../scratch && ./run lintfix && ./run test … && ./run frontendbuild	                chain ending in frontendbuild
19:46:27	./run checkscratch > /tmp/cs.log 2>&1; tail -25 /tmp/cs.log	redirect outside the tree → external_directory
19:48:55	cd ../scratch && uv run playwright install chromium	uv run (rightly denied — your no-install call)
19:50:29	ls /srv/desmo/playwright-browsers/	external_directory_read

Query

Can you find the provision command output?
Does repo still have that error
Why didnt agent test?
Fix silent failure holes

Agent asked user:
```
 1. Whose chores? (a) Just you — each person sees their own list, or (b) a shared household — you assign chores to named members
 2. Chore schedule? (a) One-off with a due date, (b) recurring (e.g. daily / weekly), or (c) both
 3. How does completion work? (a) Simple check-off, or (b) someone verifies/approves it (optionally with points)
 4. On the homepage, how should it surface? (a) plain link, (b) card with a summary (e.g. "3 chores due today"), or (c) reached
    only from another page

 1a 2c 3b 4b, or any mix — reply with your picks
```
Propose a formatting with nested points and marking which is default in bold. Want to add in steer.md, as example.

After getting those inputs, have a list of points of what will be implemented. Split by pages or features. Mention authorization for actions. Want to add in steer.md, as example. Then offer to build mockups+docs, or build app.

why did groundwork thinking and message show?
```
 Groundwork: preliminary chore-tracker plan completed
  ↻8 · 11 tool uses · 11.7k token · 43.2s
  ⎿  Preliminary plan delivered and holding — no files touched, no scratch work.
  transcript:
sessions/2026-11-10T18-51-55-230Z_01a1c6cd-71de-77db-89c9-84eebeb5472a/tasks/2026-11-10T18-54-50-803Z_01a1c6d0-1fb3-77db-89c9-84f37
360093a.jsonl

 The groundwork completed and produced a preliminary plan. Per the steer rules: "GROUNDWORK is never reported in any form — not
 its completion, not its progress — the plan surfaces in the gate message and nowhere else."

 So this notification is absorbed silently — no user-facing message. The design-questions message is already sent and is an open
 ask (numbered choices + Choose). "A
```

`never interleave` - 

Why isnt it reading my requirements properly?

Permission

Increase agent numbers?

chrome is not clear enough

Dont report banked agents - they notify

Why didnt it choose existing command?

Permissions

Why so much time wasted over `// ────────────────────────────────────────────────────────────────────────` line

--

Dont report completion for groundwork
Add `test` command
Other permissions? Check each reviewer
Why did coder finish groundwork too soon
Why did you check logs?
What is main analyzing? Whats it doing about screenshots?/
Why do we have a reviewer agent, we have specialized reviewers only right?
Why no lintfix for long lines
kill reviewers
Why placeholder didnt go?
image reviewer?
--

Levers, in order of expected effect: lower the thinking level for main (its 89% stall share and 40% reasoning ratio make it the single biggest sink; the session log shows 3 thinking_level_change events — you already toggled it once); keep the coder's level but batch reads (its worst stalls preceded single-file reads — one turn deciding 4 reads kills 3 deliberations); and accept the r=0 gateway latency as provider-bound.

Launch reviewers after coding to reduce visual clutter. Do the image review after coding.
Why scratch reviewer took 7s for lintfix and deployscratch 19s, in mockup stage
Whats the batch fixed as ?
Why is correctness checking so much stuff if its tested?
     - Design doc: Chores (https://localhost:8000/files/main/ourapp/docs/chores.md)
Have captions for each images
300s for timeouts for our commands
Close out- link to feature, then doc, then commit

Can coder and reviewer feed each other continously?

cd ../scratch && ./run test ourapp.tests.test_home_views ourapp.tests.test_chores_views ourapp.tests.test_chores_models - 56 tests

https://github.com/bcpierce00/unison

Why wait for image reviewer?
No more image reviewer?
--

1. fix every understood lint failure, investigate bugs one at a time with grounded evidence, with debugging
3. explain the data stuff, have an exemplar in reference app.
In debugging docs, have examples of those techniques 
And have example how to run test command, for both backend and playwright, so no piped output and other mistakes

Try your new debugging techniques with the code you were stuck with.

--
exact exemplar 

wait_until="networkidle"

_log_response - log only non-200 or does existing methods do that?
--

It WAS red — we shipped 4c1fa80 without a final lintfix/typecheck pass: 5 lint errors across three ops/djangoapp test files plus a mypy error (Postdeploychecks.run(None, [])) — the stage-1 presentation deploy halted on our own code; main burned ~2:30 fixing "upstream" mid-presentation and its own deploy battery rejected the tree.

Two-voiced docs: repo-map §5's sdk example shows the system/schemas/ path while app features canonically emit to app/schemas/ — the mirrors reviewer had to resolve the "canon" by cross-reading the reference before clearing it.

The e2e phantom: an intermittent lazy-FK 500 plus a get_by_label substring-matching two fields sent the coder as far as reading Django 6.1's fetch_modes source before concluding "it's a test bug" (24 min) — made worse by lintfix auto-deleting its debug prints mid-hunt.

The guard flagged a state it created itself: yesterday's deploy-loss guard blocked the final deploy over mockup files its own stage-1 deploy left untracked in main/ and graduation correctly deleted from scratch — main trusted the refusal and reached for rm, which timed out twice unattended. That's the session's top lever: the pending-deletion blind spot, which will block every graduating feature until fixed.

--
Grounded answer — the ordering was never confused; deploy-then-commit is exactly what happened. Here is the actual chain:

 1. The workflow's design is deploy → commit. Deploys ship ../scratch/ → main/ and deliberately never commit. Commits in main/
 stay the human's call until the commit offer. So "code ready → deploy → offer commit" is the designed sequence, and I followed
 it.

 2. The final deploy fired on schedule — and was refused by its own guard. After your approval, the review round, and the fix
 cycle (all green), I ran the final deploy. It refused: main/ held two uncommitted files the deploy would delete — the stage-1
 mockup pages, which graduation had removed from scratch. The guard can't tell "intentionally retired" from "about to lose work,"
 so it blocks any rsync that would delete unaccounted files. That's a data-loss safety, not an ordering rule.

 3. The root cause was an interaction, not confusion:
 - stage 1's presentation deploy put the mockups in main/ uncommitted (deploys never commit);
 - graduation then deleted them in scratch;
 - so at final-deploy time they existed only as uncommitted files in main/, and the guard's two legal exits were "commit them" or
   "delete them by hand."

 4. The pause you saw was the guard, plus absent approvals. Deleting needed your approval — the prompt timed out twice with nobody
 at the TUI (90s each), and my standing rule for refused infra is stop-and-ask, never hand-route around it. When you returned, you
 said commit (and denied the hand-deletion), so I took the guard's other exit: commit main/'s state → guard passes → deploy runs →
 everything folded into the single feature commit 5db55dc.
--

Analyse the last pi session. When should we launch coder background agent? We should launch reviewer background agents later to avoid visual clutter.

Why existing codebase was considered buggy?

Why was operator kept in dark after taking requirements? Agent should ask questions and inform about progress/.

Why did we have messages after this? This is noise to user
```
 We need your call before implementation starts:

 1. Revise mockups or docs — tell me what to change
 2. Approve — the coder implements for real

 Choose
```

Show mockups and docs soon

Dont wait for parents batch steering. Just inform, Continue async

Why wait for image reviewer?
No more image reviewer?

when to launch coder background? And reviewers?
Why didnt you use coder for scratch?

Assume tests and deploys could be flaky.
------------

For lever 1, Im considering

generatesdk module.api module1 module2 out/file.ts

It will include the props classes if its an instances of Export, and all BaseModel if its needed by an endpoint. 

Check if any edge cases are not handled.

Make it happen earlier:why
3. Docs and code together (coder owns doc updates per batch)
Was it still doing groundwork? Did coder launch as soon as possible?
`no string literals inside `raise`` - repeal this
sdk paths were wrong
Did agents have to restart? Wy only image is snapshot?
Why think about dirty files on its own?/
Feed final coder reviewer results as and when they come in
Did 2 agents review images?
Why multiple rounds for image review
CSS - append to app.scss to reduce diffs

dont deploy, except with intention to present user with new mockup or to give final deliverable to user. But start reviewer after each phase, make them review stuff. Then try to deploy. But I want automated ways to check code is fine. What do you think. Wait for my approval.

test_loginlink_requires_csrf_token - accumulate users

Remove this line. Its fragile
```
        self.assertEqual(page["props"], {})
```

It changed to

```
        # The chores summary card is the signed-in-only page prop; with no
        # chores yet it is all zeros.
        self.assertEqual(
            page["props"],
            {
                "chores_summary": {
                    "active_count": 0,
                    "overdue_count": 0,
                    "next": None,
                },
            },
        ) 
```

Comment that agent should try not touch existing methods since upstream improvements will cause merge conflicts.

Tons of:
    const page = await get_notifications_page_api({
      after: last.public_id,
      kind: kind.value || undefined,
    })
    if (page instanceof NinjaError) {
      showErrorToast(page, "Could not load more notifications")
      return
    }

Make NinjaError a thrown error. If a non 200 results in just error toast, dont have a try block, let the global handler show error. If we need to handle the error, then catch it and show error. 

minor — frontend/src/system/utils/useAppPage.ts:7 (same claim at :18, .pi/repo-map.md:101, Notifications.vue:27): the taught mechanism "Inertia mutates props in place" is false for the locked @inertiajs/core 3.9.1 — the router replaces the page object (page.value = options.page); the computeds stay live only because usePage().props is itself computed over that swap. Behavior is correct (verified across full visits, router.reload(), and only: partials — the inner props key survives core's merge), but a reader trusting the comment could capture page.props outside a computed and reintroduce the stale-snapshot bug. Fix: reword to "Inertia swaps the whole page object on every visit/reload; parse inside a computed."

Does reference and test app have sdks?
We should have MAINTAIN-CONSISTENCY groupname between steer.md and reference app and test app readme

Use a base class instead of `export: ClassVar[bool] = True`. Compare both approaches.
why so many skipped response schemas?

ruff relaxations are too much

Make a response type for
// skipped: GET /manage/models — no $ref response schema
// skipped: GET /manage/models/{model_name}/id/{public_id} — no $ref response schema
// skipped: GET /manage/models/{model_name}/list — no $ref response schema

UserDetailsPropsSchema cant be autogenerated

# djangoapp/views/users.py
PAGE_PROPS: dict[str, type[Schema]] = {
    "system/users/UserList": UserListPageProps,
    "system/users/UserDetails": UserDetailsPageProps,
    "system/users/UserEdit": UserEditPageProps,
    "system/users/UserHistory": UserHistoryPageProps,
}

Can be enstricten linting for the actual code?

are we having in framework test too? Will we have an ops command to write any .ts file even for multiple ninjas? How does it emit a typed sdk?

avoid manual zod and fetch

dont we have vue components in test app too?

Isnt this mentioninng history unnecessarily, ie we used to have props.props, in this:

```
pages parse BOTH levels via `useAppPage(FeaturePropsSchema)` from
  `system/utils/useAppPage.ts
```

create a prompt file like last prompt file. Yes, be detailed about the phases. Draw a gantt chart in mermaid.

all permission calls?

Launch coder as early as possible
Were main and reviewer-image both reviewing images?
Small arrow grazing is not a problem. After fixing images and cmd verification works, dont review images anymore. Proceed.
"Checking whether the planner has finished its prep" - no, dont wait at all

reviewers finished work fast/

```
 $ cd ../scratch && ./run playwrighttest ourapp.tests.test_chores_playwright 2>&1 | tail -5 (timeout 600s)

 ----------------------------------------------------------------------
 Ran 4 tests in 33.689s
```

Arrows and other overlaps
Permission prompts? journalctl
Agents should choose commands that dont prompt
Interrupt prep time - send feature. Dont prep.
Why are reviewers so fast?

Write design docs like a powerpoint
Option to write design docs and app together

Squash 18baa5f3de346ab21f3fdf32df46a1497abfeb7a and later. Propose a commit message. 
Undo the chore commit on vm. Want to treat vm like a brand new vm, so it should have latest commit. Ensure keys are present. Create a new vm. Share ssh command. Create a new superuser frank.einstien@mgmail.com and share a 24 hour login link.

coder anatomy
45 min
exemplar

How to call cod2ing agent, fg agent?
How to call image review agent and generate pics?
can you move the trust.json and config.json near each other and have a TODO saying wait for ....
 defaultProjectTrust: "always"

       "./run createscratch *": "allow",
      "./run deployscratch": "allow",
Where did inside-vm changes go?

Why python script? Just proceed to deploy
Why permissions?  For cd ../scratch
Just visualize the image to judge it. 
ask_parent was denied for coder?
Mockup and docs together

1. Orientation: 0→23m — paid twice. The implement spawn was resume: null — a fresh session — despite a completed 13.4-minute prep session (19:04→19:18, ended READY via ask_parent) holding exactly this context. The coder re-read the entire reference set, framework files, and test harness (60+ reads, including 239s/101s/80s thinking gaps). Steer says "resume it with implement," but the session had no mechanism spelled out (which agent id, from where) — so it spawned fresh. ~23 minutes wasted by one missing mechanic.

2. Writes + first green: 23→34m — models/views/tests/migration, including one 405-second generation turn right after the first lintfix (composing the fix batch over the lint output).

3. Framework-test debugging spiral: 34→46m (~11.5m). A full-suite run hit failures in pre-existing framework tests (logging/CSRF territory) — the coder wrote /tmp/dbg_*.py scripts, created and iterated a test_zz_dbg.py, ran git stash -u to isolate, and read ops/ source, settings, and deployscratch internals before working its way out. Its contract has no boundary for "a failing test you didn't write."

4. .venv spelunking: ~1.5m — TypedModelMeta, constraints, WSGI classes in site-packages. The no-spelunk rule lives in repo-map §8, which coder.md doesn't carry.

5. First-green ping at 50m (20:09:50, after backend green) — exactly per contract; the review board warmed on it.

6. Frontend + e2e + battery + deploy: 50→61m — final green 20:20:31; the 11-minute tail the reviewers overlapped.

Verdict on the regression (42m → 61m): not feature size — (a) the fresh-vs-resume bug costs ~23m, (b) the framework-test spiral ~11.5m, (c) spelunking ~1.5m. Fix the resume mechanism in steer (name the agent-id source: the prep's ask_parent result carries it), add two coder.md boundaries (pre-existing failures → report, don't repair the framework; never read .venv), and this run would have landed near ~35–40m.

Why pwd confusion
Permission asked for steer_subagent
10 mins for image review
    real oval
    breaking wrap
Why confused on TestResponse
Reduce mypy strictness for project
Why wait for unit tests before setting up reviewers
Queued reviewer
why familiarize again?

 One open question the review surfaced: the repo's steering notes still teach the old API wiring shape the feature upgraded.
 Fixing it touches your steering file, so it's your call.

Commands
Remember 5.3 flash doesnt have medium
Was session faster?
Why fresh coder?
reviwer assymmetry?

Review last commit, both pi and debug
Provision vm in place

How to to fewer turn boundaries. 
How to launch subagent at lower thinking level for same model without hardcoding it?

I wanted a single reviewer for all images in md
Instead I see
    why for n in 1 2 3 4
System must avoid this slowdown

Why ` python3 - <<'EOF'`

why play with json.loads

When system wants to run a bash command, explain it to user in plainish language so user can make an informed decision

Whats the end message given to user? Lets discuss

Why compact after review?
Why did session go idle after compact was cancelled?

Why didnt you remove placeholder and why reviewer didnt catch it? 

how to hide thinking?
How to justify each command?
End message too geeky?

Why did agent have to run python scripts at all and run django resolver? Werent the reference enough?
When and why was compaction decided? It was counterproductive right? 
why didnt session automatically continue after compaction?
Why didnt it continue after I canceled a compaction?
Why did it call curl? Can we have an approved pattern that steer.md can use and which agent supports? Its for localhost.

Analyze the accesses and thoughts taken by the agent. Make a repo map so agent doesnt have to discover stuff by itself. 

Remove the scout background agent.

Run reviewer agents after coding round. Think if prewarmed reviewer save time over brand new reviewers.

Have image reviewer subagent (prewarmed?) in background that run for every markdown generated. We abandoned that idea earlier.

Whats conventions reviewer and why is it slowest?


This is too terse for the user to understand. In future phrase it for a layman:

```
 Approved — compacting the stage-2 transcript, then starting the code stage with the
 wiring files I need:


 compact
```

Why did it need to run python scripts? Cant we avoid that?

Update to latest pi in vm as well as repo

Allow backup and other safe commands. It hit permission prompt.

why is service down when deploying scratch? Why did it need to run migrate
run new reviewers instead of warming
have image reviewers
whats conventions
did we examine if we need to compact
why python command?
Latest pi
allow to backup

have a repo map

Command to print all users?
first last email as args `desmo djangomanage createuser you@example.com --first-name You --last-name Name --superuser`
Dont run shell 
When proposing scripts, split into sections, comment them, meaningful var names
Why are reviewers and other agents printing to terminal and blocking questions?

Why code subagent?
Why 3580 seconds?
wrong time to prewarm reviewer

Implement these as classes instead of functions 

    "cleanscratch": (
        _plain_parser("cleanscratch", "Remove scratch/ and its /tmp/desmo contents."),
        lambda _args, _extra: scratch.cleanscratch(),
    ),
    "test": (
        _test_parser,
        lambda args, extra: testsuite.test(args.labels, extra, is_full=args.full),
    ),

three
threeflet
th

groundwork argv boot-resume guard (.pi/extensions/groundwork/index.ts) — drop when pi fires reason resume/previousSessionFile for `pi -c`/`--session` boot continues (checked 1.0.0-1.4.0: still broken)

`## Working on the app` - split into fe and be

Why last session 18 secs for 3 tests. Fail faster?
`page.goto(f"{self.live_server_url}/chores", wait_until="networkidle")`
sed and python3?
New mypy and other system upgrades
How to be safely run keepdb
Review with same agents

code shortcut menu 
https://localhost:8000/git/commits/2e44fdb/ourapp/docs/screenshots/chore_detail.png - link to file
in files, default is files, then diff (muted text)
move utils to same module as pages/components?

Agent to draw images
layout is too frameworky to an agent trying to modify the layout and add menu buttons. It should be a simple

<Navbar>
    <NavbarItem href=...>Models</NavbarItem>
    <NavbarMenu>
        Code
        <NavbarMenuItem>Models</NavbarMenuItem>
        <NavbarMenuItem>...</NavbarMenuItem>
    <NavbarMenu>
...

Dont mention Huey, mention its a cron. 
do we need ours/? Have pages/system. Move schemas to shared modules like files etc.
deployscratch error - specify which test to do

Decentralize schemas

__root__ error rendering
raise ApiError(403, "CSRF verification failed.") - can take dict/string/any

raise HttpError(409, "Order already shipped")
# → 409 {"detail": "Order already shipped"}

fieldError will take custom messageFor

Actually create will just return `_todo_out(todo)` or raise error
We have ninjaPost<TodoListOutSchema>({
        text: text.value,
        expected_row_version: 0,
      }) 
instead of postJson
It returns TodoListOutSchema or a NinjaError object. 

With a NinjaError object we can .errorAtPath(["body", "payload", "nested", 0]) and it will try to fetch error at path and return ErrorDetail or null. We can also call .childForPath(["body", "payload",]) which returns a child NinjaError which we can call without prefix.

test_home_views.py needed to test chores_summary changes. Did it waste time?

boolean to true-false
varchar to text
No chore_id int, chore Chore

Mockup error at https://localhost:8000/mockup/MockupChores - redirect to home?

Why 422 toast happened instead of validation? 

Agent in the vm generate `page.goto(f"{self.live_server_url}/chores", wait_until="networkidle")` - is this too slow?

Move schemas to inline with Vue files if used by one file?


dont supply these props
        #     "props": {
        #         "is_authenticated": True,
        #         "display_name": "Alice Smith",
        #         "public_id": "<url-safe public id>",
        #     },

when did reviewer warm up? Could we have launched it earlier?

Examine the images within https://localhost:8000/files/main/ourapp/docs/chores.md#who-can-do-what and others.
actors and ovals are diff sizes
How to update steer.md to generate people and subjects/objects of fixed size
And blocks should have fixed width

have usecase diagrams in first place? We were stuck with mermaid which forced us into usecase mould. Is there an alternative diagram thats undertandable to laymen but well documented?

direction: down direction is applicable to inner containers? The top level thing directs blocks downward. Seems inner blocks scroll horizontally.

each line in md is around 80 chars wide for readability. Update steer.md with this.

md - overflow scroll, show absolute time
Then tell me in which contexts we use relative times.
Time taken for each stage?

Why noninteractive components?

mockups - were mockup deployments fast enough? Avoid writing python files?

css
favicon
home icon

d2 with full lucide icons? No usecase diagrams. How to minimize horizontal scrolling? Have a nice viewer

toggle mode for md rendering/plain rendering in file view. We can download md files as pdf.

_capture_page and _shot_below_navbar names

`Menu` and others have an ugly dropdown icon

Merge test and reference app?
Does shortcut deploy mode check ours/ 
files-mode-btn and other css names

Branding. Dark mode.

How to track time taken for provisioning
Remove https://localhost:8000/accounts/login/, show items in dropdown only. 
User view form should be single column, each checkbox in own line. Describe each field and checkbox

Lets make a chore tracker. We should have chores which have a repetition schedule of either days per week or every N days/weeks/months. It shows chores from earliest to latest due date. Any logged in user can create and complete an instance. Chore titles are clickable links that leads to details page where we can see past instances (who and when completed it) and edit. We can archive chores too and view them with a filter.
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
How to document system changes when agent modifies system? Write down scripts?
List backups and time travel
Can agent merge from upstream, minding branch and tags?
Systemd service for backup /srv/
Manually run backup? Add descriptions

Switch to Debian for lower memory usage? Multipass is for Ubuntu. Incus can rewind machines.
Incus for native port forward
Rename to localvm for consistency, deploy from local instead of git (git tracked files)
Remove the ssh port forward `ssh -N -L 8000:localhost:443 ubuntu@192.168.1.56`
local-vm setupalogin
local-vm portforward
Update docs for adding users and login links
Can choose multiple machines, no more init and dev in run, slim down pi command
convert checkframework1 and gate to python script
provision-full and delete-vm should have a prefix
vm provsion should print 
Pi theme should be bolder
`./run init` is dangeourus

Test dbs get backed up
Run the uv, npm, playwright installs in parallel?
threeflet
Desec dns docs
org/reponame with main thing, landing page
Features - file section with git etc. Readme is crap. Gantt of scout, main work and reviewer prewarm and reviewer action, rework
Just keep pi command without desmo prefix
File shows which commits it was part of and if its part of uncommitted changes
Highlight readme in any dir

Admin file uploads - admin can download, both agent and admin can pass files back and forth
UserHistory.record_created(user, user, user.snapshot()) is a mess
Markdown parsing and stuff should return data structures, not just process strings like `assignHeadingIds` in the chain
copy paste detector in main and sub repos

TUI for config, vapid script could be in Python

## Upgrades
Bootstrap 6, with dialog element
Vue vapor
Substitute Eslint for Oxlint, Nov 2026

## Future
Have a sequence generator for tables
Central tasks - track comments and deadlines
rate limiting for http requests?
Model logs should store FK name, link, url and M2M changes too
Whitelist services for outbound connections
Redis and db memory usage?
Group and mute notification groups
Readonly mode for app?
Mutation tests?
Install playwright on first run?
Store downthinking entries for models for implementing agent
Use pipe, dont have managers
Plantuml
uv and pnpm for cached builds across folders