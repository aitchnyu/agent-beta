Headless chromium, easier to install? PLAYWRIGHT_BROWSERS_PATH
Do we need /agent? No more slash-agent?
Obscura for tests?
SSH is the real thing. Have a real tui to manage users?

--------------

Why did agent ask me for baseline commit in base? Main was supposed to have a commit. And it should have been copied to scratch. Copy the venv and node modules for speed.

Share the link of mockup and design docs at end of message. Why did it choose to share html link? Use absolute links only


Rename framework-subset to scratch-test-subset. One smoke test should load homepage.


Why did it create git user and commit?

Reduce crush memory use?

How to notify?

Designated mockup places?

When does Crush log?
Prevent overwrites of deployed stuff.
When do we commit? Commit message?
Caddy error message

https://daverupert.com/2026/08/microlighter/ - use native mermaid, no need of html in md

Test `createscratch`, `deployscratch`, `cleanscratch`

hash links in md view dont work

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

Need ssh access for phone backups?

Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

--------

Switch to Debian for lower memory usage? Multipass is for Ubuntu.

Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Redis size?
../djangoapp/static/djangoapp/assets/rolldown-runtime-QTnfLwEv.js      0.69 kB │ gzip:   0.42 kB
Decimal fields for money

apply --3way
./run importtemplate <github-url> <tag> 
import from git repo tags?

CSRF_TRUSTED_ORIGINS diverge

Google login change
Templates for Allauth
Buttons and stuff may be hardcoded for Google

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Tool to analyse error logs and stacktraces, both backend and sourcemap stacktraces, mlr for logs
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