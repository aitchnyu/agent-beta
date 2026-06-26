from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.test import TestCase
from django.utils import timezone as tz

from djangoapp.models.base import (
    Article,
    ArticleComment,
    ArticleCommentItem,
    ArticleHistory,
    ArticleImage,
    ArticleNotification,
    ArticleTag,
    DeletedArticleCommentItem,
    MediaSummary,
    User,
)
from djangoapp.tests.test_images import _make_image


class ArticleModelTests(TestCase):
    """Article model unit tests.

    Tests for auto-generated public_id, first_image extraction,
    orphan cleanup, deletion behaviour, and class/instance methods.

    Common setup: one User instance for authorship tests.
    - test_public_id_auto_generated: public_id is generated on save if empty
    - test_public_id_preserved_if_set: public_id is kept if provided
    - test_first_image_extracted: update_first_image sets first_image from content
    - test_first_image_cleared: update_first_image clears when no images in content
    - test_cleanup_orphaned_images: orphaned images are cleaned up
    - test_delete_marks_images_for_deletion: article delete marks all images for file deletion
    - test_str_returns_title: __str__ returns title
    - test_create_with_defaults: Article.create generates public_id and saves
    - test_create_with_tags_and_authors: tags and authors assigned on create
    - test_create_auto_author: creating user auto-assigned as author
    - test_create_published: Article.create with published=True sets published_at
    - test_update_changes_title: Article.update modifies title and saves
    - test_update_publishes_draft: Article.update sets published_at when published=True
    - test_update_makes_draft: Article.update clears published_at when published=False
    - test_update_keeps_published_state: Article.update with published=True keeps published_at
    - test_update_replaces_tags: Article.update clears old tags and sets new ones
    - test_create_adds_tags_and_authors: adds tags and authors on create
    - test_update_clears_and_sets_tags_and_authors: clears existing and sets new tags/authors
    - test_media_summary_returns_empty_when_no_images: returns MediaSummary with empty images list
    - test_media_summary_returns_dict_with_images: returns MediaSummary instance
    - test_image_quota_exceeded_false_when_under: returns False when under quota
    - test_image_quota_exceeded_true_when_over: returns True when over quota
    - test_existing_image_bytes: returns total bytes of associated images
    - test_get_or_404_found: returns article when public_id exists
    - test_get_or_404_not_found: raises Http404 when public_id missing
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="author1", password="pass")
        self.tag = ArticleTag.objects.create(name="python", color="#3b82f6")

    def test_public_id_auto_generated(self) -> None:
        """public_id is auto-generated from title when left empty."""
        article = Article(title="Hello World", author=self.user)
        article.save()
        self.assertTrue(article.public_id)
        self.assertIn("hello-world", article.public_id)

    def test_public_id_preserved_if_set(self) -> None:
        """public_id is kept when explicitly provided."""
        article = Article(title="Test", public_id="custom-id-12345", author=self.user)
        article.save()
        self.assertEqual(article.public_id, "custom-id-12345")

    def test_first_image_extracted(self) -> None:
        """update_first_image sets first_image from content HTML."""
        article = Article(title="Test", public_id="first-img-test", author=self.user)
        article.save()
        img_file = _make_image()
        img = ArticleImage.objects.create(article=article, image=img_file)
        article.content = (
            f'<p><img src="/articles/api/download-image/{article.public_id}/{img.uuid_id}"></p>'
        )
        article.save()
        article.update_first_image()
        article.refresh_from_db()
        self.assertEqual(article.first_image, img.uuid_id)

    def test_first_image_cleared(self) -> None:
        """update_first_image clears first_image when content has no images."""
        article = Article(title="Test", public_id="clear-img-test", author=self.user)
        article.save()
        article.content = "<p>No images</p>"
        article.save()
        article.update_first_image()
        article.refresh_from_db()
        self.assertIsNone(article.first_image)

    def test_cleanup_orphaned_images(self) -> None:
        """cleanup_orphaned_images deletes images not referenced in content."""
        article = Article(title="Test", public_id="cleanup-test", author=self.user)
        article.save()
        img1 = ArticleImage.objects.create(article=article, image=_make_image("a.png"))
        ArticleImage.objects.create(article=article, image=_make_image("b.png"))
        article.content = (
            f'<img src="/articles/api/download-image/{article.public_id}/{img1.uuid_id}">'
        )
        article.save()
        article.cleanup_orphaned_images()
        self.assertEqual(ArticleImage.objects.filter(article_id=article.pk).count(), 1)
        self.assertTrue(ArticleImage.objects.filter(pk=img1.pk).exists())

    def test_delete_marks_images_for_deletion(self) -> None:
        """Article delete removes all associated images."""
        article = Article(title="Test", public_id="del-test", author=self.user)
        article.save()
        ArticleImage.objects.create(article=article, image=_make_image("x.png"))
        ArticleImage.objects.create(article=article, image=_make_image("y.png"))
        self.assertEqual(ArticleImage.objects.filter(article_id=article.pk).count(), 2)
        article.delete()
        self.assertEqual(ArticleImage.objects.filter(article_id=article.pk).count(), 0)

    def test_str_returns_title(self) -> None:
        """__str__ returns article title."""
        article = Article(title="My Title", public_id="str-test", author=self.user)
        article.save()
        self.assertEqual(str(article), "My Title")

    def test_create_with_defaults(self) -> None:
        """Article.create generates public_id and saves."""
        article = Article.create(
            title="Created Article",
            user=self.user,
        )
        self.assertTrue(article.public_id)
        self.assertEqual(article.title, "Created Article")
        self.assertIsNone(article.published_at)

    def test_create_with_tags_and_authors(self) -> None:
        """Tags and author assigned on create."""
        article = Article.create(
            title="Tagged",
            public_id="create-tagged",
            tag_names=["python"],
            author_id=self.user.pk,
            user=self.user,
        )
        self.assertIn(self.tag, article.tags.all())
        self.assertEqual(article.author, self.user)

    def test_create_auto_author(self) -> None:
        """Creating user auto-assigned as author."""
        article = Article.create(
            title="Auto Authored",
            public_id="create-auto-author",
            user=self.user,
        )
        self.assertEqual(article.author, self.user)

    def test_create_published(self) -> None:
        """Article.create with published=True sets published_at."""
        article = Article.create(
            title="Published",
            public_id="create-pub",
            published=True,
            user=self.user,
        )
        self.assertIsNotNone(article.published_at)

    def test_update_changes_title(self) -> None:
        """Article.update modifies title and saves."""
        article = Article.create(
            title="Original",
            public_id="update-title",
            user=self.user,
        )
        article.update(
            title="Updated",
            published=False,
            user=self.user,
        )
        article.refresh_from_db()
        self.assertEqual(article.title, "Updated")

    def test_update_publishes_draft(self) -> None:
        """Article.update sets published_at when published=True."""
        article = Article.create(
            title="Draft",
            public_id="update-pub",
            user=self.user,
        )
        self.assertIsNone(article.published_at)
        article.update(
            title="Draft",
            published=True,
            user=self.user,
        )
        article.refresh_from_db()
        self.assertIsNotNone(article.published_at)

    def test_update_makes_draft(self) -> None:
        """Article.update clears published_at when published=False."""
        article = Article.create(
            title="Published",
            public_id="update-draft",
            published=True,
            user=self.user,
        )
        article.update(
            title="Published",
            published=False,
            user=self.user,
        )
        article.refresh_from_db()
        self.assertIsNone(article.published_at)

    def test_update_keeps_published_state(self) -> None:
        """Article.update with published=True keeps published_at."""
        article = Article.create(
            title="Keep State",
            public_id="update-keep",
            published=True,
            user=self.user,
        )
        self.assertIsNotNone(article.published_at)
        article.update(
            title="Keep State",
            published=True,
            user=self.user,
        )
        article.refresh_from_db()
        self.assertIsNotNone(article.published_at)

    def test_update_replaces_tags(self) -> None:
        """Article.update clears old tags and sets new ones."""
        tag2 = ArticleTag.objects.create(name="django", color="#092e20")
        article = Article.create(
            title="Tag Swap",
            public_id="update-tags",
            tag_names=["python"],
            user=self.user,
        )
        self.assertIn(self.tag, article.tags.all())
        article.update(
            title="Tag Swap",
            published=False,
            tag_names=["django"],
            user=self.user,
        )
        self.assertNotIn(self.tag, article.tags.all())
        self.assertIn(tag2, article.tags.all())

    def test_create_adds_tags_and_authors(self) -> None:
        """Create adds tags and sets author via keyword args."""
        article = Article.create(
            title="Set Tags",
            public_id="set-tags-create",
            tag_names=["python"],
            author_id=self.user.pk,
            user=self.user,
        )
        self.assertIn(self.tag, article.tags.all())
        self.assertEqual(article.author, self.user)

    def test_update_clears_and_sets_tags_and_authors(self) -> None:
        """Update clears existing tags and sets new ones."""
        article = Article.create(
            title="Set Tags Update",
            public_id="set-tags-update",
            tag_names=["python"],
            user=self.user,
        )
        tag2 = ArticleTag.objects.create(name="django", color="#092e20")
        article.update(
            title="Set Tags Update",
            published=False,
            tag_names=["django"],
            user=self.user,
        )
        self.assertNotIn(self.tag, article.tags.all())
        self.assertIn(tag2, article.tags.all())

    def test_media_summary_returns_empty_when_no_images(self) -> None:
        """Returns MediaSummary with empty images list for article without images."""
        article = Article.create(
            title="No Images",
            public_id="media-none",
            user=self.user,
        )
        summary = article.media_summary("/articles")
        self.assertIsInstance(summary, MediaSummary)
        self.assertEqual(summary.total_bytes, 0)
        self.assertEqual(summary.images, [])

    def test_media_summary_returns_dict_with_images(self) -> None:
        """Returns MediaSummary with total_bytes, quota, images."""
        article = Article.create(
            title="With Images",
            public_id="media-yes",
            user=self.user,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())
        summary = article.media_summary("/articles")
        self.assertGreater(summary.total_bytes, 0)
        self.assertEqual(summary.quota_bytes, Article.CONTENT_IMAGES_TOTAL_BYTES)
        self.assertEqual(len(summary.images), 1)
        self.assertEqual(summary.images[0].uuid_id, str(img.uuid_id))
        self.assertIn("/articles/api/download-image/", summary.images[0].image_url)

    def test_image_quota_exceeded_false_when_under(self) -> None:
        """Returns False when under quota."""
        article = Article.create(
            title="Quota OK",
            public_id="quota-ok",
            user=self.user,
        )
        self.assertFalse(article.image_quota_exceeded(100))

    def test_image_quota_exceeded_true_when_over(self) -> None:
        """Returns True when over quota."""
        article = Article.create(
            title="Quota Over",
            public_id="quota-over",
            user=self.user,
        )
        img = ArticleImage.objects.create(article=article, image=_make_image())
        ArticleImage.objects.filter(pk=img.pk).update(size=Article.CONTENT_IMAGES_TOTAL_BYTES)
        self.assertTrue(article.image_quota_exceeded(1))

    def test_existing_image_bytes(self) -> None:
        """Returns total bytes of associated images."""
        article = Article.create(
            title="Bytes",
            public_id="img-bytes",
            user=self.user,
        )
        self.assertEqual(article.existing_image_bytes(), 0)
        img = ArticleImage.objects.create(article=article, image=_make_image())
        self.assertEqual(article.existing_image_bytes(), img.size)

    def test_get_or_404_found(self) -> None:
        """Returns article when public_id exists."""
        article = Article.create(
            title="Found",
            public_id="get-404-yes",
            user=self.user,
        )
        self.assertEqual(Article.get_or_404("get-404-yes"), article)

    def test_get_or_404_not_found(self) -> None:
        """Raises Http404 when public_id missing."""
        with self.assertRaises(Http404):
            Article.get_or_404("nonexistent")


class ArticleSubscriberModelTests(TestCase):
    """Article.subscribers M2M unit tests.

    Tests for the subscribers M2M and its no-reverse-relation config.

    Common setup: one author User, one subscriber User, one Article.
    - test_subscribers_add_remove: add then remove round-trips membership
    - test_subscribers_query_from_article: filter subscribers via article.subscribers
    - test_subscribers_no_reverse_relation: related_name is "+", no reverse accessor on User
    - test_articles_a_user_subscribes_to: reverse lookup via Article.objects.filter(subscribers=...)
    """

    def setUp(self) -> None:
        self.author = User.objects.create_user(username="author", password="pass")
        self.subscriber = User.objects.create_user(username="sub", password="pass")
        self.article = Article.create(
            title="Subbed",
            public_id="sub-test",
            user=self.author,
        )

    def test_subscribers_add_remove(self) -> None:
        """add/remove round-trips membership."""
        self.article.subscribers.add(self.subscriber)
        self.assertIn(self.subscriber, self.article.subscribers.all())
        self.article.subscribers.remove(self.subscriber)
        self.assertNotIn(self.subscriber, self.article.subscribers.all())

    def test_subscribers_query_from_article(self) -> None:
        """Filter subscribers via article.subscribers."""
        self.article.subscribers.add(self.subscriber)
        self.assertTrue(self.article.subscribers.filter(pk=self.subscriber.pk).exists())
        other = User.objects.create_user(username="other", password="pass")
        self.assertFalse(self.article.subscribers.filter(pk=other.pk).exists())

    def test_subscribers_no_reverse_relation(self) -> None:
        """related_name='+' creates no reverse accessor from User to subscribers."""
        # Django would name the reverse accessor "article_set"; with related_name="+"
        # it is not created, so the User side has no way back to Article.subscribers.
        self.assertFalse(hasattr(self.subscriber, "article_set"))

    def test_articles_a_user_subscribes_to(self) -> None:
        """Reverse lookup goes through Article.objects.filter(subscribers=user)."""
        self.article.subscribers.add(self.subscriber)
        subscribed = Article.objects.filter(subscribers=self.subscriber)
        self.assertIn(self.article, subscribed)


class ArticleNotificationModelTests(TestCase):
    """ArticleNotification unique-constraint tests.

    Common setup: one User.
    - test_unique_per_comment_and_user: a duplicate (comment_public_id, user) raises IntegrityError
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="sub", password="pass")

    def test_unique_per_comment_and_user(self) -> None:
        """A second notification for the same (comment, user) raises IntegrityError."""
        ArticleNotification.objects.create(
            article_public_id="a1", comment_public_id="c1", user=self.user, content={}
        )
        with self.assertRaises(IntegrityError):
            ArticleNotification.objects.create(
                article_public_id="a1", comment_public_id="c1", user=self.user, content={}
            )


