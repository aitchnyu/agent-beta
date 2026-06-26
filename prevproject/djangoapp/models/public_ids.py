import re
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

_URL_FRIENDLY_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_public_id_format(value: str) -> None:
    if not _URL_FRIENDLY_RE.fullmatch(value):
        msg = f"Public ID '{value}' contains invalid characters. Only [a-zA-Z0-9_-] allowed."
        raise ValueError(msg)


def public_id_django_validator(value: str) -> None:
    try:
        validate_public_id_format(value)
    except ValueError as e:
        raise ValidationError(str(e)) from e


def _sanitize_sequence_name(raw: str) -> str:
    sanitized = re.sub(r"[^a-z0-9]", "_", raw.lower())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return f"public_id_seq_{sanitized}"


def generate_sequence_id(
    format_str: str,
    start: int = 1,
    now: datetime | None = None,
) -> Callable[[], str]:
    """Return a callable that generates sequential public IDs using a strftime-based format string.

    The format_str must contain exactly one ``ID`` placeholder. strftime
    format codes are expanded using ``now`` (defaults to current time),
    and ``ID`` is replaced with an auto-incrementing sequence number.

    Format examples:
        - ``"%Y-%m-%d-ID"`` → ``"2026-04-30-1"``, ``"2026-04-30-2"``
        - ``"%Y-%m-ID"``     → ``"2026-04-1"``,    ``"2026-04-2"``
        - ``"INV-%Y-ID"``    → ``"INV-2026-1"``,   ``"INV-2026-2"``

    All strftime directives are supported — see
    https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    Each unique prefix (after strftime expansion) gets its own Postgres
    sequence, so daily/monthly/etc. counters reset independently.

    Args:
        format_str: Format pattern containing exactly one ``ID`` placeholder.
        start: Sequence start value (default 1).
        now: Override the timestamp used for strftime expansion.

    Returns:
        A callable that returns a URL-friendly string matching ``[a-zA-Z0-9_-]+``.

    Raises:
        ValueError: If format_str doesn't contain exactly one ``ID``,
            or if the result isn't URL-friendly.

    """
    id_count = format_str.count("ID")
    if id_count != 1:
        msg = f"format_str must contain exactly one 'ID' placeholder, found {id_count}"
        raise ValueError(msg)

    def _generate() -> str:
        _now = now if now is not None else timezone.now()
        prefix = _now.strftime(format_str.replace("ID", ""))
        seq_name = _sanitize_sequence_name(prefix)

        with connection.cursor() as cursor:
            cursor.execute("SELECT quote_ident(%s)", [seq_name])
            quoted_name = cursor.fetchone()[0]
            cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {quoted_name} START WITH %s", [start])
            cursor.execute("SELECT nextval(%s)", [seq_name])
            seq_val = cursor.fetchone()[0]

        result = _now.strftime(format_str.replace("ID", str(seq_val)))
        validate_public_id_format(result)
        return result

    return _generate
