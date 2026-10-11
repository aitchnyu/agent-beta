Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
List backups and time travel
How to document system changes when agent modifies system? Write down scripts?
Can it merge from upstream, minding branch and tags?

deployscratch - no need of lints and tests if only mockup components or md files were changed, try to minimize.
are we building twice in scratch and main and wasting time?
Is it using the subagent results to avoid scouting? Did review agent get a headstart while deploying?

too many css classes?
Use mermaids renderer

Admin file uploads - admin can download, both agent and admin can pass files back and forth
Features - file section with git etc

TUI for config, vapid script

Still at Mermaid usecase-beta, wait till they release
Bootstrap 6, with dialog

Branding, org/reponame

Switch to Debian for lower memory usage? Multipass is for Ubuntu. Incus can rewind machines.
Incus for native port forward
Remove the ssh port forward `ssh -N -L 8000:localhost:443 ubuntu@192.168.1.56`
local-vm setupalogin
local-vm portforward
Update docs for adding users and login links

desmo user shouldnt have rw access to its files

Desec dns docs

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