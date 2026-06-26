import re
import uuid
from collections.abc import Callable
from typing import Annotated, Any, Literal

from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Prefetch, Q, QuerySet
from django.http import FileResponse, HttpRequest, HttpResponse
from inertia import InertiaResponse
from ninja import (
    NinjaAPI,
    Query,
    Router,
)
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, StringConstraints, field_validator

from djangoapp.errors import ApiError, register_api_error_handlers
from djangoapp.models.base import (
    Article,
    ArticleComment,
    ArticleCommentItem,
    ArticleHistory,
    ArticleHistoryEntryItem,
    ArticleImage,
    ArticleNotification,
    ArticleTag,
    DeletedArticleCommentItem,
    MediaSummary,
    User,
    UserProfile,
)
from djangoapp.utils import human_size, sanitize_html, strip_html

ARTICLES_PATH_PREFIX = "/articles"


def article_editors[T: Callable[[], QuerySet[User]]](fn: T) -> T:
    """Register the editors resolver (a ``() -> QuerySet[User]`` callable).

    Used as ``@article_editors`` in the app's ``views/app.py``. The callable
    decides who counts as an editor; editorship gates article creation, tag
    management, the unpublished filter, and editing/deleting any article.
    """
    Article.set_editors(fn)
    return fn


def article_participants[T: Callable[[], QuerySet[User]]](fn: T) -> T:
    """Register the participants resolver (a ``() -> QuerySet[User]`` callable).

    Used as ``@article_participants`` in the app's ``views/app.py``. The
    callable decides who counts as a participant; participants may comment on
    and subscribe to published articles, be assigned as an article's author,
    and always see their own drafts in the list.
    """
    Article.set_participants(fn)
    return fn


def is_inertia_request(request: HttpRequest) -> bool:
    return bool(request.headers.get("X-Inertia"))


def auth_user(request: HttpRequest) -> User | None:
    """Return the authenticated user, or None for anonymous."""
    if request.user.is_authenticated:
        return request.user
    return None


def user_or_404(request: HttpRequest) -> User:
    if not request.user.is_authenticated:
        raise ApiError(404, "Authentication required")
    return request.user


class ArticleTagItem(PydanticBaseModel):
    name: str
    color: str


class ArticleListItem(PydanticBaseModel):
    public_id: str
    title: str
    excerpt: str
    cover_image_url: str | None = None
    tags: list[ArticleTagItem]
    author: UserProfile
    published_at: str | None = None


class ArticleDetailsItem(PydanticBaseModel):
    public_id: str
    title: str
    content: str
    published_at: str | None = None
    tags: list[ArticleTagItem]
    author: UserProfile
    is_commenting_enabled: bool = True


class ArticleListPagination(PydanticBaseModel):
    page: int
    total_pages: int
    total_count: int


class UploadImageResponse(PydanticBaseModel):
    url: str


class SearchTagsResponse(PydanticBaseModel):
    tags: list[ArticleTagItem]


class SearchAuthorsResponse(PydanticBaseModel):
    authors: list[UserProfile]


class MessageResponse(PydanticBaseModel):
    id: str = ""
    message: str = ""


class TagWithCount(PydanticBaseModel):
    name: str
    color: str
    article_count: int


class ArticleListFilters(PydanticBaseModel):
    author: list[int] = Field(default_factory=list)
    tag: list[str] = Field(default_factory=list)
    unpublished: bool = False
    page: int = Field(default=1, ge=1)
    sort_by: Literal["published_at", "latest_comment"] = "published_at"


_StrippedStr = Annotated[str, StringConstraints(strip_whitespace=True)]


class TagSchema(PydanticBaseModel):
    name: _StrippedStr = Field(min_length=3)
    color: _StrippedStr

    @field_validator("name")
    @classmethod
    def _name_no_spaces(cls, v: str) -> str:
        if " " in v:
            msg = "Name cannot contain spaces"
            raise ValueError(msg)
        return v

    @field_validator("color")
    @classmethod
    def _color_hex(cls, v: str) -> str:
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            msg = "Color must be a hex code like #ff0000"
            raise ValueError(msg)
        return v


