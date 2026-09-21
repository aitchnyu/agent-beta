Notification with denser info and select buttons. No need of new badge. kind info is deemphasized, if we click it, show a filtered list.

No need of Hello, username
Button has Username (profile)+ badge(notification) button, dropdown has profile, notification and logout links

pyvapid for generating keys
VAPID_PRIVATE_KEY="DANGEROUSLYUNSET" Generate in provision along with db pass?
Pi's native login

CSRF, allow token based requests to pass if not sent by frontend?

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

Headless chromium, easier to install? PLAYWRIGHT_BROWSERS_PATH. Obscura for tests?

Reuse ubuntu/debian user instead of agent user. Have a des command that calls ./run

Allauth blacklist

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
Uploads dir is a single thing too
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
Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Redis and db memory usage?
Group and mute notification groups
Obscura for browser tests?