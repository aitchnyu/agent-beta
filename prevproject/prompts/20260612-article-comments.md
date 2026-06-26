## Comments

We have a 'participant' role for user for articles
Default implementation - if a user is not editor, they are participant

We will add comments to articles. They are allowed to participants, authors and editors. Its distinct from RowUpdate.
content - 1000 chars
commented_by
commented_at
deleted_by
deleted_at
updated_at 

Deleting is soft delete - it will clear content, set deleted_by and deleted_at. In frontend it will say deleted

Article has is_commenting_enabled flag, default true, we can edit it.

Permissions for comments
Create - article commenting is enabled, user is participant
Read - If they can see article, they can see comments
Update - only same person can update their comment, within 1 hour
Delete - author of article and editors can delete comments, commenter can delete their comments

In details view, have a comment fetching function that uses Inertia lazy props. Use `comments` prop key along with `props`, former being lazy loaded.

Option to sort articles by latest comment

Try to have most model wrangling logic in models, and model tests.

### Detailed Plan

#### Participant role

Update `BaseArticleService` Protocol and `BaseArticleView.role()` to return `"participant"` for any authenticated non-staff user. Currently `role()` returns `None` for non-staff [djangoapp/views/articles.py:220-225]. Change to:

```python
def role(user: AbstractUser | None) -> Literal["editor", "author", "participant"] | None:
    if user is None or not user.is_authenticated:
        return None
    if user.is_staff:
        return "editor"
    return "participant"
```

Note: `"author"` is kept in the union for Protocol compatibility but the default implementation never returns it — `"author"` is checked via `article.author_id == user.pk` (a per-article check, not a global role).

This changes `BaseArticleService` Protocol in [djangoapp/models/base.py:1604-1612], `BaseArticleView.role()` in [djangoapp/views/articles.py:220-225], and `TagView.role()` return type.

#### ArticleComment model

New model in `models/base.py` (near `ArticleHistory`):

```python
class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField(max_length=1000)
    commented_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    commented_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    deleted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
```

Soft delete: `soft_delete(user)` method clears `content`, sets `deleted_by` and `deleted_at` — same pattern as `RowUpdate.delete_comment()` [djangoapp/models/base.py:1418-1427].

Update: `update_content(new_content)` sets `content` and `updated_at`.

Model methods for permission checks:
- `can_create_comment(user)` — article `is_commenting_enabled` and user is participant (authenticated non-staff)
- `can_update_comment(user)` — same user as `commented_by`, within 1 hour of `commented_at`, not deleted
- `can_delete_comment(user, article)` — commenter can delete their own, article author can delete, editors can delete

#### is_commenting_enabled on Article

Add `is_commenting_enabled = models.BooleanField(default=True)` to Article model [djangoapp/models/base.py:1615].

Add `commenting_enabled` to `ArticleUpdateSchema` so editors can toggle it.

Add it to `ArticleDetailsItem` and `ArticleDetailsProps` so frontend knows the state.

#### Pydantic schemas

```python
class ArticleCommentItem(PydanticBaseModel):
    id: int
    content: str
    commented_by: UserProfile
    commented_at: str
    updated_at: str | None = None
    is_deleted: bool = False

class ArticleCommentsProps(PydanticBaseModel):
    comments: list[ArticleCommentItem]
    can_comment: bool = False
    can_delete_any: bool = False  # editors/article author can delete any
    user_id: int | None = None
```

#### Endpoints

| Path | Method | Purpose |
|---|---|---|
| `/api/comments/{public_id}` | GET | List comments for article (lazy prop data) |
| `/api/create-comment/{public_id}` | POST | Create comment |
| `/api/{public_id}/update-comment/{comment_id}` | POST | Update comment |
| `/api/{public_id}/delete-comment/{comment_id}` | POST | Soft delete comment |

The GET comments endpoint returns data for Inertia lazy prop loading. The details page passes a `comments_url` prop that the frontend calls to fetch comments lazily.

#### Inertia lazy props

