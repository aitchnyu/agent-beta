Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.
List backups and time travel
How to document system changes when agent modifies system? Write down scripts?

have instruction to create new user and send login link if logged out.
`add your features under ourapp/ and frontend/src/ours/ (see docs/reference/ for a complete example)`

deployscratch - no need of lints and tests if only mockup components or md files were changed.
are we building twice in scratch and main?
too many css classes?

```

 $ ./run deployscratch (timeout 900s)

 ... (224 earlier lines, ctrl+o to expand)
 Deployed scratch/ → main/ (uncommitted, services live). Commit in main/ when ready.
 Share design artifacts as absolute URLs at the BOTTOM of your message (with the summary):
   docs:  https://localhost:8000/files/main/ourapp/docs/<feature>.md
   pages: https://localhost:8000/<page-url>
 Verify each file exists in main/ before sharing the link.
```

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

apply --3way merges with `./run importtemplate <github-url> <tag>` 
import from git repo tags?

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