class ArticleTagModelTests(TestCase):
    """ArticleTag model unit tests.

    - test_str_returns_name: __str__ returns tag name
    - test_unique_name: duplicate name raises IntegrityError
    - test_create_classmethod: ArticleTag.create validates and saves
    - test_create_duplicate_raises_validation_error: duplicate name raises ValidationError
    - test_update_instance_method: ArticleTag.update changes name and color
    - test_update_validates_fields: update calls full_clean
    - test_get_or_404_found: returns tag when name exists
    - test_get_or_404_not_found: raises Http404 when name missing
    """

    def test_str_returns_name(self) -> None:
        tag = ArticleTag.objects.create(name="python", color="#3b82f6")
        self.assertEqual(str(tag), "python")

    def test_unique_name(self) -> None:
        """Duplicate tag name raises IntegrityError."""
        ArticleTag.objects.create(name="unique-tag", color="#ff0000")
        with self.assertRaises(IntegrityError):
            ArticleTag.objects.create(name="unique-tag", color="#00ff00")

    def test_create_classmethod(self) -> None:
        """ArticleTag.create validates and saves."""
        tag = ArticleTag.create(name="django", color="#092e20")
        self.assertEqual(tag.name, "django")
        self.assertEqual(tag.color, "#092e20")
        self.assertTrue(ArticleTag.objects.filter(name="django").exists())

    def test_create_duplicate_raises_validation_error(self) -> None:
        """Duplicate name raises ValidationError from full_clean."""
        ArticleTag.create(name="dup", color="#000000")
        with self.assertRaises(ValidationError):
            ArticleTag.create(name="dup", color="#ffffff")

    def test_update_instance_method(self) -> None:
        """ArticleTag.update changes name and color."""
        tag = ArticleTag.objects.create(name="old", color="#111111")
        tag.update(name="new", color="#222222")
        tag.refresh_from_db()
        self.assertEqual(tag.name, "new")
        self.assertEqual(tag.color, "#222222")

    def test_update_validates_fields(self) -> None:
        """Update calls full_clean, rejecting invalid data."""
        tag = ArticleTag.objects.create(name="valid", color="#333333")
        with self.assertRaises(ValidationError):
            tag.update(name="bad color", color="not-a-hex")

    def test_get_or_404_found(self) -> None:
        """Returns tag when name exists."""
        tag = ArticleTag.objects.create(name="found", color="#444444")
        self.assertEqual(ArticleTag.get_or_404("found"), tag)

    def test_get_or_404_not_found(self) -> None:
        """Raises Http404 when name missing."""
        with self.assertRaises(Http404):
            ArticleTag.get_or_404("nonexistent")