In `details_page()` [djangoapp/views/articles.py:411-456], add a `comments_url` field to `ArticleDetailsProps` containing the API URL. The frontend fetches comments on mount using this URL. This avoids the need for server-side Inertia deferred props — simpler and consistent with how the app uses API endpoints.

Alternative: Use `inertia-django` lazy props by passing a callable. But the current codebase doesn't use that pattern, so a dedicated API endpoint + frontend fetch is more consistent.

#### Sort by latest comment

In `list_page()` [djangoapp/views/articles.py:337-409], add an optional sort parameter `sort_by` to `ArticleListFilters`. When `sort_by="latest_comment"`, annotate the queryset with `Max("comments__commented_at")` and order by that descending.

#### Frontend

- Add `ArticleCommentItemSchema`, `ArticleCommentsResponseSchema` to `schemas.ts`
- Create `ArticleCommentSection.vue` component in `frontend/src/components/` (reusing patterns from `RowUpdateComment.vue` [frontend/src/components/RowUpdateComment.vue])
- Update `ArticleDetails.vue` to include the comment section
- Add sort option in `ArticleList.vue`

### Checklist

#### Phase 1: Model — Participant role
- [x] update `BaseArticleService` Protocol return type to `Literal["editor", "author", "participant"] | None` [djangoapp/models/base.py:1606]
- [x] update `BaseArticleView.role()` to return `"participant"` for authenticated non-staff [djangoapp/views/articles.py:220-225]
- [x] update `TagView.role()` return type annotation [djangoapp/views/articles.py:637]
- [x] add `"participant"` to all `Literal["editor", "author"]` type annotations across codebase (Protocol, view, tests)

#### Phase 2: Model — ArticleComment and is_commenting_enabled
- [x] add `is_commenting_enabled = BooleanField(default=True)` to Article model [djangoapp/models/base.py:1615]
- [x] add `ArticleComment` model to `models/base.py`
    - [x] `article` FK (CASCADE, related_name="comments")
    - [x] `content` TextField (max_length=1000)
    - [x] `commented_by` FK User (SET_NULL, null=True)
    - [x] `commented_at` DateTimeField (auto_now_add)
    - [x] `deleted_by` FK User (SET_NULL, null=True, blank=True)
    - [x] `deleted_at` DateTimeField (null=True, blank=True)
    - [x] `updated_at` DateTimeField (null=True, blank=True)
    - [x] `Meta` with indexes on `article` and `commented_at`, ordering `["-commented_at"]`
- [x] add `soft_delete(user)` method to `ArticleComment`
- [x] add `update_content(new_content)` method to `ArticleComment`
- [x] add `to_comment_item()` serialization method to `ArticleComment`
- [x] add `ArticleComment` to `models/__init__.py` exports
- [x] create migration

#### Phase 3: Model tests — ArticleComment
- [x] `ArticleCommentModelTests` in `tests/test_articles.py`
    - [x] `test_create_comment` — creates comment, verifies fields
    - [x] `test_soft_delete` — clears content, sets deleted_by and deleted_at
    - [x] `test_update_content` — updates content, sets updated_at
    - [x] `test_update_content_after_one_hour_fails` — raises error after 1 hour
    - [x] `test_update_content_by_different_user_fails` — raises error for non-author
    - [x] `test_update_deleted_comment_fails` — raises error for deleted comment
    - [x] `test_can_delete_comment_by_commenter` — commenter can delete own
    - [x] `test_can_delete_comment_by_article_author` — article author can delete
    - [x] `test_can_delete_comment_by_editor` — editor can delete
    - [x] `test_cannot_delete_comment_by_random_user` — random user gets denied
    - [x] `test_cannot_create_comment_when_disabled` — is_commenting_enabled=False blocks creation

