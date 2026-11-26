does it print model?
where it need to handle pi's json?
Previous commands checked stuff, like google present, superuser present
Quitting will allow you to do it again, no we dont endorse this

```
debian@desmo:~$ pi auth login openai-codex --no-browser
Select OpenAI Codex login method: Device code login (headless)
Open https://auth.openai.com/codex/device and enter code: 3VXM-4GW0M
Waiting for authentication...
^CLogin cancelled.
```
Lets communicate with pi login bidirectionally
can we bind ctrl+v to paste,

https:localhost:8443 for test
Set button should be test
Save - "setup Pi"

Dont show this
     Authorized redirect URI for the Google Cloud console:
     https://localhost:8443/accounts/google/login/callback/

Whats all the timeout stuff? Reimplement it?
Use model fetch as working test?

/login openai-codex, luna, test with real and fake
Update docs with new screens, for adding users and login links. New instruction for prod. Render the tui in plaintext.

Pi theme should have more contrast. Lets have our theme for pi and tui?

Lets make a chore tracker. We should have chores which have a repetition schedule of either days per week or every N days/weeks/months. It shows chores from earliest to latest due date. Any logged in user can create and complete an instance. Chore titles are clickable links that leads to details page where we can see past instances (who and when completed it) and edit. We can archive chores too and view them with a filter.
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
How to document system changes when agent modifies system? Write down scripts?
List backups and time travel
Can agent merge from upstream, minding branch and tags?
Systemd service for backup /srv/
Manually run backup? Add descriptions

Test dbs get backed up
Ribbeans branding
Desec dns docs
org/reponame with main thing, landing page
Features - file section with git etc. Readme is crap. Gantt of scout, main work and reviewer prewarm and reviewer action, rework
File shows which commits it was part of and if its part of uncommitted changes
Highlight readme in any dir
Domain name in interactive script

Admin file uploads - admin can download, both agent and admin can pass files back and forth
UserHistory.record_created(user, user, user.snapshot()) is a mess
Markdown parsing and stuff should return data structures, not just process strings like `assignHeadingIds` in the chain
copy paste detector in main and sub repos

## Upgrades
Bootstrap 6, with dialog element
Vue vapor
Substitute Eslint for Oxlint, Nov 2026
ty instead of mypy
Zig based prettier

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
uv and pnpm for cached builds across folders. Dont transfer artifacts from scratch to main.
Telemetry on install