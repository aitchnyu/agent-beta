# Todos

A signed-in user's todo list, on one page.

## Models

- `Todo` — `text`, `completed` (bool, default False), `owner` (FK → User,
  RESTRICT). Manager: `Todo.objects.active_for(user)`. Method: `toggle()`.

## Routes

All under `/todos` (one page `ours/TodosPage`); anonymous → 404.

- `GET /todos` → props `{ todos: TodoOut[] }`.
- `POST /todos/create` (body `{ text }`) → `TodoOut`.
- `POST /todos/<public_id>/toggle` → `TodoOut`. Foreign/missing id → 404.

## Files

- Model: `models/todos.py`. View: `views/todos.py` (`router`).
- Frontend: `frontend/src/ours/pages/TodosPage.vue`, component `TodoForm.vue`,
  schema in `ours/schemas.ts`.
- Tests: `tests/test_todos_models.py`, `tests/test_todos_views.py`,
  `tests/test_todos_playwright.py`.