class _ArticleSubmitBase(PydanticBaseModel):
    title: str = Field(min_length=1)
    public_id: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)


class ArticleCreateSchema(_ArticleSubmitBase):
    published: bool = False
    author_id: int | None = None
    is_commenting_enabled: bool = True


class ArticleUpdateSchema(_ArticleSubmitBase):
    published: bool
    author_id: int | None = None
    is_commenting_enabled: bool = True


class ArticleListProps(PydanticBaseModel):
    path_prefix: str
    user: UserProfile | None = None
    is_editor: bool = False
    articles: list[ArticleListItem]
    pagination: ArticleListPagination
    filters: ArticleListFilters
    selected_authors: list[UserProfile] = Field(default_factory=list)
    selected_tags: list[ArticleTagItem] = Field(default_factory=list)


class ArticleDetailsProps(PydanticBaseModel):
    path_prefix: str
    user: UserProfile | None = None
    is_editor: bool = False
    article: ArticleDetailsItem
    media_summary: MediaSummary | None = None
    can_edit: bool = False
    can_delete: bool = False
    cover_image_url: str | None = None
    history_count: int = 0
    is_commenting_enabled: bool = True
    is_subscribed: bool = False


class HeadTags(PydanticBaseModel):
    title: str | None = None
    type: str | None = None
    description: str | None = None
    cover_image_url: str | None = None


class ArticleCreateProps(PydanticBaseModel):
    path_prefix: str
    user: UserProfile | None = None
    is_editor: bool = False
    article: None = None
    media_summary: None = None


class ArticleEditProps(PydanticBaseModel):
    path_prefix: str
    user: UserProfile | None = None
    is_editor: bool = False
    article: ArticleDetailsItem
    media_summary: MediaSummary


class ArticleHistoryProps(PydanticBaseModel):
    path_prefix: str
    user: UserProfile | None = None
    is_editor: bool = False
    article_public_id: str
    article_title: str
    entries: list[ArticleHistoryEntryItem]


