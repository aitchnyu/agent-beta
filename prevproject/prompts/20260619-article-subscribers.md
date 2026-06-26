# Article Subscribers

## Handwritten requirements

Have a M2M from articles to users called `subscribers`, no reverse relation.
When a user makes a comment and it's the first one for that user for that article, make them a subscriber.
In the article page, there is a `Subscribe`/`Unsubscribe` button — it makes a background call to make the change and generates a toast.

Source: `TODO.md:1-3`.

---

## Context

- `Article` (`djangoapp/models/base.py:1744`) is a plain `models.Model`, NOT a `_BaseModelMixin` subclass. Its comments live in `ArticleComment` (`djangoapp/models/base.py:2345`), not in `RowUpdate`.
- Article comments are created in the view: `create_comment` (`djangoapp/views/articles.py:684-704`) calls `ArticleComment.objects.create(...)` directly. There is no `Article.create_comment` model method today.
- The article details page is `BaseArticleView.details_page` (`djangoapp/views/articles.py:436-483`), rendered by `frontend/src/pages/ArticleDetails.vue`. Its props shape is `ArticleDetailsProps` (`djangoapp/views/articles.py:180-190`), which already carries user-relative booleans `can_edit` / `can_delete`.
- Toasts on the frontend: `showToast` / `showErrorToast` (`frontend/src/utils/sweetalert.ts`, used in `ArticleDetails.vue:9,41,44`). `ArticleCommentSection.vue` already does background `axios` calls + toasts, so the pattern is established.

## Checking the notifications prompt

Consulted `prompts/20260406-mentions-and-notifications.md` (sections "Notifications" and "Notification type changes"). Summary for this feature:

- The existing notification system is **`RowUpdateUserNotification`** (`djangoapp/models/base.py:1635-1646`): `modelname`, `row_pk`, `row_public_id`, `user`, `datetime`, `content` (a serialized `RowUpdateResponse`). It is populated only via `_BaseModelMixin._create_notifications` (`djangoapp/models/base.py:835-851`), which is fed by `notify_users` and the `RowUpdate` audit trail.
- A `notification_count` is injected into Inertia shared props by `djangoapp/middleware.py:19-20` (`RowUpdateUserNotification.objects.filter(user=request.user).count()`).
- **Articles are not part of this system.** `Article` is not a `_BaseModelMixin`, article comments are not `RowUpdate`s, and articles are not registered in the `modelname → viewname` map that the notifications page uses. So a subscriber cannot be notified "for free" by the current infra.

Consequence: the three handwritten requirements (M2M, auto-subscribe on first comment, subscribe button) are self-contained and do **not** depend on the notification system. Notifying subscribers on later article events (new comment, article edited) is a separate follow-up — see "Notifications follow-up (decision)" below. This plan does not build it.

---

## Detailed Plan

### 1. Model — `Article.subscribers` M2M

- Add to `Article` (`djangoapp/models/base.py:1755`, alongside the existing `tags` M2M):
  ```python
  subscribers = models.ManyToManyField(User, related_name="+", blank=True)
  ```
  - `related_name="+"` → **no reverse relation** from `User` back to articles, per the requirement. Queries for "articles a user subscribes to" go through `Article.objects.filter(subscribers=user)`.
  - No `through` model needed; the default auto-created m2m table is fine.
- Migration: `djangoapp/migrations/0003_article_subscribers.py` (`./run python manage.py makemigrations`). Empty data is fine (no existing subscribers to preserve).

### 2. Auto-subscribe on first comment

In `BaseArticleView.create_comment` (`djangoapp/views/articles.py:684-704`):

- Before creating the comment, check whether this is the user's first comment on the article:
  ```python
  is_first_comment = not ArticleComment.objects.filter(
      article=article, commented_by_id=user.pk
  ).exists()
  ```
- After the existing `ArticleComment.objects.create(...)` succeeds, if `is_first_comment`, call `article.subscribers.add(user)`.
- "First comment for user for article" = no prior `ArticleComment` by that user on that article. Because the check runs **before** creation:
  - 1st comment → subscribe. ✓
  - 2nd+ comment → no subscribe, even after the user has unsubscribed. ✓ (matches "first one for user for article")
- Edge case: a soft-deleted comment (`deleted_at` set) still counts, because the existence query does not exclude soft-deleted rows. This is intended — "has ever commented" is the semantic.
- The permission gating already present (commenting disabled → 404; draft article + non-author/editor → 404) stays before the subscribe logic, so only an allowed comment triggers a subscription.

