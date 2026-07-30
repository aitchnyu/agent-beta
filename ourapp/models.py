"""User app models.

A normal Django app. Add concrete models here subclassing
``djangoapp.models.BaseModel`` (which provides ``_public_id``, ``_created_by``,
``_created_at``, ``_edited_at`` and ``get_absolute_url()``). Every model defined
here appears in the superuser models-management UI at ``/manage/models`` (listed
by name with its docstring) and its rows are browseable there; foreign-key cells
link to the referenced row via that row's ``get_absolute_url()``.

See ``docs/reference/`` for a complete copyable example (model, views, page,
test).
"""