#### Phase 4: Endpoints
- [x] add `GET /api/comments/{public_id}` — returns comments list with permission flags
- [x] add `POST /api/create-comment/{public_id}` — participant creates comment
- [x] add `POST /api/{public_id}/update-comment/{comment_id}` — commenter updates within 1 hour
- [x] add `POST /api/{public_id}/delete-comment/{comment_id}` — soft delete by commenter/author/editor
- [x] add `comments_url` to `ArticleDetailsProps`
- [x] add `is_commenting_enabled` to `ArticleDetailsItem` and `ArticleEditProps`

#### Phase 5: View tests
- [x] `ArticleCommentViewTests` in `tests/views/test_articles.py`
    - [x] `test_create_comment_as_participant` — participant can create
    - [x] `test_create_comment_as_anonymous_fails` — 404
    - [x] `test_create_comment_when_disabled_fails` — 404 when is_commenting_enabled=False
    - [x] `test_list_comments_public` — anyone can read comments on published article
    - [x] `test_update_own_comment_within_one_hour` — success
    - [x] `test_update_own_comment_after_one_hour_fails` — 404
    - [x] `test_update_others_comment_fails` — 404
    - [x] `test_delete_own_comment` — commenter deletes own
    - [x] `test_delete_comment_as_article_author` — article author deletes
    - [x] `test_delete_comment_as_editor` — editor deletes
    - [x] `test_delete_comment_as_random_user_fails` — 404

#### Phase 6: Frontend
- [x] add `ArticleCommentItemSchema`, `ArticleCommentsResponseSchema` to `schemas.ts`
- [x] add `comments_url`, `is_commenting_enabled` to `ArticleDetailsPropsSchema`
- [x] create `ArticleCommentSection.vue` component
    - [x] fetches comments from `comments_url` on mount
    - [x] displays comments with commenter name, time, content
    - [x] shows "[deleted]" for soft-deleted comments
    - [x] edit button for own comments within 1 hour
    - [x] delete button for own comments
    - [x] delete button for editors/article author on any comment
    - [x] comment form at bottom (if can_comment)
- [x] update `ArticleDetails.vue` to include `ArticleCommentSection`

#### Phase 7: Sort by latest comment
- [x] add `sort_by` field to `ArticleListFilters` (default "published_at")
- [x] in `list_page()`, when `sort_by="latest_comment"`, annotate with `Max("comments__commented_at")` and order by it
- [x] add sort dropdown in `ArticleList.vue`

#### Phase 8: Playwright tests
- [x] `ArticleCommentE2eTestCase` in `tests/playwright/test_articles.py` [following pattern in `ArticleE2eTestCase` at djangoapp/tests/playwright/test_articles.py:24]
    - [x] `test_comment_form_hidden_when_commenting_disabled` — is_commenting_enabled=False hides comment form
    - [x] `test_comment_appears_after_creation` — create comment, verify it renders with content and commenter name
    - [x] `test_soft_delete_shows_deleted` — delete comment, "[deleted]" text appears, content gone
    - [x] `test_edit_own_comment_within_one_hour` — commenter edits comment, new content displays
    - [x] `test_cannot_edit_others_comment` — edit button not visible for other user's comment
    - [x] `test_editor_can_delete_any_comment` — editor sees delete button on another user's comment
    - [x] `test_article_author_can_delete_comment` — article author sees delete button on commenter's comment
    - [x] `test_sort_by_latest_comment` — articles sorted by latest comment when sort dropdown selected

#### Phase 9: Final
- [x] `./run checkall` passes

#### Phase 10: Cleanup
- [x] DRY `can_update_comment` and `update_content` — `update_content` now calls `can_update_comment` for guard logic, `update_content` accepts `user` param [djangoapp/models/base.py:2061-2071]
- [x] Rename `can_delete_comment` → `can_soft_delete_comment` to indicate soft delete [djangoapp/models/base.py:2085]

