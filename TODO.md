Lets make a chore tracker. We should have chores which have a repetition schedule. It shows instances of the chore on a list. The logged in user can complete an instance.

Agent must discuss feature with the user and discuss mockups and diagrams (ER, state change)
For mockups, use the actual bootstrap markup and our css classes. Render it in a box (with specific class) in agent chat. Yes, it should be responsive.
Yes, agent must render all safe markup.
Generate diagrams using a specific class. Our  
When talking db tables, do draw the ER diagrams 
Viewing md file should render mermaid diagrams and mockups.

We must have explicit phases in development. User must give clear go-ahead. If not clear, ask user again.
First stage is gathering requirements, getting approval for diagrams and mockups.
Only after that we must do the coding.
Ask before deploying scratch to main.

Render UI mockup in wide area. 
Mermaid or D2 renderer for showing table relationships or other diagrams

-------
Title each diagram/mockup before rendering them and outline them differently.
Try to reduce mermaid to commonly used diagrams. Others can be loaded even later. 
Avoid git -C commands
Why did it change test_opencode.py?
Warning: The 'NO_COLOR' env is ignored due to the 'FORCE_COLOR' env being set.

Opencode sdk for connecting?

checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed
Profile test suite for speed
on update restrict on delete restrict

Buttons spill for agent text box in responsive mode.

Review using agents?

.save() sentinel for model

## Deployment
Tool to analyse error logs and stacktraces, both backend and map stacktraces
Opencode as service
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis, log analysis, sourcemap tool
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections
How to configure provider and model for Opencode?

rate limiting for http requests?
Upload files in chat or files

Run all tests in checkproject and merge coverage from both stages.

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99
Django 6.1 fetch modes? New Mypy plugin - https://github.com/typeddjango/django-stubs

## Notification center
Service worker and PWA?
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Future
Have a sequence generator for tables
Central tasks - track chats etc
Readonly mode for whole system, disable get requests too if it mutates data. Send toast. Do it at middleware level. How to do it for tasks?