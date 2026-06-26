import datetime
from typing import Any

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from djangoapp.responses import BaseContent

register = template.Library()


@register.filter
def json_escape(value: str) -> str:
    return value.replace("'", "&39;")


@register.filter
def ashtml(value: Any) -> str:  # type: ignore[misc] # noqa: ANN401 # django filter value can be any content type
    if isinstance(value, BaseContent):
        return mark_safe(value.as_html())  # noqa: S308 # mark_safe on trusted rendered HTML
    if isinstance(value, dict):
        return str(value.get("value", ""))
    return str(value)


@register.filter
def get_cell(mapping: dict[str, Any], key: str) -> Any:  # type: ignore[misc] # noqa: ANN401 # cell value can be any type
    return mapping.get(key)


@register.filter
def render_fragment(template_name: str, context_data: dict[str, Any]) -> str:  # type: ignore[misc] # django filter decorator returns Any; Any needed for arbitrary context dict
    """Render a named template fragment with the given context dict."""
    return mark_safe(render_to_string(template_name, context_data))  # noqa: S308 # mark_safe on trusted rendered template


@register.filter
def parse_iso(value: str | None) -> datetime.datetime | None:
    """Parse an ISO 8601 string into a datetime (or None)."""
    if not value:
        return None
    return datetime.datetime.fromisoformat(value)
