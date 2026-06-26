## Article History

Article history should be revealed to editors and authors. In articles page, have a link `N history entries`. It takes you to a new page.

### Handwritten requirements

changes
    title:
        old: str
        new: str
    public_id:
        old: str
        new: str
    tags:
        old:
            - name: str
            - color: str
        new:
            - name: str
            - color: str
    authors:
        old:
            - id: str
            - title: str
            - url: str | None
        new:
            ...
    published_date:
        old: date/null
        new: date/null

old and new should have same signatures. If title, public_id etc were not changed their value would be blank. For created, old and new values will be same.

ArticleHistory model is:
article: fk
article_pk_copy: a copy of pk, since if article is deleted, .article will become None
user:
time:
action: created / edited / deleted
old/new fields as individual Django columns (title, public_id, content, tags, authors, published_date)

Pydantic schemas for structured data in JSON fields (tags with name+color, authors with id+title+url).

### Pydantic Schemas

These live in `models/base.py` alongside `ArticleHistory`. `ArticleHistoryTagItem` and `ArticleHistoryAuthorItem` are needed for structured tag/author data. There is no wrapping `ArticleHistoryChanges` model — the old/new fields are stored as individual Django model columns on `ArticleHistory`.

```python
class ArticleHistoryTagItem(PydanticBaseModel):
    name: str
    color: str

class ArticleHistoryAuthorItem(PydanticBaseModel):
    id: str
    title: str
    url: str | None = None
```

### Detailed Plan

**Model**: `ArticleHistory` in `models/base.py`
- `article`: FK → Article, on_delete=SET_NULL, null=True, blank=True (keep history when article deleted)
- `article_pk_copy`: IntegerField — denormalized copy of article.pk, survives article deletion
- `article_public_id_copy`: CharField — denormalized copy of article.public_id for display
- `user`: FK → User, on_delete=SET_NULL, null=True, blank=True (keep history when user deleted), related_name="+"
- `time`: DateTimeField(auto_now_add=True)
- `action`: CharField with choices: `created`, `edited`, `deleted`
- `title_old`: CharField(blank=True, default="")
- `title_new`: CharField(blank=True, default="")
- `public_id_old`: CharField(blank=True, default="")
- `public_id_new`: CharField(blank=True, default="")
- `content_old`: TextField(blank=True, default="")
- `content_new`: TextField(blank=True, default="")
- `_tags_old`: JSONField(default=list) — list of `ArticleHistoryTagItem` dicts
- `_tags_new`: JSONField(default=list) — list of `ArticleHistoryTagItem` dicts
- `_authors_old`: JSONField(default=list) — list of `ArticleHistoryAuthorItem` dicts
- `_authors_new`: JSONField(default=list) — list of `ArticleHistoryAuthorItem` dicts
- `published_date_old`: DateTimeField(null=True, blank=True)
- `published_date_new`: DateTimeField(null=True, blank=True)
- Indexes: `[article_pk_copy]`, `[time]`
- Ordering: `-time`

**Properties on ArticleHistory**:
- `tags_old` / `tags_new` — getter/setter using TypeAdapter for `list[ArticleHistoryTagItem]` on `_tags_old`/`_tags_new`
- `authors_old` / `authors_new` — getter/setter using TypeAdapter for `list[ArticleHistoryAuthorItem]` on `_authors_old`/`_authors_new`

Unchanged fields have empty strings / empty lists / None. For `created` action, old and new are the same values.

**Recording history**:
- `Article.create()` calls `ArticleHistory.record_created(article, user)` after save — old and new values are the same
- `Article.update()` calls `ArticleHistory.record_edited(article, user, old_title, old_public_id, old_content, old_tags, old_authors, old_published_date)` — computes diff, unchanged fields are blank
- `Article.delete()` calls `ArticleHistory.record_deleted(article, user)` before actual delete — old has current values, new is blank

**Endpoints** (in `ArticleView`):
- `GET /articles/history/{public_id}` — Inertia page, shows all ArticleHistory entries for an article, visible to editors and authors of that article

**Frontend**:
- New page `ArticleHistory.vue` — shows timeline of changes with user, time, action, and field diffs
- Update `ArticleListItem` schema to include `history_count: int`
- Update `ArticleDetailsProps` schema to include `history_count: int`
- Add "N history entries" link in ArticleList.vue (visible to editors/authors only)
- Add "N history entries" link in ArticleDetails.vue (visible to editors/authors only)
- CSS styles in `styles/articles.scss` for history timeline

### Clarifications
- **No wrapping pydantic model**: Unlike RowUpdate which stores a JSON list and deserializes via pydantic, ArticleHistory stores old/new values as individual Django model columns. Only tags and authors use JSONFields with `ArticleHistoryTagItem`/`ArticleHistoryAuthorItem` pydantic schemas for structured data.
- **Created entries**: old and new are identical (all fields populated with current values).
- **Deleted entries**: old has current values, new is blank (empty strings, empty lists, None).
- **User profiles for authors**: `ArticleHistoryAuthorItem` uses `user_profiles()` from ArticleView to get id, title, url — same as list/details pages.
- **Tags as structured objects**: tags include both name and color (not just name strings), so the frontend can render colored badges in history view.
- **Permission**: Only editors and article authors can view history. Same check as `_can_edit`.

### URLs
| Path | Purpose |
|---|---|
| `/articles/history/{public_id}` | Article history page |

### Checklist

#### Phase 1: Model
- [x] add pydantic schemas in `models/base.py`
    - [x] `ArticleHistoryTagItem(name: str, color: str)`
    - [x] `ArticleHistoryAuthorItem(id: str, title: str, url: str | None)`
- [x] add `ArticleHistory` model to `models/base.py`
    - [x] columns: `article` FK (SET_NULL), `article_pk_copy`, `article_public_id_copy`, `user` FK (SET_NULL), `time`, `action`
    - [x] old/new columns: superseded by Snapshot Refactoring `_changes` JSONField
    - [x] JSON columns: superseded by Snapshot Refactoring `_changes` JSONField
    - [x] `published_date_old/new`: superseded by Snapshot Refactoring `_changes` JSONField
    - [x] `record_created` classmethod — uses `snapshot.as_new()`
    - [x] `record_edited` classmethod — uses `old_snapshot.difference(new_snapshot)`
    - [x] `record_deleted` classmethod — `_changes={}`
    - [x] `Meta` with indexes and ordering
- [x] add `ArticleHistory` to `models/__init__.py` exports
- [x] create migration

