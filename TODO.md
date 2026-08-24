Auth for ttyd
Switch to Colima and Incus
Switch to Debian for lower memory usage?
hash links in md view dont work
Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Redis size?
../djangoapp/static/djangoapp/assets/rolldown-runtime-QTnfLwEv.js      0.69 kB │ gzip:   0.42 kB

apply --3way
./run importtemplate <github-url> <tag> 
import from git repo tags?

CSRF_TRUSTED_ORIGINS diverge

No more login-for-test

We were assuming a web ui.
Questions, todos and subagents were banned with opencode. Lets bring them back.
Have a mockup laf? No more mermaid and mockups.
------------

checkall - rename to checkframework1
We will have a checkframework2 which builds vm and tests our test app
It tests /agent is accessible only by superuser

checkscratch - it will check if files outside ourapp/ and ours are changed. If outside files are changed it will trigger more tests.
We will run a subset of framework views and playwright tests.
Identify and tag those tests. It will test existing stuff is not broken, but will not add too much time

Test with changing site theme. Generate color schemes.

-------------

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

Decimal fields for money

# Relative cutoff: only releases from the last 7 days are eligible
exclude-newer = "P7D"

Google login change
Templates for Allauth
Buttons and stuff may be hardcoded for Google

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Tool to analyse error logs and stacktraces, both backend and sourcemap stacktraces
Serve files in fs, accelerate using Caddy
Backup regularly - https://www.pghardstorage.org/examples
Provision in vm with curl|bash

## Notification center
Service worker and PWA?
Have link to correct place
Group them by url/key
Browser notification/email to send to user
Which ones to mute?

## Future
Have a sequence generator for tables
Central tasks - track chats etc
rate limiting for http requests?
Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level. How to do it for tasks?
Support multiple apps in same server
Model logs should store FK name, link, url and M2M changes too
Comments and deadlines
Whitelist services for outbound connections