Rationale for putting the logic in the view rather than a new model method: comment creation already lives in the view (`ArticleComment.objects.create(...)`), and the auto-subscribe is a side effect of that specific flow. Adding it next to the existing create call keeps the change minimal. (A future `Article.create_comment` model method, mentioned as a review item in the notifications prompt, would simply move both the create and the subscribe in together.)

### 3. Server-side subscription state on the details page

- Add `is_subscribed: bool = False` to `ArticleDetailsProps` (`djangoapp/views/articles.py:180-190`). It is user-relative, so it belongs on the props (like `can_edit`), not on `ArticleDetailsItem`.
- In `details_page` (`djangoapp/views/articles.py:436-483`), compute it for authenticated users only:
  ```python
  is_subscribed = bool(
      user is not None and article.subscribers.filter(pk=user.pk).exists()
  )
  ```
  Pass `is_subscribed=is_subscribed` into the props. Anonymous → `False` (and the button is hidden client-side anyway).
- No prefetch of the full subscriber set — only an existence check, so no N+1 / large-set concerns.

### 4. Subscribe / Unsubscribe API

Two idempotent POST endpoints on `BaseArticleView` (`djangoapp/views/articles.py`), consistent with the existing `/api/create-comment/{public_id}` style:

- `POST /api/subscribe/{public_id}` → `MessageResponse(id=public_id)`
- `POST /api/unsubscribe/{public_id}` → `MessageResponse(id=public_id)`

Both:
- `user = _user_or_404(request)` (anonymous → 404).
- `article = Article.get_or_404(public_id)`.
- Visibility gate mirroring `details_page`: if `article.published_at is None and self.role(user) is None: raise Http404` (drafts only visible to editor/author, who are the only ones who could subscribe).
- Subscribe: `article.subscribers.add(user)`. Unsubscribe: `article.subscribers.remove(user)`. Both are no-ops if already in the desired state (idempotent, safe on double-click).

Two endpoints (rather than one toggle) so the action is explicit and idempotent; the frontend sends whichever matches the current displayed state.

### 5. Frontend — schema + button

`frontend/src/schemas.ts`:
- Add `is_subscribed: z.boolean().optional().default(false)` to `ArticleDetailsPropsSchema` (`frontend/src/schemas.ts:715-726`).

`frontend/src/pages/ArticleDetails.vue`:
- Add a local reactive mirror of the prop: `const subscribed = ref(p.is_subscribed)` (props are readonly, so mutate the local ref).
- Render a button near the header action area (next to the Edit/Delete block, `ArticleDetails.vue:82-104`), shown only when `p.user !== null`:
  - Label: `subscribed.value ? "Unsubscribe" : "Subscribe"`.
  - Class: a distinct class on the button (e.g. `btn-subscribe`) for stable Playwright selectors, mirroring how other article buttons are structured.
- Click handler:
  ```ts
  async function toggleSubscription() {
    const wasSubscribed = subscribed.value
    const endpoint = wasSubscribed ? "unsubscribe" : "subscribe"
    subscribed.value = !wasSubscribed            // optimistic
    try {
      await axios.post(`${pathPrefix}/api/${endpoint}/${p.article.public_id}`)
      showToast("success", wasSubscribed ? "Unsubscribed" : "Subscribed")
    } catch (e) {
      subscribed.value = wasSubscribed            // revert on failure
      showErrorToast(e, "Failed to update subscription")
    }
  }
  ```
  - Disabled while in-flight (track a `subscribing` ref) to avoid duplicate rapid calls.

### 6. No changes needed elsewhere

- `ArticleCommentSection.vue` is unaffected — subscription state is independent of the comment list, and auto-subscribe happens server-side during comment creation (no client involvement).
- List page, edit/create pages, history page: no subscriber UI in this scope.

---

## Notify subscribers on new comment (new requirement)

**Handwritten requirement:** When we create a comment, we send a notification with content to the other subscribers.

**Decision: dedicated `ArticleNotification` model** (option A), merged into the existing `/notifications` inbox and the shared `notification_count`. Chosen over reusing `RowUpdateUserNotification` (option B) because that table is coupled to the `RowUpdate` audit trail, the `TABLES_MODELS_TO_VIEWS` `modelname → viewname` map, and the `{viewname}/row-details/{row_pk}` link scheme — none of which articles fit (they live at `/articles/id/{public_id}` and their comments are `ArticleComment`, not `RowUpdate`). A dedicated model keeps article events self-contained while still surfacing in the one inbox users already have.