#### Phase 2: History recording in model methods
- [x] update `Article.create()` to accept `user` param and call `ArticleHistory.record_created()`
- [x] update `Article.update()` to accept `user` param, snapshot old values, call `ArticleHistory.record_edited()`
- [x] update `Article.delete()` to accept `user` param and call `ArticleHistory.record_deleted()`
- [x] update all callers in `views/articles.py` to pass `user` to create/update/delete

#### Phase 3: History endpoint
- [x] add `GET /history/{public_id}` route to `ArticleView` — Inertia page
- [x] permission: visible to editors and authors of the article
- [x] `ArticleHistoryProps` pydantic schema
- [x] pass `path_prefix` to page

#### Phase 4: Frontend
- [x] add `ArticleHistoryTagItem`, `ArticleHistoryAuthorItem` schemas to `schemas.ts`
- [x] add `ArticleHistoryPropsSchema` to `schemas.ts`
- [x] create `ArticleHistory.vue` page
    - [x] timeline of history entries: action label, user name, timestamp
    - [x] show field diffs (old → new) for each field, tag badges with colors
- [x] update `ArticleListItemSchema` to add `history_count`
- [x] update `ArticleDetailsPropsSchema` to add `history_count`
- [x] add "N history entries" link in `ArticleList.vue` (editors/authors only)
- [x] add "N history entries" link in `ArticleDetails.vue` (editors/authors only)
- [x] add CSS for history timeline in `styles/articles.scss`

#### Phase 5: Backend tests
- [x] `ArticleHistoryModelTests` in `test_articles.py`
    - [x] `test_record_created` — creates entry with action="created", all fields present old==new
    - [x] `test_record_edited_detects_title_change` — records title change, other fields absent
    - [x] `test_record_edited_detects_content_change` — records content change
    - [x] `test_record_edited_detects_tag_change` — records tag change with name+color
    - [x] `test_record_edited_detects_author_change` — records author change with id+title+url
    - [x] `test_record_edited_detects_published_date_change` — records published_at change
    - [x] `test_record_edited_no_changes` — all change fields absent when nothing changed
    - [x] `test_record_deleted` — creates entry with action="deleted", empty changes
    - [x] `test_survives_article_deletion` — article_pk_copy persists after article FK nullified
    - [x] `test_changes_roundtrip` — pydantic round-trip for `_changes` JSON field
- [x] `ArticleHistoryViewTests` in `tests/views/test_articles.py`
    - [x] `test_history_visible_to_editor` — editor sees history page
    - [x] `test_history_visible_to_author` — author sees history page
    - [x] `test_history_hidden_from_anon` — anonymous gets 404
    - [x] `test_history_hidden_from_non_author` — non-author non-editor gets 404
    - [x] `test_history_shows_entries` — page contains history entries

#### Phase 6: Final
- [x] `./run checkall` passes

---

### Snapshot Refactoring

Replace 12 individual old/new Django columns with a single `_changes` JSONField storing serialized `ArticleHistoryContent`. This simplifies the model, eliminates the `record_edited` DB re-fetch, and makes `Article.update()` cleaner.

#### New Pydantic Schemas

```python
class FieldChange(PydanticBaseModel):
    old: str
    new: str

class NullableFieldChange(PydanticBaseModel):
    old: str | None
    new: str | None

class TagListChange(PydanticBaseModel):
    old: list[ArticleHistoryTagItem]
    new: list[ArticleHistoryTagItem]

class AuthorListChange(PydanticBaseModel):
    old: list[ArticleHistoryAuthorItem]
    new: list[ArticleHistoryAuthorItem]

class ArticleHistoryContent(PydanticBaseModel):
    title: FieldChange | None = None
    public_id: FieldChange | None = None
    content: FieldChange | None = None
    tags: TagListChange | None = None
    authors: AuthorListChange | None = None
    published_date: NullableFieldChange | None = None

class ArticleSnapshot(PydanticBaseModel):
    title: str
    public_id: str
    content: str
    tags: list[ArticleHistoryTagItem]
    authors: list[ArticleHistoryAuthorItem]
    published_date: datetime.date | None

    def as_new(self) -> ArticleHistoryContent:
        """All fields with old==new — used for 'created' action."""
        return ArticleHistoryContent(
            title=FieldChange(old=self.title, new=self.title),
            public_id=FieldChange(old=self.public_id, new=self.public_id),
            content=FieldChange(old=self.content, new=self.content),
            tags=TagListChange(old=self.tags, new=self.tags),
            authors=AuthorListChange(old=self.authors, new=self.authors),
            published_date=NullableFieldChange(
                old=self.published_date.isoformat() if self.published_date else None,
                new=self.published_date.isoformat() if self.published_date else None,
            ),
        )

    def difference(self, other: ArticleSnapshot) -> ArticleHistoryContent:
        """Only changed fields — self is old, other is new."""
        changes: dict[str, Any] = {}
        if self.title != other.title:
            changes["title"] = FieldChange(old=self.title, new=other.title)
        if self.public_id != other.public_id:
            changes["public_id"] = FieldChange(old=self.public_id, new=other.public_id)
        if self.content != other.content:
            changes["content"] = FieldChange(old=self.content, new=other.content)
        if self.tags != other.tags:
            changes["tags"] = TagListChange(old=self.tags, new=other.tags)
        if self.authors != other.authors:
            changes["authors"] = AuthorListChange(old=self.authors, new=other.authors)
        if self.published_date != other.published_date:
            changes["published_date"] = NullableFieldChange(
                old=self.published_date.isoformat() if self.published_date else None,
                new=other.published_date.isoformat() if other.published_date else None,
            )
        return ArticleHistoryContent(**changes)
```

Note: `ArticleSnapshot.published_date` is `datetime.date | None` (native date, not ISO string). Serialization to ISO string happens in `as_new()` and `difference()` when building `NullableFieldChange`. Deserialization from JSON via `ArticleHistoryContent.model_validate()` produces strings in `NullableFieldChange.old/new` — matching what zod expects on the frontend.

#### Updated `ArticleHistoryEntryItem`

Flat old/new fields replaced with single nested `changes`:

```python
class ArticleHistoryEntryItem(PydanticBaseModel):
    id: int
    action: Literal["created", "edited", "deleted"]
    time: str
    changes: ArticleHistoryContent   # replaces 12 flat fields
```

#### `Article.snapshot()` method

New method on Article model that captures current state as `ArticleSnapshot`:

```python
def snapshot(self, user_profiles=None) -> ArticleSnapshot:
    tags = [ArticleHistoryTagItem(name=t.name, color=t.color) for t in self.tags.all()]
    authors = ArticleHistory.snapshot_authors(self, user_profiles)
    return ArticleSnapshot(
        title=self.title,
        public_id=self.public_id,
        content=self.content,
        tags=tags,
        authors=authors,
        published_date=self.published_at.date() if self.published_at else None,
    )
```

