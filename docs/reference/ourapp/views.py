"""Example API — copy into ``ourapp/views.py`` and mount in ``ourapp/urls.py``.

A django-ninja API for this app: page responses render via Inertia
(``InertiaResponse``, component ``ours/<Page>``); data responses are pydantic
schemas (ninja validates them). CSRF is handled by the host (the ``X-CSRFTOKEN``
header is set globally in ``main.ts``).
"""

from __future__ import annotations

from django.http import HttpRequest
from inertia import InertiaResponse
from ninja import NinjaAPI, Schema

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
    title: str
    body: str = ""


def _note_out(note: Note) -> NoteOutSchema:
    return NoteOutSchema(
        public_id=note._public_id,  # noqa: SLF001 # BaseModel built-in column
        title=note.title,
        body=note.body,
        owner_public_id=note.owner.public_id,
        owner_title=note.owner.display_name,
    )


@api.get("/notes", response=None)
def notes_page(request: HttpRequest) -> InertiaResponse:
    """Render the notes list as an Inertia page (component ``ours/NotesPage``)."""
    notes = [
        _note_out(n)
        for n in Note.objects.select_related("owner").order_by("-_created_at")
    ]
    return InertiaResponse(
        request,
        "ours/NotesPage",
        {"props": {"notes": [n.model_dump() for n in notes]}},
    )


@api.post("/notes/create", response=NoteOutSchema)
def create_note(request: HttpRequest, payload: NoteCreateSchema) -> NoteOutSchema:
    """Create a note from a JSON body; return the new note."""
    note = Note.objects.create(
        title=payload.title.strip(),
        body=payload.body.strip(),
        owner=request.user,
    )
    return _note_out(note)
