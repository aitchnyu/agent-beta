"""Todos feature — a single-page todo list owned by the signed-in user.

Endpoints (all under ``/todos``, one Inertia page ``TodosPage``):
- GET  /todos                    — the user's todos (404 when anonymous)
- POST /todos/create             — add a todo (audit-logged) → TodoOutSchema
- POST /todos/{public_id}/toggle — flip completion (audit-logged) → TodoOutSchema

Both mutating payloads carry ``expected_row_version`` — the row's
``row_version`` as the client last saw it (creates send 0). On a stale number
``save_plus`` raises ``Http404`` itself, so views stay happy-path.
Create writes the todo + its notification in one ``transaction.atomic()``
block; toggle is single-row. Data is pk-free (only ``public_id``).

Shape: the Inertia page is a PLAIN Django view (routed in ``urls.py``);
the two POST endpoints ride this module's ninja Router.
"""

# MAINTAIN-CONSISTENCY repo-map: excerpted in .pi/repo-map.md §9 — change both together.

from __future__ import annotations

from django.db import transaction
from django.http import Http404, HttpRequest
from inertia import InertiaResponse
from ninja import Router, Schema

from djangoapp.ninja_api import ExportedSchemaMixin
import pydantic

from djangoapp.models import Notification, User
from djangoapp.shortcuts import user_or_404
from ourapp.models import Todo

router = Router()


class TodoOutSchema(Schema, ExportedSchemaMixin):
    """pk-free serialisation of a todo (never send the integer pk)."""

    public_id: str
    text: str
    completed: bool
    row_version: int
    owner_public_id: str


class TodoCreateSchema(Schema, ExportedSchemaMixin):
    """Create payload (text + the required version; a create is always 0)."""

    text: str
    expected_row_version: int

    # Validator signatures live here — .venv stub reads for these are a
    # §9 gap in .pi/repo-map.md, not a step of your work.
    @pydantic.field_validator("text")
    @classmethod
    def _stripped(cls, value: str) -> str:
        value = value.strip()
        if not value:
            msg = "text must not be empty"
            raise ValueError(msg)  # ninja renders this as a standard 422
        return value

    # Cross-field checks: model_validator(mode="after") reads sibling values.
    @pydantic.model_validator(mode="after")
    def _version_zero_on_create(self) -> "TodoCreateSchema":
        if self.expected_row_version != 0:
            msg = "a create always starts at row_version 0"
            raise ValueError(msg)
        return self


class TodoToggleSchema(Schema, ExportedSchemaMixin):
    """Toggle payload: the todo's row_version as the client last saw it."""

    expected_row_version: int


def _todo_out(todo: Todo) -> TodoOutSchema:
    return TodoOutSchema(
        public_id=todo.public_id,
        text=todo.text,
        completed=todo.completed,
        row_version=todo.row_version,
        owner_public_id=todo.owner.public_id,
    )


def _todo_or_404(public_id: str, owner: User) -> Todo:
    """Fetch a todo by public_id owned by ``owner``, or raise Http404.

    Scoping by owner keeps a 404 (not 403) when the row is someone else's, so a
    foreign id never reveals whether it exists.
    """
    try:
        return Todo.objects.get(public_id=public_id, owner=owner)
    except Todo.DoesNotExist as exc:
        raise Http404 from exc



def todos_page(request: HttpRequest) -> InertiaResponse:
    """Render the signed-in user's todos (component ``TodosPage``)."""
    user = user_or_404(request)
    todos = Todo.objects.active_for(user)
    return InertiaResponse(
        request,
        "TodosPage",
        {"props": {"todos": [_todo_out(t).model_dump() for t in todos]}},
    )


@router.post("/todos/create", response=TodoOutSchema)
def create_todo(request: HttpRequest, payload: TodoCreateSchema) -> TodoOutSchema:
    """Create a todo from a JSON body; return the new todo.

    The canonical multi-write shape: the todo + its notification are one
    ``transaction.atomic()`` block (all-or-nothing — a partial commit
    must never leave a todo the user wasn't told about), and the
    notification push is scheduled by ``record`` itself on ``on_commit``
    — the user is only ever informed AFTER the data is durable.
    ``save_plus`` (not ``objects.create``) so the write is
    audit-logged and stamps ``created_by``/``last_updated_by``. A nonzero
    ``expected_row_version`` never reaches the model — the create schema's
    ``model_validator`` rejects it as a 422 (a create always starts at
    row_version 0); a stale version on a toggle, by contrast, is the
    model's 404.
    """
    user = user_or_404(request)
    with transaction.atomic():
        todo = Todo(text=payload.text, owner=user)
        todo.save_plus(actor=user, expected_row_version=payload.expected_row_version)
        Notification.record(
            recipient=user,
            kind="todo.created",
            body=f"Todo created: {todo.text[:80]}",
            url="/todos",
        )
    return _todo_out(todo)


@router.post("/todos/{public_id}/toggle", response=TodoOutSchema)
def toggle_todo(
    request: HttpRequest, public_id: str, payload: TodoToggleSchema
) -> TodoOutSchema:
    """Flip a todo's completion state; return the updated todo.

    ``save_plus`` writes an ``updated`` revision only when a data column
    changed (``completed`` always flips here) and re-stamps ``last_updated_*``.
    A stale ``expected_row_version`` (the todo changed since the client
    read it) makes the model raise ``Http404`` — indistinguishable from a
    missing row, with no view-side error handling.
    """
    user = user_or_404(request)
    todo = _todo_or_404(public_id, user)
    todo.toggle()
    todo.save_plus(actor=user, expected_row_version=payload.expected_row_version)
    return _todo_out(todo)
