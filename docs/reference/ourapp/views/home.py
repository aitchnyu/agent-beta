"""Home feature — the app's landing page.

Owns the single public route ``/`` (rendered as the Inertia component
``Home``). It shows login state, the current **Fact of the Day** (a singleton
rotated daily by the Huey cron in ``ourapp/tasks/``), and links to the app's
features; the integer ``pk`` is never exposed, only the ``public_id``.

The route is a PLAIN Django view (routed in ``urls.py``) — pages never
ride a ninja Router; that is for JSON/file endpoints only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from inertia import InertiaResponse

from djangoapp.logging import get_logger
from djangoapp.shortcuts import maybe_user
from ourapp.models import FactOfTheDay
from ourapp.views.facts import fact_out

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = get_logger(__name__)


def home_page(request: HttpRequest) -> InertiaResponse:
    """Render the landing page (component ``Home``).

    The page's own props carry the current **Fact of the Day**
    (``FactOfTheDay.current()``, a read-only lookup — a GET never creates or
    mutates a row; ``None`` before the first cron run / when the fact pool is
    empty). Login state is the shared viewer prop (``user``, injected on every
    page by SharedPropsMiddleware).
    """
    user = maybe_user(request)
    # Example structured log lines (see agentconfig/steer.md § Logging). The
    # event is a short human phrase (spaces, not snake_case); key/value fields
    # make the line jq-filterable. method/path/user_public_id/username are
    # already bound by LoggingContextMiddleware, so they're not repeated here.
    if user is None:
        logger.info("home viewed", viewer="anonymous")
    else:
        logger.info("home viewed", viewer=user.username)

    # The current pick (read-only): the Huey cron rotates it daily via
    # choose_for_today(); current() just returns whatever the cron last set, so a
    # GET never creates or mutates a row. None before the first run / when the
    # fact pool is empty.
    daily = FactOfTheDay.current()
    fact_of_day = (
        fact_out(daily.fact).model_dump()
        if daily is not None and daily.fact is not None
        else None
    )
    return InertiaResponse(request, "Home", {"props": {"fact_of_day": fact_of_day}})