#### `ArticleHistory` model changes

**Drop** 12 columns: `title_old/new`, `public_id_old/new`, `content_old/new`, `_tags_old/new`, `_authors_old/new`, `published_date_old/new`

**Add**: `_changes = models.JSONField(default=dict)`

**Remove**: `tags_old`/`tags_new` property getter/setters, `_tags_list_adapter`, `_authors_list_adapter`

**Keep**: `article`, `article_pk_copy`, `article_public_id_copy`, `user`, `time`, `action`, indexes, ordering, `snapshot_tags()`, `snapshot_authors()`

#### Rewritten record methods

- **`record_created(article, user, snapshot)`** — `snapshot.as_new()` → `_changes`
- **`record_edited(article, user, old_snapshot, new_snapshot)`** — `old_snapshot.difference(new_snapshot)` → `_changes`
- **`record_deleted(article, user)`** — `_changes={}` (no field data)

#### Updated `to_article_history_entry_item()`

```python
def to_article_history_entry_item(self) -> ArticleHistoryEntryItem:
    content = ArticleHistoryContent.model_validate(self._changes) if self._changes else ArticleHistoryContent()
    return ArticleHistoryEntryItem(
        id=self.pk,
        action=cast(Literal["created", "edited", "deleted"], self.action),
        time=self.time.isoformat(),
        changes=content,
    )
```

#### Updated `Article.create()` and `Article.update()`

**`create()`**: After save + tag/author assignment → `article.snapshot(_user_profiles)` → `record_created(article, user, snapshot)`

**`update()`**:
1. `old_snapshot = self.snapshot(_user_profiles)` — before any changes
2. Apply scalar field changes, `self.save()`
3. Update tags/authors (clear + add)
4. `new_snapshot = self.snapshot(_user_profiles)` — after changes
5. `ArticleHistory.record_edited(self, user, old_snapshot, new_snapshot)`

This eliminates the current `record_edited` hack of re-fetching from DB and accepting `tag_names`/`author_ids` params to compute future M2M state.

#### Frontend `schemas.ts`

```ts
const FieldChangeSchema = z.object({ old: z.string(), new: z.string() })
const NullableFieldChangeSchema = z.object({ old: z.string().nullable(), new: z.string().nullable() })
const TagListChangeSchema = z.object({ old: z.array(ArticleHistoryTagItemSchema), new: z.array(ArticleHistoryTagItemSchema) })
const AuthorListChangeSchema = z.object({ old: z.array(ArticleHistoryAuthorItemSchema), new: z.array(ArticleHistoryAuthorItemSchema) })
const ArticleHistoryChangesSchema = z.object({
  title: FieldChangeSchema.nullish(),
  public_id: FieldChangeSchema.nullish(),
  content: FieldChangeSchema.nullish(),
  tags: TagListChangeSchema.nullish(),
  authors: AuthorListChangeSchema.nullish(),
  published_date: NullableFieldChangeSchema.nullish(),
})

export const ArticleHistoryEntrySchema = z.object({
  id: z.number(),
  action: z.enum(["created", "edited", "deleted"]),
  time: z.string(),
  changes: ArticleHistoryChangesSchema,
})
```

#### Frontend `ArticleHistory.vue`

Replace `entry.title_old` → `entry.changes.title?.old`, `entry.title_new` → `entry.changes.title?.new`, etc.
`hasChanges()` becomes `Object.keys(entry.changes ?? {}).length > 0`. All template `v-if` guards update similarly.

#### Data semantics

- **Created**: all `ArticleHistoryContent` fields present with `old == new`
- **Edited**: only changed fields present, unchanged fields are `None` (absent from JSON)
- **Deleted**: `_changes` is `{}` (empty `ArticleHistoryContent`)

#### Snapshot Refactoring Checklist

##### Phase A: Backend schemas & model
- [x] add `FieldChange`, `NullableFieldChange`, `TagListChange`, `AuthorListChange`, `ArticleHistoryContent`, `ArticleSnapshot` pydantic schemas to `models/base.py`
- [x] update `ArticleHistoryEntryItem` to use `changes: ArticleHistoryContent` instead of 12 flat fields
- [x] remove `_tags_list_adapter`, `_authors_list_adapter`
- [x] add `Article.snapshot()` method on Article model
- [x] refactor `ArticleHistory` model: drop 12 old/new columns, add `_changes` JSONField
- [x] remove `tags_old`/`tags_new` property getter/setters
- [x] rewrite `record_created(article, user, snapshot)` to use `snapshot.as_new()`
- [x] rewrite `record_edited(article, user, old_snapshot, new_snapshot)` to use `old_snapshot.difference(new_snapshot)`
- [x] keep `record_deleted(article, user)` — `_changes={}`
- [x] update `to_article_history_entry_item()` to deserialize `_changes`
- [x] create migration (drops 12 columns, adds `_changes`; existing history data lost)

##### Phase B: Article create/update
- [x] update `Article.create()` to call `article.snapshot()` then `record_created(article, user, snapshot)`
- [x] update `Article.update()` to snapshot before changes, apply changes, snapshot after, then `record_edited(article, user, old_snapshot, new_snapshot)`

##### Phase C: Frontend
- [x] add `FieldChangeSchema`, `NullableFieldChangeSchema`, `TagListChangeSchema`, `AuthorListChangeSchema`, `ArticleHistoryChangesSchema` to `schemas.ts`
- [x] update `ArticleHistoryEntrySchema` to use `changes: ArticleHistoryChangesSchema`
- [x] update `ArticleHistory.vue` to use nested `entry.changes.title?.old` pattern
- [x] update `hasChanges()` to check `Object.keys(entry.changes ?? {}).length > 0`

##### Phase D: Tests
- [x] update `ArticleHistoryModelTests` — all assertions change from `entry.title_old` to `entry.to_article_history_entry_item().changes.title?.old` pattern
- [x] update `record_edited` calls to pass snapshots instead of `tag_names`/`author_ids` params
- [x] update `test_tags_authors_property_roundtrip` — no more `_tags_old` column, test `_changes` JSON instead
- [x] verify `ArticleHistoryViewTests` still pass (minimal changes expected)

##### Phase E: Final
- [x] `./run checkall` passes

---

### aihere items

