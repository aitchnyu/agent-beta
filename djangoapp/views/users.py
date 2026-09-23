from __future__ import annotations

from typing import Literal

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.http import (  # ninja inspects view signatures at runtime
    Http404,
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import redirect, render
from django.utils import timezone
from inertia import InertiaResponse
from ninja import (
    Query,
    Router,
)
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, field_validator

from djangoapp.logging import get_logger
from djangoapp.models import (
    LoginKey,
    User,
    UserHistory,
    UserHistoryEntryItem,
    UserSessionIndex,
)
from djangoapp.ninja_api import ApiError, make_ninja_api
from djangoapp.utils import sanitize_html

USERS_PATH_PREFIX = "/users"

logger = get_logger(__name__)


class UserListItem(PydanticBaseModel):
    public_id: str
    first_name: str
    last_name: str
    username: str
    email: str
    has_public_profile: bool
    is_active: bool
    is_staff: bool
    is_superuser: bool


class UserListPagination(PydanticBaseModel):
    page: int
    total_pages: int
    total_count: int


class UserListFilters(PydanticBaseModel):
    page: int = Field(default=1, ge=1)
    q: str = ""


class UserListProps(PydanticBaseModel):
    path_prefix: str
    users: list[UserListItem]
    pagination: UserListPagination
    filters: UserListFilters


class UserDetailsProps(PydanticBaseModel):
    path_prefix: str
    public_id: str
    first_name: str
    last_name: str
    username: str | None = None
    description: str | None = None
    is_owner: bool = False
    # Admin-only attributes of the target user. Populated only when the
    # viewer is a superuser (gated client-side by the shared
    # viewer_is_superuser prop); the details page is otherwise public, so
    # the real email/staff/superuser/active state is never leaked to
    # anonymous.
    email: str | None = None
    has_public_profile: bool = False
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    history_count: int = 0
    # Admin-only, populated for superuser viewers like the attrs above.
    last_login: str | None = None
    session_count: int = 0


class UserEditItem(PydanticBaseModel):
    public_id: str
    # username is read-only (never editable); shown for context only.
    username: str
    first_name: str
    last_name: str
    email: str
    description: str
    has_public_profile: bool
    is_active: bool
    is_staff: bool
    is_superuser: bool


class UserEditProps(PydanticBaseModel):
    path_prefix: str
    target: UserEditItem


class UserUpdateSchema(PydanticBaseModel):
    """Editable user fields. ``username`` is intentionally absent (read-only)."""

    first_name: str = Field(min_length=1)
    last_name: str = ""
    email: str = Field(min_length=1)
    description: str = ""
    has_public_profile: bool = False
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False

    @field_validator("description")
    @classmethod
    def _sanitize_description(cls, v: str) -> str:
        return sanitize_html(v)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        try:
            validate_email(v)
        except ValidationError as exc:
            msg = "; ".join(exc.messages)
            raise ValueError(msg) from exc
        return v


class UserHistoryProps(PydanticBaseModel):
    path_prefix: str
    target_public_id: str
    target_title: str
    entries: list[UserHistoryEntryItem]


class MessageResponse(PydanticBaseModel):
    id: str = ""


class LoginLinkRequest(PydanticBaseModel):
    """Issue payload; the allowlist is the UI's TTL select (minutes)."""

    ttl_minutes: Literal[15, 60, 480, 1440] = 15


class LoginLinkResponse(PydanticBaseModel):
    url: str
    expires_at: str


class LogoutResponse(PydanticBaseModel):
    sessions: int


class UserSearchItem(PydanticBaseModel):
    public_id: str
    username: str
    title: str


class UserSearchResponse(PydanticBaseModel):
    users: list[UserSearchItem]


def viewer_is_superuser(request: HttpRequest) -> bool:
    """Whether the requesting viewer is a superuser (drives admin-only props).

    Equals the shared ``viewer_is_superuser`` prop; computed here so the
    details page can populate the target's admin attributes only for
    superuser viewers without re-deriving it from the request in-template.
    """
    user = request.user
    return bool(user.is_authenticated and user.is_superuser)


def superuser_or_404(request: HttpRequest) -> User:
    """Return the requesting superuser, else raise 404."""
    viewer = request.user
    if not (viewer.is_authenticated and viewer.is_superuser):
        msg = "Superuser access required"
        raise ApiError(404, msg)
    return viewer


def get_user_or_404(public_id: str) -> User:
    try:
        target: User = User.objects.get(public_id=public_id)
    except User.DoesNotExist:
        raise ApiError(404, "User not found") from None
    else:
        return target


def redeem_login_key(request: HttpRequest, key: str) -> HttpResponse:
    """Log in a user via a one-time key (``makeloginlink`` / details page).

    Login keys are the operator path for environments without Google
    credentials (the VM); the key is the sole credential and redemption
    consumes it atomically — the link works exactly once. Any miss
    (unknown, used, expired) is a 404 like every other resource gate. Not
    DEBUG-gated: the unguessable, single-use key is the gate.

    An ALREADY-AUTHENTICATED viewer is refused with a plain explainer page
    (409, shared ``simple.html`` shell) BEFORE the key is touched.
    """
    if request.user.is_authenticated:
        logger.warning(
            "login link redemption refused, viewer already signed in",
            viewer=request.user.username,
        )
        return render(request, "login_link_refused.html", status=409)
    user = LoginKey.redeem(key)
    if user is None:
        raise Http404
    # No authenticate() happened, so the backend must be explicit; the
    # user_logged_in receiver records the login, and the session is indexed
    # by SessionIdleTouchMiddleware on its next authenticated request.
    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(settings.LOGIN_REDIRECT_URL)


users_router = Router()


@users_router.get("/list", response=None, include_in_schema=False)
def list_page(request: HttpRequest, filters: Query[UserListFilters]) -> HttpResponse:
    superuser_or_404(request)

    q = filters.q.strip()
    qs = User.search_users(q) if q else User.objects.all().order_by("username")
    paginator = Paginator(qs, 25, orphans=5)
    page = paginator.get_page(filters.page)

    items = [
        UserListItem(
            public_id=u.public_id,
            first_name=u.first_name,
            last_name=u.last_name,
            username=u.username,
            email=u.email,
            has_public_profile=u.has_public_profile,
            is_active=u.is_active,
            is_staff=u.is_staff,
            is_superuser=u.is_superuser,
        )
        for u in page.object_list
    ]
    props = UserListProps(
        path_prefix=USERS_PATH_PREFIX,
        users=items,
        pagination=UserListPagination(
            page=page.number,
            total_pages=paginator.num_pages,
            total_count=paginator.count,
        ),
        filters=filters,
    )
    return InertiaResponse(request, "UserList", {"props": props.model_dump()})


@users_router.get("/api/search", response=UserSearchResponse, include_in_schema=False)
def search(
    request: HttpRequest,
    q: str = "",
) -> UserSearchResponse:
    """Username search for the list page's jump-to-profile multiselect."""
    superuser_or_404(request)
    qs = User.search_users(q)[:20]
    return UserSearchResponse(
        users=[
            UserSearchItem(
                public_id=u.public_id,
                username=u.username,
                title=u.display_name,
            )
            for u in qs
        ],
    )


@users_router.get("/id/{public_id}", response=None, include_in_schema=False)
def details_page(request: HttpRequest, public_id: str) -> HttpResponse:
    target = get_user_or_404(public_id)

    viewer = request.user if request.user.is_authenticated else None
    is_owner = viewer is not None and viewer.pk == target.pk
    is_super = viewer_is_superuser(request)
    # Owner is gated by the same flag: description/username only when public.
    if target.has_public_profile:
        username = target.username
        description: str | None = target.description
    else:
        username = None
        description = None

    props = UserDetailsProps(
        path_prefix=USERS_PATH_PREFIX,
        public_id=target.public_id,
        first_name=target.first_name,
        last_name=target.last_name,
        username=username,
        description=description,
        is_owner=is_owner,
    )
    # Admin-only attribute panel + history count: never leak to anonymous.
    if is_super:
        props.email = target.email
        props.has_public_profile = target.has_public_profile
        props.is_active = target.is_active
        props.is_staff = target.is_staff
        props.is_superuser = target.is_superuser
        props.history_count = UserHistory.objects.filter(target_user=target).count()
        props.last_login = target.last_login.isoformat() if target.last_login else None
        props.session_count = UserSessionIndex.objects.filter(
            user=target, expire_date__gt=timezone.now()
        ).count()
    return InertiaResponse(request, "UserDetails", {"props": props.model_dump()})


@users_router.get("/edit/{public_id}", response=None, include_in_schema=False)
def edit_page(request: HttpRequest, public_id: str) -> HttpResponse:
    superuser_or_404(request)
    target = get_user_or_404(public_id)

    props = UserEditProps(
        path_prefix=USERS_PATH_PREFIX,
        target=UserEditItem(
            public_id=target.public_id,
            username=target.username,
            first_name=target.first_name,
            last_name=target.last_name,
            email=target.email,
            description=target.description,
            has_public_profile=target.has_public_profile,
            is_active=target.is_active,
            is_staff=target.is_staff,
            is_superuser=target.is_superuser,
        ),
    )
    return InertiaResponse(request, "UserEdit", {"props": props.model_dump()})


@users_router.post("/edit/{public_id}")
def edit_submit(request: HttpRequest, public_id: str, payload: UserUpdateSchema) -> MessageResponse:
    viewer = superuser_or_404(request)
    target = get_user_or_404(public_id)
    # Prevent admin lockout: a superuser must not clear their own
    # superuser/active flag. Because every /users/* management route
    # gates on an authenticated superuser, this also guarantees the
    # active-superuser count can never fall to zero through this endpoint.
    if viewer.pk == target.pk and (not payload.is_superuser or not payload.is_active):
        msg = "You cannot remove your own superuser or active status."
        raise ApiError(400, msg)
    target.update(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        description=payload.description,
        has_public_profile=payload.has_public_profile,
        is_active=payload.is_active,
        is_staff=payload.is_staff,
        is_superuser=payload.is_superuser,
        user=viewer,
    )
    return MessageResponse(id=target.public_id)


@users_router.get("/history/{public_id}", response=None, include_in_schema=False)
def history_page(request: HttpRequest, public_id: str) -> HttpResponse:
    superuser_or_404(request)
    target = get_user_or_404(public_id)

    entries = [
        e.to_user_history_entry_item() for e in UserHistory.objects.filter(target_user=target)
    ]
    props = UserHistoryProps(
        path_prefix=USERS_PATH_PREFIX,
        target_public_id=target.public_id,
        target_title=target.display_name,
        entries=entries,
    )
    return InertiaResponse(request, "UserHistory", {"props": props.model_dump()})


@users_router.post("/api/{public_id}/loginlink", response=LoginLinkResponse)
def issue_login_link(
    request: HttpRequest,
    public_id: str,
    payload: LoginLinkRequest,
) -> LoginLinkResponse:
    """Issue a one-time login link for the target (superuser only).

    The URL is built from the request origin, so it is correct behind the
    VM's tunnel (https://localhost:8000). The raw key exists only in this
    response (and the audit history records the event, never the key).
    """
    viewer = superuser_or_404(request)
    target = get_user_or_404(public_id)
    key, expires_at = LoginKey.issue(target, minutes=payload.ttl_minutes)
    UserHistory.record_login_link(target, viewer, minutes=payload.ttl_minutes)
    logger.info(
        "login link generated",
        actor=viewer.public_id,
        target=target.public_id,
        ttl_minutes=payload.ttl_minutes,
    )
    return LoginLinkResponse(
        url=request.build_absolute_uri(f"/login-for-test/{key}/"),
        # The row's own deadline, straight from LoginKey.issue.
        expires_at=expires_at.isoformat(),
    )


@users_router.post("/api/{public_id}/logout", response=LogoutResponse)
def force_logout(request: HttpRequest, public_id: str) -> LogoutResponse:
    """End every active session of the target (superuser only).

    Deletes the unexpired session rows via the UserSessionIndex mapping;
    index rows CASCADE away. The target's next request is anonymous.
    Unindexed sessions (pre-index or flush-login, until their next request)
    can survive this.
    """
    viewer = superuser_or_404(request)
    target = get_user_or_404(public_id)
    keys = list(
        UserSessionIndex.objects.filter(user=target, expire_date__gt=timezone.now()).values_list(
            "session_id", flat=True
        )
    )
    _total, by_model = Session.objects.filter(session_key__in=keys).delete()
    # by-model dict: the cascade also removes index rows, which are not sessions.
    sessions = by_model.get("sessions.Session", 0)
    # Audit trail like the sibling admin action (issue_login_link): the
    # destructive action must be visible in the target's timeline + logs.
    UserHistory.record_logout_all(target, viewer, sessions)
    logger.info(
        "user sessions ended",
        actor=viewer.public_id,
        target=target.public_id,
        sessions=sessions,
    )
    return LogoutResponse(sessions=sessions)


# Both POSTs are CSRF-protected by make_ninja_api's default csrf_guard (it
# runs in ninja's auth pipeline; the frontend sends X-CSRFToken always).
users_api = make_ninja_api("users", users_router, prefix=USERS_PATH_PREFIX.strip("/"))
