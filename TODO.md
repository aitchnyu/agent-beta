Test `createscratch`, `mergescratch`, `cleanscratch`
deploy_ourapp

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

We were assuming a web ui, so thats why we were returning html markup in our agent
Go back to returning .md markup
We can deploy mockups to the application.
We will have a mockup 
Feature lifecycle?
Questions, todos and subagents were banned with opencode. Lets bring them back.
No more mermaid and mockups within agent.

Test with changing site theme. Generate color schemes.

--------

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

Decimal fields for money

Google login change
Templates for Allauth
Buttons and stuff may be hardcoded for Google

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Tool to analyse error logs and stacktraces, both backend and sourcemap stacktraces
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