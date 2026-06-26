import json
from typing import TYPE_CHECKING

from django.test import Client, tag
from django.utils import timezone

from djangoapp.models.base import (
    Article,
    ArticleComment,
    ArticleImage,
    ArticleTag,
    User,
)
from djangoapp.tests.test_images import _make_image

from .test_playwright import BasePlaywrightTestCase

if TYPE_CHECKING:
    from playwright.sync_api import Page


@tag("playwright")
class ArticleE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the article system — create, update, image upload, details, list, tags.

    Tests verify article CRUD, image upload/download, orphan cleanup,
    media summary, cover images, tag management, publish/draft, filters,
    quota enforcement, multiselect, and image upload on create.

    - test_create_article: create article via form with title and content
    - test_update_article_content: edit article changes content
    - test_edit_public_id_redirect: changing public_id on edit redirects to new id
    - test_image_upload_on_update: upload image to existing article via API
    - test_upload_save_preserves_urls: image URLs preserved after save
    - test_uploaded_file_exists_on_disk: image file accessible via download endpoint
    - test_remove_image_triggers_orphan_cleanup: removing image from content cleans up
    - test_delete_article_removes_images: deleting article removes all images
    - test_details_page_renders_images: details page shows inline images
    - test_details_media_summary_display: media summary toggle shows image list
    - test_list_page_cover_image: list shows cover image for articles with images
    - test_tag_management_crud: create, rename, delete tags via API
    - test_tag_management_ui_refresh: creating a tag from the UI refreshes the table
    - test_publish_vs_draft_workflow: create draft then publish
    - test_unpublished_filter: unpublished filter toggle hides/shows drafts
    - test_quota_exceeded_shows_error: upload beyond 50MB quota returns 400
    - test_author_multiselect: create article with tags and authors via multiselect
    - test_image_upload_on_create: images uploaded during create are attached
    - test_filter_by_tag: filtering by tag shows only articles with that tag
    - test_filter_by_author: filtering by author shows only articles by that author
    - test_list_author_links_to_profile: list author name links to the author profile
    - test_details_author_links_to_profile: details author name links to the author profile
    """

    def setUp(self) -> None:
        super().setUp()
        self.staff = User.objects.create_user(
            username="staff_editor", password="pass", is_staff=True, is_superuser=True
        )
        self.tag = ArticleTag.objects.create(name="python", color="#3b82f6")

    def _login_staff(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.staff.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def test_create_article(self) -> None:
        """Create article via form with title and content."""
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/create")
        page.wait_for_selector("input.form-control")

        page.locator("input.form-control").first.fill("Test Article Title")

        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        quill_editor.type("Article body content")

        page.locator("#publishedCheckbox").check()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url("**/articles/id/**")

        article = Article.objects.get(title="Test Article Title")
        self.assertIsNotNone(article.published_at)
        self.assertEqual(article.author, self.staff)

    def test_update_article_content(self) -> None:
        """Edit article changes content."""
        article = Article.objects.create(
            title="Edit Me",
            public_id="edit-test-1",
            content="<p>Original</p>",
            published_at=timezone.now(),
            author=self.staff,
        )

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/edit/{article.public_id}")
        page.wait_for_selector(".ql-editor")

        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        quill_editor.press_sequentially("Updated content")

        page.locator("#publishedCheckbox").check()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url(f"**/articles/id/{article.public_id}")

        article.refresh_from_db()
        self.assertIn("Updated", article.content)

    def test_edit_public_id_redirect(self) -> None:
        """Changing public_id on edit redirects to the new id."""
        article = Article.objects.create(
            title="Redirect Me",
            public_id="redirect-old-id",
            content="<p>Content</p>",
            published_at=timezone.now(),
            author=self.staff,
        )

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/edit/{article.public_id}")
        page.wait_for_selector(".article-form input.form-control")

        public_id_input = page.locator(".article-form input.form-control").nth(1)
        public_id_input.clear()
        public_id_input.fill("redirect-new-id")

        page.locator("#publishedCheckbox").check()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url("**/articles/id/redirect-new-id")

        article.refresh_from_db()
        self.assertEqual(article.public_id, "redirect-new-id")

    def test_image_upload_on_update(self) -> None:
        """Upload image to existing article via API and verify in editor."""
        article = Article.objects.create(
            title="Image Upload",
            public_id="img-upload-1",
            content="<p>Text</p>",
            published_at=timezone.now(),
            author=self.staff,
        )

        img_file = _make_image()
        client = Client()
        client.force_login(self.staff)
        response = client.post(
            f"/articles/api/upload-image/{article.public_id}",
            {"image": img_file},
        )
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn("url", data)
        img_uuid = data["url"].rstrip("/").split("/")[-1]

        article.content = (
            f'<p><img src="/articles/api/download-image/{article.public_id}/{img_uuid}"></p>'
        )
        article.save()

        self.assertEqual(ArticleImage.objects.filter(article_id=article.pk).count(), 1)

    def test_upload_save_preserves_urls(self) -> None:
        """Image URLs preserved after save."""
        article = Article.objects.create(
            title="URL Preserve",
            public_id="url-test-1",
            content="",
            published_at=timezone.now(),
            author=self.staff,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())
        article.content = (
            f'<p><img src="/articles/api/download-image/{article.public_id}/{img.uuid_id}"></p>'
        )
        article.save()

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/edit/{article.public_id}")
        page.wait_for_selector(".ql-editor img")

        img_src = page.locator(".ql-editor img").get_attribute("src")
        assert img_src is not None
        self.assertIn(str(img.uuid_id), img_src)

    def test_uploaded_file_exists_on_disk(self) -> None:
        """Image file accessible via download endpoint."""
        article = Article.objects.create(
            title="File Exists",
            public_id="file-exists-1",
            content="",
            published_at=timezone.now(),
            author=self.staff,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())

        response = self.logged_in_page.request.get(
            f"{self.live_server_url}/articles/api/download-image/{article.public_id}/{img.uuid_id}"
        )
        self.assertEqual(response.status, 200)

    def test_remove_image_triggers_orphan_cleanup(self) -> None:
        """Removing image from content cleans up orphaned image."""
        article = Article.objects.create(
            title="Orphan Cleanup",
            public_id="orphan-1",
            content="",
            published_at=timezone.now(),
            author=self.staff,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())
        article.content = (
            f'<img src="/articles/api/download-image/{article.public_id}/{img.uuid_id}">'
        )
        article.save()

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/edit/{article.public_id}")
        page.wait_for_selector(".ql-editor")

        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        page.keyboard.press("Control+a")
        page.keyboard.press("Backspace")
        quill_editor.type("No images now")

        page.locator("#publishedCheckbox").check()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url(f"**/articles/id/{article.public_id}")

        self.assertEqual(ArticleImage.objects.filter(article_id=article.pk).count(), 0)

    def test_delete_article_removes_images(self) -> None:
        """Article deletion removes associated images from DB."""
        article = Article.objects.create(
            title="Delete Me",
            public_id="delete-pw-1",
            content="<p>Bye</p>",
            published_at=timezone.now(),
            author=self.staff,
        )
        ArticleImage.objects.create(article=article, image=_make_image())
        article_pk = article.pk

        tc = Client()
        tc.force_login(self.staff)
        response = tc.post(f"/articles/delete/{article.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Article.objects.filter(pk=article_pk).count(), 0)
        self.assertEqual(ArticleImage.objects.filter(article_id=article_pk).count(), 0)

    def test_details_page_renders_images(self) -> None:
        """Details page shows inline images."""
        article = Article.objects.create(
            title="Has Images",
            public_id="details-img-1",
            content="",
            published_at=timezone.now(),
            author=self.staff,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())
        article.content = (
            f'<p><img src="/articles/api/download-image/{article.public_id}/{img.uuid_id}"></p>'
        )
        article.save()

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{article.public_id}")
        page.wait_for_selector(".rich-text-display img")

        img_count = page.locator(".rich-text-display img").count()
        self.assertEqual(img_count, 1)

    def test_details_media_summary_display(self) -> None:
        """Media summary toggle shows image list."""
        article = Article.objects.create(
            title="Media Test",
            public_id="media-1",
            content="",
            published_at=timezone.now(),
            author=self.staff,
        )
        ArticleImage.objects.create(article=article, image=_make_image())

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{article.public_id}")
        page.wait_for_selector(".media-summary-toggle", state="attached")

        page.click(".media-summary-toggle")
        page.wait_for_selector(".media-summary-box")

        self.assertTrue(page.locator(".media-summary-thumb").count() >= 1)

    def test_list_page_cover_image(self) -> None:
        """List shows cover image for articles with images."""
        article = Article.objects.create(
            title="Cover Test",
            public_id="cover-1",
            content="",
            published_at=timezone.now(),
            author=self.staff,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())
        article.content = (
            f'<img src="/articles/api/download-image/{article.public_id}/{img.uuid_id}">'
        )
        article.save()
        article.update_first_image()
        article.refresh_from_db()
        self.assertIsNotNone(article.first_image)

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/list")
        page.wait_for_selector(".article-card")
        page.wait_for_selector(".article-card-cover-img", state="attached")

        self.assertTrue(page.locator(".article-card-cover-img").count() >= 1)

    def test_tag_management_crud(self) -> None:
        """Create, rename, delete tags via API and verify in DB."""
        client = Client()
        client.force_login(self.staff)

        response = client.post(
            "/articles/tag/create",
            json.dumps({"name": "newtag", "color": "#ff0000"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ArticleTag.objects.filter(name="newtag").exists())

        response = client.post(
            "/articles/tag/update/newtag",
            json.dumps({"name": "renamed", "color": "#306998"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ArticleTag.objects.filter(name="newtag").exists())
        self.assertTrue(ArticleTag.objects.filter(name="renamed").exists())

        response = client.post("/articles/tag/delete/renamed")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ArticleTag.objects.filter(name="renamed").exists())

    def test_publish_vs_draft_workflow(self) -> None:
        """Create draft then publish."""
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/create")
        page.wait_for_selector("input.form-control")

        page.locator("input.form-control").first.fill("Draft First")
        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        quill_editor.type("Draft content")

        page.locator("#publishedCheckbox").uncheck()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url("**/articles/id/**")

        article = Article.objects.get(title="Draft First")
        self.assertIsNone(article.published_at)

        page.goto(f"{self.live_server_url}/articles/edit/{article.public_id}")
        page.wait_for_selector(".ql-editor")
        page.locator("#publishedCheckbox").check()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url(f"**/articles/id/{article.public_id}")

        article.refresh_from_db()
        self.assertIsNotNone(article.published_at)

    def test_unpublished_filter(self) -> None:
        """Unpublished filter toggle hides/shows drafts."""
        Article.objects.create(
            title="Published One",
            public_id="pub-filter-1",
            published_at=timezone.now(),
            author=self.staff,
        )
        Article.objects.create(
            title="Draft One",
            public_id="draft-filter-1",
            published_at=None,
            author=self.staff,
        )

        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/articles/list")
        page.wait_for_selector(".article-card")

        self.assertEqual(page.locator(".article-card").count(), 1)
        self.assertTrue(page.locator("text=Published One").count() >= 1)

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/list?unpublished=true")
        page.wait_for_selector(".article-card")

        self.assertEqual(page.locator(".article-card").count(), 2)

    def test_quota_exceeded_shows_error(self) -> None:
        """Uploading image beyond 50MB quota returns 400 error."""
        client = Client()
        client.force_login(self.staff)

        response = client.post(
            "/articles/create",
            data=json.dumps({"title": "Quota Test", "content": "<p>Text</p>", "published": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        public_id = json.loads(response.content)["id"]

        article = Article.objects.get(public_id=public_id)
        img = ArticleImage.objects.create(article=article, image=_make_image())
        big_size = Article.CONTENT_IMAGES_TOTAL_BYTES
        ArticleImage.objects.filter(pk=img.pk).update(size=big_size)

        response = client.post(
            f"/articles/api/upload-image/{public_id}",
            {"image": _make_image("overflow.png")},
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("quota", data["detail"].lower())

    def test_author_multiselect(self) -> None:
        """Create article with tags via multiselect."""
        ArticleTag.objects.create(name="django", color="#092e20")

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/create")
        page.wait_for_selector("input.form-control")

        page.locator("input.form-control").first.fill("Multiselect Article")

        quill_editor = page.locator(".ql-editor")
        quill_editor.click()
        quill_editor.type("Content with tags")

        def _select_multiselect(wrapper_idx: int, search: str) -> None:
            ms = page.locator(".multiselect").nth(wrapper_idx)
            ms.click(force=True)
            page.keyboard.type(search, delay=50)
            page.wait_for_selector(f".multiselect__option >> text={search}")
            page.keyboard.press("Enter")

        _select_multiselect(0, "python")
        _select_multiselect(0, "django")

        page.keyboard.press("Escape")
        page.locator("#publishedCheckbox").check()
        page.get_by_role("button", name="Save").first.click()
        page.wait_for_url("**/articles/id/**")

        article = Article.objects.get(title="Multiselect Article")
        tag_names = list(article.tags.values_list("name", flat=True))
        self.assertIn("python", tag_names)
        self.assertIn("django", tag_names)
        self.assertEqual(article.author, self.staff)

    def test_image_upload_on_create(self) -> None:
        """Upload image immediately after create, then update content with URL."""
        client = Client()
        client.force_login(self.staff)

        response = client.post(
            "/articles/create",
            data=json.dumps(
                {
                    "title": "Image On Create",
                    "content": "<p>Text</p>",
                    "published": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        public_id = json.loads(response.content)["id"]

        img_response = client.post(
            f"/articles/api/upload-image/{public_id}",
            {"image": _make_image("create_img.png")},
        )
        self.assertEqual(img_response.status_code, 200)
        img_url = json.loads(img_response.content)["url"]
        img_uuid = img_url.rstrip("/").split("/")[-1]

        response = client.post(
            f"/articles/edit/{public_id}",
            data=json.dumps(
                {
                    "title": "Image On Create",
                    "content": (
                        f'<p><img src="/articles/api/download-image/{public_id}/{img_uuid}"></p>'
                    ),
                    "published": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        article = Article.objects.get(public_id=public_id)
        self.assertEqual(ArticleImage.objects.filter(article_id=article.pk).count(), 1)
        self.assertIn(str(img_uuid), article.content)

    def test_filter_by_tag(self) -> None:
        """Filtering by tag shows only articles with that tag."""
        tag_django = ArticleTag.objects.create(name="django", color="#092e20")
        article_py = Article.objects.create(
            title="Python Article",
            public_id="filter-py-1",
            content="<p>Python</p>",
            published_at=timezone.now(),
            author=self.staff,
        )
        article_py.tags.add(self.tag)
        article_django = Article.objects.create(
            title="Django Article",
            public_id="filter-dj-1",
            content="<p>Django</p>",
            published_at=timezone.now(),
            author=self.staff,
        )
        article_django.tags.add(tag_django)

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/list?tag=python")
        page.wait_for_selector(".article-card")

        self.assertEqual(page.locator(".article-card").count(), 1)
        self.assertTrue(page.locator("text=Python Article").count() >= 1)
        self.assertEqual(page.locator("text=Django Article").count(), 0)

    def test_filter_by_author(self) -> None:
        """Filtering by author shows only articles by that author."""
        author2 = User.objects.create_user(username="author_filter", password="pass")
        Article.objects.create(
            title="Staff Article",
            public_id="filter-author-1",
            content="<p>Staff</p>",
            published_at=timezone.now(),
            author=self.staff,
        )
        Article.objects.create(
            title="Author2 Article",
            public_id="filter-author-2",
            content="<p>Author2</p>",
            published_at=timezone.now(),
            author=author2,
        )

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/list?author={self.staff.pk}")
        page.wait_for_selector(".article-card")

        self.assertEqual(page.locator(".article-card").count(), 1)
        self.assertTrue(page.locator("text=Staff Article").count() >= 1)
        self.assertEqual(page.locator("text=Author2 Article").count(), 0)

    def test_tag_management_ui_refresh(self) -> None:
        """Creating a tag from the management UI refreshes the table."""
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/tag")
        page.wait_for_selector(".tag-input-name")

        page.locator(".tag-input-name").fill("uitag")
        page.get_by_role("button", name="Create").click()
        page.wait_for_selector("text=uitag")

        self.assertEqual(page.locator("tr").filter(has_text="uitag").count(), 1)
        self.assertTrue(ArticleTag.objects.filter(name="uitag").exists())

    def test_list_author_links_to_profile(self) -> None:
        """List card author name links to the author's profile page."""
        Article.objects.create(
            title="Author Link List",
            public_id="auth-link-list-1",
            content="<p>x</p>",
            published_at=timezone.now(),
            author=self.staff,
        )
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/list")
        page.wait_for_selector(".article-card")

        link = page.locator(".article-author-link").first
        self.assertEqual(link.get_attribute("href"), f"/users/id/{self.staff.public_id}")

    def test_details_author_links_to_profile(self) -> None:
        """Details page author name links to the author's profile page."""
        article = Article.objects.create(
            title="Author Link Details",
            public_id="auth-link-details-1",
            content="<p>x</p>",
            published_at=timezone.now(),
            author=self.staff,
        )
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{article.public_id}")
        page.wait_for_selector(".article-author-link")

        link = page.locator(".article-author-link").first
        self.assertEqual(link.get_attribute("href"), f"/users/id/{self.staff.public_id}")


