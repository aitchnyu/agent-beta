Review N commits
Readme - desmo is a codename
Readme - tree of files created/affected

CSRF, allow token based requests to pass if not sent by frontend? csrf_guard and new function for make_ninja_api? Document?

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

VAPID_PRIVATE_KEY="DANGEROUSLYUNSET" Generate in provision along with db pass?
Pi's native login

Reuse ubuntu/debian user instead of having an agent user. Can we do it with existing privileges? 
Have a desmo command that calls ./run on app dir. For example `desmo pi` is same as cd-ing to app dir and running `./run pi`
The ubuntu/debian user has desmo command available to him.
Instead of app in srv and systemd, call it desmo 
Readme to mention steps

Allauth whitelist/blacklist to allow only certain users. Document in readme.

_assert_select_budget - dont overprovision by more than 33%

save_with_logs take sequence number

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
Uploads dir is a single thing too. Sample app for file hosting?
Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Backup regularly - https://www.pghardstorage.org/examples
Provision in vm with domain with curl|bash. What all should user provide?
Readme for end users and devs, Desec dns

## Future
Have a sequence generator for tables
Central tasks - track comments and deadlines
rate limiting for http requests?
Support multiple apps in same server
Model logs should store FK name, link, url and M2M changes too
Whitelist services for outbound connections
Redis and db memory usage?
Group and mute notification groups