class CommentCreateSchema(PydanticBaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return sanitize_html(v)


class CommentUpdateSchema(PydanticBaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return sanitize_html(v)


class ArticleCommentsResponse(PydanticBaseModel):
    comments: list[ArticleCommentItem | DeletedArticleCommentItem]
    can_comment: bool = False
    can_delete_any: bool = False
    user_id: int | None = None


def build_cover_image_url(public_id: str, first_image: uuid.UUID | None) -> str | None:
    if first_image is None:
        return None
    return f"{ARTICLES_PATH_PREFIX}/api/download-image/{public_id}/{first_image}"


def can_download_image_or_404(user: User | None, article: Article) -> None:
    if article.published_at is not None:
        return
    if user is not None and Article.can_be_edited_by(user, article):
        return
    raise ApiError(404, "Article not found")


def viewable_or_404(user: User | None, article: Article) -> None:
    """404 unless the user may view this article.

    Published articles are viewable by anyone; drafts are viewable only by
    editors and the article's author. Used by the details page and the
    comment list. Subscribing and commenting are blocked on drafts entirely
    (see published_or_404).
    """
    if article.published_at is not None:
        return
    if user is not None and Article.can_be_edited_by(user, article):
        return
    raise ApiError(404, "Article not found")


def published_or_404(article: Article) -> None:
    """404 for draft articles — drafts can't be subscribed to or commented on."""
    if article.published_at is None:
        raise ApiError(404, "Article not found")


def editor_or_404(request: HttpRequest) -> User:
    user = user_or_404(request)
    if not Article.is_editor(user):
        raise ApiError(404, "Article not found")
    return user


def article_og_head(props: ArticleDetailsProps) -> HeadTags:
    return HeadTags(
        title=props.article.title,
        type="article",
        description=strip_html(props.article.content)[:200] if props.article.content else None,
        cover_image_url=props.cover_image_url,
    )


ARTICLE_DETAILS_NOSCRIPT_TEMPLATE = "articles/article_details_static.html"


articles_router = Router()


@articles_router.get("/list", response=None, include_in_schema=False)
def list_page(request: HttpRequest, filters: Query[ArticleListFilters]) -> HttpResponse:
    user = auth_user(request)
    editor = Article.is_editor(user) if user is not None else False

    qs = Article.objects.all()

    if editor and filters.unpublished:
        pass
    else:
        visible = Q(published_at__isnull=False)
        if user is not None and Article.is_participant(user):
            visible |= Q(author_id=user.pk)
        qs = qs.filter(visible)

    if filters.author:
        qs = qs.filter(author_id__in=filters.author).distinct()

    if filters.tag:
        qs = qs.filter(tags__name__in=filters.tag).distinct()

    if filters.sort_by == "latest_comment":
        qs = qs.annotate(latest_comment_at=Max("comments__commented_at"))
        qs = qs.order_by(
            F("latest_comment_at").desc(nulls_last=True),
            "-published_at",
            "-id",
        )
    else:
        qs = qs.order_by("-published_at", "-id")
    qs = qs.prefetch_related(
        "tags",
        Prefetch("author", queryset=User.objects.all()),
    )

    paginator = Paginator(qs, 25, orphans=5)
    page = paginator.get_page(filters.page)

    articles_list: list[ArticleListItem] = []
    for article in page.object_list:
        tags = list(article.tags.all())
        excerpt = strip_html(article.content)[:200]
        item = ArticleListItem(
            public_id=article.public_id,
            title=article.title,
            excerpt=excerpt,
            cover_image_url=build_cover_image_url(article.public_id, article.first_image),
            tags=[ArticleTagItem(name=t.name, color=t.color) for t in tags],
            author=Article.user_profile(article.author),
            published_at=(article.published_at.isoformat() if article.published_at else None),
        )
        articles_list.append(item)

    pagination = ArticleListPagination(
        page=page.number,
        total_pages=paginator.num_pages,
        total_count=paginator.count,
    )

    user_item = Article.user_profile(user) if user is not None else None
    selected_authors: list[UserProfile] = []
    if filters.author:
        author_qs = User.objects.filter(pk__in=filters.author)
        selected_authors = [Article.user_profile(u) for u in author_qs]
    selected_tags: list[ArticleTagItem] = []
    if filters.tag:
        selected_tags = [
            ArticleTagItem(name=t.name, color=t.color)
            for t in ArticleTag.objects.filter(name__in=filters.tag)
        ]
    props = ArticleListProps(
        path_prefix=ARTICLES_PATH_PREFIX,
        user=user_item,
        is_editor=editor,
        articles=articles_list,
        pagination=pagination,
        filters=filters,
        selected_authors=selected_authors,
        selected_tags=selected_tags,
    )

    return InertiaResponse(request, "ArticleList", {"props": props.model_dump()})


@articles_router.get("/id/{public_id}", response=None, include_in_schema=False)
def details_page(request: HttpRequest, public_id: str) -> HttpResponse:
    article = Article.get_or_404_with_annotations(public_id)
    user = auth_user(request)

    viewable_or_404(user, article)

    tags = list(article.tags.all())
    author_profile = Article.user_profile(article.author)

    media_summary = None
    can_edit_flag = False
    if user is not None:
        can_edit_flag = Article.can_be_edited_by(user, article)
        if can_edit_flag:
            media_summary = article.media_summary(ARTICLES_PATH_PREFIX)

    article_item = ArticleDetailsItem(
        public_id=article.public_id,
        title=article.title,
        content=article.content,
        published_at=(article.published_at.isoformat() if article.published_at else None),
        tags=[ArticleTagItem(name=t.name, color=t.color) for t in tags],
        author=author_profile,
        is_commenting_enabled=article.is_commenting_enabled,
    )
    user_item = Article.user_profile(user) if user is not None else None
    history_count = 0
    if user is not None and can_edit_flag:
        history_count = ArticleHistory.objects.filter(article=article).count()
    is_subscribed = bool(user is not None and article.subscribers.filter(pk=user.pk).exists())
    props = ArticleDetailsProps(
        path_prefix=ARTICLES_PATH_PREFIX,
        user=user_item,
        is_editor=Article.is_editor(user) if user is not None else False,
        article=article_item,
        media_summary=media_summary,
        can_edit=can_edit_flag,
        can_delete=can_edit_flag,
        cover_image_url=build_cover_image_url(article.public_id, article.first_image),
        history_count=history_count,
        is_commenting_enabled=article.is_commenting_enabled,
        is_subscribed=is_subscribed,
    )

    template_data: dict[str, Any] = {}
    if not is_inertia_request(request):
        template_data = {
            "head_tags": article_og_head(props),
            "noscript_template_name": ARTICLE_DETAILS_NOSCRIPT_TEMPLATE,
            "noscript_template_data": {"article": props.article},
        }
    return InertiaResponse(
        request,
        "ArticleDetails",
        {"props": props.model_dump()},
        template_data=template_data,
    )


@articles_router.get("/create", response=None, include_in_schema=False)
def create_page(request: HttpRequest) -> HttpResponse:
    user = editor_or_404(request)

    props = ArticleCreateProps(
        path_prefix=ARTICLES_PATH_PREFIX,
        user=Article.user_profile(user),
        is_editor=True,
    )
    return InertiaResponse(request, "ArticleCreate", {"props": props.model_dump()})


@articles_router.post("/create")
def create_submit(request: HttpRequest, payload: ArticleCreateSchema) -> MessageResponse:
    user = editor_or_404(request)

    article = Article.create(
        title=payload.title,
        public_id=payload.public_id,
        content=payload.content,
        published=payload.published,
        tag_names=payload.tags,
        author_id=payload.author_id,
        is_commenting_enabled=payload.is_commenting_enabled,
        user=user,
    )

    return MessageResponse(id=article.public_id)


@articles_router.get("/edit/{public_id}", response=None, include_in_schema=False)
def edit_page(request: HttpRequest, public_id: str) -> HttpResponse:
    article = Article.get_or_404_with_annotations(public_id)
    user = user_or_404(request)
    if not Article.can_be_edited_by(user, article):
        raise ApiError(404, "Article not found")

    media_summary = article.media_summary(ARTICLES_PATH_PREFIX)

    tags = list(article.tags.all())
    author_profile = Article.user_profile(article.author)

    article_item = ArticleDetailsItem(
        public_id=article.public_id,
        title=article.title,
        content=article.content,
        published_at=(article.published_at.isoformat() if article.published_at else None),
        tags=[ArticleTagItem(name=t.name, color=t.color) for t in tags],
        author=author_profile,
    )
    props = ArticleEditProps(
        path_prefix=ARTICLES_PATH_PREFIX,
        user=Article.user_profile(user),
        is_editor=Article.is_editor(user),
        article=article_item,
        media_summary=media_summary,
    )
    return InertiaResponse(request, "ArticleEdit", {"props": props.model_dump()})


@articles_router.post("/edit/{public_id}")
def edit_submit(
    request: HttpRequest, public_id: str, payload: ArticleUpdateSchema
) -> MessageResponse:
    article = Article.get_or_404_with_annotations(public_id)
    user = user_or_404(request)
    if not Article.can_be_edited_by(user, article):
        raise ApiError(404, "Article not found")

    author_id = payload.author_id if (payload.author_id and Article.is_editor(user)) else None
    article.update(
        title=payload.title,
        public_id=payload.public_id,
        content=payload.content,
        published=payload.published,
        tag_names=payload.tags,
        author_id=author_id,
        is_commenting_enabled=payload.is_commenting_enabled,
        user=user,
    )

    return MessageResponse(id=article.public_id)


@articles_router.post("/delete/{public_id}")
def delete_submit(request: HttpRequest, public_id: str) -> MessageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)
    if not Article.can_be_edited_by(user, article):
        raise ApiError(404, "Article not found")

    article.delete(user=user)
    return MessageResponse(message="Article deleted")


@articles_router.get("/history/{public_id}", response=None, include_in_schema=False)
def history_page(request: HttpRequest, public_id: str) -> HttpResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)
    if not Article.can_be_edited_by(user, article):
        raise ApiError(404, "Article not found")

    entries_qs = ArticleHistory.objects.filter(article=article).order_by("-time")

    entries = [e.to_article_history_entry_item() for e in entries_qs]

    props = ArticleHistoryProps(
        path_prefix=ARTICLES_PATH_PREFIX,
        user=Article.user_profile(user),
        is_editor=Article.is_editor(user),
        article_public_id=article.public_id,
        article_title=article.title,
        entries=entries,
    )
    return InertiaResponse(request, "ArticleHistory", {"props": props.model_dump()})


