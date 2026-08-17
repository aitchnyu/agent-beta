/srv/app1 (server could have multiple apps in it)
    main
    scratch
Services
    app1-uvicorn
    app1-opencode

Our process has sudo access?
It has create db access too

Our repo has provision script that executes on a given server.
VM should have a 1gb limit
Install htop in it.

Limit Redis size

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed. Run a subset of tests.
Test with changing site theme. Generate color schemes.
Command to test one backend/playwright test, command to test python
```python
uv run ruff format 2>&1 | tail -1 && uv run ruff check --color=never 2>&1 | tail -1 && uv run mypy --no-color-output . 2>&1 | tail -1 && uv run manage.py shell -c "
from django.template import Template, Context
import pathlib
out = Template('').render(Context())
print('RENDERED:', out)
for u in out.split(): print(u, pathlib.Path('djangoapp/static', u.lstrip('/static/')).is_file())
" 2>&1 | grep -v "objects imported"
```

Log m2m changes too
Decimal fields for money

Upload files in chat or files. We will have to copy files to scratch again.
Can agent render color changes and adding logos?

Buttons spill for agent text box in responsive mode.

Review using agents after finishing coding?

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Tool to analyse error logs and stacktraces, both backend and map stacktraces
Opencode as service
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis, log analysis, sourcemap tool
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections
How to configure provider and model for Opencode?

Django 6.1 fetch modes? New Mypy plugin - https://github.com/typeddjango/django-stubs

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