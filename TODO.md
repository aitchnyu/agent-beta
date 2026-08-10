Add type stubs for GitPython — `import git` has no py.typed, so git_data.py uses `Any`/`# noqa: ANN401`
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`
Upgrade ruff. Ensure our lint commands catch any problem. Ensure ruff is tighter.
How will you tighten mypy

Look at using Huey to run background tasks and cron.
Example app should have a cron task that chooses a fact of the day at random. Yes, visiting fact will show one fixed fact of the day.
We need a screen multiplexer which will run runserver, npm run dev, opencode, huey in one terminal. One ./run command for this.
Add this command to near the top of readme. Mention which programs like node, opencode is needed to run the project.

We have to list features in readme in bullet points
  huey for async tasks and 
  can inspect data within models
  agent


## Cron and huey
Require redis
Huey based background and scheduled tasks?
Decorator for tasks
Screen mux for dev, instructions

Does the chore tracker thing need Huey anyway?
rate limiting for http requests?

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed
Run all tests in checkproject and merge coverage from both stages.
When agent is cut off due to redeployment, download latest message to show to user?
How to configure provider and model for Opencode?

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"
Review using agents?

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99
Django 6.1 fetch modes? New Mypy. https://github.com/typeddjango/django-stubs

Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level.

## Task center
Categories and tags

## Notification center
Service worker and PWA?
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Chatting
Upload files

## Deployment
Tool to analyse error logs and stacktraces, both backend and map stacktraces
Opencode as service
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis, log analysis, sourcemap tool
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections

## Future
Mermaid or D2 renderer for showing table relationships or other diagrams