- [x] `Article.update()` — use `clear()` + bulk `add()` with `filter(name__in=...)` instead of clear + loop get/add [djangoapp/models/base.py]
- [x] `ArticleHistoryAuthorItem` — replaced with pydantic `UserProfile` shared between models and views [djangoapp/models/base.py]
- [x] `FieldChange` — renamed to `StringChange` [djangoapp/models/base.py]
- [x] `NullableFieldChange` — renamed to `NullableDatetimeChange` for `published_date` [djangoapp/models/base.py]
- [x] `ArticleHistory.article_pk_copy` — removed, queries use `article` FK instead [djangoapp/models/base.py]
- [x] `ArticleListItemSchema.history_count` — removed from list page (backend + frontend) [frontend/src/schemas.ts]

#### Round 2

- [x] `Article.create()` — `user` param made required `AbstractUser` (not `| None`) [djangoapp/models/base.py]
- [x] `Article.create()` — renamed `_user_profiles` → `author_profile_fn`, `Callable[[AbstractUser], UserProfile]` (not `Any`, not `None`). Applied to `create()`, `snapshot()`, `update()`, `snapshot_authors()` [djangoapp/models/base.py]
- [x] `Article.create()` — use `.set()` instead of `.add()` for tags and authors [djangoapp/models/base.py]
- [x] `Article.update()` — replaced `get_user_model()` with `User` (already imported at top) [djangoapp/models/base.py]
- [x] `NullableDatetimeChange` → `NullableDateChange` — fields use `date_type | None` instead of `str | None` [djangoapp/models/base.py]
- [x] `ArticleHistory.snapshot_authors()` — takes `Callable[[AbstractUser], UserProfile]`, single call per author, no loop/fallback [djangoapp/models/base.py]
- [x] `_user_profiles_for_history()` — removed entirely, views pass `self.user_profile` directly as `author_profile_fn` [djangoapp/views/articles.py]
- [x] Added `_user_or_404(request)` helper; `_can_edit_or_404`/`_can_delete_or_404` take `AbstractUser` (not `| None`); updated all callers [djangoapp/views/articles.py]
- [x] `test_record_created` — removed empty aihere comment [djangoapp/tests/test_articles.py]

---

### ArticleService — Replace `author_profile_fn` callback with service object

Replace the `author_profile_fn: Callable[[AbstractUser], UserProfile]` callback parameter on `Article.create()`, `Article.update()`, `Article.snapshot()` with a service object attached to `Article` via `add_to_class`. The service encapsulates `role()` and `user_profiles()` — the app-specific logic currently defined in `AppArticleView` and passed as callbacks.

#### Motivation

- `author_profile_fn` is a callback that leaks view-layer logic into the model API. Every caller must thread it through.
- `ArticleView` abstract methods (`role`, `user_profiles`) duplicate what the service provides.
- A service object on `Article` lets model methods call `Article._service.user_profiles([...])` directly — no callbacks.

#### New classes

**`BaseArticleService`** — abstract base class in `models/base.py` (near `Article`):

```python
class BaseArticleService(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def role(user: AbstractUser | None) -> Literal["editor", "author"] | None: ...

    @staticmethod
    @abc.abstractmethod
    def user_profiles(users: Iterable[AbstractUser]) -> list[UserProfile]: ...
```

Only two abstract methods. No `user_profile` — callers use `svc.user_profiles([user])[0]` when needed. `path_prefix` is NOT on the service — it stays on `ArticleView` since it's per-mount, not per-app.

**`ArticleService`** — concrete class in `views/app.py`:

```python
class ArticleService(BaseArticleService):
    @staticmethod
    def role(user: AbstractUser | None) -> Literal["editor", "author"] | None:
        if user is None or not user.is_authenticated:
            return None
        if user.is_staff:
            return "editor"
        return None

    @staticmethod
    def user_profiles(users: Iterable[AbstractUser]) -> list[UserProfile]:
        return [
            UserProfile(
                id=str(u.pk),
                title=(f"{u.first_name} {u.last_name}").strip() or u.username,
                url=None,
            )
            for u in users
        ]
```

**Attachment** — in `views/app.py` at module level:

```python
Article.add_article_service(ArticleService)
```

`_service` is a class attribute holding the service class (not instance — all methods are static). Stored as `type[BaseArticleService]` type annotation on `Article`.

**Sugar method** on `Article` — typechecked wrapper around `add_to_class`:

```python
@classmethod
def add_article_service(cls, service_cls: type[BaseArticleService]) -> None:
    cls.add_to_class("_service", service_cls)
```

This ensures mypy checks that the argument is a `type[BaseArticleService]` subclass, catching missing method implementations at type-check time.

#### Migration: `author_profile_fn` → `Article._service`

##### `Article.snapshot()` — remove `author_profile_fn` param

```python
# Before
def snapshot(self, author_profile_fn: Callable[[AbstractUser], UserProfile]) -> ArticleSnapshot:
    authors = ArticleHistory.snapshot_authors(self, author_profile_fn)

# After
def snapshot(self) -> ArticleSnapshot:
    authors = ArticleHistory.snapshot_authors(self, Article._service.user_profiles)
```

Note: `ArticleHistory.snapshot_authors` takes `Callable[[Iterable[AbstractUser]], list[UserProfile]]` — but `_service.user_profiles` takes a list. Options:
  - (A) Keep `snapshot_authors(article, author_profile_fn)` signature, pass a lambda: `lambda u: Article._service.user_profiles([u])[0]`
  - (B) Change `snapshot_authors` to accept `Callable[[Iterable[AbstractUser]], list[UserProfile]]` and call `user_profiles` directly
  - (C) `snapshot_authors` calls `Article._service.user_profiles` directly, no param needed

Option (C) is cleanest — `snapshot_authors` uses the service internally:

```python
@classmethod
def snapshot_authors(cls, article: Article) -> list[UserProfile]:
    return Article._service.user_profiles(article.authors.all())
```

Then `Article.snapshot()` simply calls `ArticleHistory.snapshot_authors(self)`.

##### `Article.create()` — remove `author_profile_fn` param

```python
# Before
def create(cls, ..., author_profile_fn, user):
    ...
    snapshot = article.snapshot(author_profile_fn)

# After
def create(cls, ..., user):
    ...
    snapshot = article.snapshot()
```

##### `Article.update()` — remove `author_profile_fn` param

```python
# Before
def update(self, ..., author_profile_fn, user):
    old_snapshot = self.snapshot(author_profile_fn)
    ...
    new_snapshot = self.snapshot(author_profile_fn)

# After
def update(self, ..., user):
    old_snapshot = self.snapshot()
    ...
    new_snapshot = self.snapshot()
```

##### `ArticleView` — delegate to `Article._service`

```python
# Before (in ArticleView)
def user_profile(self, user):
    return self.user_profiles([user])[0]

# After
def user_profiles(self, users):
    return Article._service.user_profiles(users)

def role(self, user):
    return Article._service.role(user)
```

