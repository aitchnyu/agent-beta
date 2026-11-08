# Repo map — put your head down and research the repo through this file.

<!-- MAINTAIN-CONSISTENCY repo-map — this map is generated from
     .pi/steer.md (workflow, layout, commands — the source of truth);
     §9 skeletons excerpt docs/reference/**; diagram guidance derives
     from docs/d2.md. When the map disagrees, fix the map. -->

Trust the files over the map. If the file structure changed too much,
read a live session's logs to see the missteps, then rewrite this map
streamlined.
Sync test: `ops/tests/test_repo_map.py` — every repo path named here
must exist; when the test fails, refresh this map.

## 1. Feature workflow

Five stages, each transition an explicit operator pick: [1] Mockups +
initial doc (authored together, ONE presentation deploy) →
MockupDocsGate → [2] Code (scratch, `./run checkscratch` between
batches, NO deploys) → [3] Agent review + ONE fix cycle + the FINAL
deploy → [4] CommitOffer → [5] Final checklist → one-sentence close.
Stages 2–4 run as ONE turn; the session never compacts — the operator
can. `deployscratch` has two deploy points per feature — the stage-1
mockup+doc presentation and the stage-3 deliverable.

- Mockups: `frontend/src/app/pages/Mockup<Name>.vue`, served verbatim
  by the hatch route `/mockup/<page>` (plain view `mockup_page` in
  `ourapp/views/home.py`, routed `ourapp/urls.py`) — hardcoded markup,
  no props/backend, superuser-only, `div.mockup` wrapper.
  `?props=<base64url JSON>` presets state (`_B64JsonProps`).
  Graduation = real page + DELETE mockup + homepage link.
- The initial doc ships exactly three filled sections ("Who can do
  what" / "The data" / "How the data changes", fences included) plus
  `pending` markers for the rest; the coder fills pending sections in
  the batch that implements them.
- Warm-up at stage-1 start: the `coder` spawns as GROUNDWORK
  (background) and the reviewer fleet FAMILIARIZES on the requirement
  digest; both hold through the gate. The image reviewer spawns when
  the doc's validation renders exist — ONE verdict; fixing its
  comments never re-triggers it.
- Reviewers (code): correctness / conventions / mirrors / trace for big
  diffs (single `reviewer` otherwise) — familiarized at stage-1 start,
  verified at the coder's final green; round 2 resumes them on the fix
  diff. The `coder` agent implements
  stage 2 (background): groundwork at stage-1 start, resumed to
  implement at the gate's approval, resumed again for reviewer-found
  fixes.

## 2. Scratch discipline

- `../scratch/` is the edit surface; `main/` reachable only via
  deploy. `./run createscratch` (wipes existing — ask first),
  `./run checkscratch` FROM `main/` (the battery alone — the
  between-batches gate; never touches main/), `./run deployscratch`
  FROM `main/` (same battery → rsync `--delete` → migrate/restart on
  backend diff), `./run cleanscratch`.
- A green battery (`checkscratch` or the deploy's own) IS the whole
  verification — no post-deploy e2e, no re-runs. `deployscratch`
  refuses on its own if `main/` holds dirty files scratch doesn't
  carry — follow its file list.
- Ninja = JSON only; pages are plain Django views (per-module
  `page_urls` mounted before the APIs). Page URLs serve the Inertia
  protocol (HTML or page JSON under `X-Inertia`) — `router.reload({only})`
  is a page call, never a data call; data goes through the generated
  sdk functions.
- Formatting/lint ≠ deploy points — fold into the next batch;
  `cd ../scratch && ./run lintfix` after every write batch.
- Payload schemas + typed client: regenerate a feature's sdk on demand
  — `cd ../scratch && ./run djangomanage generatesdk
  djangoapp.views.users.users_api
  frontend/src/system/schemas/users_sdk.ts` (<api-symbol> = dotted
  path to the NinjaAPI instance). Output path follows the feature:
  framework features (djangoapp.views.*) →
  `frontend/src/system/schemas/<feature>_sdk.ts`; app features
  (ourapp.views.api) → `frontend/src/app/schemas/<feature>_sdk.ts`
  (the reference trio is the exemplar). Walks the api's router tree —
  nested `add_router` mounts included, prefixes joined — and emits
  zod schemas for every model REACHABLE from an endpoint (responses,
  bodies, GET query models, transitive field refs) + typed client
  functions (`{method}_{view}`, e.g. `post_set_price`) importing
  http.ts through the `@` alias (`@/system/utils/http` — depth-
  independent, regen never needs a hand fix) — commit the sdk;
  regenerate on payload changes, never hand-edit. PAGE props are not
  generated: hand-write them in a `<feature>_props.ts` schema file
  beside the sdk.
- Edits via `edit`, one surgical diff per spot; never script batches
  or wholesale rewrites.

## 3. Doc conventions (.pi/steer.md § Feature docs)

- One file per feature: `ourapp/docs/<feature>.md`; ~80-char wrap;
  title = feature name only; two audiences (plain front, "For
  developers" tail).
- Outline: title+para · who-can-do-what (usecase-beta d2) · the data
  (plain words then sql_table d2) · how data changes (exhaustive
  change list + safety rails) · what you see (screenshots) · history
  (optional) · for developers.
- Diagrams: d2 fences, `direction: down` top-level, actors
  `shape: person` pinned 180×160, use-case boxes `width: 240` +
  `style.border-radius: 24` (never `shape: oval`); mandatory
  `./run checkmarkdownd2 <file.md>` after every fence write.

## 4. BaseModel save_plus / row_version (`djangoapp/models/base.py`)

- `SKIP_ROW_VERSION_CHECK = -1`; `class BaseModel`; `row_version`
  default 0; `get_absolute_url()`.
- `save_plus(*, actor, expected_row_version)`: create (0) stamps
  audit + one `created` log; update diffs pre-edit row → one
  `updated` log (no-op = no log); mismatch → `Http404`; bumps
  `row_version`.
- `delete_plus(*, actor)`: purges field history, writes lean
  `deleted` tombstone, deletes row.
- `BaseModelUpdateLog`; `Notification.record(...)` goes INSIDE
  `transaction.atomic()`; push fan-out on `on_commit`.
- FKs: `on_delete=models.RESTRICT` always; money = DecimalField;
  never `get_user_model()` — `from djangoapp.models import User`;
  m2m changes not logged.

## 5. Endpoints + Inertia pages pattern

Copy from the §9 skeletons first; the full reference files back them.

- Pages = PLAIN Django views in `ourapp/views/<feature>.py`, routed
  `path(...)` in `ourapp/urls.py` (see also
  `docs/reference/ourapp/urls.py`). JSON/file = `Router` endpoints
  (`@router.post("/todos/create", response=Schema)`).
- `ourapp/views/__init__.py` combines feature routers onto one `Router`
  (`router.add_router("/", <feature>.router)`) and builds the single API via
  `make_ninja_api("ourapp", router, prefix="")` (error handlers + CSRF guard
  ride along); mounted last in urls.py so page paths win.
- Errors: `ApiError(status, *, type=, msg=, ctx=)` from
  `djangoapp.ninja_api` — never `HttpError`.
- Auth: `user_or_404(request)` / `maybe_user(request)` from
  `djangoapp.shortcuts`; ownership failure = 404 not 403.
- Payloads pk-free (`public_id` only); page data nested under `props`
  → pages parse BOTH levels via `useAppPage(FeaturePropsSchema)` from
  `frontend/src/system/utils/useAppPage.ts` — returns `{ shared, data }`,
  computed inside (Inertia swaps the whole page object on every
  visit/reload; parsing inside a computed is what keeps it live); every
  payload stays zod-parsed; HTTP via
  `frontend/src/system/utils/http.ts` (`ninjaPost`/`ninjaGet`/
  `ninjaDelete` — non-2xx throws: a 422 as `NinjaError`, the rest via
  the taxonomy; toast-only callers let it fly to main.ts' handlers);
  toasts via `showToast`/`showErrorToast`; inline field errors via
  `FieldError` + `errorAtPath`.
- Page routes taking a `public_id` path param use `<uuid:public_id>` —
  pages resolve before API mounts, so a bare `<str:public_id>` page
  route shadows same-shape API paths (e.g. `POST /chores/create` under
  `chores/<str:public_id>`); the UUID converter can't match fixed
  segments like `create`.
- Pages render `<PageTitle :value="…"/>`.
- zod: one component → inline; one feature →
  `frontend/src/app/schemas/<feature>.ts`; framework →
  `system/schemas/`.

## 6. Test layout

- Flat: `ourapp/tests/test_<feature>_<layer>.py` (layers: `models`,
  `views`, `commands`, `playwright`). Bases:
  `djangoapp.tests._base.BaseTestCase` / `BaseInertiaTestCase` (fast
  hashers); playwright:
  `djangoapp.tests.playwright._base.BasePlaywrightTestCase` (carries
  `playwright` tag + harness — no hand-tagging).
- Class docstring = one-line description + one bullet per test in
  declaration order.
- Run: `./run test <labels…>` (fast, keepdb) / `./run test --full`.

## 7. Copy-me trio (see also `docs/reference/`)

- Backend: `docs/reference/ourapp/models/todos.py`,
  `docs/reference/ourapp/views/todos.py`
- Tests: `docs/reference/ourapp/tests/test_todos_models.py`,
  `docs/reference/ourapp/tests/test_todos_views.py`,
  `docs/reference/ourapp/tests/test_todos_playwright.py`
- Frontend: `docs/reference/frontend/src/pages/TodosPage.vue`,
  `docs/reference/frontend/src/schemas/todos_sdk.ts`
- Wiring: `docs/reference/ourapp/urls.py` +
  `docs/reference/ourapp/views/__init__.py`

## 8. Gotchas that cost sessions time (don't rediscover)

- **Django-model queries from a script**: `export
  DJANGO_SETTINGS_MODULE=djangoproject.settings && ./run python -c
  'import django; django.setup(); from ourapp.models import Todo;
  …'`. Everything else (settings env, allowlist) already rides
  `./run`. Prefer `dbstate`/management commands when one exists —
  and note `./run python -c` PROMPTS the operator by design; reserve
  it for when no command answers the question. Code-phase only —
  while a feature is a mockup, python stays untouched (steer's
  no-probe/no-python rule): a mockup question is answered by the
  operator's click on the deployed link, not a query.
- **JSON API surface**: introspect via the NinjaAPI instance, not the
  filesystem: `from ourapp.views import api; [p for p in
  api.urls]` (mount point + operation paths). Pages are NOT on api —
  they are plain views (§5).
- **Inertia test helpers**: read `docs/reference/frontend/` first;
  the live helpers sit in site-packages — do not go spelunking there.
- **`dbbackups/` inside main/ is a postgres-owned island.** Never
  chown/copy/write into it; pgbackrest (running as postgres) fails
  the backup when its ownership changes.
- **Gate leftover landmine**: a gate run leaves the DB at the assert-11
  restore point — testapp migration rows included. If a fresh feature
  500s with tables missing, check `django_migrations` for a colliding
  `0001_initial`.

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

A `Meta.constraints` rule (uniqueness etc.) uses the same `ClassVar`
form — from `docs/reference/ourapp/models/facts.py`:

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