@articles_router.post("/api/upload-image/{public_id}")
def upload_image(request: HttpRequest, public_id: str) -> UploadImageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)
    if not Article.can_be_edited_by(user, article):
        raise ApiError(404, "Article not found")

    image_file = request.FILES.get("image")
    if not image_file:
        raise ApiError(400, "No image file provided")
    assert image_file.size is not None

    if article.image_quota_exceeded(image_file.size):
        existing = article.existing_image_bytes()
        quota = Article.CONTENT_IMAGES_TOTAL_BYTES
        msg = f"Image would exceed quota ({human_size(existing)} of {human_size(quota)} used)"
        raise ApiError(400, msg)

    img = ArticleImage.objects.create(article=article, image=image_file)
    return UploadImageResponse(
        url=f"{ARTICLES_PATH_PREFIX}/api/download-image/{public_id}/{img.uuid_id}"
    )


@articles_router.get("/api/download-image/{public_id}/{image_id}", response=None)
def download_image(request: HttpRequest, public_id: str, image_id: str) -> FileResponse:
    article = Article.get_or_404(public_id)

    user = auth_user(request)
    can_download_image_or_404(user, article)

    try:
        img_uuid = uuid.UUID(image_id)
        img = ArticleImage.objects.get(uuid_id=img_uuid, article_id=article.pk)
    except ArticleImage.DoesNotExist, ValueError:
        raise ApiError(404, "Image not found") from None

    try:
        return FileResponse(img.image, as_attachment=False)
    except FileNotFoundError:
        raise ApiError(404, "File missing from storage") from None


