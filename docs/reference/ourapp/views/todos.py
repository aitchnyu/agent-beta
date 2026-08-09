"""Todos feature — a single-page todo list owned by the signed-in user.

Endpoints (all under ``/todos``, one Inertia page ``ours/TodosPage``):
- GET  /todos                    — the user's todos (404 when anonymous)
- POST /todos/create             — add a todo (audit-logged) → TodoOutSchema
- POST /todos/{public_id}/toggle — flip completion (audit-logged) → TodoOutSchema

A toggle and a create each write one row, so they need no extra transaction
beyond ``save_with_logs``'s own. Data is pk-free (only ``public_id``).
"""

from __future__ import annotations

from django.http import Http404, HttpRequest
from inertia import InertiaResponse
from ninja import Router, Schema

from djangoapp.models import User
from djangoapp.shortcuts import user_or_404
from ourapp.models import Todo

router = Router()


class TodoOutSchema(Schema):
    """pk-free serialisation of a todo (never send the integer pk)."""

    public_id: str
    text: str
    completed: bool
    owner_public_id: str


class TodoCreateSchema(Schema):
    """Create payload (text required)."""

    text: str


def _todo_out(todo: Todo) -> TodoOutSchema:
    return TodoOutSchema(
        public_id=todo.public_id,
        text=todo.text,
        completed=todo.completed,
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


@router.get("/todos", response=None)
def todos_page(request: HttpRequest) -> InertiaResponse:
    """Render the signed-in user's todos (component ``ours/TodosPage``)."""
    user = user_or_404(request)
    todos = Todo.objects.active_for(user)
    return InertiaResponse(
        request,
        "ours/TodosPage",
        {"props": {"todos": [_todo_out(t).model_dump() for t in todos]}},
    )


@router.post("/todos/create", response=TodoOutSchema)
def create_todo(request: HttpRequest, payload: TodoCreateSchema) -> TodoOutSchema:
    """Create a todo from a JSON body; return the new todo.

    Uses ``save_with_logs`` (not ``objects.create``) so the write is audit-logged
    as a ``created`` revision and stamps ``created_by``/``last_updated_by``.
    """
    user = user_or_404(request)
    todo = Todo(text=payload.text.strip(), owner=user)
    todo.save_with_logs(user=user)
    return _todo_out(todo)


@router.post("/todos/{public_id}/toggle", response=TodoOutSchema)
def toggle_todo(request: HttpRequest, public_id: str) -> TodoOutSchema:
    """Flip a todo's completion state; return the updated todo.

    ``save_with_logs`` writes an ``updated`` revision only when a data column
    changed (``completed`` always flips here) and re-stamps ``last_updated_*``.
    """
    user = user_or_404(request)
    todo = _todo_or_404(public_id, user)
    todo.toggle()
    todo.save_with_logs(user=user)
    return _todo_out(todo)