- (A) **Chosen** — new `ArticleNotification` model; integrate into `_notifications_page`, the count middleware, and the delete/clear endpoints.
- (B) Reuse `RowUpdateUserNotification` with `modelname="article"`, `row_public_id=article.public_id`, and an article-shaped `content`. Reuses count/delete/clear for free but leaks article events into a `RowUpdate`-named table and still needs a frontend link/render branch. Lower effort, less clean.

### Detailed plan

#### 1. Model — `ArticleNotification` (`djangoapp/models/base.py`, after `RowUpdateUserNotification:1635`)

Mirror the `RowUpdateUserNotification` shape, article-flavoured:

```python
class ArticleNotification(models.Model):
    article_public_id = models.CharField(max_length=255)
    comment_public_id = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    datetime = models.DateTimeField(auto_now_add=True)
    content = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["user", "-id"])]
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(fields=["comment_public_id", "user"], name="uniq_article_notif_per_comment_user"),
        ]
```

- `UniqueConstraint(comment_public_id, user)` makes notification creation idempotent (safe under retries/double-submit).
- Migration `0004_article_notification`.

Content payload (built once per comment) — keeps the inbox renderable without extra queries:

```python
{
  "action": "commented",
  "article": {"public_id": "...", "title": "..."},
  "comment": {"public_id": "...", "content": "<sanitized html>"},
  "commenter": {"id": "<public id>", "title": "<display name>"},
}
```

Builder: `Article.comment_notification_content(comment, actor) -> dict` (parallel to `_build_row_update_response`), using `Article.user_profile(actor)` for the commenter.

#### 2. Trigger — `create_comment` (`djangoapp/views/articles.py:687-709`)

After the comment is created (and the first-comment auto-subscribe), notify the **other** subscribers (everyone except the commenter):

```python
recipients = list(article.subscribers.exclude(pk=user.pk))
if recipients:
    content = Article.comment_notification_content(comment, user)
    ArticleNotification.objects.bulk_create(
        [
            ArticleNotification(
                article_public_id=article.public_id,
                comment_public_id=str(comment.public_id),
                user=r,
                content=content,
            )
            for r in recipients
        ],
        ignore_conflicts=True,
    )
```

- Only published articles reach here (`create_comment` already calls `_published_or_404`).
- Actor (the commenter) is excluded — matches the `RowUpdate` "no self-notification" rule (`_create_notifications` filters out `context.user`).
- `ignore_conflicts=True` + the unique constraint guard against duplicate notifications if `create_comment` ever runs twice for the same comment.

#### 3. Scope (revised)

**Only create `ArticleNotification` rows on comment. Do NOT surface them anywhere** — no changes to the count middleware, the `/notifications` page, the delete/clear endpoints, or any frontend. They are tested only for being created (recipients, actor exclusion, idempotency). Presenting them in the inbox is deferred (the integration sketch below is kept as a reference for later, not implemented now).

<details>
<summary>Deferred: inbox integration sketch (not implemented)</summary>

- Count middleware (`djangoapp/middleware.py:19-20`): `count = RowUpdateUserNotification.filter(user).count() + ArticleNotification.filter(user).count()`.
- `_notifications_page` (`djangoapp/views/base.py:123-184`): merge `ArticleNotification` (sort by datetime, paginate); add an `"articles"` viewname bucket.
- `NotificationItem` (`djangoapp/responses.py:55-59`): add `kind: Literal["row","article"] = "row"` + optional `article: dict | None`.
- Delete/clear (`djangoapp/views/base.py:98-120`): carry `kind` per id (ids collide across the two tables); `viewname == "articles"` clears `ArticleNotification`.
- `Notifications.vue`: branch on `kind === "article"` — commenter + snippet, link to `/articles/id/{public_id}`.

</details>

### Checklist — Phase 9: notify subscribers on comment

