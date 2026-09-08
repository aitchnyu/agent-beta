When I view md file, I want to see outline of headlines in the top. It should expand if more than 300px.

Hash links in md view doesnt work, ensure those links are rendered correctly. Same for links to other files.

Have tests for all of these.

We had mockups and mermaid in md using html classes. Now render mermaid using ```mermaid``` markup and ensure it renders

We used to have this:

<div class="rich-diagram">
```stateDiagram-v2
    [*] --> pending : generated from the schedule
    pending --> completed : user completes
    completed --> pending : undo
    completed --> [*]
```
</div>

Steer also has messages like: use the HTML-safe lookalikes `‹` `›` `∧`

We will no longer have html in markdown for mockup and mermaid.

Git uncommitted files and commit viewer will link to file url
Diffs will be rendered in two panes or one pane depending on viewport width

Also is U the symbol for new file as in `U ourapp/tests/test_chores_playwright.py`. Have new, mod, del next to filenames with color coding

---------
1. Reference-cloning replaced requirements gathering (the core deviation). On "go", the agent never produced a requirements list or asked anything. It declared "The reference's facts feature is nearly a twin of this request" and used the reference app as a substitute for elicitation — then built the whole twin: DB model, migration, Huey cron task, a seed command with 20 hardcoded proverbs it invented, design doc, README entry, homepage link, live-DB seeding. Nothing asked for a database, a curator story, a timezone for "day", or data provenance. The user's earlier corrections ("just show one") were already evidence that the agent's inferred scope ran ahead of stated intent — and it doubled down at the exact moment it should have slowed down.

2. The 22-minute silent mega-build. "Go" compressed every remaining stage (build → test → migration → deploy → seed → reviewer) into one uninterrupted turn of batched edits and lint/mypy fix loops (9 ruff issues, "two chars over — trimming", mypy narrowing…). Stage summaries existed for stages 1–2 but vanished exactly when the work got biggest. "What are you doing" wasn't a scope objection — it was lost visibility and trust.

3. Weak finish-line self-audit. After "commit" it left base.html uncommitted (calling it "pre-existing drift") and scratch alive — the two things its own workflow treats as end-of-job conditions. The user had to catch both, then ask for the merge it should have proposed. "Finished" was declared while the operator still had cleanup work to assign.

4. Unrequested production action. Seeded the live database unprompted (it even predicted the permission prompt this would raise) rather than asking whether 20 agent-invented proverbs should go in the operator's DB.

Root causes
The steer workflow's approve-gate was treated as approving the reference feature in full, not a plan for this requirement.
"Have a task to…" (an increment) was read as a trigger to re-derive the complete design.
No check-in cadence during build; no pre-"done" checklist (clean tree? scratch gone? one logical commit? live URL shown?).
What would have kept it on the path
After "go": one message — requirement list + what it plans to clone from the reference + open questions (data source, timezone) + batches — and a quick ack before the mega-build.
One check-in per batch/stage during build (it already does this for mockups; it stopped when it mattered most).
A finish gate it runs itself: git status clean, scratch deleted, single feature commit, seeded state confirmed — so the operator never has to say "you forgot…".

----------

Final checklist:
    git status clean
    single feature commit
    all migrations and production scripts executed
    scratch gone
    single sentence report to user

deployscratch should run hostnames command. Echo a 'App is available under hostnames' before printing it.

Huey has atleast 1 workers. Change it.

Have serial numbers for questions. We got questions like

```
3. Just finished the agent review (a second agent re-read the whole diff against your requirement) — verdict: no must-fixes,           
    requirements fully covered. It flagged two cosmetic nits: a stale "mockup" comment in style.scss and the empty-state copy showing   
    an ops command to visitors.                                                                                                         
                                                                                                                                        
 Remaining: fix those two nits (2-minute deploy), then the last step is offering to commit — commits stay your call.                    
                                                                                                                                        
 Fix the two nits and then give you the commit summary?
```


And:
```
- commit / hold
```

Make an example question in steer:
```
We need to do this. Here are your choices

1. choice 1
2. choice 2

Choose
```

Why too much changes?

Render git as tree
---------------

We have `Security & data access` and `Authoritative docs` section in steer. Move the content to elsewhere.

In models checklist in steer, ensure we use DecimalField for money.

I see this function used:
multipass exec app -- sudo -u app -H bash /srv/app/main/deploy/vm.sh \
    app .venv/bin/python manage.py promotetosuperuser <email>
Rename to run-as-app

Unhelpful command:
```
multipass shell app
sudo -u agent -H bash -l
```
--------------
Prevent overwrites of deployed stuff.

Test `createscratch`, `deployscratch`, `cleanscratch`

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

--------

Switch to Debian for lower memory usage? Multipass is for Ubuntu.

apply --3way merges with `./run importtemplate <github-url> <tag>` 
import from git repo tags?

Google login change
Templates for Allauth
Buttons and stuff may be hardcoded for Google

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Tool to analyse error logs and stacktraces, both backend and sourcemap stacktraces, mlr (miller) for logs
Backup regularly - https://www.pghardstorage.org/examples
Provision in vm with domain with curl|bash

## Notification center
Service worker and PWA?
Have link to correct place
Group them by url/key
Browser notification/email to send to user
Which ones to mute?

## Future
Have a sequence generator for tables
Central tasks - track comments and deadlines
rate limiting for http requests?
Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level. How to do it for tasks?
Support multiple apps in same server
Model logs should store FK name, link, url and M2M changes too
Whitelist services for outbound connections
Have a real tui to manage users?
Headless chromium, easier to install? PLAYWRIGHT_BROWSERS_PATH. Obscura for tests?
Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Redis and db memory usage?