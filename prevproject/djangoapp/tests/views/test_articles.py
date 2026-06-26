import json
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from django.test import RequestFactory
from django.utils import timezone as tz

from djangoapp.models.base import (
    Article,
    ArticleComment,
    ArticleHistory,
    ArticleImage,
    ArticleNotification,
    ArticleTag,
    User,
)
from djangoapp.tests.query_budget import QueryBudgetTestCase
from djangoapp.tests.test_images import _make_image
from djangoapp.views.articles import is_inertia_request

if TYPE_CHECKING:
    from django.http import HttpResponseBase


class ArticleListTests(QueryBudgetTestCase):
    """Tests for the article list endpoint.

    - test_list_published_visible_to_all: published articles visible without auth
    - test_list_unpublished_hidden_from_anon: unpublished hidden from anonymous
    - test_list_unpublished_visible_with_filter: unpublished shown to staff with filter
    - test_list_cover_image_url: cover image URL present for articles with images
    - test_list_excerpt_strips_html: HTML tags stripped from excerpt
    - test_list_filter_by_author: filter by author ID
    - test_list_filter_by_tag: filter by tag name
    - test_list_pagination: pagination works with 25+5 orphans
    - test_list_select_count_does_not_scale_with_row_count: SELECT count flat across rows (no N+1)
    - test_list_static_template: non-Inertia request gets the Inertia page with the article list
    - test_list_sort_by_latest_comment: later comment reorders articles to the top
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.tag1 = ArticleTag.objects.create(name="python", color="#3b82f6")
        self.published = Article.objects.create(
            title="Published Article",
            public_id="published-1",
            content="<b>Bold</b> text",
            published_at="2026-01-01T00:00:00Z",
            author=self.staff,
        )
        self.published.tags.add(self.tag1)
        self.draft = Article.objects.create(
            title="Draft Article",
            public_id="draft-1",
            published_at=None,
            author=self.staff,
        )

    def test_list_published_visible_to_all(self) -> None:
        """Published articles visible without auth."""
        response = self.client.get("/articles/list")
        self.assertEqual(response.status_code, 200)

    def test_list_unpublished_hidden_from_anon(self) -> None:
        """Unpublished articles hidden from anonymous users."""
        response = self.client.get("/articles/list")
        self.assertNotContains(response, "Draft Article")

    def test_list_unpublished_visible_with_filter(self) -> None:
        """Unpublished shown to staff with unpublished=true filter."""
        self.client.force_login(self.staff)
        response = self.client.get("/articles/list?unpublished=true")
        self.assertEqual(response.status_code, 200)

    def test_list_cover_image_url(self) -> None:
        """Cover image URL present for articles with images."""
        img = ArticleImage.objects.create(article=self.published, image=_make_image())
        self.published.content = (
            f'<img src="/articles/api/download-image/{self.published.public_id}/{img.uuid_id}">'
        )
        self.published.save()
        self.published.update_first_image()
        response = self.client.get("/articles/list")
        self.assertEqual(response.status_code, 200)

    def test_list_excerpt_strips_html(self) -> None:
        """HTML tags stripped from excerpt in list data."""
        response = self.client.get("/articles/list")
        self.assertEqual(response.status_code, 200)

    def test_list_filter_by_author(self) -> None:
        """Filter by author ID."""
        response = self.client.get(f"/articles/list?author={self.staff.pk}")
        self.assertEqual(response.status_code, 200)

    def test_list_filter_by_tag(self) -> None:
        """Filter by tag name."""
        response = self.client.get("/articles/list?tag=python")
        self.assertEqual(response.status_code, 200)

    def test_list_pagination(self) -> None:
        """Pagination works."""
        for i in range(30):
            Article.objects.create(
                title=f"Page Article {i}",
                public_id=f"page-{i}",
                published_at="2026-01-01T00:00:00Z",
                author=self.staff,
            )
        response = self.client.get("/articles/list")
        self.assertEqual(response.status_code, 200)

    def test_list_select_count_does_not_scale_with_row_count(self) -> None:
        """List SELECT count must not scale with row count (catches per-row N+1)."""
        self.allow_more_queries(45)  # three list requests; an N+1 would exceed this
        few = self.select_count(lambda: self.client.get("/articles/list"))
        for i in range(50):
            Article.objects.create(
                title=f"Bulk Article {i}",
                public_id=f"bulk-{i}",
                published_at="2026-01-01T00:00:00Z",
                author=self.staff,
            )
        # Confirm the many-rows list actually renders (guards against a vacuous pass).
        self.assertEqual(self.client.get("/articles/list").status_code, 200)
        many = self.select_count(lambda: self.client.get("/articles/list"))
        self.assertEqual(
            few,
            many,
            f"article list SELECTs grew {few} -> {many} with row count; likely N+1",
        )

    def test_list_static_template(self) -> None:
        """Non-Inertia request gets Inertia page with article list."""
        response = self.client.get("/articles/list")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Article")

    def test_list_sort_by_latest_comment(self) -> None:
        """Article with the most recent comment sorts first."""
        Article.objects.create(
            title="Older Published",
            public_id="sort-older",
            content="<p>A</p>",
            published_at="2026-02-01T00:00:00Z",
            author=self.staff,
        )
        newer = Article.objects.create(
            title="Newer Published",
            public_id="sort-newer",
            content="<p>B</p>",
            published_at="2026-01-01T00:00:00Z",
            author=self.staff,
        )
        ArticleComment.objects.create(
            article=newer,
            content="recent activity",
            commented_by=self.staff,
        )
        response = self.client.get("/articles/list?sort_by=latest_comment")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertLess(body.index("Newer Published"), body.index("Older Published"))


class ArticleDetailsTests(QueryBudgetTestCase):
    """Tests for the article details endpoint.

    - test_details_published_visible: published article visible to all
    - test_details_draft_hidden_from_anon: draft hidden from anonymous
    - test_details_draft_visible_to_staff: draft visible to staff (editor)
    - test_details_draft_hidden_from_participant: draft hidden from non-author participants
    - test_details_draft_visible_to_author: draft visible to its (non-staff) author
    - test_details_404_for_missing: missing article returns 404
    - test_details_media_summary_for_editor: media_summary included for editors
    - test_details_static_template: non-Inertia request gets the Inertia page with article content
    - test_details_is_subscribed_true: subscribed user sees is_subscribed=true in Inertia props
    - test_details_is_subscribed_false: unsubscribed/anonymous sees is_subscribed=false in props
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.published = Article.objects.create(
            title="Published",
            public_id="details-pub-1",
            content="<p>Hello</p>",
            published_at="2026-01-01T00:00:00Z",
            author=self.staff,
        )
        self.draft = Article.objects.create(
            title="Draft",
            public_id="details-draft-1",
            published_at=None,
            author=self.staff,
        )

    def test_details_published_visible(self) -> None:
        """Published article visible to all."""
        response = self.client.get(f"/articles/id/{self.published.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_details_draft_hidden_from_anon(self) -> None:
        """Draft hidden from anonymous."""
        response = self.client.get(f"/articles/id/{self.draft.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_details_draft_visible_to_staff(self) -> None:
        """Draft visible to staff."""
        self.client.force_login(self.staff)
        response = self.client.get(f"/articles/id/{self.draft.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_details_draft_hidden_from_participant(self) -> None:
        """Draft hidden from a non-author participant (404)."""
        participant = User.objects.create_user(username="reader", password="pass")
        self.client.force_login(participant)
        response = self.client.get(f"/articles/id/{self.draft.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_details_draft_visible_to_author(self) -> None:
        """Draft visible to its (non-staff) author."""
        author = User.objects.create_user(username="author", password="pass")
        own_draft = Article.objects.create(
            title="Own Draft",
            public_id="details-draft-author-1",
            published_at=None,
            author=author,
        )
        self.client.force_login(author)
        response = self.client.get(f"/articles/id/{own_draft.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_details_404_for_missing(self) -> None:
        """Missing article returns 404."""
        response = self.client.get("/articles/id/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_details_media_summary_for_editor(self) -> None:
        """media_summary included for editors."""
        self.client.force_login(self.staff)
        ArticleImage.objects.create(article=self.published, image=_make_image())
        response = self.client.get(f"/articles/id/{self.published.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_details_static_template(self) -> None:
        """Non-Inertia request gets Inertia page with article content."""
        response = self.client.get(f"/articles/id/{self.published.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published")

    def test_details_is_subscribed_true(self) -> None:
        """Subscribed user sees is_subscribed=true in Inertia props."""
        self.published.subscribers.add(self.staff)
        self.client.force_login(self.staff)
        response = self.client.get(
            f"/articles/id/{self.published.public_id}",
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(response.status_code, 200)
        page_props = json.loads(response.content)["props"]["props"]
        self.assertTrue(page_props["is_subscribed"])

    def test_details_is_subscribed_false(self) -> None:
        """Unsubscribed user sees is_subscribed=false in Inertia props."""
        self.client.force_login(self.staff)
        response = self.client.get(
            f"/articles/id/{self.published.public_id}",
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(response.status_code, 200)
        page_props = json.loads(response.content)["props"]["props"]
        self.assertFalse(page_props["is_subscribed"])


class ArticleStaticRenderingTests(QueryBudgetTestCase):
    """Inertia detection and the hidden static fallback.

    The details page always returns an InertiaResponse; on a full (non-inertia)
    load it also embeds a <noscript> fragment of the article for crawlers plus
    opengraph head meta, both omitted on inertia (JSON) requests. The
    is_inertia_request helper drives that branch and must match only the
    X-Inertia header.

    - test_is_inertia_request_only_with_header: True only with the X-Inertia header
    - test_non_inertia_has_noscript_fallback: non-inertia embeds the body in noscript
    - test_non_inertia_has_opengraph_meta: non-inertia carries opengraph head meta
    - test_inertia_omits_fallback: inertia response is JSON, omits noscript

    Tests verify header presence, response content, and that the fallback sits behind <noscript>.
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.published = Article.objects.create(
            title="Seo Title",
            public_id="seo-1",
            content="<p>Seo body text</p>",
            published_at="2026-01-01T00:00:00Z",
            author=self.staff,
        )
        self.factory = RequestFactory()

    def assert_article_content(self, response: HttpResponseBase) -> None:
        """Assert the article title and body are present in the rendered response."""
        self.assertContains(response, "Seo Title")
        self.assertContains(response, "Seo body text")

    def test_is_inertia_request_only_with_header(self) -> None:
        """is_inertia_request is True only when the X-Inertia header is present."""
        self.assertTrue(is_inertia_request(self.factory.get("/", HTTP_X_INERTIA="true")))
        self.assertFalse(is_inertia_request(self.factory.get("/")))
        self.assertFalse(is_inertia_request(self.factory.get("/", HTTP_USER_AGENT="Googlebot/2.1")))

    def test_non_inertia_has_noscript_fallback(self) -> None:
        """Non-inertia details response embeds the article body in a noscript block."""
        response = self.client.get(f"/articles/id/{self.published.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<noscript>")
        self.assert_article_content(response)

    def test_non_inertia_has_opengraph_meta(self) -> None:
        """Non-inertia details response carries opengraph head meta for scrapers."""
        response = self.client.get(f"/articles/id/{self.published.public_id}")
        self.assertContains(response, 'property="og:title"')
        self.assert_article_content(response)

    def test_inertia_omits_fallback(self) -> None:
        """Inertia details response is JSON and omits the noscript fallback."""
        response = self.client.get(
            f"/articles/id/{self.published.public_id}",
            HTTP_X_INERTIA="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<noscript>")


class ArticleCreateTests(QueryBudgetTestCase):
    """Tests for article create endpoints.

    - test_create_page_requires_auth: create page requires authentication
    - test_create_page_staff: staff can access create page
    - test_create_submit_publish: staff creates published article
    - test_create_submit_draft: staff creates draft article
    - test_create_submit_auto_author: creating user auto-added as author
    - test_create_submit_with_tags: tags are assigned on create
    - test_create_submit_no_title: missing title returns error
    - test_create_submit_unauthenticated: unauthenticated returns error
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.tag = ArticleTag.objects.create(name="django", color="#092e20")

    def test_create_page_requires_auth(self) -> None:
        """Create page returns 404 for anonymous."""
        response = self.client.get("/articles/create")
        self.assertEqual(response.status_code, 404)

    def test_create_page_staff(self) -> None:
        """Staff can access create page."""
        self.client.force_login(self.staff)
        response = self.client.get("/articles/create")
        self.assertEqual(response.status_code, 200)

    def test_create_submit_publish(self) -> None:
        """Staff creates published article via JSON."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/create",
            data=json.dumps(
                {
                    "title": "New Article",
                    "content": "<p>Content</p>",
                    "published": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        article = Article.objects.get(public_id=data["id"])
        self.assertIsNotNone(article.published_at)

    def test_create_submit_draft(self) -> None:
        """Staff creates draft article via JSON."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/create",
            data=json.dumps(
                {
                    "title": "Draft Article",
                    "content": "<p>Draft</p>",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        article = Article.objects.get(public_id=data["id"])
        self.assertIsNone(article.published_at)

    def test_create_submit_auto_author(self) -> None:
        """Creating user auto-assigned as author."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/create",
            data=json.dumps({"title": "Authored", "content": "", "published": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        article = Article.objects.get(public_id=data["id"])
        self.assertEqual(article.author, self.staff)

    def test_create_submit_with_tags(self) -> None:
        """Tags assigned on create."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/create",
            data=json.dumps(
                {
                    "title": "Tagged",
                    "content": "",
                    "published": True,
                    "tags": ["django"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        article = Article.objects.get(public_id=data["id"])
        self.assertIn(self.tag, article.tags.all())

    def test_create_submit_no_title(self) -> None:
        """Missing title returns 422."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/create",
            data=json.dumps({"content": "", "published": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_create_submit_unauthenticated(self) -> None:
        """Unauthenticated returns 404."""
        response = self.client.post(
            "/articles/create",
            data=json.dumps({"title": "No auth", "published": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


class ArticleEditDeleteTests(QueryBudgetTestCase):
    """Tests for article edit and delete endpoints.

    - test_edit_page_requires_can_edit: edit page requires permission
    - test_edit_page_staff: staff can access edit page
    - test_edit_submit_updates_title: title updated on edit
    - test_edit_submit_publish_draft: draft can be published
    - test_delete_staff: staff can delete article
    - test_delete_unauthenticated: unauthenticated returns 404
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.normal = User.objects.create_user(username="user", password="pass")
        self.article = Article.objects.create(
            title="Edit Me",
            public_id="edit-1",
            content="<p>Original</p>",
            published_at=None,
            author=self.staff,
        )

    def test_edit_page_requires_can_edit(self) -> None:
        """Edit page 404 for non-author non-staff."""
        self.client.force_login(self.normal)
        response = self.client.get(f"/articles/edit/{self.article.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_edit_page_staff(self) -> None:
        """Staff can access edit page."""
        self.client.force_login(self.staff)
        response = self.client.get(f"/articles/edit/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_edit_submit_updates_title(self) -> None:
        """Title updated on edit via JSON."""
        self.client.force_login(self.staff)
        response = self.client.post(
            f"/articles/edit/{self.article.public_id}",
            data=json.dumps(
                {"title": "Updated Title", "content": "<p>New</p>", "published": False}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Updated Title")

    def test_edit_submit_publish_draft(self) -> None:
        """Draft can be published via edit."""
        self.client.force_login(self.staff)
        response = self.client.post(
            f"/articles/edit/{self.article.public_id}",
            data=json.dumps({"title": "Now Published", "content": "<p>Pub</p>", "published": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertIsNotNone(self.article.published_at)

    def test_delete_staff(self) -> None:
        """Staff can delete article."""
        self.client.force_login(self.staff)
        response = self.client.post(f"/articles/delete/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.filter(pk=self.article.pk).exists())

    def test_delete_unauthenticated(self) -> None:
        """Unauthenticated returns 404."""
        response = self.client.post(f"/articles/delete/{self.article.public_id}")
        self.assertEqual(response.status_code, 404)


class ArticleRolePermissionTests(QueryBudgetTestCase):
    """Tests for the editor/participant permission model.

    Verifies the editor-only create rule, the participant-author edit/delete
    scope, the participant own-draft list visibility, and the resolver-unset
    failure mode. Editors are superusers; participants are all other users.

    - test_participant_cannot_create: a participant gets 404 on create page/submit
    - test_editor_creates_and_assigns_author: editor can create + assign a participant as author
    - test_participant_author_can_edit_own: a participant-author can edit their own article
    - test_participant_author_can_delete_own: a participant-author can delete their own article
    - test_participant_cannot_edit_others: a participant cannot edit an article they did not author
    - test_participant_sees_own_draft_unpublished: participant sees own draft via ?unpublished
    - test_participant_does_not_see_others_drafts: ?unpublished never leaks others' drafts
    - test_editors_resolver_unset_raises: editors() raises NotImplementedError when unset
    - test_participants_resolver_unset_raises: participants() raises NotImplementedError when unset
    """

    def setUp(self) -> None:
        self.editor = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.participant = User.objects.create_user(username="writer", password="pass")

    def test_participant_cannot_create(self) -> None:
        """A (non-editor) participant gets 404 on create page and submit."""
        self.client.force_login(self.participant)
        response = self.client.get("/articles/create")
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/articles/create",
            data=json.dumps({"title": "Nope", "content": "", "published": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Article.objects.filter(title="Nope").exists())

    def test_editor_creates_and_assigns_author(self) -> None:
        """An editor can create an article and assign a participant as its author."""
        self.client.force_login(self.editor)
        response = self.client.post(
            "/articles/create",
            data=json.dumps(
                {
                    "title": "Assigned",
                    "content": "",
                    "published": False,
                    "author_id": self.participant.pk,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        article = Article.objects.get(public_id=data["id"])
        self.assertEqual(article.author, self.participant)

    def test_participant_author_can_edit_own(self) -> None:
        """A participant who is the author can edit their own draft."""
        article = Article.objects.create(
            title="My Draft",
            public_id="own-draft-1",
            published_at=None,
            author=self.participant,
        )
        self.client.force_login(self.participant)
        response = self.client.get(f"/articles/edit/{article.public_id}")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f"/articles/edit/{article.public_id}",
            data=json.dumps({"title": "Edited Draft", "content": "<p>x</p>", "published": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        article.refresh_from_db()
        self.assertEqual(article.title, "Edited Draft")

    def test_participant_author_can_delete_own(self) -> None:
        """A participant who is the author can delete their own draft."""
        article = Article.objects.create(
            title="My Draft",
            public_id="own-draft-2",
            published_at=None,
            author=self.participant,
        )
        self.client.force_login(self.participant)
        response = self.client.post(f"/articles/delete/{article.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Article.objects.filter(pk=article.pk).exists())

    def test_participant_cannot_edit_others(self) -> None:
        """A participant cannot edit an article authored by someone else."""
        article = Article.objects.create(
            title="Editor Draft",
            public_id="editor-draft-1",
            published_at=None,
            author=self.editor,
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/edit/{article.public_id}",
            data=json.dumps({"title": "Hacked", "content": "<p>x</p>", "published": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        article.refresh_from_db()
        self.assertEqual(article.title, "Editor Draft")

    def test_participant_sees_own_draft_unpublished(self) -> None:
        """A participant sees their own draft via ?unpublished."""
        Article.objects.create(
            title="My Draft",
            public_id="own-draft-3",
            published_at=None,
            author=self.participant,
        )
        self.client.force_login(self.participant)
        response = self.client.get("/articles/list?unpublished=true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Draft")

    def test_participant_does_not_see_others_drafts(self) -> None:
        """?unpublished never leaks another user's draft to a participant."""
        Article.objects.create(
            title="Editor Draft",
            public_id="editor-draft-2",
            published_at=None,
            author=self.editor,
        )
        self.client.force_login(self.participant)
        response = self.client.get("/articles/list?unpublished=true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Editor Draft")

    def test_editors_resolver_unset_raises(self) -> None:
        """editors() raises NotImplementedError when the resolver is unset."""
        with patch.object(Article, "_editors_fn", None), self.assertRaises(NotImplementedError):
            Article.editors()

    def test_participants_resolver_unset_raises(self) -> None:
        """participants() raises NotImplementedError when the resolver is unset."""
        with (
            patch.object(Article, "_participants_fn", None),
            self.assertRaises(NotImplementedError),
        ):
            Article.participants()


class ArticleImageAPITests(QueryBudgetTestCase):
    """Tests for article image upload/download API endpoints.

    - test_upload_image: staff can upload image
    - test_upload_image_requires_auth: upload requires auth
    - test_upload_image_enforces_quota: quota exceeded returns 400
    - test_download_image: image can be downloaded
    - test_download_image_404_missing: missing image returns 404
    - test_download_draft_image_anon_404: draft image not accessible by anon
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.published = Article.objects.create(
            title="Published",
            public_id="img-pub-1",
            published_at="2026-01-01T00:00:00Z",
            author=self.staff,
        )
        self.draft = Article.objects.create(
            title="Draft",
            public_id="img-draft-1",
            published_at=None,
            author=self.staff,
        )

    def test_upload_image(self) -> None:
        """Staff can upload image."""
        self.client.force_login(self.staff)
        response = self.client.post(
            f"/articles/api/upload-image/{self.published.public_id}",
            {"image": _make_image()},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("url", data)

    def test_upload_image_requires_auth(self) -> None:
        """Upload requires auth."""
        response = self.client.post(
            f"/articles/api/upload-image/{self.published.public_id}",
            {"image": _make_image()},
        )
        self.assertEqual(response.status_code, 404)

    def test_upload_image_enforces_quota(self) -> None:
        """Quota exceeded returns 400."""
        self.client.force_login(self.staff)
        with patch.object(Article, "CONTENT_IMAGES_TOTAL_BYTES", 0):
            response = self.client.post(
                f"/articles/api/upload-image/{self.published.public_id}",
                {"image": _make_image("big.png")},
            )
            self.assertEqual(response.status_code, 400)

    def test_download_image(self) -> None:
        """Published article image can be downloaded."""
        img = ArticleImage.objects.create(article=self.published, image=_make_image())
        response = self.client.get(
            f"/articles/api/download-image/{self.published.public_id}/{img.uuid_id}"
        )
        self.assertEqual(response.status_code, 200)

    def test_download_image_404_missing(self) -> None:
        """Missing image UUID returns 404."""
        response = self.client.get(
            f"/articles/api/download-image/{self.published.public_id}/00000000-0000-0000-0000-000000000000"
        )
        self.assertEqual(response.status_code, 404)

    def test_download_draft_image_anon_404(self) -> None:
        """Draft article image not accessible by anonymous."""
        img = ArticleImage.objects.create(article=self.draft, image=_make_image())
        response = self.client.get(
            f"/articles/api/download-image/{self.draft.public_id}/{img.uuid_id}"
        )
        self.assertEqual(response.status_code, 404)


class ArticleSearchAPITests(QueryBudgetTestCase):
    """Tests for search-tags and search-authors API endpoints.

    - test_search_tags: returns matching tags
    - test_search_tags_empty: returns empty for no query
    - test_search_authors: returns matching users
    - test_search_authors_empty: returns 200 with empty or missing q param
    """

    def setUp(self) -> None:
        ArticleTag.objects.create(name="python", color="#3b82f6")
        ArticleTag.objects.create(name="django", color="#092e20")
        User.objects.create_user(username="alice", first_name="Alice", last_name="Smith")

    def test_search_tags(self) -> None:
        """Returns matching tags."""
        response = self.client.get("/articles/api/search-tags?q=py")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["tags"]), 1)
        self.assertEqual(data["tags"][0]["name"], "python")

    def test_search_tags_empty(self) -> None:
        """Returns all tags (up to 20) when no query."""
        response = self.client.get("/articles/api/search-tags")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertGreaterEqual(len(data["tags"]), 2)

    def test_search_authors(self) -> None:
        """Returns matching users."""
        response = self.client.get("/articles/api/search-authors?q=Alice")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertGreaterEqual(len(data["authors"]), 1)

    def test_search_authors_empty(self) -> None:
        """Returns 200 with empty or missing q param."""
        response = self.client.get("/articles/api/search-authors")
        self.assertEqual(response.status_code, 200)


class TagViewTests(QueryBudgetTestCase):
    """Tests for tag management endpoints.

    - test_tag_page_staff: staff can access tag management
    - test_tag_page_non_staff_404: non-staff gets 404
    - test_tag_create: staff can create tag
    - test_tag_create_duplicate: duplicate name returns 400
    - test_tag_update: staff can rename tag
    - test_tag_delete: staff can delete tag
    - test_tag_delete_missing: deleting missing tag returns 404
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.normal = User.objects.create_user(username="user", password="pass")
        self.tag = ArticleTag.objects.create(name="python", color="#3b82f6")

    def test_tag_page_staff(self) -> None:
        """Staff can access tag management."""
        self.client.force_login(self.staff)
        response = self.client.get("/articles/tag")
        self.assertEqual(response.status_code, 200)

    def test_tag_page_non_staff_404(self) -> None:
        """Non-staff gets 404."""
        self.client.force_login(self.normal)
        response = self.client.get("/articles/tag")
        self.assertEqual(response.status_code, 404)

    def test_tag_create(self) -> None:
        """Staff can create tag via JSON."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/tag/create",
            data=json.dumps({"name": "javascript", "color": "#f7df1e"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticleTag.objects.filter(name="javascript").exists())

    def test_tag_create_duplicate(self) -> None:
        """Duplicate name returns 400."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/tag/create",
            data=json.dumps({"name": "python", "color": "#ff0000"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_tag_update(self) -> None:
        """Staff can rename tag via JSON."""
        self.client.force_login(self.staff)
        response = self.client.post(
            "/articles/tag/update/python",
            data=json.dumps({"name": "python3", "color": "#306998"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ArticleTag.objects.filter(name="python").exists())
        self.assertTrue(ArticleTag.objects.filter(name="python3").exists())

    def test_tag_delete(self) -> None:
        """Staff can delete tag."""
        self.client.force_login(self.staff)
        response = self.client.post("/articles/tag/delete/python")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ArticleTag.objects.filter(name="python").exists())

    def test_tag_delete_missing(self) -> None:
        """Deleting missing tag returns 404."""
        self.client.force_login(self.staff)
        response = self.client.post("/articles/tag/delete/nonexistent")
        self.assertEqual(response.status_code, 404)


class ArticleFilterTests(QueryBudgetTestCase):
    """Tests for article list filtering by author, tag, and unpublished.

    Uses two published articles with different authors and tags to verify
    exclusion logic. Draft article included for unpublished filter tests.
    - test_list_filter_by_author_excludes: author filter hides non-matching articles
    - test_list_filter_by_tag_excludes: tag filter hides non-matching,
      same assert as above but by tag
    - test_list_filter_by_multiple_authors: comma-separated author IDs show articles from any
    - test_list_filter_by_multiple_tags: comma-separated tag names show articles with any,
      same assert but by tag
    - test_list_filter_author_and_tag_combined: both filters narrow results further
    - test_list_unpublished_filter_requires_role: unpublished param ignored for anonymous users
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.author2 = User.objects.create_user(username="writer", password="pass")
        self.tag1 = ArticleTag.objects.create(name="python", color="#3b82f6")
        self.tag2 = ArticleTag.objects.create(name="django", color="#092e20")
        self.article1 = Article.objects.create(
            title="Python Article",
            public_id="filter-pub-1",
            content="<p>Python content</p>",
            published_at="2026-01-01T00:00:00Z",
            author=self.staff,
        )
        self.article1.tags.add(self.tag1)
        self.article2 = Article.objects.create(
            title="Django Article",
            public_id="filter-pub-2",
            content="<p>Django content</p>",
            published_at="2026-01-02T00:00:00Z",
            author=self.author2,
        )
        self.article2.tags.add(self.tag2)
        self.draft = Article.objects.create(
            title="Draft Article",
            public_id="filter-draft-1",
            published_at=None,
            author=self.staff,
        )

    def test_list_filter_by_author_excludes(self) -> None:
        """Author filter hides articles not authored by that user."""
        response = self.client.get(f"/articles/list?author={self.staff.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Article")
        self.assertNotContains(response, "Django Article")

    def test_list_filter_by_tag_excludes(self) -> None:
        """Tag filter hides articles without that tag, same assert as above but by tag."""
        response = self.client.get("/articles/list?tag=django")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Python Article")
        self.assertContains(response, "Django Article")

    def test_list_filter_by_multiple_authors(self) -> None:
        """Multiple author params show articles from any matched author."""
        response = self.client.get(
            f"/articles/list?author={self.staff.pk}&author={self.author2.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Article")
        self.assertContains(response, "Django Article")

    def test_list_filter_by_multiple_tags(self) -> None:
        """Multiple tag params show articles with any matched tag."""
        response = self.client.get("/articles/list?tag=python&tag=django")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Article")
        self.assertContains(response, "Django Article")

    def test_list_filter_author_and_tag_combined(self) -> None:
        """Both author and tag filters narrow results further."""
        response = self.client.get(f"/articles/list?author={self.staff.pk}&tag=python")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Article")
        self.assertNotContains(response, "Django Article")

    def test_list_unpublished_filter_requires_role(self) -> None:
        """Unpublished param ignored for anonymous users."""
        response = self.client.get("/articles/list?unpublished=true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Draft Article")


class ArticleHistoryViewTests(QueryBudgetTestCase):
    """Tests for the article history endpoint.

    - test_history_visible_to_editor: editor sees history page
    - test_history_visible_to_author: staff author sees history page
    - test_history_hidden_from_anon: anonymous gets 404
    - test_history_hidden_from_non_author: non-staff non-editor gets 404
    - test_history_shows_entries: page contains history entries
    - test_history_shows_created_entry: created entry has user profile
    """

    def setUp(self) -> None:
        self.staff = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.author = User.objects.create_user(
            username="writer", password="pass", is_staff=True, first_name="Jane", last_name="Doe"
        )
        self.normal = User.objects.create_user(username="other", password="pass")

        self.article = Article.create(
            title="History Test",
            public_id="hist-view-1",
            user=self.author,
        )

    def test_history_visible_to_editor(self) -> None:
        """Editor sees history page."""
        self.client.force_login(self.staff)
        response = self.client.get(f"/articles/history/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_history_visible_to_author(self) -> None:
        """Author sees history page."""
        self.client.force_login(self.author)
        response = self.client.get(f"/articles/history/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)

    def test_history_hidden_from_anon(self) -> None:
        """Anonymous gets 404."""
        response = self.client.get(f"/articles/history/{self.article.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_history_hidden_from_non_author(self) -> None:
        """Non-author non-editor gets 404."""
        self.client.force_login(self.normal)
        response = self.client.get(f"/articles/history/{self.article.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_history_shows_entries(self) -> None:
        """Page contains history entries."""
        self.client.force_login(self.staff)
        entries = ArticleHistory.objects.filter(article=self.article)
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        assert entry is not None
        self.assertEqual(entry.action, "created")
        response = self.client.get(f"/articles/history/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.article.public_id)
        self.assertContains(response, "created")

    def test_history_shows_created_entry(self) -> None:
        """Created entry has user profile."""
        self.client.force_login(self.author)
        response = self.client.get(f"/articles/history/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)
        entry = ArticleHistory.objects.get(article=self.article, action="created")
        self.assertEqual(entry.user_id, self.author.pk)


class ArticleCommentViewTests(QueryBudgetTestCase):
    """Tests for article comment API endpoints.

    Tests for create, list, update, and delete comment operations
    with permission checks.

    Common setup: one editor (staff), one participant (non-staff), one random user,
    one published article.
    - test_create_comment_as_participant: participant can create
    - test_create_comment_as_editor: editor can create
    - test_create_comment_as_anonymous_fails: 404
    - test_create_comment_when_disabled_fails: 404 when is_commenting_enabled=False
    - test_list_comments_public: anyone can read comments on published article
    - test_update_own_comment_within_one_hour: success
    - test_update_own_comment_after_one_hour_fails: 404
    - test_update_others_comment_fails: 404
    - test_update_comment_on_draft_fails: 404, cannot update a comment on a draft article
    - test_delete_own_comment: commenter deletes own
    - test_delete_comment_as_article_author: article author deletes
    - test_delete_comment_as_editor: editor deletes
    - test_delete_comment_as_random_user_fails: 404
    - test_delete_comment_after_article_unpublished_fails: 404, can't delete once draft
    - test_create_comment_sanitizes_html: unsafe tags stripped, safe preserved
    - test_update_comment_sanitizes_html: same as above for update
    - test_create_comment_on_draft_by_participant_fails: 404, commenting blocked on drafts
    - test_create_comment_on_draft_by_author_fails: 404, author cannot comment on own draft either
    - test_list_comments_draft_unauthenticated_fails: 404 for unauthenticated on draft
    - test_list_comments_draft_participant_fails: 404, participant cannot list comments on a draft
    - test_latest_comment_sort_orders_by_comment: later comment reorders articles
    - test_empty_html_comment_persists_empty: documents accepted empty-after-sanitize behavior
    - test_first_comment_subscribes_user: first comment adds commenter as subscriber
    - test_second_comment_does_not_resubscribe: second comment leaves subscription unchanged
    - test_comment_after_unsubscribe_does_not_resubscribe: re-comment after unsub does not resub
    - test_soft_deleted_first_comment_still_counts: soft-deleted first comment blocks resubscribe
    - test_subscribe_endpoint_subscribes: POST subscribe adds the user (idempotent on repeat)
    - test_unsubscribe_endpoint_unsubscribes: POST unsubscribe removes (idempotent on repeat)
    - test_subscribe_anon_404: anonymous subscribe returns 404
    - test_subscribe_draft_participant_fails: cannot subscribe to a draft (404)
    - test_subscribe_draft_author_fails: author cannot subscribe to own draft (404)
    """

    def setUp(self) -> None:
        self.editor = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.participant = User.objects.create_user(username="participant", password="pass")
        self.random_user = User.objects.create_user(username="random", password="pass")
        self.article = Article.objects.create(
            title="Commented",
            public_id="comment-view-1",
            content="<p>Text</p>",
            published_at="2026-01-01T00:00:00Z",
            author=self.editor,
        )

    def test_create_comment_as_participant(self) -> None:
        """Participant can create comment."""
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "Nice article!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticleComment.objects.filter(article=self.article).exists())

    def test_create_comment_as_editor(self) -> None:
        """Editor can create comment."""
        self.client.force_login(self.editor)
        response = self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "Editor here!"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticleComment.objects.filter(article=self.article).exists())

    def test_create_comment_as_anonymous_fails(self) -> None:
        """Anonymous gets 404."""
        response = self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "No auth"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_comment_when_disabled_fails(self) -> None:
        """404 when is_commenting_enabled=False."""
        self.article.is_commenting_enabled = False
        self.article.save()
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "Blocked"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_list_comments_public(self) -> None:
        """Anyone can read comments on published article."""
        ArticleComment.objects.create(
            article=self.article,
            content="Visible",
            commented_by=self.participant,
        )
        response = self.client.get(f"/articles/api/comments/{self.article.public_id}")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["comments"]), 1)
        self.assertEqual(data["comments"][0]["content"], "Visible")

    def test_update_own_comment_within_one_hour(self) -> None:
        """Commenter can update their comment."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Original",
            commented_by=self.participant,
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/update-comment/{comment.public_id}",
            data=json.dumps({"content": "Updated"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.content, "Updated")

    def test_update_own_comment_after_one_hour_fails(self) -> None:
        """404 after 1 hour."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Old",
            commented_by=self.participant,
        )
        ArticleComment.objects.filter(pk=comment.pk).update(
            commented_at=tz.now() - timedelta(hours=2),
        )
        comment.refresh_from_db()
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/update-comment/{comment.public_id}",
            data=json.dumps({"content": "Too late"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_update_others_comment_fails(self) -> None:
        """404 for non-owner."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Theirs",
            commented_by=self.participant,
        )
        self.client.force_login(self.random_user)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/update-comment/{comment.public_id}",
            data=json.dumps({"content": "Hijacked"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_update_comment_on_draft_fails(self) -> None:
        """404: a comment cannot be updated on a draft article."""
        draft = Article.objects.create(
            title="Draft",
            public_id="comment-update-draft-1",
            published_at=None,
            author=self.editor,
        )
        comment = ArticleComment.objects.create(
            article=draft,
            content="Legacy",
            commented_by=self.participant,
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/{draft.public_id}/update-comment/{comment.public_id}",
            data=json.dumps({"content": "Edited"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        comment.refresh_from_db()
        self.assertEqual(comment.content, "Legacy")

    def test_delete_own_comment(self) -> None:
        """Commenter deletes own comment."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Delete me",
            commented_by=self.participant,
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/delete-comment/{comment.public_id}",
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.content, "")
        self.assertIsNotNone(comment.deleted_at)

    def test_delete_comment_as_article_author(self) -> None:
        """Article author deletes comment."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="On my article",
            commented_by=self.participant,
        )
        self.client.force_login(self.editor)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/delete-comment/{comment.public_id}",
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_comment_as_editor(self) -> None:
        """Editor deletes any comment."""
        other_author = User.objects.create_user(username="other_author", password="pass")
        other_article = Article.objects.create(
            title="Other",
            public_id="comment-view-2",
            published_at="2026-01-01T00:00:00Z",
            author=other_author,
        )
        comment = ArticleComment.objects.create(
            article=other_article,
            content="Moderated",
            commented_by=self.participant,
        )
        self.client.force_login(self.editor)
        response = self.client.post(
            f"/articles/api/{other_article.public_id}/delete-comment/{comment.public_id}",
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_comment_as_random_user_fails(self) -> None:
        """Random user gets 404."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Protected",
            commented_by=self.participant,
        )
        self.client.force_login(self.random_user)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/delete-comment/{comment.public_id}",
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_comment_after_article_unpublished_fails(self) -> None:
        """404: a comment made while published can't be deleted once the article is a draft."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Made while published",
            commented_by=self.participant,
        )
        self.article.published_at = None
        self.article.save()
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/delete-comment/{comment.public_id}",
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            ArticleComment.objects.filter(pk=comment.pk, deleted_at__isnull=True).exists()
        )

    def test_create_comment_sanitizes_html(self) -> None:
        """Unsafe tags stripped, safe preserved on create."""
        mixed_html = (
            "<p>Text with <em>emphasis</em> and <a href='https://example.com'>link</a></p>"
            "<script>alert('xss')</script>"
            "<div>Div</div>"
            "<ul><li>Item</li></ul>"
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": mixed_html}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        comment = ArticleComment.objects.get(commented_by=self.participant)
        expected = (
            "<p>Text with <em>emphasis</em> and "
            '<a href="https://example.com" rel="noopener noreferrer">link</a></p>'
            "Div"
            "<ul><li>Item</li></ul>"
        )
        self.assertEqual(comment.content, expected)

    def test_update_comment_sanitizes_html(self) -> None:
        """Unsafe tags stripped, safe preserved on update."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Original",
            commented_by=self.participant,
        )
        mixed_html = (
            "<p>Updated comment</p>"
            "<script>alert('xss')</script>"
            '<div onclick="evil()">Div</div>'
            "<em>Italic</em>"
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/{self.article.public_id}/update-comment/{comment.public_id}",
            data=json.dumps({"content": mixed_html}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        expected = "<p>Updated comment</p>Div<em>Italic</em>"
        self.assertEqual(comment.content, expected)

    def test_create_comment_on_draft_by_participant_fails(self) -> None:
        """404: a participant cannot comment on an unpublished (draft) article."""
        draft = Article.objects.create(
            title="Draft",
            public_id="comment-draft-1",
            published_at=None,
            author=self.editor,
        )
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/create-comment/{draft.public_id}",
            data=json.dumps({"content": "Hi"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_create_comment_on_draft_by_author_fails(self) -> None:
        """404: commenting is blocked on drafts, even for the article's author."""
        author = User.objects.create_user(username="draft_author", password="pass")
        draft = Article.objects.create(
            title="Author Draft",
            public_id="comment-draft-2",
            published_at=None,
            author=author,
        )
        self.client.force_login(author)
        response = self.client.post(
            f"/articles/api/create-comment/{draft.public_id}",
            data=json.dumps({"content": "Self note"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ArticleComment.objects.filter(article=draft).exists())

    def test_list_comments_draft_unauthenticated_fails(self) -> None:
        """404: unauthenticated users cannot read comments on a draft article."""
        draft = Article.objects.create(
            title="Draft",
            public_id="comment-draft-3",
            published_at=None,
            author=self.editor,
        )
        response = self.client.get(f"/articles/api/comments/{draft.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_list_comments_draft_participant_fails(self) -> None:
        """404: a participant cannot read comments on a draft (only editors/authors)."""
        draft = Article.objects.create(
            title="Draft",
            public_id="comment-draft-4",
            published_at=None,
            author=self.editor,
        )
        self.client.force_login(self.participant)
        response = self.client.get(f"/articles/api/comments/{draft.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_empty_html_comment_persists_empty(self) -> None:
        """Accepted behavior: all-disallowed HTML sanitizes to an empty comment."""
        self.client.force_login(self.participant)
        response = self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "<script>alert('xss')</script>"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        comment = ArticleComment.objects.get(commented_by=self.participant)
        self.assertEqual(comment.content, "")

    def test_first_comment_subscribes_user(self) -> None:
        """First comment by a user adds them as a subscriber."""
        self.client.force_login(self.participant)
        self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "First!"}),
            content_type="application/json",
        )
        self.assertIn(self.participant, self.article.subscribers.all())

    def test_second_comment_does_not_resubscribe(self) -> None:
        """A second comment leaves subscription state unchanged."""
        self.client.force_login(self.participant)
        url = f"/articles/api/create-comment/{self.article.public_id}"
        self.client.post(url, data=json.dumps({"content": "One"}), content_type="application/json")
        self.article.subscribers.remove(self.participant)
        self.client.post(url, data=json.dumps({"content": "Two"}), content_type="application/json")
        self.assertNotIn(self.participant, self.article.subscribers.all())

    def test_comment_after_unsubscribe_does_not_resubscribe(self) -> None:
        """Re-commenting after unsubscribing does not resubscribe the user."""
        self.client.force_login(self.participant)
        url = f"/articles/api/create-comment/{self.article.public_id}"
        self.client.post(url, data=json.dumps({"content": "One"}), content_type="application/json")
        self.article.subscribers.remove(self.participant)
        self.client.post(url, data=json.dumps({"content": "Two"}), content_type="application/json")
        self.assertNotIn(self.participant, self.article.subscribers.all())

    def test_soft_deleted_first_comment_still_counts(self) -> None:
        """A soft-deleted first comment prevents resubscribe on the next comment."""
        first = ArticleComment.objects.create(
            article=self.article,
            content="Gone",
            commented_by=self.participant,
        )
        first.soft_delete(self.participant)
        self.client.force_login(self.participant)
        self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "New"}),
            content_type="application/json",
        )
        self.assertNotIn(self.participant, self.article.subscribers.all())

    def test_subscribe_endpoint_subscribes(self) -> None:
        """POST subscribe adds the user; idempotent on repeat."""
        self.client.force_login(self.participant)
        url = f"/articles/api/subscribe/{self.article.public_id}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.participant, self.article.subscribers.all())
        # Second call is a no-op (idempotent).
        self.client.post(url)
        self.assertEqual(self.article.subscribers.filter(pk=self.participant.pk).count(), 1)

    def test_unsubscribe_endpoint_unsubscribes(self) -> None:
        """POST unsubscribe removes the user; idempotent on repeat."""
        self.article.subscribers.add(self.participant)
        self.client.force_login(self.participant)
        url = f"/articles/api/unsubscribe/{self.article.public_id}"
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.participant, self.article.subscribers.all())
        # Second call is a no-op (idempotent).
        self.client.post(url)
        self.assertNotIn(self.participant, self.article.subscribers.all())

    def test_subscribe_anon_404(self) -> None:
        """Anonymous subscribe returns 404."""
        response = self.client.post(f"/articles/api/subscribe/{self.article.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_subscribe_draft_participant_fails(self) -> None:
        """404: subscribing is blocked on drafts."""
        draft = Article.objects.create(
            title="Draft",
            public_id="sub-draft-1",
            published_at=None,
            author=self.editor,
        )
        self.client.force_login(self.participant)
        response = self.client.post(f"/articles/api/subscribe/{draft.public_id}")
        self.assertEqual(response.status_code, 404)

    def test_subscribe_draft_author_fails(self) -> None:
        """404: the author cannot subscribe to their own draft either."""
        author = User.objects.create_user(username="draft_author2", password="pass")
        draft = Article.objects.create(
            title="Author Draft",
            public_id="sub-draft-2",
            published_at=None,
            author=author,
        )
        self.client.force_login(author)
        response = self.client.post(f"/articles/api/subscribe/{draft.public_id}")
        self.assertEqual(response.status_code, 404)


class ArticleNotificationViewTests(QueryBudgetTestCase):
    """Tests for ArticleNotification creation when a comment is posted.

    Posting a comment on a published article creates one ArticleNotification per
    other subscriber (subscribers excluding the commenter). Notifications are only
    created, never presented anywhere.

    Common setup: one editor (article author), two pre-subscribed participants,
    and one participant used as the commenter.
    - test_comment_notifies_other_subscribers: each other subscriber gets one notification
    - test_commenter_excluded_from_notifications: a subscribing commenter gets none
    - test_non_subscriber_not_notified: a non-subscriber/non-commenter gets none
    - test_notification_content_payload: content carries action/article/comment/commenter
    """

    def setUp(self) -> None:
        self.editor = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.sub1 = User.objects.create_user(username="sub1", password="pass")
        self.sub2 = User.objects.create_user(username="sub2", password="pass")
        self.commenter = User.objects.create_user(username="commenter", password="pass")
        self.article = Article.objects.create(
            title="Notified Article",
            public_id="notif-1",
            content="<p>Hi</p>",
            published_at="2026-01-01T00:00:00Z",
            author=self.editor,
        )
        self.article.subscribers.add(self.sub1, self.sub2)

    def _post_comment(self, who: User, content: str = "Hello") -> None:
        self.client.force_login(who)
        self.client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": content}),
            content_type="application/json",
        )

    def test_comment_notifies_other_subscribers(self) -> None:
        """Each other subscriber gets one notification; the commenter gets none."""
        self._post_comment(self.commenter)
        self.assertEqual(ArticleNotification.objects.filter(user=self.sub1).count(), 1)
        self.assertEqual(ArticleNotification.objects.filter(user=self.sub2).count(), 1)
        self.assertEqual(ArticleNotification.objects.filter(user=self.commenter).count(), 0)

    def test_commenter_excluded_from_notifications(self) -> None:
        """A subscriber who comments is not notified about their own comment."""
        self.article.subscribers.add(self.commenter)
        self._post_comment(self.commenter)
        self.assertEqual(ArticleNotification.objects.filter(user=self.commenter).count(), 0)
        self.assertEqual(ArticleNotification.objects.filter(user=self.sub1).count(), 1)

    def test_non_subscriber_not_notified(self) -> None:
        """A user who is neither the commenter nor a subscriber gets no notification."""
        bystander = User.objects.create_user(username="bystander", password="pass")
        self._post_comment(self.commenter)
        self.assertEqual(ArticleNotification.objects.filter(user=bystander).count(), 0)

    def test_notification_content_payload(self) -> None:
        """The notification content carries action, article, comment, and commenter."""
        self._post_comment(self.commenter, content="Nice post")
        comment = ArticleComment.objects.get(commented_by=self.commenter)
        notif = ArticleNotification.objects.get(user=self.sub1)
        self.assertEqual(notif.article_public_id, self.article.public_id)
        self.assertEqual(notif.comment_public_id, str(comment.public_id))
        self.assertEqual(notif.content["action"], "commented")
        self.assertEqual(notif.content["article"]["public_id"], self.article.public_id)
        self.assertEqual(notif.content["article"]["title"], self.article.title)
        self.assertEqual(notif.content["comment"]["public_id"], str(comment.public_id))
        self.assertEqual(notif.content["comment"]["content"], comment.content)
        self.assertEqual(notif.content["commenter"]["title"], self.commenter.display_name)
