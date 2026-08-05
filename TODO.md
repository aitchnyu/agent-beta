Our app may have separate features. Lets not stuff everything into one file. 
Models are multi file modules, we use multiple modules to separate them. 
views are multi-file modules, use ninja to combine to a whole.
Same for views and playwright tests
Have README.md and docs/ in our app. README.md describes all features in brief. There are individual md files for each feature linked from README. Catalog features in each individual file.

Have a checklist in steer.md to maintain desirable structure when adding or changing feature:
  update readme, mostly to describe feature, not internal implementation
  add individual feature md files in docs and link from readme
  add model module for feature
  add view module for feature and wire all api endpoints
  add tests for models, views, tasks, commands etc

Checklist for views:
  db things that must happen together must happen in a transaction

Add as checklist, we can describe them in detail under a heading or have sub checklists.

Have a facts and todo feature in example app.
Facts have 
  - command - seed db with 20 facts each about cars, science, animals, geography
  -

Homepage should be served by ourapp only, adjust urls.py for that.

-----------

except git.BadName, git.BadObject, git.GitCommandError, ValueError:

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed


Page title for apps - as component

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99

Check the various url modules. Think of git urls not being under a ninja. Look at the error messages and how it could be confusing. Think of consistency of error handlers. Dont ask questions or write files yet.
Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc
Move git urls to Ninja - be consistent

When agent is cut off due to redeployment, download latest message to show to user?

How to configure provider and model for Opencode?

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Include logging, including storing in db in example app

Run all tests in checkproject and merge coverage from both stages.

Readonly mode for whole system, disable get requests too if it mutates data. Do it at middleware level.

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
Whitelist of services
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections

## Future
keep login_for_test?
Mermaid or D2 renderer for showing table relationships or other diagrams