- [x] add `ArticleNotification` model in [djangoapp/models/base.py] (after `RowUpdateUserNotification`) with `UniqueConstraint(comment_public_id, user)` + index
- [x] add `Article.comment_notification_content(article, comment, actor) -> dict` builder
- [x] create migration `0004_article_notification`
- [x] in `create_comment` [djangoapp/views/articles.py], after comment create, `bulk_create` `ArticleNotification` for `article.subscribers.exclude(pk=user.pk)` with `ignore_conflicts=True`
- [x] backend tests: comment notifies other subscribers; commenter & non-subscribers get none; idempotent on repeat; content payload correct
- [x] `./run checkall` passes

---

## Checklist

### Phase 1: Model + migration

- [x] add `subscribers = models.ManyToManyField(User, related_name="+", blank=True)` to `Article` in [djangoapp/models/base.py:1755]
- [x] create migration `0003_article_subscribers` via `./run python manage.py makemigrations`
- [x] `./run typecheck` passes

### Phase 2: Auto-subscribe on first comment

- [x] in `create_comment` [djangoapp/views/articles.py:684-704]
    - [x] compute `is_first_comment` via existence check on `ArticleComment` (article + `commented_by_id`) **before** creating the comment
    - [x] after `ArticleComment.objects.create(...)` succeeds, `article.subscribers.add(user)` when `is_first_comment`
- [x] `./run typecheck` passes

### Phase 3: Details page subscription state

- [x] add `is_subscribed: bool = False` to `ArticleDetailsProps` in [djangoapp/views/articles.py:180-190]
- [x] compute `is_subscribed` (existence check, authenticated users only) in `details_page` [djangoapp/views/articles.py:436-483]
- [x] pass `is_subscribed=...` into the `ArticleDetailsProps(...)` call [djangoapp/views/articles.py:468-479]

### Phase 4: Subscribe / Unsubscribe API

- [x] add `POST /api/subscribe/{public_id}` in [djangoapp/views/articles.py] → `MessageResponse`; anon 404, draft visibility gate, `article.subscribers.add(user)`
- [x] add `POST /api/unsubscribe/{public_id}` in [djangoapp/views/articles.py] → `MessageResponse`; anon 404, draft visibility gate, `article.subscribers.remove(user)`

### Phase 5: Frontend

- [x] add `is_subscribed` to `ArticleDetailsPropsSchema` in [frontend/src/schemas.ts:715-726]
- [x] add Subscribe/Unsubscribe button + `toggleSubscription()` handler in [frontend/src/pages/ArticleDetails.vue]
    - [x] local `subscribed` ref initialized from `p.is_subscribed`
    - [x] optimistic toggle, `showToast` on success, revert + `showErrorToast` on failure
    - [x] stable button class for Playwright selectors
    - [x] hidden when `p.user === null`
- [x] `cd frontend && npm run lint:fix && npm run type-check && npm run lint` passes

### Phase 6: Backend tests

- [x] extend `ArticleModelTests` / add `ArticleSubscriberModelTests` in [djangoapp/tests/test_articles.py]
    - [x] `test_subscribers_add_remove` — add/remove round-trips
    - [x] `test_subscribers_no_reverse_relation` — `User` has no `article_set` reverse manager (confirms `related_name="+"`)
- [x] extend `ArticleCommentViewTests` in [djangoapp/tests/views/test_articles.py]
    - [x] `test_first_comment_subscribes_user` — first comment adds the commenter to `article.subscribers`
    - [x] `test_second_comment_does_not_resubscribe` — second comment leaves subscription state unchanged
    - [x] `test_comment_after_unsubscribe_does_not_resubscribe` — unsubscribed user commenting again is not re-subscribed
    - [x] `test_soft_deleted_first_comment_still_counts` — user with a soft-deleted comment is not re-subscribed on next comment
    - [x] `test_subscribe_endpoint_subscribes` — `POST /api/subscribe/{public_id}` adds the user; idempotent on repeat
    - [x] `test_unsubscribe_endpoint_unsubscribes` — `POST /api/unsubscribe/{public_id}` removes the user; idempotent on repeat
    - [x] `test_subscribe_anon_404` — anonymous → 404
    - [x] `test_subscribe_draft_participant_ok` — participant CAN subscribe to a draft (mirrors `details_page` visibility); author can too
- [x] extend `ArticleDetailsTests` in [djangoapp/tests/views/test_articles.py]
    - [x] `test_details_is_subscribed_true` — subscribed user sees `is_subscribed` true in Inertia props
    - [x] `test_details_is_subscribed_false` — unsubscribed user sees false

### Phase 7: Playwright tests

