Every Inertia page should include `<PageTitle :value="something"/>`. When its mounted or value changed, it will change document.title. Inertia pages should supply the value. Either they can be descriptive like "Projects" or derived from data like name "John Smith's portfolio" etc.

Update steer.md with the instructions. Hope we have a checklist for inertia pages.

-------

Check the various url modules. Think of git urls not being under a ninja. Look at the error messages and how it could be confusing. Think of consistency of error handlers. Dont ask questions or write files yet.
Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc
Move git urls to Ninja - be consistent

I see
from djangoapp.views.git import (
    git_commit_file_diff,
    git_commit_file_list,
    git_commit_list,
    git_uncommitted_diff,
    git_uncommitted_list,
)
Import the git and use git.fn1, git.fn2 etc

Find all instances of this and make it consistent
except git.BadName, git.BadObject, git.GitCommandError, ValueError:

--------
Include logging, including storing in db in example app
Log backend in json, log stack on api error
Send frontend errors to backend, make it easy to search/filter by line
logger = logging.getLogger(__name__) - agent added

--------
Add type stubs for GitPython — `import git` has no py.typed, so git_data.py uses `Any`/`# noqa: ANN401`
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

--------
Does the chore tracker thing need Huey anyway?

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed
Run all tests in checkproject and merge coverage from both stages.
When agent is cut off due to redeployment, download latest message to show to user?
How to configure provider and model for Opencode?

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99

Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level.

## Task center
Categories and tags

## Notification center
Service worker and PWA?
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Cron and huey
Require redis
Huey based background and scheduled tasks?
Decorator for tasks
Screen mux for dev

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