@articles_router.get("/api/search-tags", response=SearchTagsResponse)
def search_tags(
    request: HttpRequest,  # noqa: ARG001 # Ninja requires request parameter
    q: str = "",
) -> SearchTagsResponse:
    qs = ArticleTag.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("name")[:20]
    return SearchTagsResponse(tags=[ArticleTagItem(name=t.name, color=t.color) for t in qs])


@articles_router.get("/api/search-authors", response=SearchAuthorsResponse)
def search_authors(
    request: HttpRequest,  # noqa: ARG001 # Ninja requires request parameter
    q: str = "",
) -> SearchAuthorsResponse:
    qs = User.search_users(q)[:20]
    return SearchAuthorsResponse(authors=[Article.user_profile(u) for u in qs])


@articles_router.get("/api/comments/{public_id}", response=ArticleCommentsResponse)
def list_comments(request: HttpRequest, public_id: str) -> ArticleCommentsResponse:
    article = Article.get_or_404(public_id)
    user = auth_user(request)

    viewable_or_404(user, article)

    comment_items = ArticleComment.for_article(article)

    can_comment = bool(
        user is not None and article.is_commenting_enabled and article.published_at is not None
    )
    can_delete_any = bool(user is not None and Article.can_be_edited_by(user, article))

    return ArticleCommentsResponse(
        comments=comment_items,
        can_comment=can_comment,
        can_delete_any=can_delete_any,
        user_id=user.pk if user else None,
    )


@articles_router.post("/api/create-comment/{public_id}")
def create_comment(
    request: HttpRequest, public_id: str, payload: CommentCreateSchema
) -> MessageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)

    if not article.is_commenting_enabled:
        raise ApiError(404, "Commenting is not available")

    published_or_404(article)

    is_first_comment = not ArticleComment.objects.filter(
        article=article, commented_by_id=user.pk
    ).exists()
    comment = ArticleComment.objects.create(
        article=article,
        content=payload.content,
        commented_by_id=user.pk,
    )
    if is_first_comment:
        article.subscribers.add(user)
    recipients = list(article.subscribers.exclude(pk=user.pk))
    if recipients:
        content = Article.comment_notification_content(article, comment, user)
        ArticleNotification.objects.bulk_create(
            [
                ArticleNotification(
                    article_public_id=article.public_id,
                    comment_public_id=str(comment.public_id),
                    user=recipient,
                    content=content,
                )
                for recipient in recipients
            ],
            ignore_conflicts=True,
        )
    return MessageResponse(id=str(comment.public_id))


