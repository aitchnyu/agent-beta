"""Huey background + periodic tasks for this app (one file per feature).

``huey.contrib.djhuey`` auto-discovers each installed app's ``tasks`` module; a
package works because importing it (this ``__init__``) imports the feature
submodules, which registers their decorated tasks. Add a new feature's tasks in
``tasks/<feature>.py`` and import them below so djhuey picks them up.
"""

from ourapp.tasks.facts import choose_fact_of_the_day

__all__ = ["choose_fact_of_the_day"]
