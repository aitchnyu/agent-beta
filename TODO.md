Outline of md files
raw=true?
hash links in md view dont work
https://daverupert.com/2026/08/microlighter/ - use native mermaid, no need of html in md
<div class="rich-diagram">
```stateDiagram-v2
    [*] --> pending : generated from the schedule
    pending --> completed : user completes
    completed --> pending : undo
    completed --> [*]
```
</div>
use the HTML-safe lookalikes `‹` `›` `∧`
Git: link to real filename, double diff

Agent command: resume old session?

Unhelpful command:
```
multipass shell app
sudo -u agent -H bash -l
```

Use Goose agent?
Cant select options in one tap
Not showing command output
Need equivalent `option notifications bell`
How to notify?

Avoid this app fn?
multipass exec app -- sudo -u app -H bash /srv/app/main/deploy/vm.sh \
    app .venv/bin/python manage.py promotetosuperuser <email>

Headless chromium, easier to install? PLAYWRIGHT_BROWSERS_PATH
Obscura for tests?
--------------
Prevent overwrites of deployed stuff.
When do we commit? Commit message?

Test `createscratch`, `deployscratch`, `cleanscratch`

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

--------

Switch to Debian for lower memory usage? Multipass is for Ubuntu.

Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Redis size?
../djangoapp/static/djangoapp/assets/rolldown-runtime-QTnfLwEv.js      0.69 kB │ gzip:   0.42 kB
These requests not in a page that needs mermaid:
https://app.local/static/djangoapp/assets/mermaid-core-CVHOu6Nn.js
https://app.local/static/djangoapp/assets/mermaid-uncommon-BQPmhl13.js
Decimal fields for money

apply --3way
./run importtemplate <github-url> <tag> 
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