- [x] add `ArticleSubscriberE2eTestCase` in [djangoapp/tests/playwright/test_articles.py]
    - [x] `test_subscribe_button_toggles` — button toggles label Subscribe → Unsubscribe after click, toast appears
    - [x] `test_subscribe_persists_after_reload` — reload after subscribe shows the Unsubscribe state (persisted)
    - [x] `test_unsubscribe_via_button` — clicking Unsubscribe flips back and persists
    - [x] `test_first_comment_auto_subscribes` — first comment flips the button to Unsubscribe on reload (auto-subscribe)

### Phase 8: Final

- [x] `./run checkall` passes (ruff, mypy, 525 backend tests, frontend lint/type-check, 173 playwright tests)

---

## Progress

Implemented in full per plan. Backend: `Article.subscribers = ManyToManyField(User, related_name="+", blank=True)` (`djangoapp/models/base.py`) + migration `0003_article_subscribers`. Auto-subscribe on first comment added to `BaseArticleView.create_comment` (`djangoapp/views/articles.py`): existence-checks the user's prior comments on the article *before* creating, then `article.subscribers.add(user)` only on the first. `is_subscribed` added to `ArticleDetailsProps` and computed in `details_page` via an existence check (authenticated users only). Two idempotent endpoints `POST /api/subscribe/{public_id}` and `POST /api/unsubscribe/{public_id}`, gated by `_subscribeable_or_404`.

Frontend: `is_subscribed` added to `ArticleDetailsPropsSchema`; `ArticleDetails.vue` renders a `.btn-subscribe` button (Subscribe/Unsubscribe) for logged-in users, optimistically toggling a local `subscribed` ref, toasting on success, reverting + error toast on failure.

Deviation from plan: the plan's "draft visibility" gate text said drafts visible only to editor/author, but the existing `details_page` shows drafts to any authenticated user (`if article.published_at is None and self.role(user) is None`). To keep subscribe consistent with where the button appears, `_subscribeable_or_404` mirrors `details_page` exactly — so any authenticated user can subscribe (draft or not). The corresponding view test asserts a participant CAN subscribe to a draft rather than 404.

Test note: the Inertia page JSON nests component props under `props.props` (shared props like `notification_count` are siblings), so `test_details_is_subscribed_*` reads `json.loads(response.content)["props"]["props"]["is_subscribed"]`. The no-reverse-relation assertion is behavioral (`hasattr(user, "article_set") is False`) rather than introspecting `Article._meta`, to avoid an SLF001 lint on `_meta`.

`./run checkall` green: ruff + mypy clean, 525 backend tests pass, frontend lint/type-check clean, 173 playwright tests pass.

## Draft permission tightening (follow-up)

Requirements added after initial implementation: drafts cannot be subscribed to or commented on, and only editors and the article's author may view a draft.

- `_viewable_or_404(user, article)` now returns early for published articles; for drafts it 404s unless the user is an editor (`role == "editor"`) or the article's author (`article.author_id == user.pk`). Used by `details_page` and `list_comments`.
- `_published_or_404(article)` added: 404s on any draft. Used by `create_comment`, `subscribe`, `unsubscribe`, and (for consistency) `update_comment` and `delete_comment`.
- `create_comment`: removed the old editor/author draft allowance — all draft comments now 404.
- `update_comment` / `delete_comment`: gated by `_published_or_404` so no comment mutations are possible on a draft. Note: this is stricter than `list_comments` (which uses `_viewable_or_404`, so editors/authors can still *view* a draft's comments) — an editor viewing a draft's comments cannot edit or delete them. Accepted asymmetry: commenting is fully disabled on drafts.
- `list_comments`: gated by `_viewable_or_404`; `can_comment` is false on drafts.
- Frontend `ArticleDetails.vue`: subscribe button hidden on drafts (`v-if` requires `p.article.published_at`); comment form hidden on drafts (`canComment` requires published).
- README "Permissions" table rewritten with a `participant` column; documents that drafts are viewable only by editors/authors and that commenting/subscribing are disabled on drafts.
- Tests updated: `test_create_comment_on_draft_by_author_fails` (404), `test_subscribe_draft_participant_fails` / `test_subscribe_draft_author_fails` (404), added `test_list_comments_draft_participant_fails`, `test_details_draft_hidden_from_participant`, `test_details_draft_visible_to_author`, `test_update_comment_on_draft_fails`, `test_delete_comment_after_article_unpublished_fails`. `./run checkall` green.
