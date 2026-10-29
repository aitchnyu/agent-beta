Analyze the accesses and thoughts taken by the agent. Make a repo map so agent doesnt have to discover stuff by itself. 

Remove the scout background agent.

Run reviewer agents after coding round. Think if prewarmed reviewer save time over brand new reviewers.

Have image reviewer subagent (prewarmed?) in background that run for every markdown generated. We abandoned that idea earlier.

Whats conventions reviewer and why is it slowest?

Whats the criteria for which agent proposes compact tool?

This is too terse for the user to understand. In future phrase it for a layman:

```
 Approved — compacting the stage-2 transcript, then starting the code stage with the
 wiring files I need:


 compact
```

Why did it need to run python scripts? Cant we avoid that?

Update to latest pi in vm as well as repo

Allow backup and other safe commands. It hit permission prompt.

why is service down when deploying scratch? Why did it need to run migrate
run new reviewers instead of warming
have image reviewers
whats conventions
did we examine if we need to compact
why python command?
Latest pi
allow to backup

have a repo map

Command to print all users?
first last email as args `desmo djangomanage createuser you@example.com --first-name You --last-name Name --superuser`
Dont run shell 
When proposing scripts, split into sections, comment them, meaningful var names
Why are reviewers and other agents printing to terminal and blocking questions?

Why code subagent?
Why 3580 seconds?
wrong time to prewarm reviewer

Implement these as classes instead of functions 

    "cleanscratch": (
        _plain_parser("cleanscratch", "Remove scratch/ and its /tmp/desmo contents."),
        lambda _args, _extra: scratch.cleanscratch(),
    ),
    "test": (
        _test_parser,
        lambda args, extra: testsuite.test(args.labels, extra, is_full=args.full),
    ),

three
threeflet
th

groundwork argv boot-resume guard (.pi/extensions/groundwork/index.ts) — drop when pi fires reason resume/previousSessionFile for `pi -c`/`--session` boot continues (checked 1.0.0-1.4.0: still broken)

`## Working on the app` - split into fe and be

Why last session 18 secs for 3 tests. Fail faster?
`page.goto(f"{self.live_server_url}/chores", wait_until="networkidle")`
sed and python3?
New mypy and other system upgrades
How to be safely run keepdb
Review with same agents

code shortcut menu 
https://localhost:8000/git/commits/2e44fdb/ourapp/docs/screenshots/chore_detail.png - link to file
in files, default is files, then diff (muted text)
move utils to same module as pages/components?

Agent to draw images
layout is too frameworky to an agent trying to modify the layout and add menu buttons. It should be a simple

<Navbar>
    <NavbarItem href=...>Models</NavbarItem>
    <NavbarMenu>
        Code
        <NavbarMenuItem>Models</NavbarMenuItem>
        <NavbarMenuItem>...</NavbarMenuItem>
    <NavbarMenu>
...

Dont mention Huey, mention its a cron. 
do we need ours/? Have pages/system. Move schemas to shared modules like files etc.
deployscratch error - specify which test to do

Decentralize schemas

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

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows chores from earliest to latest due date. Any logged in user can create and complete an instance. Chores have links where we can see past instances and edit. We can archive chores too and view them with a filter.
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
How to document system changes when agent modifies system? Write down scripts?
List backups and time travel
Can agent merge from upstream, minding branch and tags?
Systemd service for backup /srv/
Manually run backup? Add descriptions

Switch to Debian for lower memory usage? Multipass is for Ubuntu. Incus can rewind machines.
Incus for native port forward
Rename to localvm for consistency, deploy from local instead of git (git tracked files)
Remove the ssh port forward `ssh -N -L 8000:localhost:443 ubuntu@192.168.1.56`
local-vm setupalogin
local-vm portforward
Update docs for adding users and login links
Can choose multiple machines, no more init and dev in run, slim down pi command
convert checkframework1 and gate to python script
provision-full and delete-vm should have a prefix

Test dbs get backed up
Run the uv, npm, playwright installs in parallel?
threeflet
Desec dns docs
org/reponame with main thing, landing page
Features - file section with git etc. Readme is crap. Gantt of scout, main work and reviewer prewarm and reviewer action, rework
Just keep pi command without desmo prefix

Admin file uploads - admin can download, both agent and admin can pass files back and forth
UserHistory.record_created(user, user, user.snapshot()) is a mess
Markdown parsing and stuff should return data structures, not just process strings like `assignHeadingIds` in the chain
copy paste detector in main and sub repos

TUI for config, vapid script could be in Python

## Upgrades
Bootstrap 6, with dialog element
Vue vapor
Substitute Eslint for Oxlint, Nov 2026

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