`ArticleView` keeps its abstract `role` and `user_profiles` methods (for `TagView` which also uses them), but `AppArticleView` implementations become one-line delegations to the service. Eventually `AppArticleView` could be simplified further.

##### `ArticleView` callers — remove `author_profile_fn=` kwargs

```python
# Before
article = Article.create(..., author_profile_fn=self.user_profile)
article.update(..., author_profile_fn=self.user_profile)

# After
article = Article.create(..., user=user)
article.update(..., user=user)
```

##### Tests — remove `author_profile_fn` param, attach test service

Test files pass `_author_profile` as `author_profile_fn`. After migration:

```python
# Before
Article.create(title="Test", user=self.user, author_profile_fn=_author_profile)

# After — need a test service attached to Article
Article.add_article_service(TestArticleService)
Article.create(title="Test", user=self.user)
```

Or define a test-only `TestArticleService(BaseArticleService)` and attach it in `setUpClass` / at module level.

#### Checklist

##### Phase A: Base class, sugar method, and service
- [x] add `BaseArticleService` ABC to `models/base.py` with abstract `role()` and `user_profiles()`
- [x] add `add_article_service(cls, service_cls: type[BaseArticleService])` classmethod to `Article` — wraps `add_to_class("_service", service_cls)`
- [x] add `ClassVar[type[BaseArticleService]]` annotation on `Article`
- [x] add `ArticleService(BaseArticleService)` to `views/app.py` with current `AppArticleView` logic
- [x] attach service: `Article.add_article_service(ArticleService)` in `views/app.py`

##### Phase B: Remove `author_profile_fn` from Article methods
- [x] `ArticleHistory.snapshot_authors()` — remove `author_profile_fn` param, call `Article._service.user_profiles(article.authors.all())` directly
- [x] `Article.snapshot()` — remove `author_profile_fn` param
- [x] `Article.create()` — remove `author_profile_fn` param
- [x] `Article.update()` — remove `author_profile_fn` param
- [x] `ArticleView.create_submit()` — remove `author_profile_fn=self.user_profile` kwarg
- [x] `ArticleView.edit_submit()` — remove `author_profile_fn=self.user_profile` kwarg

##### Phase C: Simplify ArticleView / AppArticleView
- [x] `ArticleView.user_profiles()` — delegate to `Article._service.user_profiles()`
- [x] `ArticleView.role()` — keep abstract (used by `TagView`), `AppArticleView.role()` delegates to `ArticleService.role()`
- [x] `AppArticleView.user_profiles()` — delegates to `ArticleService.user_profiles()`

##### Phase D: Tests
- [x] add `TestArticleService(BaseArticleService)` to `tests/test_articles.py` matching current `_author_profile` logic
- [x] attach in test setup: `Article.add_article_service(TestArticleService)`
- [x] remove all `author_profile_fn=_author_profile` kwargs from test calls
- [x] add `TestArticleService` to `tests/playwright/test_articles.py` and remove `author_profile_fn=self._profile` kwargs
- [x] add `TestArticleService` to `tests/views/test_articles.py` and remove `author_profile_fn=_profile` kwargs

##### Phase E: Final
- [x] `./run checkall` passes

---

### Round 4: `user_queryset`, snapshot methods on Article, single author

#### Requirements

1. **`BaseArticleService.user_queryset()`** — replaces `user_profiles()`. Returns annotated `QuerySet[AbstractUser]` with `name` and `url`. Base class annotates `name=Concat(first_name, last_name)`, `url=None`. Subclass overrides `url` with actual URL logic.

2. **Remove `user_profiles()`** from `BaseArticleService` and `ArticleService`. All callers use `Article._service.user_queryset()` with `Prefetch` instead.

3. **Move `snapshot_tags` and `snapshot_authors` to `Article`** — become instance methods `article.snapshot_tags()` and `article.snapshot_authors()`. `snapshot_authors` uses `Article._service.user_queryset()` to fetch annotated authors.

4. **Single author per article** — `authors` M2M → `author` FK. Each article has exactly one author.

#### Inconsistencies / breaking changes with single-author

| Area | Current (M2M) | Single author impact |
|---|---|---|
| `Article.authors` field | `ManyToManyField(User)` | → `ForeignKey(User, on_delete=RESTRICT)` |
| `Article.create()` | `author_ids: list[int]`, `.authors.set(...)`, `.authors.add(user)` | → `author_id: int`, single FK assignment. `user` param may become the author automatically (remove separate `author_ids`). |
| `Article.update()` | `author_ids: list[int]`, `.authors.set(...)` | → `author_id: int`, `self.author = User.objects.get(...)`. Or remove author changing from update entirely. |
| `ArticleView._is_author_or_editor()` | `article.authors.filter(pk=user.pk).exists()` | → `article.author_id == user.pk` |
| `ArticleView` list/details/edit | `authors = list(article.authors.all())` + `self.user_profiles(authors)` | → `article.author` (single object), use `Prefetch` or annotated queryset |
| `ArticleListItem` / `ArticleDetailsItem` | `authors: list[ArticleAuthorItem]` | → `author: ArticleAuthorItem` (single object, not list) |
| `ArticleAuthorItem` | `id: str, name: str` | Same shape, but singular not in a list |
| `ArticleListFilters` | `author: list[int]` + `qs.filter(authors__pk__in=...)` | → `author: int` + `qs.filter(author_id=...)`, or keep as list for "OR" filter |
| `ArticleEdit` / `ArticleCreate` form | multiselect for authors | → single select or no selector (auto-assign current user) |
| `ArticleForm.vue` | `<Multiselect>` for authors | → single select dropdown or hidden field |
| `ArticleSnapshot` | `authors: list[UserProfile]` | → `author: UserProfile` (single) |
| `AuthorListChange` | `old: list[...], new: list[...]` | → `AuthorChange(old=UserProfile, new=UserProfile)` — single old/new, not lists |
| `ArticleHistoryContent` | `authors: AuthorListChange \| None` | → `author: AuthorChange \| None` |
| History test `test_record_edited_detects_author_change` | Asserts `len(d.changes.authors.old) == 1` | → Assert `d.changes.author.old.id == ...` |
| `search_authors` API | Returns list of `ArticleAuthorItem` for multiselect | → Still useful if admin can reassign author, or remove endpoint |
| `ArticleHistory.snapshot_authors()` | Returns `list[UserProfile]` | → Returns single `UserProfile` |
| `TagView` | Uses `self.role()` and `self.user_profiles()` from `ArticleView` | `role` stays, `user_profiles` removed, TagView may need its own service or not use profiles |
| `ArticleList.vue` filter | Multiselect author filter | → Single select dropdown or remove |
| E2E tests `test_author_multiselect` | Creates with multiple authors/tags | → Single author only, test needs rewrite |
| `_is_author_or_editor` permission check | Checks M2M membership | → `article.author_id == user.pk` or `user.is_staff` |

