"""Example API — copy into ``ourapp/views.py`` and mount in ``ourapp/urls.py``.

A django-ninja API for this app: page responses render via Inertia
(``InertiaResponse``, component ``ours/<Page>``); data responses are pydantic
schemas (ninja validates them). CSRF is handled by the host (the ``X-CSRFTOKEN``
header is set globally in ``main.ts``).

Endpoints:
- GET  /notes                 — list page (``ours/NotesPage``)
- POST /notes/create          — create a note (audit-logged) → NoteOutSchema
- GET  /notes/<public_id>     — detail page + revision count (``ours/NoteDetail``)
- GET  /notes/<public_id>/edit— edit form (``ours/NoteEdit``)
- PUT  /notes/<public_id>     — update a note (audit-logged) → NoteOutSchema
"""

from __future__ import annotations

from django.http import Http404, HttpRequest
from inertia import InertiaResponse
from ninja import NinjaAPI, Schema

from djangoapp.models import BaseModelUpdateLog
from djangoapp.shortcuts import user_or_404
from ourapp.models import Note

api = NinjaAPI(urls_namespace="ourapp-http")


class NoteOutSchema(Schema):
    """pk-free serialisation of a note (never send the integer pk)."""

    public_id: str
    title: str
    body: str
    owner_public_id: str
    owner_title: str


class NoteCreateSchema(Schema):
    """Create/update payload (title required, body optional)."""

    title: str
    body: str = ""


def _note_out(note: Note) -> NoteOutSchema:
    return NoteOutSchema(
        public_id=note.public_id,
        title=note.title,
        body=note.body,
        owner_public_id=note.owner.public_id,
        owner_title=note.owner.display_name,
    )


def _note_or_404(public_id: str) -> Note:
    """Fetch a note by public_id (with its owner prefetched) or raise Http404."""
    try:
        return Note.objects.select_related("owner").get(public_id=public_id)
    except Note.DoesNotExist as exc:
        raise Http404 from exc


def _revisions(note: Note) -> int:
    """Number of audit-log rows for this note (one per create + each edit)."""
    return BaseModelUpdateLog.objects.filter(
        model=Note.log_model_name(), model_pk=note.pk
    ).count()


@api.get("/notes", response=None)
def notes_page(request: HttpRequest) -> InertiaResponse:
    """Render the notes list as an Inertia page (component ``ours/NotesPage``)."""
    notes = [
        _note_out(n)
        for n in Note.objects.select_related("owner").order_by("-created_at")
    ]
    return InertiaResponse(
        request,
        "ours/NotesPage",
        {"props": {"notes": [n.model_dump() for n in notes]}},
    )


@api.post("/notes/create", response=NoteOutSchema)
def create_note(request: HttpRequest, payload: NoteCreateSchema) -> NoteOutSchema:
    """Create a note from a JSON body; return the new note.

    Uses ``save_with_logs`` (not ``objects.create``) so the write is audit-logged
    as a ``created`` revision and stamps ``created_by``/``last_updated_by``.
    """
    user = user_or_404(request)
    note = Note(title=payload.title.strip(), body=payload.body.strip(), owner=user)
    note.save_with_logs(user=user)
    return _note_out(note)


@api.get("/notes/{public_id}", response=None)
def note_detail_page(request: HttpRequest, public_id: str) -> InertiaResponse:
    """Render one note + its revision count (component ``ours/NoteDetail``)."""
    note = _note_or_404(public_id)
    return InertiaResponse(
        request,
        "ours/NoteDetail",
        {"props": {"note": _note_out(note).model_dump(), "revisions": _revisions(note)}},
    )


@api.get("/notes/{public_id}/edit", response=None)
def note_edit_page(request: HttpRequest, public_id: str) -> InertiaResponse:
    """Render the note edit form prefilled (component ``ours/NoteEdit``)."""
    note = _note_or_404(public_id)
    return InertiaResponse(
        request,
        "ours/NoteEdit",
        {"props": {"note": _note_out(note).model_dump()}},
    )


@api.put("/notes/{public_id}", response=NoteOutSchema)
def update_note(request: HttpRequest, public_id: str, payload: NoteCreateSchema) -> NoteOutSchema:
    """Update a note's title/body; return the updated note.

    ``save_with_logs`` writes an ``updated`` revision only when a data column
    changed (a no-op edit logs nothing) and re-stamps ``last_updated_*``.
    """
    user = user_or_404(request)
    note = _note_or_404(public_id)
    note.title = payload.title.strip()
    note.body = payload.body.strip()
    note.save_with_logs(user=user)
    return _note_out(note)
