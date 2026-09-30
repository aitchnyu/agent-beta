Audit trail - keep track of stuff after deletes?

/dbbackups
Backup regularly - https://www.pghardstorage.org/examples

Admin file uploads - admin can download, both agent and admin can pass files back and forth

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis. And file uploads.

Home and user icons. Where to get icon set autonomously? https://lucide.dev/

```
multipass shell app
sudo -u agent -H bash -l
```

Switch to Debian for lower memory usage? Multipass is for Ubuntu. Incus can rewind machines.
Incus for native port forward
Remove the ssh port forward `ssh -N -L 8000:localhost:443 ubuntu@192.168.1.56`

apply --3way merges with `./run importtemplate <github-url> <tag>` 
import from git repo tags?

Run all tests in checkproject and merge coverage from both stages. Improve test coverage

## Deployment
Provision in vm with domain with curl|bash and have branch/release. What all should user provide?
Readme for end users and devs. VM, pi /login and /model selection, Desec dns

## Future
Have a sequence generator for tables
Central tasks - track comments and deadlines
rate limiting for http requests?
Model logs should store FK name, link, url and M2M changes too
Whitelist services for outbound connections
Redis and db memory usage?
Group and mute notification groups