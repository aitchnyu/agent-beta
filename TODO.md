Test `createscratch`, `deployscratch`, `cleanscratch`

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

Google login change
Templates for Allauth
Buttons and stuff may be hardcoded for Google

Logout a user
Generate login link for user with time limit (generate logs)
Show last login for user

Login from localhost?

Use toasts in checklist
Merge Files and Git in top, have Uncommitted, committed, files with highlighting
--------

```
multipass shell app
sudo -u agent -H bash -l
```
Switch to Debian for lower memory usage? Multipass is for Ubuntu. Incus can rewind machines.

apply --3way merges with `./run importtemplate <github-url> <tag>` 
import from git repo tags?

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Readme for end users and devs
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