We are changing the apps thing. 

We will no longer have apps/ with its inner git. Remove that. No more dynamic module loading and Application models. No more buildbackend and buildfrontend.

This project is a template, user must clone this and then add stuff to ourapp/ app. Its a normal django app. We will still have djangoapp. User will use the agent on server which will modify only ourapp/ and deploy it. We will have one frontend for entire app. Agent can modify frontend/src/components/ours and frontend/src/pages/ours. our steer.md must reflect that. User usually intends to do that.

We will still have BaseTable in djangoapp which is used as parent of concrete models in ourapp/. Models are regular concrete classes. But rename to BaseModel. We will have a models management set of pages, similar to app management pages. Superuser can see a list of models in ourapp/ with their docstrings and see a list of rows and sort by x. For fk columns, use the model method to generate urls.

Project is like:

```
parent/
    main
    copy
```
main will contain the code and .git. Opencode can act upon parent/. When we ask agent to add a new feature, it will copy main (minus .git and node_modules) to a new copy/, edit those, and runs full suite of lints and tests. After tests pass offer to commit. When they pass, we copy those changes to main. In dev, it would automatically reload. In future we should ask prod to reload the app.

---------
We are not testing _ourapp_models, _confined_to_repo, files endpoints fully. We are just using mocks.

We assume we should use same checkall for main and copy. Have an another function checkproject that includes those tests. We will have a test app.
It will have 
    ourapp/
        ...its files...
    frontend/
        src/
            components/
                ours
            pages/
                ours
We will have code that exercises models, git and files. We will have tests in djangoapp for models, git and files which are exlcluded by a tag. When we run checkproject, it will create a copy, then copy the test app and run those excluded tests.

Reference app should also be same format. And we should test reference app too. Reference app ships with tests inside itself.


---------
How to test _ourapp_models
How to test _confined_to_repo (git)
How to test files endpoint
Have a test app with all dirs. Make git changes. Run tests and merge coverage.
reference - have full tree
Have a basic ourapp/

Whats the main url
Maintain a deployment - how to sync changes?
Ref app
How to require rsync
Why do we need BaseModel?
Can we keep adding stuff even if not complete?
----------
Parallel command prompts problems?

Render relationships in fe? Focus on table
Does readme tell how to render tables?

Shell command deleting app by itself?
`./run djangomanage shell -c` - ban this?
Dont mark something as done if network fails
Add a readme?
Dont commit before asking
Dont show full read output
Dont show full edit output
Reject overly long commands - like using cat instead of write
Ensure long commands have newlines

Readonly mode for whole system, disable get requests too if it mutates data.

Page title for apps

./run typecheck
uv run mypy apps/TodoList2App/app.py
playwright_test - it uses existing db, reverts

os.environ.get("OPENCODE_BASE_URL", f"http://{_OPENCODE_HOST}:{_OPENCODE_PORT}")

Tasks center - categories
Shared widgets and components, layout etc
Share error tracking in FE

## Notification center
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Cron and huey
Decorator for tasks

## Chatting
Upload files

### Request-response
Plan - gather requirements
Mention files - link to them
Mention code - show

Show source maps for main and sub apps? How to read errors from them?

How to make /prompt endpoint as stateless as possible?
Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

logger = logging.getLogger(__name__) - agent added

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

Huey based background and scheduled tasks?
-----------
Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc

## Deployment
Async support for terminal
Long lived connections for notifications
Tool to analyse error logs and stacktraces
Opencode as service
Whitelist of services
Serve files in fs, accelerate using Caddy
Who is committing to git

## Future
keep login_for_test?
Offline workers and notifications
Error handling for frontend and backend
Whitelist services for outbound connections
Mermaid or D2 renderer for showing table relationships or other diagrams