class ArticleImageModelTests(TestCase):
    """ArticleImage model unit tests.

    - test_size_set_on_save: size is set from image file on save
    - test_delete_safely: delete_safely removes the image record
    """

    def setUp(self) -> None:
        user = User.objects.create_user(username="imgtest", password="pass")
        self.article = Article(title="Test", public_id="img-test", author=user)
        self.article.save()

    def test_size_set_on_save(self) -> None:
        """Image size is automatically set from file on save."""
        img_file = _make_image()
        img = ArticleImage.objects.create(article=self.article, image=img_file)
        self.assertGreater(img.size, 0)

    def test_delete_safely(self) -> None:
        """delete_safely removes the image record."""
        img = ArticleImage.objects.create(article=self.article, image=_make_image())
        img.delete_safely()
        self.assertFalse(ArticleImage.objects.filter(pk=img.pk).exists())


class ArticleHistoryModelTests(TestCase):
    """ArticleHistory model unit tests.

    Tests for recording created/edited/deleted actions, field-level diffs,
    and pydantic round-trips.

    Common setup: one User and one ArticleTag instance.
    - test_record_created: creates entry with action="created", all fields present old==new
    - test_record_edited_detects_title_change: records title change, other fields absent
    - test_record_edited_detects_content_change: records content change
    - test_record_edited_detects_tag_change: records tag change with name+color
    - test_record_edited_detects_author_change: records author change with id+title+url
    - test_record_edited_detects_published_date_change: records published_at change
    - test_record_edited_no_changes: all change fields absent when nothing changed
    - test_record_deleted: creates entry with action="deleted", empty changes
    - test_changes_roundtrip: pydantic serialization/deserialization for _changes JSON field
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="editor", password="pass")
        self.tag = ArticleTag.objects.create(name="python", color="#3b82f6")

    def test_record_created(self) -> None:
        """Creates entry with action='created', all fields present old==new."""
        article = Article.create(
            title="Test",
            public_id="hist-created",
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="created")
        self.assertEqual(entry.action, "created")
        d = entry.to_article_history_entry_item()
        assert d.changes.title is not None
        self.assertEqual(d.changes.title.old, "Test")
        self.assertEqual(d.changes.title.new, "Test")
        assert d.changes.public_id is not None
        self.assertEqual(d.changes.public_id.old, article.public_id)
        self.assertEqual(d.changes.public_id.new, article.public_id)
        assert d.changes.content is not None
        self.assertEqual(d.changes.content.old, "")
        self.assertEqual(d.changes.content.new, "")
        assert d.changes.published_date is not None

    def test_record_edited_detects_title_change(self) -> None:
        """Records title change, other fields absent."""
        article = Article.create(
            title="Old Title",
            public_id="hist-edit-title",
            user=self.user,
        )
        ArticleHistory.objects.filter(article=article).delete()
        article.update(
            title="New Title",
            published=False,
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="edited")
        d = entry.to_article_history_entry_item()
        assert d.changes.title is not None
        self.assertEqual(d.changes.title.old, "Old Title")
        self.assertEqual(d.changes.title.new, "New Title")
        self.assertIsNone(d.changes.public_id)
        self.assertIsNone(d.changes.content)
        self.assertIsNone(d.changes.tags)
        self.assertIsNone(d.changes.author)

    def test_record_edited_detects_content_change(self) -> None:
        """Records content change, same as title but for content."""
        article = Article.create(
            title="Test",
            public_id="hist-edit-content",
            content="old",
            user=self.user,
        )
        ArticleHistory.objects.filter(article=article).delete()
        article.update(
            title="Test",
            published=False,
            content="new content",
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="edited")
        d = entry.to_article_history_entry_item()
        assert d.changes.content is not None
        self.assertEqual(d.changes.content.old, "old")
        self.assertEqual(d.changes.content.new, "new content")
        self.assertIsNone(d.changes.title)

    def test_record_edited_detects_tag_change(self) -> None:
        """Records tag change with name+color."""
        article = Article.create(
            title="Test",
            public_id="hist-edit-tag",
            tag_names=["python"],
            user=self.user,
        )
        ArticleHistory.objects.filter(article=article).delete()
        ArticleTag.objects.create(name="django", color="#092e20")
        article.update(
            title="Test",
            published=False,
            tag_names=["django"],
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="edited")
        d = entry.to_article_history_entry_item()
        assert d.changes.tags is not None
        self.assertEqual(len(d.changes.tags.old), 1)
        self.assertEqual(d.changes.tags.old[0].name, "python")
        self.assertEqual(d.changes.tags.old[0].color, "#3b82f6")
        self.assertEqual(len(d.changes.tags.new), 1)
        self.assertEqual(d.changes.tags.new[0].name, "django")

    def test_record_edited_detects_author_change(self) -> None:
        """Records author change with id+title."""
        user2 = User.objects.create_user(username="writer", first_name="Jane", last_name="Doe")
        article = Article.create(
            title="Test",
            public_id="hist-edit-author",
            author_id=self.user.pk,
            user=self.user,
        )
        ArticleHistory.objects.filter(article=article).delete()
        article.update(
            title="Test",
            published=False,
            author_id=user2.pk,
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="edited")
        d = entry.to_article_history_entry_item()
        assert d.changes.author is not None
        self.assertEqual(d.changes.author.old.id, self.user.pk)
        self.assertEqual(d.changes.author.new.id, user2.pk)

    def test_record_edited_detects_published_date_change(self) -> None:
        """Records published_at change."""
        article = Article.create(
            title="Test",
            public_id="hist-edit-pub",
            user=self.user,
        )
        ArticleHistory.objects.filter(article=article).delete()
        self.assertIsNone(article.published_at)
        article.update(
            title="Test",
            published=True,
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="edited")
        d = entry.to_article_history_entry_item()
        assert d.changes.published_date is not None
        self.assertIsNone(d.changes.published_date.old)
        self.assertIsNotNone(d.changes.published_date.new)
        self.assertIsNotNone(d.changes.published_date)

    def test_record_edited_no_changes(self) -> None:
        """All change fields absent when nothing changed."""
        article = Article.create(
            title="Same",
            public_id="hist-no-change",
            user=self.user,
        )
        ArticleHistory.objects.filter(article=article).delete()
        article.update(
            title="Same",
            published=False,
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="edited")
        d = entry.to_article_history_entry_item()
        self.assertIsNone(d.changes.title)
        self.assertIsNone(d.changes.content)
        self.assertIsNone(d.changes.tags)
        self.assertIsNone(d.changes.author)
        self.assertIsNone(d.changes.published_date)

    def test_record_deleted(self) -> None:
        """Creates entry with action='deleted', empty changes."""
        article = Article.create(
            title="Delete Me",
            public_id="hist-deleted",
            user=self.user,
        )
        public_id_copy = article.public_id
        ArticleHistory.objects.filter(article=article).delete()
        article.delete(user=self.user)
        entry = ArticleHistory.objects.get(article_public_id_copy=public_id_copy, action="deleted")
        self.assertEqual(entry.action, "deleted")
        d = entry.to_article_history_entry_item()
        self.assertIsNone(d.changes.title)
        self.assertIsNone(d.changes.content)
        self.assertIsNone(entry.article)
        self.assertEqual(entry.article_public_id_copy, public_id_copy)

    def test_changes_roundtrip(self) -> None:
        """Pydantic round-trip for _changes JSON field."""
        article = Article.create(
            title="Roundtrip",
            public_id="hist-roundtrip",
            tag_names=["python"],
            user=self.user,
        )
        entry = ArticleHistory.objects.get(article=article, action="created")
        d = entry.to_article_history_entry_item()
        assert d.changes.tags is not None
        self.assertEqual(len(d.changes.tags.old), 1)
        self.assertEqual(d.changes.tags.old[0].name, "python")
        self.assertEqual(d.changes.tags.old[0].color, "#3b82f6")
        assert d.changes.author is not None
        self.assertEqual(d.changes.author.old.id, self.user.pk)


class ArticleCommentModelTests(TestCase):
    """ArticleComment model unit tests.

    Tests for comment CRUD, soft delete, update with timeout,
    permission checks, and serialization.

    Common setup: one editor (staff), one participant (non-staff), one Article.
    - test_create_comment: creates comment, verifies fields
    - test_soft_delete: clears content, sets deleted_by and deleted_at
    - test_update_content: updates content, sets updated_at
    - test_update_content_after_one_hour_fails: raises ValueError after 1 hour
    - test_update_content_by_different_user_fails: raises ValueError for non-author
    - test_update_deleted_comment_fails: raises ValueError for deleted comment
    - test_can_soft_delete_comment_by_commenter: commenter can soft delete own
    - test_can_soft_delete_comment_by_article_author: article author can soft delete
    - test_can_soft_delete_comment_by_editor: editor can soft delete
    - test_cannot_soft_delete_comment_by_random_user: random user gets denied
    - test_cannot_create_comment_when_disabled: is_commenting_enabled=False blocks creation
    - test_for_article_active_comment: active comment returned as ArticleCommentItem
    - test_for_article_deleted_comment: soft-deleted returned as DeletedArticleCommentItem
    - test_for_article_updated_comment: updated comment has updated_at set
    - test_for_article_deleted_user: deleted user shows [deleted] profile
    - test_for_article_returns_mixed: returns both active and deleted items
    - test_for_article_no_n_plus_1: comment list uses 2 queries regardless of count
    """

    def setUp(self) -> None:
        self.editor = User.objects.create_user(
            username="editor", password="pass", is_staff=True, is_superuser=True
        )
        self.participant = User.objects.create_user(username="participant", password="pass")
        self.random_user = User.objects.create_user(username="random", password="pass")
        self.article = Article.create(
            title="Commented Article",
            public_id="comment-test",
            user=self.editor,
        )

    def test_create_comment(self) -> None:
        """Creates comment, verifies fields."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Hello world",
            commented_by=self.participant,
        )
        self.assertEqual(comment.content, "Hello world")
        self.assertEqual(comment.article, self.article)
        self.assertEqual(comment.commented_by, self.participant)
        self.assertIsNotNone(comment.commented_at)
        self.assertIsNone(comment.deleted_at)
        self.assertIsNone(comment.updated_at)

    def test_soft_delete(self) -> None:
        """Clears content, sets deleted_by and deleted_at."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="To delete",
            commented_by=self.participant,
        )
        comment.soft_delete(self.participant)
        comment.refresh_from_db()
        self.assertEqual(comment.content, "")
        self.assertEqual(comment.deleted_by, self.participant)
        self.assertIsNotNone(comment.deleted_at)

    def test_update_content(self) -> None:
        """Updates content, sets updated_at."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Original",
            commented_by=self.participant,
        )
        comment.update_content(self.participant, "Updated")
        comment.refresh_from_db()
        self.assertEqual(comment.content, "Updated")
        self.assertIsNotNone(comment.updated_at)

    def test_update_content_after_one_hour_fails(self) -> None:
        """Raises ValueError after 1 hour."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Old",
            commented_by=self.participant,
        )

        ArticleComment.objects.filter(pk=comment.pk).update(
            commented_at=tz.now() - timedelta(hours=2),
        )
        comment.refresh_from_db()
        with self.assertRaises(ValueError):
            comment.update_content(self.participant, "New")

    def test_update_content_by_different_user_fails(self) -> None:
        """can_update_comment returns False for non-author."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Theirs",
            commented_by=self.participant,
        )
        self.assertFalse(comment.can_update_comment(self.random_user))

    def test_update_deleted_comment_fails(self) -> None:
        """Raises ValueError for deleted comment."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Gone",
            commented_by=self.participant,
        )
        comment.soft_delete(self.participant)
        with self.assertRaises(ValueError):
            comment.update_content(self.participant, "Try")

    def test_can_soft_delete_comment_by_commenter(self) -> None:
        """Commenter can soft delete own comment."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Mine",
            commented_by=self.participant,
        )
        self.assertTrue(comment.can_soft_delete_comment(self.participant, self.article))

    def test_can_soft_delete_comment_by_article_author(self) -> None:
        """Article author can soft delete any comment on their article."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="On my article",
            commented_by=self.participant,
        )
        self.assertTrue(comment.can_soft_delete_comment(self.editor, self.article))

    def test_can_soft_delete_comment_by_editor(self) -> None:
        """Editor can soft delete any comment."""
        other_author = User.objects.create_user(username="other_author", password="pass")
        other_article = Article.create(
            title="Other Article",
            public_id="comment-test-other",
            user=other_author,
        )
        comment = ArticleComment.objects.create(
            article=other_article,
            content="On other article",
            commented_by=self.participant,
        )
        self.assertTrue(comment.can_soft_delete_comment(self.editor, other_article))

    def test_cannot_soft_delete_comment_by_random_user(self) -> None:
        """Random user gets denied."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Not yours",
            commented_by=self.participant,
        )
        self.assertFalse(comment.can_soft_delete_comment(self.random_user, self.article))

    def test_cannot_create_comment_when_disabled(self) -> None:
        """is_commenting_enabled=False blocks creation."""
        self.article.is_commenting_enabled = False
        self.article.save()
        self.assertFalse(self.article.is_commenting_enabled)

    def test_for_article_active_comment(self) -> None:
        """Active comment returned as ArticleCommentItem with content."""
        ArticleComment.objects.create(
            article=self.article,
            content="Hello",
            commented_by=self.participant,
        )
        items = ArticleComment.for_article(self.article)
        self.assertEqual(len(items), 1)
        item = items[0]
        assert isinstance(item, ArticleCommentItem)
        self.assertEqual(item.content, "Hello")
        self.assertEqual(item.commented_by.id, self.participant.pk)
        self.assertIsNotNone(item.commented_at)
        self.assertIsNone(item.updated_at)

    def test_for_article_deleted_comment(self) -> None:
        """Soft-deleted comment returned as DeletedArticleCommentItem without content."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Gone",
            commented_by=self.participant,
        )
        comment.soft_delete(self.participant)
        items = ArticleComment.for_article(self.article)
        self.assertEqual(len(items), 1)
        item = items[0]
        assert isinstance(item, DeletedArticleCommentItem)
        self.assertTrue(item.is_deleted)
        self.assertFalse(hasattr(item, "content"))

    def test_for_article_updated_comment(self) -> None:
        """Updated comment has updated_at set."""
        comment = ArticleComment.objects.create(
            article=self.article,
            content="Original",
            commented_by=self.participant,
        )
        comment.update_content(self.participant, "Edited")
        items = ArticleComment.for_article(self.article)
        self.assertEqual(len(items), 1)
        item = items[0]
        assert isinstance(item, ArticleCommentItem)
        self.assertEqual(item.content, "Edited")
        self.assertIsNotNone(item.updated_at)

    def test_for_article_deleted_user(self) -> None:
        """Comment with deleted user shows [deleted] profile."""
        ArticleComment.objects.create(
            article=self.article,
            content="Orphan",
            commented_by=self.participant,
        )
        self.participant.delete()
        items = ArticleComment.for_article(self.article)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].commented_by.title, "[deleted]")

    def test_for_article_returns_mixed(self) -> None:
        """for_article returns list with both active and deleted items."""
        ArticleComment.objects.create(
            article=self.article, content="Active", commented_by=self.participant
        )
        deleted = ArticleComment.objects.create(
            article=self.article, content="Will delete", commented_by=self.participant
        )
        deleted.soft_delete(self.participant)
        items = ArticleComment.for_article(self.article)
        self.assertEqual(len(items), 2)
        types = {type(i) for i in items}
        self.assertIn(ArticleCommentItem, types)
        self.assertIn(DeletedArticleCommentItem, types)

    def test_for_article_no_n_plus_1(self) -> None:
        """Commenter profiles are bulk-fetched: query count is constant per article."""
        commenters = [User.objects.create_user(username=f"u{n}", password="pass") for n in range(5)]
        for commenter in commenters:
            ArticleComment.objects.create(
                article=self.article, content="Hi", commented_by=commenter
            )
        with self.assertNumQueries(2):
            items = ArticleComment.for_article(self.article)
        self.assertEqual(len(items), 5)
