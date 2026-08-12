Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

`Awaiting your reply` is premature - I clicked it and it was thinking

update steer - Dont use get_user_model() - use our user model only
should we ask ruff not to emit colors? `ourapp/tests/test_chores_models.py:7: [1m[31merror:(B[m Module (B[m[1m"ourapp.models"(B[m does not explicitly export attribute (B[m[1m"Chore"(B[m  (B[m[33m[attr-defined](B[m`
Task checklist in steer should mention:
  Ask how to link or summarize in homepage or otherwise make it accessible from another page
  If there is a pending scratch, ask if it should be deleted

When agent is cut off due to redeployment, download latest message to show to user?

Review using agents?

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed
Profile test suite for speed

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