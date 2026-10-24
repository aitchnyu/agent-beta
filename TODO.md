__root__ error rendering
raise ApiError(403, "CSRF verification failed.") - can take dict/string/any

raise HttpError(409, "Order already shipped")
# → 409 {"detail": "Order already shipped"}

fieldError will take custom messageFor

Actually create will just return `_todo_out(todo)` or raise error
We have ninjaPost<TodoListOutSchema>({
        text: text.value,
        expected_row_version: 0,
      }) 
instead of postJson
It returns TodoListOutSchema or a NinjaError object. 

With a NinjaError object we can .errorAtPath(["body", "payload", "nested", 0]) and it will try to fetch error at path and return ErrorDetail or null. We can also call .childForPath(["body", "payload",]) which returns a child NinjaError which we can call without prefix.

test_home_views.py needed to test chores_summary changes. Did it waste time?

boolean to true-false
varchar to text
No chore_id int, chore Chore

Mockup error at https://localhost:8000/mockup/MockupChores - redirect to home?

Why 422 toast happened instead of validation? 

Agent in the vm generate `page.goto(f"{self.live_server_url}/chores", wait_until="networkidle")` - is this too slow?

Move schemas to inline with Vue files if used by one file?


dont supply these props
        #     "props": {
        #         "is_authenticated": True,
        #         "display_name": "Alice Smith",
        #         "public_id": "<url-safe public id>",
        #     },

when did reviewer warm up? Could we have launched it earlier?

Examine the images within https://localhost:8000/files/main/ourapp/docs/chores.md#who-can-do-what and others.
actors and ovals are diff sizes
How to update steer.md to generate people and subjects/objects of fixed size
And blocks should have fixed width

have usecase diagrams in first place? We were stuck with mermaid which forced us into usecase mould. Is there an alternative diagram thats undertandable to laymen but well documented?

direction: down direction is applicable to inner containers? The top level thing directs blocks downward. Seems inner blocks scroll horizontally.

each line in md is around 80 chars wide for readability. Update steer.md with this.

d2 layout engine
d2 theme
d2 auto dark mode?

scroll to top and permalinks?

md - overflow scroll, show absolute time
Then tell me in which contexts we use relative times.
Time taken for each stage?

Why noninteractive components?

mockups - were mockup deployments fast enough? Avoid writing python files?

css
favicon
home icon

d2 with full lucide icons? No usecase diagrams. How to minimize horizontal scrolling? Have a nice viewer

toggle mode for md rendering/plain rendering in file view. We can download md files as pdf.

_capture_page and _shot_below_navbar names

`Menu` and others have an ugly dropdown icon

Merge test and reference app?
Does shortcut deploy mode check ours/ 
files-mode-btn and other css names

Branding. Dark mode.

How to track time taken for provisioning
Remove https://localhost:8000/accounts/login/, show items in dropdown only. 
User view form should be single column, each checkbox in own line. Describe each field and checkbox

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
How to document system changes when agent modifies system? Write down scripts?
List backups and time travel
Can agent merge from upstream, minding branch and tags?

Switch to Debian for lower memory usage? Multipass is for Ubuntu. Incus can rewind machines.
Incus for native port forward
Rename to localvm for consistency, deploy from local instead of git (git tracked files)
Remove the ssh port forward `ssh -N -L 8000:localhost:443 ubuntu@192.168.1.56`
local-vm setupalogin
local-vm portforward
Update docs for adding users and login links

Dont mention Huey, mention its a cron.  
do we need ours/
deployscratch error - specify which test to do

threeflet
Desec dns docs
org/reponame with main thing, landing page
Features - file section with git etc. Readme is crap.

Admin file uploads - admin can download, both agent and admin can pass files back and forth
UserHistory.record_created(user, user, user.snapshot()) is a mess
Markdown parsing and stuff should return data structures, not just process strings like `assignHeadingIds` in the chain
copy paste detector in main and sub repos

TUI for config, vapid script could be in Python

## Upgrades
Bootstrap 6, with dialog element
TSC7 if compatible, Vue vapor

## Future
Have a sequence generator for tables
Central tasks - track comments and deadlines
rate limiting for http requests?
Model logs should store FK name, link, url and M2M changes too
Whitelist services for outbound connections
Redis and db memory usage?
Group and mute notification groups
Readonly mode for app?
Mutation tests?
