# Type stubs for ``huey.contrib.djhuey`` — the django integration decorators.
#
# Each decorator wraps a function and returns a huey ``Task``: calling it
# enqueues, ``.call_local()`` runs it inline (used in tests). Modeled as a
# callable wrapper exposing both, so ``task()`` and ``task.call_local()``
# type-check (an identity decorator would drop ``.call_local()``).

from collections.abc import Callable

class _DbTask:
    def __call__(self, *args: object, **kwargs: object) -> object: ...
    def call_local(self, *args: object, **kwargs: object) -> object: ...

def db_task(*args: object, **kwargs: object) -> Callable[[Callable[..., object]], _DbTask]: ...
def db_periodic_task(
    *args: object, **kwargs: object
) -> Callable[[Callable[..., object]], _DbTask]: ...
