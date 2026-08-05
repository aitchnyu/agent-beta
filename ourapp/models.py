"""User app models.

A normal Django app. Add concrete models here subclassing
``djangoapp.models.BaseModel`` (which provides ``public_id``, ``created_by``,
``created_at``, ``last_updated_at``, ``last_updated_by``, ``get_absolute_url()``,
and the ``save_with_logs``/``delete_with_logs`` audit hooks). Every model defined
here appears in the superuser models-management UI at ``/manage/models`` (listed
by name with its docstring) and its rows are browseable there; foreign-key cells
link to the referenced row via that row's ``get_absolute_url()``.

See ``docs/reference/`` for a complete copyable example (model, views, page,
test).
"""