#### Phase 11: Remaining items
- [x] `djangoapp/views/articles.py:375` — sort by nulls last using `F().desc(nulls_last=True)`, removed `has_comments` annotation
- [x] `djangoapp/views/articles.py:672` — added `ArticleComment.for_article()` classmethod that returns serialized list
- [x] `djangoapp/views/articles.py:673` — `ArticleCommentItem` (active, no `is_deleted`) and `DeletedArticleCommentItem` (no `content`) as a discriminated union
- [x] `djangoapp/models/base.py:2033` — `commented_at` and `updated_at` now `datetime_type` instead of `str`
- [x] `frontend/src/components/ArticleCommentSection.vue:130` — extracted `ArticleCommentItemComponent.vue`

#### Phase 12: Remaining items
- [x] `frontend/src/components/ActiveArticleComment.vue:42` — pass `publicId` and `pathPrefix` props instead of regex-parsing `commentsUrl`

#### Phase 13: Rich text for comments
- [x] Add `sanitize_content` validator to `CommentCreateSchema` and `CommentUpdateSchema` in `djangoapp/views/articles.py`, mirroring `CommentRequest.sanitize_comment` in `djangoapp/views/base.py:404-407`
    - [x] Import `sanitize_html` from `djangoapp.utils`
- [x] Test: `test_create_comment_sanitizes_html` — unsafe tags stripped, safe preserved, in `djangoapp/tests/views/test_articles.py`
- [x] Test: `test_update_comment_sanitizes_html` — same as above for update endpoint
- [x] Replace `<textarea>` with `<RichTextEditor>` in `ArticleCommentSection.vue` create form
- [x] Replace `<textarea>` with `<RichTextEditor>` in `ActiveArticleComment.vue` edit mode
- [x] Replace plain text `{{ comment.content }}` with `<RenderRawHtml>` in `ActiveArticleComment.vue`

#### Phase 14: `is_commenting_enabled` toggle on create/edit
- [x] Add `is_commenting_enabled` to `ArticleUpdateSchema` and `ArticleCreateSchema` in `djangoapp/views/articles.py`
- [x] Add `is_commenting_enabled` param to `Article.create()` and `Article.update()` in `djangoapp/models/base.py`
- [x] Pass `is_commenting_enabled` through `create_submit` and `edit_submit`
- [x] Add "Enable comments" toggle (bootstrap switch) to `ArticleForm.vue`
- [x] Wire `isCommentingEnabled` in `ArticleCreate.vue` (default `true`) and `ArticleEdit.vue`

#### Phase 16: All users can comment
- [x] Remove `!p.is_editor` gate from `canComment` in `ArticleDetails.vue`
- [x] Remove `user_role == "participant"` check from `list_comments` `can_comment` in `djangoapp/views/articles.py`
- [x] Remove `self.role(user) != "participant"` check from `create_comment` in `djangoapp/views/articles.py`
- [x] Test: `test_create_comment_as_editor` in `djangoapp/tests/views/test_articles.py`
- [x] E2E test: `test_comment_form_visible_for_editor` in `djangoapp/tests/playwright/test_articles.py`

#### Phase 15: Reactive form object for article create/edit
- [x] Add `ArticleFormData` interface to `frontend/src/schemas.ts`
    - [x] Fields: `title`, `publicId`, `content`, `selectedTags: ArticleTagItem[]`, `isCommentingEnabled: boolean`
- [x] Update `frontend/src/components/ArticleForm.vue`
    - [x] Replace individual `v-model` props (title, publicId, content, selectedTags, isCommentingEnabled) with single `modelValue: ArticleFormData` prop + `update:modelValue` emit
    - [x] Bind fields via `v-model="modelValue.title"` etc.
- [x] Update `frontend/src/pages/ArticleCreate.vue`
    - [x] Replace individual refs with `reactive<ArticleFormData>`, default `isCommentingEnabled` to `true`
    - [x] Pass `v-model="form"`
- [x] Update `frontend/src/pages/ArticleEdit.vue`
    - [x] Replace individual refs with `reactive<ArticleFormData>` initialized from `p.article`
    - [x] Pass `v-model="form"`

## Code review of commit d5a21ed (post-implementation)

