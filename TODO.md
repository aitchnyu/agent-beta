class BaseModel(models.Model):
    """Abstract base for the concrete models in ourapp/.

    We must intend to address rows by their public ids. Its UUID7 by default, but
    we can use friendly names etc.

    Rows are addressed in the superuser-only models-management UI by
    their ``_public_id``; :meth:`get_absolute_url` returns that detail URL.
    """

    _public_id = models.CharField(
        max_length=100, db_index=True, editable=False, default=generate_uuid7_id
    )
    _created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="+",
    )
    _created_at = models.DateTimeField(auto_now_add=True)
    _edited_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        """Override per-model for a friendlier label."""
        return self._public_id

    def get_absolute_url(self) -> str:
        """Superuser-only models-management detail URL for this row.

        Built from the concrete class name + ``_public_id``; must match the
        route in ``djangoapp/views/manage.py``
        (``MANAGE_MODELS_URL_PREFIX/<model>/id/<id>``).
        """
        return f"{MANAGE_MODELS_URL_PREFIX}/{type(self).__name__}/id/{self._public_id}"

BaseModel will now have public_id, created_by (nullable user), created_at, last_updated_at, last_updated_by (nullable user)

Page title for apps - as component

Base model - just created and updated 
Just log stuff. .save_with_logs(user, updated=True) and .delete_with_logs
How to test it?
Test file manager without mocks
Avoid some linting errors

Inertia 3 - https://github.com/inertiajs/inertia-django/issues/99

Have better error messages for /opencode
NinjaAPI consistency - like error handlers etc

When agent is cut off due to redeployment, download latest message to show to user?

How to configure provider and model for Opencode?

docs/ for llm. Have feature catalog.
Models and views are multi-file modules.
ours/ in frontend - even for utils, configure vite
checkall vs checkscratch - run if anything outside of ours/ and ourapp/ is changed
Split models and views as separate files. Same for tests.

Generate multiline, render as multiline:
./run python -c "import inspect; from inertia import InertiaResponse; print(inspect.signature(InertiaResponse))"

Example app should be bigger
Include logging, including storing in db

Run all tests in checkproject and merge coverage from both stages.

Readonly mode for whole system, disable get requests too if it mutates data. Do it at middleware level.

## Error tracking
Log backend in json
Which analysis tool?
Send frontend errors to backend, make it easy to search/filter by line
Show source maps for main and sub apps? How to read errors from them?

## Task center
Categories and tags

## Notification center
Service worker and PWA?
Have link to correct place
Group them
Browser notification/email to send to user
Which ones to mute?

## Cron and huey
Require redis
Huey based background and scheduled tasks?
Decorator for tasks
Screen mux for dev

## Chatting
Upload files

## Give chat to end users?
Limit file access to specific tree
Specific tool calls

Poorly typed stuff in opencode.py - `def _is_idle(event: dict[str, Any]) -> bool:`

Add type stubs for GitPython — `import git` has no py.typed, so git_data.py uses `Any`/`# noqa: ANN401`

logger = logging.getLogger(__name__) - agent added

## Deployment
Tool to analyse error logs and stacktraces
Opencode as service
Whitelist of services
Serve files in fs, accelerate using Caddy
Who is committing to git
Require rsync, redis
Backup regularly - https://www.pghardstorage.org/examples
Whitelist services for outbound connections

## Future
keep login_for_test?
Mermaid or D2 renderer for showing table relationships or other diagrams