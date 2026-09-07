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