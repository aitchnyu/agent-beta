# Repo map — read once, then fire your first batch in parallel.

<!-- MAINTAIN-CONSISTENCY repo-map — this map is generated from
     .pi/steer.md (workflow, layout, commands — the source of truth);
     §9 skeletons excerpt docs/reference/**; diagram guidance derives
     from docs/d2.md. When the map disagrees, fix the map. -->

Trust the files over the map. This could be stale.

Sync test: `ops/tests/test_repo_map.py` — every path named here must
exist.

How to use this map (every role):

- Paths below are EXACT — never `ls`/`find`/re-read the map to locate
  something a section already names; that hunt is the misstep this
  map exists to prevent.
- steer.md is SECTION-SCOPED reading: grep the heading, read that
  span — never the full file (~2,300 lines).
- One turn = ONE parallel batch of reads — your role's batch is §0.

## 0. First parallel batch (per role)

- CODER, after this map: the §7 exemplars + the feature's
  `ourapp/docs/<feature>.md` + its `Mockup*.vue` pages — one batch.
- MAIN, session open: this map + `.pi/agents/coder.md` — one batch.
  Stage-1 authoring adds `docs/d2.md`, the §7 frontend pair, and
  the homepage pair (`frontend/src/app/pages/Home.vue`,
  `ourapp/docs/home.md`) — one batch.
- REVIEWERS: your agent file + the diff's touched files + at most
  the §9 skeleton for your layer.

## 1. Feature workflow (steer § Feature workflow is the source)

Five stages, operator-gated: [1] mockups + initial doc (authored
together, ONE presentation deploy) → MockupDocsGate → [2] code in
`../scratch/` (`./run checkscratch` between batches, NO deploys) →
[3] review (four reviewers: correctness / conventions / trace /
image) + ONE fix cycle + the FINAL deploy → [4] CommitOffer → [5]
checklist close.

- Mockups: `frontend/src/app/pages/Mockup<Name>.vue` served verbatim
  at `/mockup/<page>` (plain view `mockup_page` in
  `ourapp/views/home.py`, routed `ourapp/urls.py`) — hardcoded
  markup, no props/backend, superuser-only, `div.mockup` wrapper,
  `?props=<base64url JSON>` presets state. Graduation = real page +
  DELETE mockup + homepage link.
- The initial doc ships three filled sections ("Who can do what" /
  "The data" / "How the data changes", fences included) plus
  `pending` markers; the coder fills a marker in the batch that
  implements it.
- The `coder` spawns as GROUNDWORK at the BuildPlan pick (parallel
  to `createscratch`) and holds through
  the gate; the fleet familiarizes at the coder's FIRST green batch
  and verifies at final green; reviewer-image is a full fleet member
  (its visual pass judges fresh final renders).

## 2. Scratch discipline

- `../scratch/` is the edit surface; `main/` is reachable only via
  deploy. `./run createscratch` (wipes existing — ask first),
  `./run checkscratch` FROM `main/` (the between-batches battery,
  never touches main/), `./run deployscratch` FROM `main/` (same
  battery → rsync `--delete` → migrate/restart on backend diff),
  `./run cleanscratch`.
- A green battery IS the whole verification — no post-deploy e2e, no
  re-runs. `deployscratch` refuses on its own when `main/` holds
  dirty files scratch doesn't carry — follow its file list.
- Formatting: `cd ../scratch && ./run lintfix` after every write
  batch — it IS ruff + oxlint + prettier + eslint; no other format
  command exists, don't hunt for one.
- Ninja = JSON only; pages are plain Django views (per-module
  `page_urls` mounted before the APIs). Page URLs serve the Inertia
  protocol (HTML or page JSON under `X-Inertia`) — `router.reload
  ({only})` is a page call, never a data call; data goes through the
  generated sdk functions.
- Payload schemas + typed client: `cd ../scratch && ./run
  djangomanage generatesdk <api-symbol> <out>` (`<api-symbol>` =
  dotted path to the NinjaAPI instance, e.g.
  `djangoapp.views.users.users_api`; out follows the feature —
  framework → `frontend/src/system/schemas/<feature>_sdk.ts`, app →
  `frontend/src/app/schemas/<feature>_sdk.ts`). Walks nested mounts,
  emits zod schemas + typed client fns (`{method}_{view}`) via the
  `@` alias. Commit the sdk; regenerate on payload changes, never
  hand-edit. PAGE props are not generated: hand-write
  `<feature>_props.ts` beside the sdk.
- Edits via `edit`, one surgical diff per spot; never script batches
  or wholesale rewrites.

## 3. Doc conventions (steer § Feature docs)

- One file per feature: `ourapp/docs/<feature>.md`; ~80-char wrap;
  title = feature name; plain front + "For developers" tail.
- Outline: title+para · who-can-do-what (usecase d2) · the data
  (plain words + sql_table d2) · how data changes (exhaustive list +
  rails) · what you see (screenshots) · history (optional) · for
  developers.
- d2 fences: `direction: down`; actors `shape: person` 180×160;
  use-case boxes `width: 240` + `style.border-radius: 24` (never
  `shape: oval`); `./run checkmarkdownd2 <file.md>` after every
  fence write.

## 4. BaseModel save_plus / row_version (`djangoapp/models/base.py`)

- `SKIP_ROW_VERSION_CHECK = -1`; `row_version` default 0;
  `get_absolute_url()`.
- `save_plus(*, actor, expected_row_version)`: create (0) stamps
  audit + one `created` log; update diffs pre-edit row → one
  `updated` log (no-op = no log); mismatch → `Http404`; bumps
  `row_version`. `delete_plus(*, actor)`: purges field history,
  lean `deleted` tombstone.
- `Notification.record(...)` INSIDE `transaction.atomic()`; push
  fan-out on `on_commit`. FKs: `on_delete=models.RESTRICT` always;
  money = DecimalField; never `get_user_model()` — `from
  djangoapp.models import User`.

## 5. Endpoints + Inertia pages pattern

Copy from the §9 skeletons first; the §7 reference files back them.

- Pages = PLAIN views in `ourapp/views/<feature>.py`, routed
  `path(...)` in `ourapp/urls.py`. JSON = `Router` endpoints
  (`@router.post("/todos/create", response=Schema)`).
- `ourapp/views/__init__.py` combines feature routers and builds the
  single API via `make_ninja_api("ourapp", router, prefix="")`
  (error handlers + CSRF guard ride along); mounted LAST in urls.py
  so page paths win.
- Errors: `ApiError(status, *, type=, msg=, ctx=)` from
  `djangoapp.ninja_api` — never `HttpError`. Auth:
  `user_or_404` / `maybe_user` from `djangoapp.shortcuts`; ownership
  failure = 404 not 403.
- Payloads pk-free (`public_id`); page data nested under `props` →
  pages parse BOTH levels via `useAppPage(FeaturePropsSchema)` from
  `frontend/src/system/utils/useAppPage.ts` (computed inside —
  Inertia swaps the whole page object every visit); HTTP via
  `frontend/src/system/utils/http.ts` (`ninjaPost`/`ninjaGet`/
  `ninjaDelete`; a 422 throws `NinjaError`); toasts
  `showToast`/`showErrorToast`; inline errors `FieldError` +
  `errorAtPath`.
- Page routes with an id param use `<uuid:public_id>` — pages
  resolve before API mounts, so a bare `<str:public_id>` page route
  shadows same-shape API paths.
- `<PageTitle :value="…"/>` on every page. zod: one component →
  inline; one feature → `frontend/src/app/schemas/<feature>.ts`;
  framework → `system/schemas/`.

## 6. Test layout

- Flat: `ourapp/tests/test_<feature>_<layer>.py` (`models`, `views`,
  `commands`, `playwright`). Bases:
  `djangoapp.tests._base.BaseTestCase` / `BaseInertiaTestCase` (fast
  hashers); playwright:
  `djangoapp.tests.playwright._base.BasePlaywrightTestCase` (carries
  the `playwright` tag + the shared-page harness — read
  `djangoapp/tests/playwright/_base.py` BEFORE writing e2e; the
  page/login helpers live there, not in site-packages).
- Class docstring = one line + one bullet per test, declaration
  order. Run: `./run test <labels…>` / `--full`; e2e:
  `./run playwrighttest <labels…>`; README PNGs:
  `./run screenshots <TestClass>`.

## 7. First parallel batch — the copy-me exemplars (ONE batch, no ls/find)

- Backend: `docs/reference/ourapp/models/todos.py`,
  `docs/reference/ourapp/views/todos.py`
- Tests: `docs/reference/ourapp/tests/test_todos_models.py`,
  `docs/reference/ourapp/tests/test_todos_views.py`,
  `docs/reference/ourapp/tests/test_todos_playwright.py`
- Frontend: `docs/reference/frontend/src/pages/TodosPage.vue`,
  `docs/reference/frontend/src/schemas/todos_sdk.ts`
- Wiring: `docs/reference/ourapp/urls.py`,
  `docs/reference/ourapp/views/__init__.py`

## 8. Gotchas that cost sessions time (don't rediscover)

- **Django-model queries from a script**: `export
  DJANGO_SETTINGS_MODULE=djangoproject.settings && ./run python -c
  'import django; django.setup(); …'` — everything else rides
  `./run`. Prefer `./run djangomanage dbstate`/management commands;
  `./run python -c`
  PROMPTS by design. Code-phase only — a mockup question is answered
  by the operator's click on the deployed link, not a query.
- **JSON API surface**: introspect via the NinjaAPI instance, not the
  filesystem: `from ourapp.views import api; [p for p in api.urls]`.
  Pages are NOT on api — plain views (§5).
- **Inertia test helpers**: read `docs/reference/frontend/` first;
  the live helpers sit in site-packages — no spelunking.
- **`dbbackups/` inside main/ is a postgres-owned island** — never
  chown/copy/write into it.
- **Gate leftover landmine**: a gate run leaves the DB at the
  assert-11 restore point — if a fresh feature 500s with tables
  missing, check `django_migrations` for a colliding `0001_initial`.

## 9. Copy-me skeletons (read these BEFORE opening reference files)

The distilled shapes from `docs/reference/` — copy these first; open
the full file only when an excerpt runs out.

<!-- MAINTAIN-CONSISTENCY repo-map — these skeletons excerpt
     docs/reference/ourapp/{models,views,tests} todos files,
     docs/reference/ourapp/models/facts.py,
     docs/reference/ourapp/views/__init__.py, docs/reference/ourapp/urls.py,
     docs/reference/frontend/src/{schemas/todos_sdk.ts,pages/TodosPage.vue},
     and djangoapp/tests/_base.py; changing any side means updating the
     other. steer.md stage [3] and .pi/agents/coder.md cite this as
     "§9" — update them on renumber. -->

**Model** — from `docs/reference/ourapp/models/todos.py`:

```python
class TodoManager(models.Manager["Todo"]):
    def active_for(self, user: User) -> models.QuerySet["Todo"]:
        return self.get_queryset().filter(owner=user).order_by("-created_at")


class Todo(BaseModel):
    text = models.CharField(max_length=500)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="todos"
    )
    objects = TodoManager()

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]
```

A `Meta.constraints` rule uses the same `ClassVar` form — from
`docs/reference/ourapp/models/facts.py`:

```python
    class Meta:
        ordering: ClassVar[list[str]] = ["-last_updated_at"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["singleton"], name="factoftheday_singleton_row"),
        ]
```

**View module** — from `docs/reference/ourapp/views/todos.py`:

```python
_MAX_TEXT_LEN: Final = 500  # module constants: Final, never ClassVar (mypy misc)
router = Router()

class TodoOutSchema(Schema):   # pk-free: public_id, never the int pk
    public_id: str; text: str; completed: bool; row_version: int; owner_public_id: str

def todos_page(request: HttpRequest) -> InertiaResponse:   # PLAIN view, routed in urls.py
    user = user_or_404(request)
    return InertiaResponse(request, "TodosPage",
        {"props": {"todos": [_todo_out(t).model_dump() for t in todos]}})

@router.post("/todos/create", response=TodoOutSchema)
def create_todo(request, payload: TodoCreateSchema) -> TodoOutSchema:
    user = user_or_404(request)
    with transaction.atomic():          # multi-write = one atomic block
        todo = Todo(text=payload.text, owner=user)
        todo.save_plus(actor=user, expected_row_version=payload.expected_row_version)
        Notification.record(recipient=user, kind="todo.created", body=…, url="/todos")
    return _todo_out(todo)
```

**Registration + routing** — `ourapp/views/__init__.py` + `ourapp/urls.py`:

```python
router = Router()                          # every feature's router combined:
router.add_router("/", todos.router)
api = make_ninja_api("ourapp", router, prefix="")  # handlers + CSRF guard ride along
# urls.py: PAGES first (plain path()s), then the API MOUNTED LAST:
urlpatterns = [path("todos", todos_page, name="todos"), …, path("", api.urls)]
```

**View tests** — from `docs/reference/ourapp/tests/test_todos_views.py`:

```python
class TodosViewTests(BaseTestCase):
    def setUp(self) -> None:
        self.alice = User.objects.create_user(username="alice", password="x")
        self.client = Client()
        self.client.force_login(self.alice)

    def _toggle(self, public_id: str, expected_row_version: int):
        return self.client.post(
            f"/todos/{public_id}/toggle",
            data={"expected_row_version": expected_row_version},
            content_type="application/json",
        )

    # page GET: props = feature_props_of(client.get("/todos", HTTP_X_INERTIA="true").json())
    # endpoint POSTs: body = resp.json() — then pk-free asserts on body
    # pk-free assert: for t in todos: self.assertNotIn("id", t)
```

**Test harness** — from `djangoapp/tests/_base.py` + the views tests:

```python
from djangoapp.tests._base import BaseTestCase, BaseInertiaTestCase, feature_props_of

# unit tests → BaseTestCase (fast MD5 hasher);
# inertia-prop view tests → BaseInertiaTestCase, then:


class MyViewTests(BaseInertiaTestCase):
    def test_page_lists(self):
        self.client.get("/mine", HTTP_X_INERTIA="true")
        props = self.feature_props()  # the page's own data; assert inside it
        self.assertEqual(props["models"][0]["name"], "x")
```

JSON bodies: resp.json() on test-client responses — json.loads
only for plain strings (e.g. playwright's `request.post_data`).

**Frontend schema + page** — from
`docs/reference/frontend/src/schemas/todos_sdk.ts` +
`docs/reference/frontend/src/pages/TodosPage.vue`:

```ts
export const TodoOutSchema = z.object({
  public_id: z.string(), row_version: z.number().int().nonnegative(), … })


// page: useAppPage parses BOTH levels reactively (computed inside —
// reload-safe); mutate via the GENERATED sdk fn, then let props re-render
const { data: p } = useAppPage(TodosPagePropsSchema)   // ../../system/utils/useAppPage
const todos = computed(() => p.value.todos)
await post_toggle_todo(todo.public_id, { expected_row_version: todo.row_version })
await router.reload()   // server is source of truth after every mutation
```