@articles_router.post("/api/{public_id}/update-comment/{comment_public_id}")
def update_comment(
    request: HttpRequest,
    public_id: str,
    comment_public_id: str,
    payload: CommentUpdateSchema,
) -> MessageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)

    published_or_404(article)

    try:
        comment = ArticleComment.objects.get(public_id=comment_public_id, article=article)
    except ArticleComment.DoesNotExist, ValueError:
        raise ApiError(404, "Comment not found") from None

    if not comment.can_update_comment(user):
        raise ApiError(404, "You cannot edit this comment")

    comment.update_content(user, payload.content, check=False)
    return MessageResponse(id=str(comment.public_id))


@articles_router.post("/api/{public_id}/delete-comment/{comment_public_id}")
def delete_comment(
    request: HttpRequest,
    public_id: str,
    comment_public_id: str,
) -> MessageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)

    published_or_404(article)

    try:
        comment = ArticleComment.objects.get(public_id=comment_public_id, article=article)
    except ArticleComment.DoesNotExist, ValueError:
        raise ApiError(404, "Comment not found") from None

    if not comment.can_soft_delete_comment(user, article):
        raise ApiError(404, "You cannot delete this comment")

    comment.soft_delete(user)
    return MessageResponse(message="Comment deleted")


@articles_router.post("/api/subscribe/{public_id}")
def subscribe(request: HttpRequest, public_id: str) -> MessageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)
    published_or_404(article)
    article.subscribers.add(user)
    return MessageResponse(id=article.public_id)


@articles_router.post("/api/unsubscribe/{public_id}")
def unsubscribe(request: HttpRequest, public_id: str) -> MessageResponse:
    article = Article.get_or_404(public_id)
    user = user_or_404(request)
    published_or_404(article)
    article.subscribers.remove(user)
    return MessageResponse(id=article.public_id)


@articles_router.get("/tag", response=None, include_in_schema=False)
def tag_page(request: HttpRequest) -> HttpResponse:
    editor_or_404(request)

    tags = list(ArticleTag.objects.annotate(article_count=Count("article")).order_by("name"))

    tag_items = [
        TagWithCount(name=t.name, color=t.color, article_count=t.article_count).model_dump()
        for t in tags
    ]
    user = auth_user(request)
    user_profile = Article.user_profile(user) if user is not None else None
    props: dict[str, Any] = {
        "path_prefix": ARTICLES_PATH_PREFIX,
        "user": user_profile.model_dump() if user_profile else None,
        "is_editor": True,
        "tags": tag_items,
    }
    return InertiaResponse(request, "ArticleTagManagement", {"props": props})


@articles_router.post("/tag/create")
def tag_create(request: HttpRequest, payload: TagSchema) -> MessageResponse:
    editor_or_404(request)

    if ArticleTag.objects.filter(name=payload.name).exists():
        raise ApiError(400, f"Tag '{payload.name}' already exists")

    tag = ArticleTag.create(name=payload.name, color=payload.color)
    return MessageResponse(id=tag.name)


@articles_router.post("/tag/update/{tag_name}")
def tag_update(request: HttpRequest, tag_name: str, payload: TagSchema) -> MessageResponse:
    editor_or_404(request)

    tag = ArticleTag.get_or_404(tag_name)

    if payload.name != tag.name and ArticleTag.objects.filter(name=payload.name).exists():
        raise ApiError(400, f"Tag '{payload.name}' already exists")

    tag.update(name=payload.name, color=payload.color)
    return MessageResponse(id=tag.name)


@articles_router.post("/tag/delete/{tag_name}")
def tag_delete(request: HttpRequest, tag_name: str) -> MessageResponse:
    editor_or_404(request)

    tag = ArticleTag.get_or_404(tag_name)
    tag.delete()
    return MessageResponse(message="Tag deleted")


articles_api = NinjaAPI(urls_namespace="articles-http")
register_api_error_handlers(articles_api)
articles_api.add_router(ARTICLES_PATH_PREFIX.strip("/"), articles_router)
