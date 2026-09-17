drobeans 
dendron 	Greek   δένδρον 	tree / wood 	105
lobos 	    Greek   λῶβος 	pod 	1029
umbellatum 	Latin 	umbels — flower clusters radiating from a common center 	11
umbella 	Latin 	a sunshade, parasol, or umbrella (dim. of umbra, shade) 	30

desm- 	Greek δεσμός (desmos) 	band, bond, chain ?
-od- 	Greek -oeides / -odes 	"like, of the shape of" ?
-ium 	Latin 	taxonomic singular noun ending ?

Tool to analyse error logs and stacktraces, both backend and sourcemap stacktraces, mlr (miller) for logs

Generate backend logs with some test function.
Generate frontend errors from some playwright actions.
Use miller (mlr) command to track error by backend stacktrace/frontend stacktrace
How will we decode frontend logs which are minified
Track by user
Have a tool that will
Mention in steer.md, which links to docs/logs.md
Document in readme - find all errors by user, find all errors by user, both frontend and backend, from the logs you gathered
Gather logs from Huey too
Can agent use this?

Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.  
Test with changing site theme. Generate color schemes. Then try to upgrade to postgis.

Notification center
Service worker and PWA?
Have link to correct place
Group them by url/key
Browser notification/email to send to user
Which ones to mute?

Headless chromium, easier to install? PLAYWRIGHT_BROWSERS_PATH. Obscura for tests?
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
Provision in vm with domain with curl|bash

## Document
Readme for end users and devs
Code and git viewing
Models management
Logout sessions, view sessions
Session length is a sliding window
Mockup widgets - have a demo page

## Future
Have a sequence generator for tables
Central tasks - track comments and deadlines
rate limiting for http requests?
Support multiple apps in same server
Model logs should store FK name, link, url and M2M changes too
Whitelist services for outbound connections
Accelerate file serving with Caddy - have FileResponse - test with checkframework2
Redis and db memory usage?