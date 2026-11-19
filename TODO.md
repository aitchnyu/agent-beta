Select.BLANK
Better coverage and more checkframework2 tests

check all the textual code. Find wrong and outdated shit like .BLANK. Any way to architect it to be more declarative than selecting each element and changing its state? Dont write code till I allow.

Which places have poor test coverage? Check recent commits. What needs to be included in checkframework2?

Launch the setup
No need of login warning for homepage?
Can choose multiple machines, no more init and dev in run, slim down pi command
No more desmo command
/login openai-codex, luna, test with real and fake
Providers with recommended models - Openrouter

Update docs for adding users and login links
Pi theme should be bolder
`./run init` is dangeourus

Lets make a chore tracker. We should have chores which have a repetition schedule of either days per week or every N days/weeks/months. It shows chores from earliest to latest due date. Any logged in user can create and complete an instance. Chore titles are clickable links that leads to details page where we can see past instances (who and when completed it) and edit. We can archive chores too and view them with a filter.
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
How to document system changes when agent modifies system? Write down scripts?
List backups and time travel
Can agent merge from upstream, minding branch and tags?
Systemd service for backup /srv/
Manually run backup? Add descriptions

Test dbs get backed up
threeflet
Desec dns docs
org/reponame with main thing, landing page
Features - file section with git etc. Readme is crap. Gantt of scout, main work and reviewer prewarm and reviewer action, rework
File shows which commits it was part of and if its part of uncommitted changes
Highlight readme in any dir

Admin file uploads - admin can download, both agent and admin can pass files back and forth
UserHistory.record_created(user, user, user.snapshot()) is a mess
Markdown parsing and stuff should return data structures, not just process strings like `assignHeadingIds` in the chain
copy paste detector in main and sub repos

Vapid script could be in Python

## Upgrades
Bootstrap 6, with dialog element
Vue vapor
Substitute Eslint for Oxlint, Nov 2026
ty instead of mypy

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
Plantuml
uv and pnpm for cached builds across folders
Telemetry on install