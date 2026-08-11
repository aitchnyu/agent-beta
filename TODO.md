checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed

## Deployment
Tool to analyse error logs and stacktraces, both backend and map stacktraces
Opencode as service
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis, log analysis, sourcemap tool
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections
How to configure provider and model for Opencode?

Render UI mockup in wide area. 
Mermaid or D2 renderer for showing table relationships or other diagrams
rate limiting for http requests?
Upload files in chat or files

Run all tests in checkproject and merge coverage from both stages.
When agent is cut off due to redeployment, download latest message to show to user?
Review using agents?
Generate multiline, render as multiline:
  ./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99
Django 6.1 fetch modes? New Mypy plugin - https://github.com/typeddjango/django-stubs

## Notification center
Service worker and PWA?
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Future
Have a sequence generator for tables
Central tasks - track chats etc
Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level.