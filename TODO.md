createsuperuser - should be promote, create user for 
Django 6.1 fetch modes? New Mypy plugin - https://github.com/typeddjango/django-stubs

Auth for ttyd
hash links in md view dont work
How to support multiple apps?
Extend playwright tests, test after building vm too
Accelerate file serving with Caddy - have FileResponse
Add agent command to repo only
Replace agent?
Redis size?
../djangoapp/static/djangoapp/assets/rolldown-runtime-QTnfLwEv.js      0.69 kB │ gzip:   0.42 kB

Have a mockup laf?
./run checkscratch

apply --3way
./run importtemplate <github-url> <tag> 
import from git repo tags?

postgres username and password
Set git user, set opencode credentials
Worker count for granian and huey config

CSRF_TRUSTED_ORIGINS diverge

-------------

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed. Run a subset of tests.
Test with changing site theme. Generate color schemes.
Decimal fields for money
Command to test one backend/playwright test, command to test python
```bash
uv run ruff format 2>&1 | tail -1 && uv run ruff check --color=never 2>&1 | tail -1 && uv run mypy --no-color-output . 2>&1 | tail -1 && uv run manage.py shell -c "
from django.template import Template, Context
import pathlib
out = Template('').render(Context())
print('RENDERED:', out)
for u in out.split(): print(u, pathlib.Path('djangoapp/static', u.lstrip('/static/')).is_file())
" 2>&1 | grep -v "objects imported"
```

```bash
ssh app1 'cd /srv/app1/main && .venv/bin/python manage.py shell -c "from djangoapp.models import User; [print(u.pk, u.username, u.email, u.is_superuser) for u in User.objects.all()]"'
```

New agent
    command permission model
    interactive over network
    lower memory usage
    subagents to review
    can specify auth secrets path
    No more pty_shim
    No need of .git for parent

https://github.com/anomalyco/opentui/issues/1333

# Relative cutoff: only releases from the last 7 days are eligible
exclude-newer = "P7D"

_UNSET caught earlier stage
ttyd MemoryMax too low

Log m2m changes too

Google login change
Templates for Allauth
Buttons and stuff may be hardcoded for Google

Upload files in chat or files. We will have to copy files to scratch again.
Can agent render color changes and adding logos?

Buttons spill for agent text box in responsive mode.

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Tool to analyse error logs and stacktraces, both backend and sourcemap stacktraces
Serve files in fs, accelerate using Caddy
Who is committing to git
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections
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