#### Decision points

- **Can authors be reassigned?** Only editors can set/change author. Authors cannot. `ArticleCreate` — editors see author selector, authors auto-assigned to self. `ArticleEdit` — editors see author selector, authors cannot change it.
- **Author filter on list page**: keep as "any of" filter — `author: list[int]` + `qs.filter(author_id__in=...)`.
- **`author_ids` param on create/update**: `create()` — `author_id: int | None = None`; editors can set any author, authors auto-assigned to `user`. `update()` — `author_id: int | None = None`; only editors can change it.
- **Migration**: no need to keep existing data. Fresh migration.

#### Detailed plan

##### Backend model changes

**`Article` model** (`models/base.py`):
- `authors = ManyToManyField(User)` → `author = ForeignKey(User, on_delete=RESTRICT, related_name="articles")`
- `Article.create()`: remove `author_ids` param, add `author_id: int | None = None`. If editor provides `author_id`, use it; otherwise set `article.author = user`
- `Article.update()`: `author_ids: list[int]` → `author_id: int | None = None`; only editors can change it
- Move `ArticleHistory.snapshot_tags` → `Article.snapshot_tags()` (instance method)
- Move `ArticleHistory.snapshot_authors` → `Article.snapshot_author()` (instance method, singular, returns single `UserProfile`)
- `Article.snapshot()`: uses `self.snapshot_tags()` and `self.snapshot_author()`
- `Article.snapshot_author()`: uses `Article._service.user_queryset()` to get annotated author

**`BaseArticleService`**:
- Replace `user_profiles()` → `user_queryset() -> QuerySet[AbstractUser]` (abstract)
- Base class not needed — just have it on `ArticleService` since every app will annotate differently

Wait — keep `user_queryset` abstract on `BaseArticleService` so mypy enforces it.

```python
class BaseArticleService(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def role(user: AbstractUser | None) -> Literal["editor", "author"] | None: ...

    @staticmethod
    @abc.abstractmethod
    def user_queryset() -> QuerySet[AbstractUser]: ...
```

**`ArticleService`**:
- Remove `user_profiles()`
- Add `user_queryset()`:
  ```python
  @staticmethod
  def user_queryset() -> QuerySet[AbstractUser]:
      return User.objects.annotate(
          name=Concat("first_name", Value(" "), "last_name"),
          url=Value(None, output_field=CharField()),
      )
  ```

**Pydantic schemas** (`models/base.py`):
- `ArticleSnapshot.authors: list[UserProfile]` → `author: UserProfile`
- `AuthorListChange` → `AuthorChange(old: UserProfile, new: UserProfile)`
- `ArticleHistoryContent.authors: AuthorListChange | None` → `author: AuthorChange | None`
- `ArticleSnapshot.as_new()`: `authors=AuthorListChange(...)` → `author=AuthorChange(old=self.author, new=self.author)`
- `ArticleSnapshot.difference()`: `self.authors != other.authors` → `self.author != other.author`, `AuthorChange(old=self.author, new=other.author)`

**`ArticleHistory` model**:
- Remove classmethod `snapshot_tags` (moved to Article)
- Remove classmethod `snapshot_authors` (moved to Article)
- Keep `record_created`, `record_edited`, `record_deleted` unchanged (they take snapshots)

##### Backend view changes (`views/articles.py`)

**Schemas**:
- `ArticleAuthorItem` stays same shape (`id: str, name: str`)
- `ArticleListItem.authors: list[ArticleAuthorItem]` → `author: ArticleAuthorItem`
- `ArticleDetailsItem.authors: list[ArticleAuthorItem]` → `author: ArticleAuthorItem`
- `ArticleCreateProps`: remove `authors` list — editors get `author_id` field, authors auto-assigned
- `ArticleEditProps`: `author: ArticleAuthorItem` — editors can change, authors cannot
- `ArticleCreateSchema.authors: list[int]` → `author_id: int | None = None` (editors only)
- `ArticleUpdateSchema.authors: list[int]` → `author_id: int | None = None`

**`ArticleView` methods**:
- `_is_author_or_editor()`: `article.authors.filter(pk=user.pk).exists()` → `article.author_id == user.pk`
- `_can_edit()`: same simplification
- `list_page()`: replace `qs.prefetch_related("tags", "authors")` with `qs.prefetch_related("tags", Prefetch("author", queryset=Article._service.user_queryset()))`. Build `ArticleAuthorItem` from `article.author.name` (annotated).
- `details_page()`: same prefetch pattern. `article.author` instead of `list(article.authors.all())`.
- `create_page()`: editors see author selector, authors don't.
- `create_submit()`: `author_ids=payload.authors` → `author_id=payload.author_id` if editor, else `user`.
- `edit_page()`: pass `author: ArticleAuthorItem` instead of `authors: list[...]`.
- `edit_submit()`: `author_ids=payload.authors` → `author_id=payload.author_id` (only if editor).
- `search_authors`: keep — editors need it for the author selector on edit page.

**`AppArticleView`**:
- `user_profiles()` removed. `role()` delegates to `ArticleService.role()`.

**`ArticleView` (ABC)**:
- Remove abstract `user_profiles()`. Keep abstract `role()`.

##### Frontend changes

**`schemas.ts`**:
- `ArticleListItemSchema.authors: z.array(...)` → `author: ArticleAuthorItemSchema`
- `ArticleDetailsPropsSchema.authors: z.array(...)` → `author: ArticleAuthorItemSchema`
- `ArticleHistoryChangesSchema.authors: AuthorListChangeSchema.nullish()` → `author: AuthorChangeSchema.nullish()` where `AuthorChangeSchema = z.object({old: ArticleHistoryAuthorItemSchema, new: ArticleHistoryAuthorItemSchema})`
- `ArticleCreateSchema`: remove `authors` field
- `ArticleEditSchema`: `authors: z.array(z.number())` → `author_id: z.number().optional()`

**`ArticleList.vue`**:
- `article.authors.map(a => a.name).join(", ")` → `article.author.name`
- Author filter: keep `author: list[int]` param, but change from multiselect to single select (or keep as multiselect for "any of" filtering — backend uses `author_id__in`)

**`ArticleDetails.vue`**:
- `p.article.authors.map(...)` → `p.article.author.name`

**`ArticleEdit.vue`**:
- `selectedAuthors` multiselect → single author dropdown (editors only)
- Submit: `authors: selectedAuthors.map(a => a.id)` → `author_id: selectedAuthor?.id`