Findings from reviewing `d5a21ed` "Article comments" against the spec and AGENTS.md. Decisions recorded below.

### Decisions

- [#2 empty-after-sanitize comment bug] Accepted as-is — `sanitize_content` runs after `min_length` validation, so `<script>x</script>` can persist as `""`. No change.
- [#4 latest_comment sort includes soft-deleted comments] Accepted — a deleted comment still counts as latest activity. The sort test must assert deleted comments DO rank the article up [djangoapp/views/articles.py:388].
- [#6 `"author"` role in `Literal`] Kept as an extension point for subclasses; the dead `if user_role == "author"` branch in `_can_edit` [djangoapp/views/articles.py:307] is intentional. No change.
- [#10 `updated_at` semantics] Edits only; `soft_delete` deliberately does not set `updated_at`. No change.
- [#11 inconsistent endpoint return shapes] Accepted — create/update return `MessageResponse(id=...)`, delete returns `MessageResponse(message=...)`. Asymmetry is justified (create/update benefit from returning an id; delete does not). No change.
- [#15 user id in `commented_by`/`user_id`] Sharing the user id is acceptable. No change.

### Checklist

#### Phase 17: Review fixes
- [x] add `public_id` UUID to `ArticleComment` model [djangoapp/models/base.py:2051]
    - [x] `public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)`
    - [x] add migration (0048: add non-unique, then alter to unique, plus deleted_by RESTRICT)
    - [x] `for_article()` returns `public_id` (str) instead of `c.pk` in `ArticleCommentItem`/`DeletedArticleCommentItem` [djangoapp/models/base.py:2033,2042]
- [x] stop leaking comment PK in URLs/responses
    - [x] change `comment_id` path param to `comment_public_id` (str) in update/delete routes [djangoapp/views/articles.py:720,742]
    - [x] `MessageResponse(id=str(comment.public_id))` in `create_comment`/`update_comment` [djangoapp/views/articles.py:715,737]
    - [x] drop `ArticleCommentsResponse.user_id` leak [djangoapp/views/articles.py:236] — return server-side per-comment `can_edit`/`can_delete` flags instead
    - [x] update `frontend/src/schemas.ts` comment schemas (`id` -> `public_id: string`)
    - [x] update `ActiveArticleComment.vue` URL building to use `public_id`
- [x] gate `create_comment` on published-or-permitted articles [djangoapp/views/articles.py:710]
    - [x] if `article.published_at is None` and user is not editor and not article author -> Http404
- [x] constrain `sort_by` to `Literal["published_at", "latest_comment"] = "published_at"` [djangoapp/views/articles.py:123]
    - [x] mirror in `frontend/src/schemas.ts` `ArticleListFiltersSchema` (z.enum)
- [x] remove dead `if self.commented_at is None: return True` branch [djangoapp/models/base.py:2072]
- [x] add `check: bool = True` param to `update_content` to avoid double permission check [djangoapp/models/base.py:2082]
    - [x] view passes `check=False` after its own `can_update_comment` gate [djangoapp/views/articles.py:736]
- [x] align edit-window boundary to `<=` on both sides (frontend already `<`, backend already `<=`) [frontend/src/components/ArticleCommentSection.vue:41, djangoapp/models/base.py:2079]
- [x] change `deleted_by` FK `on_delete` to `models.RESTRICT` [djangoapp/models/base.py:2054]
    - [x] keep `commented_by` as `SET_NULL` so `[deleted]` display still works
    - [x] update migration
- [x] write missing tests [djangoapp/tests/views/test_articles.py, djangoapp/tests/test_articles.py]
    - [x] draft article `list_comments` Http404 for unauthenticated user
    - [x] `create_comment` on draft by non-permitted user -> 404 (and by author -> ok)
    - [x] `latest_comment` sort: later comment reorders articles; deleted comment still counts (accepted behavior)
    - [x] empty-after-sanitize regression guard: all-disallowed HTML currently persists as `""`
- [x] `./run checkall` passes (backend 456, playwright 164)