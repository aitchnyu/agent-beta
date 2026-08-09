Page title for apps - as component

Every Inertia page should include `<PageTitle :value="something"/>`. When its mounted or value changed, it will change document.title. Inertia pages should supply the value. Either they can be descriptive like "Projects" or derived from data like name "John Smith's portfolio" etc.

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

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99

When agent is cut off due to redeployment, download latest message to show to user?

How to configure provider and model for Opencode?

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Include logging, including storing in db in example app

Run all tests in checkproject and merge coverage from both stages.

Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level.

## Error tracking
Log backend in json
Which analysis tool?
Send frontend errors to backend, make it easy to search/filter by line
Show source maps for main and sub apps? How to read errors from them?

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

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

Add type stubs for GitPython — `import git` has no py.typed, so git_data.py uses `Any`/`# noqa: ANN401`

logger = logging.getLogger(__name__) - agent added

## Deployment
Tool to analyse error logs and stacktraces
Opencode as service
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections

## Future
keep login_for_test?
Mermaid or D2 renderer for showing table relationships or other diagrams