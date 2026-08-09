"""Facts feature — random trivia, optionally scoped to a topic.

Endpoints:
- GET /facts            — a random fact (any topic) + every topic, for linking
- GET /facts/{slug}     — a random fact in one topic, or 404 if the topic is gone

Page responses render the Inertia components ``ours/FactsPage`` and
``ours/FactTopicPage``; data is pk-free (only ``public_id``).
"""

from __future__ import annotations

from django.http import Http404, HttpRequest
from inertia import InertiaResponse
from ninja import Router, Schema

from ourapp.models import Fact, Topic

router = Router()


class TopicOutSchema(Schema):
    """pk-free serialisation of a topic."""

    public_id: str
    name: str
    slug: str


class FactOutSchema(Schema):
    """pk-free serialisation of a fact (nested topic, no integer pk)."""

    public_id: str
    text: str
    topic: TopicOutSchema


def _topic_out(topic: Topic) -> TopicOutSchema:
    return TopicOutSchema(public_id=topic.public_id, name=topic.name, slug=topic.slug)


def _fact_out(fact: Fact) -> FactOutSchema:
    return FactOutSchema(
        public_id=fact.public_id,
        text=fact.text,
        topic=_topic_out(fact.topic),
    )


def _all_topics() -> list[TopicOutSchema]:
    """Every topic (alphabetical) so the page can link to each one."""
    return [_topic_out(t) for t in Topic.objects.all()]


def _topic_or_404(slug: str) -> Topic:
    """Fetch a topic by slug or raise Http404."""
    try:
        return Topic.objects.get(slug=slug)
    except Topic.DoesNotExist as exc:
        raise Http404 from exc


@router.get("/facts", response=None)
def facts_page(request: HttpRequest) -> InertiaResponse:
    """Render a random fact (any topic) + the topic list (``ours/FactsPage``)."""
    fact = Fact.objects.random()
    return InertiaResponse(
        request,
        "ours/FactsPage",
        {
            "props": {
                "fact": _fact_out(fact).model_dump() if fact else None,
                "topics": [t.model_dump() for t in _all_topics()],
            },
        },
    )


@router.get("/facts/{slug}", response=None)
def fact_topic_page(request: HttpRequest, slug: str) -> InertiaResponse:
    """Render a random fact in one topic, or 404 if the topic is gone.

    (component ``ours/FactTopicPage``). A missing topic is a 404, not an empty
    page, so dead links surface instead of rendering blank.
    """
    topic = _topic_or_404(slug)
    fact = topic.random_fact()
    return InertiaResponse(
        request,
        "ours/FactTopicPage",
        {
            "props": {
                "topic": _topic_out(topic).model_dump(),
                "fact": _fact_out(fact).model_dump() if fact else None,
                "topics": [t.model_dump() for t in _all_topics()],
            },
        },
    )
