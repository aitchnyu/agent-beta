# Todos

A signed-in user's private todo list, on one page: add todos, tick them
off, untick them. Anonymous visitors get a 404 — a private feature never
leaks its existence.

## Who can do what

```d2
direction: down
guest: Anonymous visitor {shape: person}
member: Signed-in member {shape: person}
todos: Todos {
  add: Add a todo {shape: oval}
  toggle: Tick it off / untick {shape: oval}
}
member -> todos.add
todos.toggle -> todos.add: extend {style.stroke-dash: 3}
note: The page 404s — a private feature never leaks its existence. {shape: text}
```

## The data

One model. A **todo** is the text, a done flag, and its owner:

```d2
user: User {
  shape: sql_table
  id: int {constraint: primary_key}
}
todo: Todo {
  shape: sql_table
  text: varchar(500)
  completed: boolean
  owner_id: int
}
todo.owner_id -> user.id: owns · 1..N · RESTRICT
```

`Todo.objects.active_for(user)` lists a user's todos, newest first;
`toggle()` flips completion. Deleting the owner is refused (`RESTRICT`).

## How the data changes

- **Add** — `POST /todos/create` with `{ text }` → the todo, newest first.
- **Toggle** — `POST /todos/<public_id>/toggle` → flips `completed`.
  A foreign or missing id → 404 (never another user's row).

## What you see

One page: the add form and the list, with a Toggle button per todo.

![The todos page — one open and one completed](screenshots/todos.png)

## For developers

- Model: `models/todos.py`. Manager: `Todo.objects.active_for(user)`.
  Method: `toggle()`.
- View: `views/todos.py` (the router; all routes under `/todos`).
- Frontend: `ours/pages/TodosPage.vue` (props schema inline), component
  `TodoForm.vue`, shared `TodoSchema` in `ours/todosSchemas.ts`.
- Tests: `tests/test_todos_{models,views,playwright}.py`.