**`ArticleCreate.vue`**:
- Remove author selection entirely (auto-assigned to current user)

**`ArticleForm.vue`**:
- Remove author multiselect from shared form. Author only shown on edit (for editors).

**`ArticleHistory.vue`**:
- `entry.changes.authors` → `entry.changes.author`
- `entry.changes.authors.old[0]` → `entry.changes.author.old`
- Remove `v-for` loops over author lists

##### Test changes

**`tests/test_articles.py`**:
- `Article.create()`: remove `author_ids` params
- `Article.update()`: `author_ids` → `author_id` or remove
- `test_record_edited_detects_author_change`: `d.changes.authors.old[0]` → `d.changes.author.old`
- `test_record_edited_no_changes`: remove `author_ids` from update call
- `test_update_replaces_tags`: remove `author_ids` assertions
- `TestArticleService`: `user_profiles` → `user_queryset`

**`tests/views/test_articles.py`**:
- Update create/update payloads (remove `authors: [...]` list, use `author_id` or omit)
- `article.authors.add(user)` → `article.author = user; article.save()` in setUp

**`tests/playwright/test_articles.py`**:
- `test_author_multiselect`: rewrite for single author
- `article.authors.add(user)` → `article.author = user; article.save()`

##### Checklist

###### Phase A: `user_queryset` + remove `user_profiles`
- [x] `BaseArticleService`: replace abstract `user_profiles()` with concrete `user_queryset() -> QuerySet[AbstractUser]`
- [x] `ArticleService`: inherits `user_queryset()` from base, no override needed
- [x] `ArticleView` ABC: remove abstract `user_profiles()`
- [x] `AppArticleView`: remove `user_profiles()` override
- [x] `Article.snapshot_author()`: new method, uses `Article._service.user_queryset()` to get annotated author, returns `UserProfile`
- [x] `Article.snapshot_tags()`: move from `ArticleHistory.snapshot_tags` to instance method
- [x] `Article.snapshot()`: use `self.snapshot_tags()` and `self.snapshot_author()`
- [x] `ArticleHistory.snapshot_authors` and `snapshot_tags`: remove classmethods
- [x] `TestArticleService`: inherits `user_queryset()` from base in all test files

###### Phase B: Single author model change
- [x] `Article.authors` M2M → `Article.author` FK (`on_delete=RESTRICT`)
- [x] `Article.create()`: remove `author_ids`, set `article.author = user`
- [x] `Article.update()`: `author_ids: list[int]` → `author_id: int | None = None`
- [x] `ArticleSnapshot.authors: list[UserProfile]` → `author: UserProfile`
- [x] `AuthorListChange` → `AuthorChange(old: UserProfile, new: UserProfile)`
- [x] `ArticleHistoryContent.authors` → `author`
- [x] `ArticleSnapshot.as_new()` and `difference()`: update for single author
- [x] create migration (fresh, no data preservation)

###### Phase C: View and schema updates
- [x] `ArticleListItem.authors` → `author: ArticleAuthorItem`
- [x] `ArticleDetailsItem.authors` → `author: ArticleAuthorItem`
- [x] `ArticleUpdateSchema.authors: list[int]` → `author_id: int | None = None`
- [x] `ArticleCreateSchema.authors` → remove
- [x] `ArticleView._is_author_or_editor()`: `article.author_id == user.pk`
- [x] `ArticleView.list_page()`: `Prefetch("author", queryset=Article._service.user_queryset())`
- [x] `ArticleView.details_page()`: same prefetch, `article.author` instead of list
- [x] `ArticleView.create_submit()`: remove `author_ids`
- [x] `ArticleView.edit_submit()`: `author_id=payload.author_id`
- [x] `ArticleView.edit_page()`: pass single author
- [x] `ArticleListFilters.author`: keep `list[int]`, backend uses `author_id__in`

###### Phase D: Frontend
- [x] `schemas.ts`: `author` replaces `authors` in list/details/history schemas
- [x] `ArticleList.vue`: `article.author.name` instead of `.map().join()`
- [x] `ArticleDetails.vue`: same
- [x] `ArticleEdit.vue`: single author select for editors
- [x] `ArticleCreate.vue`: remove author selection
- [x] `ArticleForm.vue`: remove author multiselect, add single author select for editors on edit
- [x] `ArticleHistory.vue`: `entry.changes.author?.old` instead of `entry.changes.authors?.old[0]`

###### Phase E: Tests
- [x] `tests/test_articles.py`: remove `author_ids` params, update assertions for single author
- [x] `tests/views/test_articles.py`: `article.author = user` in setUp, update create/update payloads
- [x] `tests/playwright/test_articles.py`: rewrite `test_author_multiselect`, `article.author = user`

###### Phase F: Final
- [x] `./run checkall` passes

---

### Round 5: Remaining aihere items

- [x] `djangoapp/views/articles.py:341` — `# aihere use the annotated query so dont have n+1 queries here` — removed stale comment; `prefetch_related("tags").select_related("author")` is the correct Django pattern
- [x] `djangoapp/views/articles.py:602` — `# aihere service should have a search_users which take search string and return annotated queryset of user. Use it for this method.` — added `search_users(q, limit)` on `BaseArticleService`, used in `search_authors`; removed `Q` import from views
- [x] `djangoapp/models/base.py:1657` — `# aihere make this kwarg only` — removed stale comment (already kwarg-only with `*`)
- [x] `djangoapp/models/base.py:1711` — `# aihere make this kwarg only` — removed stale comment (already kwarg-only with `*`)
- [x] Fixed pre-existing mypy `attr-defined` errors: all `annotated.name`/`annotated.url` on `user_queryset()` results now use `getattr()` pattern for consistency

---

### Round 6: Merge `BaseArticleService` into `BaseArticleView`

Move `BaseArticleService` methods (`role`, `user_queryset`, `search_users`) to `BaseArticleView`. The view class acts as the service. The model defines a `Protocol` with only those 3 methods — `BaseArticleView` just happens to implement them.

#### Motivation

- `BaseArticleService` is a separate class whose only concrete subclass (`ArticleService`) is `pass` — it inherits everything.
- `BaseArticleView.role()` is a one-line delegate to `Article._service.role(user)`. The view should be the source of truth.
- Eliminates a whole class (`ArticleService`) and module-level registration from `app.py`.

#### Detailed Plan

##### 1. In `base.py`: Replace `BaseArticleService` with a `Protocol`

The model doesn't know about views. It knows about a class with 3 methods:

