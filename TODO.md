Reference app has a file download feature. Admin can upload a file, it allows download till a set date (1 week default). Then its not available.
BaseModel should have .mark_file_field_for_deletion that will delete file after transaction.
Files must go into media/ in main/ 
Files are served by django in local, by caddy if caddy is detected. Caddy can intercept requests this way. Have a serve_file(request, filename) for this

In reference app docs and steer (files upload section), mention it illustrates:
    mark_file_field_for_deletion
    files are in media/
    serve_file

Test serve_file in checkframework2

Row delete - how to delete files, replace file and remove older

---------------
Audit trail - keep track of stuff after deletes?

/dbbackups

Admin file uploads - admin can download, both agent and admin can pass files back and forth

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

Home and user icons. Where to get icon set autonomously?

```
  echo "==> playwright browsers (shared cache, cross-platform)"
  multipass exec desmo -- sudo bash /srv/desmo/main/deploy/vm.sh playwright-setup
  echo "==> playwright chromium system deps"
  multipass exec desmo -- sudo bash /srv/desmo/main/deploy/vm.sh playwright-deps

  # Provisioning's /tmp leftovers — per-file rationale in deploy/vm.sh
  # (cleanup-provision-tmp).
  multipass exec desmo -- sudo bash /srv/desmo/main/deploy/vm.sh cleanup-provision-tmp
```

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
Backup regularly - https://www.pghardstorage.org/examples
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