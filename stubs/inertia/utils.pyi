from collections.abc import Callable
from typing import Any

# inertia.utils ships no py.typed (see stubs/inertia/__init__.pyi); only the
# symbols the app imports are stubbed, mirroring the library's loose API.
def optional(prop: Callable[[], Any]) -> Any: ...