```python
class BaseArticleService(Protocol):
    @staticmethod
    def role(user: AbstractUser | None) -> Literal["editor", "author"] | None: ...

    @staticmethod
    def user_queryset() -> models.QuerySet[AbstractUser]: ...

    @classmethod
    def search_users(cls, q: str) -> models.QuerySet[AbstractUser]: ...
```

`Article._service: ClassVar[type[BaseArticleService]]` stays unchanged. `set_article_service` signature stays. Call sites (`Article._service.role(user)`, `Article._service.user_queryset()`, `Article._service.search_users(q=q)`) stay unchanged.

Move imports (`Concat`, `Value`, `Q`, `CharField`) out of the old class body — no longer needed in `base.py` since Protocol has no implementations.

##### 2. In `articles.py` (`BaseArticleView`): Add the 3 method implementations

Move default implementations from old `BaseArticleService` to `BaseArticleView` as `@staticmethod` / `@classmethod`:

```python
class BaseArticleView(ControllerBase):
    @staticmethod
    def role(user: AbstractUser | None) -> Literal["editor", "author"] | None:
        if user is None or not user.is_authenticated:
            return None
        if user.is_staff:
            return "editor"
        return None

    @staticmethod
    def user_queryset() -> models.QuerySet[AbstractUser]:
        return User.objects.annotate(
            name=Concat("first_name", Value(" "), "last_name"),
            url=Value(None, output_field=CharField()),
        )

    @classmethod
    def search_users(cls, q: str) -> models.QuerySet[AbstractUser]:
        return cls.user_queryset().filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q)
        )[:20]
```

Remove the old `def role(self, user)` delegate method that called `Article._service.role(user)`.

All existing `self.role(user)` calls within `BaseArticleView` continue to work — `@staticmethod` is callable on instances.

##### 3. In `BaseArticleView.url()`: Register the view as the service

Add `Article.set_article_service(cls)` at the start of `url()`. This replaces the module-level `Article.set_article_service(ArticleService)` in `app.py`.

Relax the "already registered" guard in `set_article_service` — change from raising `RuntimeError` to allowing re-registration (since `url()` may be called multiple times in tests or server reloads).

##### 4. In `app.py`: Delete `ArticleService` and registration

```python
# DELETE:
class ArticleService(BaseArticleService):
    pass
Article.set_article_service(ArticleService)
```

Remove `BaseArticleService` from imports. `AppArticleView(BaseArticleView): pass` stays unchanged.

##### 5. Call sites in `articles.py` — no changes needed

All three `_service` call sites continue to work because `_service` is now set to the `BaseArticleView` subclass:

| Call site | Before | After (same) |
|-----------|--------|---------------|
| `BaseArticleView.role` | `Article._service.role(user)` | Removed (method is now on `BaseArticleView`) |
| `BaseArticleView.list_page` | `Article._service.user_queryset()` | Unchanged |
| `ArticleView.search_authors` | `Article._service.search_users(q=q)` | Unchanged |
| `Article.user_profile` (model) | `Article._service.user_queryset()` | Unchanged |

##### 6. `TagView` delegation — no changes needed

`cls().role` on line 223 stores a `@staticmethod`, which is callable. `TagView._role_fn(user)` works unchanged.

##### 7. Type safety

- `Protocol` enables structural subtyping — `BaseArticleView` satisfies `type[BaseArticleService]` by having the 3 matching methods, no inheritance needed.
- `articles.py` doesn't import `BaseArticleService` at all.
- mypy verifies at `set_article_service(cls)` that `cls` matches the Protocol.

##### 8. Imports cleanup

- `base.py`: Remove `Concat`, `Value`, `Q`, `CharField` imports (no longer used — Protocol has no implementations)
- `articles.py`: Add `Concat`, `Value`, `Q`, `CharField` imports (for `user_queryset` and `search_users` implementations)
- `app.py`: Remove `BaseArticleService` import

##### 9. README update

Update the Articles section: remove `BaseArticleService` as a standalone class. Document that `BaseArticleView` provides `role`, `user_queryset`, and `search_users`, and that `AppArticleView` can override them.

#### Checklist

##### Phase A: Protocol and view methods
- [x] Replace `BaseArticleService` with `Protocol` in `models/base.py` (3 method stubs, no implementations)
- [x] Add `@staticmethod role`, `@staticmethod user_queryset`, `@classmethod search_users` to `BaseArticleView` in `views/articles.py`
- [x] Remove old `def role(self, user)` delegate from `BaseArticleView`
- [x] Add `Article.set_article_service(cls)` to `BaseArticleView.url()`
- [x] Relax `set_article_service` guard to allow re-registration
- [x] Move imports: `Concat`, `Value`, `Q`, `CharField` from `base.py` to `articles.py`

##### Phase B: Cleanup app.py
- [x] Delete `class ArticleService(BaseArticleService): pass` and `Article.set_article_service(ArticleService)`
- [x] Remove `BaseArticleService` import

##### Phase C: README
- [x] Update Articles section to reflect `BaseArticleView` as service provider

##### Phase D: Final
- [x] `./run checkall` passes

---

### Round 7: Code review findings (commit 1168fe2)

- [x] `frontend/src/pages/ArticleList.vue:121` — author multiselect `label="name"` changed to `label="title"` since `UserProfile` uses `title` not `name`
- [x] N+1 queries in `list_page` loop — `Article.user_profile()` now reads from annotated `user.name`/`user.url` directly, only falls back to DB query when annotations missing
- [x] N+1 queries in `details_page` — uses `Article.get_or_404_with_annotations()` which prefetches author with annotated queryset
- [x] N+1 queries in `edit_page` — uses `Article.get_or_404_with_annotations()` which prefetches author with annotated queryset
- [x] `NullableDateChange` at `models/base.py` — `published_date` field changed from `date_type | None` to `datetime_type | None`, snapshot now stores full `published_at` datetime
- [x] `author_id` / `UserProfile.id` type consistency — `UserProfile.id` changed from `str` to `int`:
    - [x] `UserProfile.id` — changed from `str` to `int` in `models/base.py`, `responses.py`, `schemas.ts`, `User` interface
    - [x] `ArticleEdit.vue:41` — sends `selectedAuthor.value?.id` as-is (now `int`), no conversion needed
    - [x] `ArticleList.vue:38` — `String(a.id)` still works, `a.id` is now `int`
    - [x] `ArticleHistory` author change snapshots — `AuthorChange.old.id` / `AuthorChange.new.id` now `int` via `UserProfile.id: int`
    - [x] Updated all test assertions from `str(self.user.pk)` to `self.user.pk`
- [x] Author filter state not restored from URL in `ArticleList.vue` — backend sends `selected_authors` and `selected_tags` as props, frontend initializes from them directly
