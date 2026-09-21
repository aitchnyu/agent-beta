How to recommend notifications to user? After transaction? Add transactions to reference app

UserSessionIndex is tracking sessions for user. Can we make PushSubscription a one to one relationship to UserSessionIndex?
why have `session_key = models.CharField....` when there is UserSessionIndex.
push_test and _push call _deliver. Cant we have an easy to use function that notifies a users active sessions?
is on_user_logged_out needed anymore?


session_key = models.CharField(max_length=40, null=True, blank=True, editable=False)

Subscription truth in wrong place?

VAPID_PRIVATE_KEY="DANGEROUSLYUNSET" Generate in provision along with db pass?
Move notifications to async tasks?
CSRF, allow token based requests to pass if not sent by frontend?

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

Notification center
Service worker and PWA?
Have link to correct place
Group them by url/key
Browser notification/email to send to user
Which ones to mute?

Every request sends an update response for unread
Show badge with unread count

Headless chromium, easier to install? PLAYWRIGHT_BROWSERS_PATH. Obscura for tests?

Have a playwright test for generating screenshots in a small viewport. Screenshots are needed for and referenced in readme.
Capture only specific areas for screenshots.
Capture screenshots for
    list of models, list for a model, row details
    user list, user details
    all code and git features
    mockup - have a route which renders a todo list (static html) with mockup background

--------
Reuse ubuntu/debian user instead of agent user. Have a des command that calls ./run

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
Provision in vm with domain with curl|bash. What all should user provide?

## Document
Readme for end users and devs
Session length is a sliding window, we have login links

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