"""Helpers for plain-Django Inertia page views.

Pages used to ride ninja routers (for ``Query[...]`` parsing and the
shared handlers); they are plain views now — ninja hosts JSON only —
and these are the pieces of that machinery a page still needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import register_converter
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from django.http import HttpRequest


class RelPathConverter:
    """A repo-relative path that MAY be empty.

    The built-in ``path`` converter requires ≥1 char (``.+``), so it can't
    serve a browse root (rel=""). Matching ``.*`` lets one route serve both
    the root and subpaths. Django converters are process-wide, so registering
    it here (the page-support module both files.py and git.py import) makes
    import order irrelevant.
    """

    regex = r".*"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:  # pragma: no cover -- reverse() only
        return value


register_converter(RelPathConverter, "relpath")


def parse_query[ModelT: BaseModel](request: HttpRequest, model: type[ModelT]) -> ModelT:
    """Validate ``request.GET`` into ``model``, defaults on bad input.

    A page never 422s over filters: unparseable values (``page=abc``) fall
    back to the model's own defaults, which the filter models define for
    every field.
    """
    try:
        return model.model_validate(request.GET.dict())
    except ValidationError:
        return model()