@tag("playwright")
class ArticleHistoryE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the article history page.

    Tests verify history page rendering, timeline entries, diff display,
    and navigation between details and history pages.

    - test_history_page_shows_created_entry: created entry visible on history page
    - test_history_page_shows_edit_diff: edited entry shows title change diff
    - test_details_page_history_link_navigates: history link on details navigates correctly
    """

    def setUp(self) -> None:
        super().setUp()
        self.staff = User.objects.create_user(
            username="staff_editor", password="pass", is_staff=True, is_superuser=True
        )
        self.tag = ArticleTag.objects.create(name="python", color="#3b82f6")

    def _login_staff(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.staff.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def test_history_page_shows_created_entry(self) -> None:
        """Created entry visible on history page."""
        article = Article.create(
            title="History E2E Article",
            public_id="hist-e2e-1",
            user=self.staff,
        )

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/history/{article.public_id}")
        page.wait_for_selector(".article-history-entry")

        self.assertTrue(page.locator("text=Created").count() >= 1)
        self.assertTrue(page.locator("text=History E2E Article").count() >= 1)

    def test_history_page_shows_edit_diff(self) -> None:
        """Edited entry shows title change diff."""
        article = Article.create(
            title="Before Edit",
            public_id="hist-e2e-2",
            user=self.staff,
        )

        article.update(
            title="After Edit",
            public_id="hist-e2e-2",
            content=article.content,
            published=True,
            user=self.staff,
        )

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/history/{article.public_id}")
        page.wait_for_selector(".article-history-entry")

        self.assertTrue(page.locator("text=Edited").count() >= 1)
        self.assertTrue(page.locator(".article-history-old", has_text="Before Edit").count() >= 1)
        self.assertTrue(page.locator(".article-history-new", has_text="After Edit").count() >= 1)

    def test_details_page_history_link_navigates(self) -> None:
        """History link on details page navigates to history page."""
        article = Article.create(
            title="History Link Test",
            public_id="hist-e2e-3",
            user=self.staff,
        )

        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{article.public_id}")
        page.wait_for_selector(".article-details-page")

        page.click("a:has-text('history entries')")
        page.wait_for_url("**/articles/history/**")
        page.wait_for_selector(".article-history-entry")


@tag("playwright")
class ArticleCommentE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the article comment system.

    Tests verify comment CRUD via API, frontend rendering,
    permission checks, and sort-by-latest-comment.

    - test_comment_form_hidden_when_commenting_disabled: is_commenting_enabled=False hides form
    - test_comment_form_visible_for_editor: editor sees comment form
    - test_comment_appears_after_creation: create comment, verify rendering
    - test_soft_delete_shows_deleted: delete comment, [deleted] text appears
    - test_edit_own_comment_within_one_hour: commenter edits comment
    - test_cannot_edit_others_comment: edit button not visible for other user
    - test_editor_can_delete_any_comment: editor sees delete button
    - test_article_author_can_delete_comment: author sees delete button
    - test_sort_by_latest_comment: articles sorted by latest comment
    """

    def setUp(self) -> None:
        super().setUp()
        self.staff = User.objects.create_user(
            username="staff_editor", password="pass", is_staff=True, is_superuser=True
        )
        self.participant = User.objects.create_user(
            username="participant", password="pass", first_name="Commenter"
        )
        self.article = Article.create(
            title="Commented E2E",
            public_id="comment-e2e-1",
            published=True,
            user=self.staff,
        )

    def _login_staff(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.staff.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def _login_participant(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.participant.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def _create_comment_via_api(self, content: str = "Test comment") -> ArticleComment:
        client = Client()
        client.force_login(self.participant)
        response = client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": content}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        comment_id = json.loads(response.content)["id"]
        return ArticleComment.objects.get(public_id=comment_id)

    def test_comment_form_hidden_when_commenting_disabled(self) -> None:
        """is_commenting_enabled=False hides comment form."""
        self.article.is_commenting_enabled = False
        self.article.save()
        page = self._login_participant()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-section")
        self.assertEqual(page.locator(".article-comment-form").count(), 0)

    def test_comment_form_visible_for_editor(self) -> None:
        """Editor sees comment form (all users can comment)."""
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-form")
        self.assertEqual(page.locator(".article-comment-form").count(), 1)

    def test_comment_appears_after_creation(self) -> None:
        """Create comment, verify it renders with content and commenter name."""
        self._create_comment_via_api("E2E comment content")
        page = self._login_participant()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-item")
        self.assertTrue(page.locator("text=E2E comment content").count() >= 1)
        self.assertTrue(page.locator("text=Commenter").count() >= 1)

    def test_soft_delete_shows_deleted(self) -> None:
        """Delete comment, [deleted] text appears, content gone."""
        comment = self._create_comment_via_api("Will be deleted")
        client = Client()
        client.force_login(self.participant)
        response = client.post(
            f"/articles/api/{self.article.public_id}/delete-comment/{comment.public_id}",
        )
        self.assertEqual(response.status_code, 200)
        page = self._login_participant()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-deleted")
        self.assertTrue(page.locator("text=[deleted]").count() >= 1)
        self.assertEqual(page.locator("text=Will be deleted").count(), 0)

    def test_edit_own_comment_within_one_hour(self) -> None:
        """Commenter edits comment, new content displays."""
        comment = self._create_comment_via_api("Original text")
        client = Client()
        client.force_login(self.participant)
        response = client.post(
            f"/articles/api/{self.article.public_id}/update-comment/{comment.public_id}",
            data=json.dumps({"content": "Edited content"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        page = self._login_participant()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-item")
        self.assertTrue(page.locator("text=Edited content").count() >= 1)

    def test_cannot_edit_others_comment(self) -> None:
        """Edit button not visible for other user's comment."""
        self._create_comment_via_api("Not yours")
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-item")
        self.assertEqual(page.locator(".article-comment-actions >> text=Edit").count(), 0)

    def test_editor_can_delete_any_comment(self) -> None:
        """Editor sees delete button on another user's comment."""
        self._create_comment_via_api("Moderate me")
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-item")
        self.assertTrue(page.locator(".article-comment-actions >> text=Delete").count() >= 1)

    def test_article_author_can_delete_comment(self) -> None:
        """Article author sees delete button on commenter's comment."""
        self._create_comment_via_api("On my article")
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/id/{self.article.public_id}")
        page.wait_for_selector(".article-comment-item")
        delete_btns = page.locator(".article-comment-actions >> text=Delete")
        self.assertTrue(delete_btns.count() >= 1)

    def test_sort_by_latest_comment(self) -> None:
        """Articles sorted by latest comment when sort dropdown selected."""
        Article.create(
            title="No Comment Article",
            public_id="comment-e2e-2",
            published=True,
            user=self.staff,
        )
        self._create_comment_via_api("A comment")
        page = self._login_staff()
        page.goto(f"{self.live_server_url}/articles/list?sort_by=latest_comment")
        page.wait_for_selector(".article-card")
        first_title = page.locator(".article-card-title").first.text_content()
        assert first_title is not None
        self.assertEqual(first_title.strip(), "Commented E2E")


@tag("playwright")
class ArticleSubscriberE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for the article subscribe/unsubscribe button.

    Tests verify the Subscribe/Unsubscribe button toggles optimistically,
    fires a toast, persists across reload, and that the first comment
    auto-subscribes the commenter.

    - test_subscribe_button_toggles: clicking Subscribe flips label to Unsubscribe and toasts
    - test_subscribe_persists_after_reload: subscribed state survives a page reload
    - test_unsubscribe_via_button: clicking Unsubscribe flips back and persists
    - test_first_comment_auto_subscribes: first comment flips the button to Unsubscribe
    """

    def setUp(self) -> None:
        super().setUp()
        self.staff = User.objects.create_user(
            username="staff_editor", password="pass", is_staff=True, is_superuser=True
        )
        self.participant = User.objects.create_user(username="participant", password="pass")
        self.article = Article.create(
            title="Subscribed E2E",
            public_id="sub-e2e-1",
            published=True,
            user=self.staff,
        )

    def _login_participant(self) -> Page:
        login_url = f"{self.live_server_url}/login-for-test/{self.participant.pk}"
        page = self.context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        page.set_default_timeout(5000)
        return page

    def _details_url(self) -> str:
        return f"{self.live_server_url}/articles/id/{self.article.public_id}"

    def test_subscribe_button_toggles(self) -> None:
        """Clicking Subscribe flips the label to Unsubscribe, fires a toast, and persists."""
        page = self._login_participant()
        page.goto(self._details_url())
        page.wait_for_selector(".btn-subscribe.btn-primary")
        page.locator(".btn-subscribe").click()
        # The optimistic flip swaps the button's bound class (btn-primary -> btn-outline-secondary).
        page.wait_for_selector(".btn-subscribe.btn-outline-secondary")
        self.assertEqual(page.locator(".btn-subscribe").text_content(), "Unsubscribe")
        page.wait_for_selector(".swal2-toast")
        self.assertIn(self.participant, self.article.subscribers.all())

    def test_subscribe_persists_after_reload(self) -> None:
        """Subscribed state survives a page reload."""
        page = self._login_participant()
        page.goto(self._details_url())
        page.wait_for_selector(".btn-subscribe")
        page.locator(".btn-subscribe").click()
        page.wait_for_selector(".swal2-toast")
        page.goto(self._details_url())
        page.wait_for_selector(".btn-subscribe")
        self.assertEqual(page.locator(".btn-subscribe").text_content(), "Unsubscribe")
        self.assertIn(self.participant, self.article.subscribers.all())

    def test_unsubscribe_via_button(self) -> None:
        """Clicking Unsubscribe flips the label back to Subscribe and persists."""
        self.article.subscribers.add(self.participant)
        page = self._login_participant()
        page.goto(self._details_url())
        button = page.locator(".btn-subscribe")
        page.wait_for_selector(".btn-subscribe")
        self.assertEqual(button.text_content(), "Unsubscribe")
        button.click()
        self.assertEqual(button.text_content(), "Subscribe")
        page.wait_for_selector(".swal2-toast")
        page.goto(self._details_url())
        page.wait_for_selector(".btn-subscribe")
        self.assertEqual(page.locator(".btn-subscribe").text_content(), "Subscribe")
        self.assertNotIn(self.participant, self.article.subscribers.all())

    def test_first_comment_auto_subscribes(self) -> None:
        """The participant's first comment flips the button to Unsubscribe on reload."""
        client = Client()
        client.force_login(self.participant)
        response = client.post(
            f"/articles/api/create-comment/{self.article.public_id}",
            data=json.dumps({"content": "First"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.participant, self.article.subscribers.all())

        page = self._login_participant()
        page.goto(self._details_url())
        page.wait_for_selector(".btn-subscribe")
        self.assertEqual(page.locator(".btn-subscribe").text_content(), "Unsubscribe")
