Lets make a chore tracker. We should have chores which have a repetition schedule of either days per week or every N days/weeks/months. It shows chores from earliest to latest due date. Any logged in user can create and complete an instance. Chore titles are clickable links that leads to details page where we can see past instances (who and when completed it) and edit. We can archive chores too and view them with a filter.
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
vm provsion should print 
Pi theme should be bolder
`./run init` is dangeourus

Test dbs get backed up
Run the uv, npm, playwright installs in parallel?
threeflet
Desec dns docs
org/reponame with main thing, landing page
Features - file section with git etc. Readme is crap. Gantt of scout, main work and reviewer prewarm and reviewer action, rework
Just keep pi command without desmo prefix
File shows which commits it was part of and if its part of uncommitted changes
Highlight readme in any dir

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
Install playwright on first run?
Store downthinking entries for models for implementing agent
Use pipe, dont have managers
Plantuml
uv and pnpm for cached builds across folders