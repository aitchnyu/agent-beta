from __future__ import annotations

import typing
import uuid
from typing import Any, ClassVar, Literal, cast

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import TrigramSimilarity
from django.db import models
from pydantic import BaseModel as PydanticBaseModel


def generate_uuid7_id() -> str:
    return str(uuid.uuid7())


class UserManager(DjangoUserManager):  # type: ignore[type-arg] # manager is parametrised implicitly via self.model = User
    """Manager for the custom ``User`` model.

    Subclasses Django's ``UserManager`` so ``create_user`` /
    ``create_superuser`` and allauth keep working unchanged. ``public_id``
    auto-generates from the field's ``default=generate_uuid7_id``.
    """

    use_in_migrations = True


class User(AbstractUser):
    """Project-wide custom user model (``AUTH_USER_MODEL``).

    Carries a URL-safe UUID7 ``public_id`` (used in all public URLs and
    API responses), an optional rich-text ``description`` shown only when
    ``has_public_profile`` is set, and a ``search_users`` trigram search.
    Concrete views/API must never send the integer ``pk`` to clients.
    """

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    description = models.TextField(blank=True, default="")
    has_public_profile = models.BooleanField(default=False)

    objects = UserManager()  # type: ignore[misc] # custom user manager replaces AbstractUser's (allauth)

    class Meta:
        db_table = "auth_user"
        # GIN trigram indexes back User.search_users (pg_trgm similarity).
        indexes: ClassVar[list[models.Index]] = [
            GinIndex(
                fields=["first_name"],
                opclasses=["gin_trgm_ops"],
                name="user_first_name_trgm_idx",
            ),
            GinIndex(
                fields=["last_name"],
                opclasses=["gin_trgm_ops"],
                name="user_last_name_trgm_idx",
            ),
            GinIndex(
                fields=["username"],
                opclasses=["gin_trgm_ops"],
                name="user_username_trgm_idx",
            ),
        ]

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    @classmethod
    def search_users(cls, q: str) -> models.QuerySet[typing.Self]:
        """Return users ranked by trigram similarity across name fields.

        Matches ``first_name``, ``last_name`` and ``username`` using
        ``pg_trgm`` ``TrigramSimilarity`` and orders by best match.
        An empty query returns all users ordered by username so callers
        can still slice a top-N without special-casing empty input.
        """
        cleaned = q.strip()
        if not cleaned:
            return cast(
                "models.QuerySet[typing.Self]",
                cls.objects.all().order_by("username"),
            )
        return cast(
            "models.QuerySet[typing.Self]",
            cls.objects.annotate(
                similarity=(
                    TrigramSimilarity("first_name", cleaned)
                    + TrigramSimilarity("last_name", cleaned)
                    + TrigramSimilarity("username", cleaned)
                ),
            )
            .filter(similarity__gt=0.1)
            .order_by("-similarity", "username"),
        )

    def snapshot(self) -> UserSnapshot:
        return UserSnapshot(
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            description=self.description,
            has_public_profile=self.has_public_profile,
            is_active=self.is_active,
            is_staff=self.is_staff,
            is_superuser=self.is_superuser,
        )

    def update(  # noqa: PLR0913 # 8 params: all needed for user update
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        description: str,
        has_public_profile: bool,
        is_active: bool,
        is_staff: bool,
        is_superuser: bool,
        user: User,
    ) -> None:
        """Apply the editable fields, persist, and record a history entry.

        Only the 8 editable fields move; ``username`` and ``public_id`` are
        identity and never mutate. A no-op submit (nothing changed) creates
        no history noise.
        """
        old_snapshot = self.snapshot()
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.description = description
        self.has_public_profile = has_public_profile
        self.is_active = is_active
        self.is_staff = is_staff
        self.is_superuser = is_superuser
        self.save()
        new_snapshot = self.snapshot()
        if any(v is not None for v in old_snapshot.difference(new_snapshot).model_dump().values()):
            UserHistory.record_edited(self, user, old_snapshot, new_snapshot)

    generate_uuid7_id = staticmethod(generate_uuid7_id)


class UserProfile(PydanticBaseModel):
    # pk-free: only the URL-safe public_id is ever sent to clients.
    public_id: str
    title: str


class StringChange(PydanticBaseModel):
    old: str
    new: str


class BoolChange(PydanticBaseModel):
    old: bool
    new: bool


class UserHistoryContent(PydanticBaseModel):
    first_name: StringChange | None = None
    last_name: StringChange | None = None
    email: StringChange | None = None
    description: StringChange | None = None
    has_public_profile: BoolChange | None = None
    is_active: BoolChange | None = None
    is_staff: BoolChange | None = None
    is_superuser: BoolChange | None = None


class UserSnapshot(PydanticBaseModel):
    first_name: str
    last_name: str
    email: str
    description: str
    has_public_profile: bool
    is_active: bool
    is_staff: bool
    is_superuser: bool

    def as_new(self) -> UserHistoryContent:
        return UserHistoryContent(
            first_name=StringChange(old=self.first_name, new=self.first_name),
            last_name=StringChange(old=self.last_name, new=self.last_name),
            email=StringChange(old=self.email, new=self.email),
            description=StringChange(old=self.description, new=self.description),
            has_public_profile=BoolChange(
                old=self.has_public_profile,
                new=self.has_public_profile,
            ),
            is_active=BoolChange(old=self.is_active, new=self.is_active),
            is_staff=BoolChange(old=self.is_staff, new=self.is_staff),
            is_superuser=BoolChange(
                old=self.is_superuser,
                new=self.is_superuser,
            ),
        )

    def difference(self, other: UserSnapshot) -> UserHistoryContent:
        changes: dict[str, Any] = {}
        if self.first_name != other.first_name:
            changes["first_name"] = StringChange(old=self.first_name, new=other.first_name)
        if self.last_name != other.last_name:
            changes["last_name"] = StringChange(old=self.last_name, new=other.last_name)
        if self.email != other.email:
            changes["email"] = StringChange(old=self.email, new=other.email)
        if self.description != other.description:
            changes["description"] = StringChange(old=self.description, new=other.description)
        if self.has_public_profile != other.has_public_profile:
            changes["has_public_profile"] = BoolChange(
                old=self.has_public_profile,
                new=other.has_public_profile,
            )
        if self.is_active != other.is_active:
            changes["is_active"] = BoolChange(old=self.is_active, new=other.is_active)
        if self.is_staff != other.is_staff:
            changes["is_staff"] = BoolChange(old=self.is_staff, new=other.is_staff)
        if self.is_superuser != other.is_superuser:
            changes["is_superuser"] = BoolChange(
                old=self.is_superuser,
                new=other.is_superuser,
            )
        return UserHistoryContent(**changes)


class UserHistoryEntryItem(PydanticBaseModel):
    public_id: str
    action: Literal["created", "edited", "deleted"]
    time: str
    changes: UserHistoryContent


class UserHistory(models.Model):
    """Per-field diff history of ``User`` edits.

    ``target_user`` is the edited user (SET_NULL on delete) and ``user`` is
    the superuser actor. ``target_user_public_id_copy`` survives deletion so
    history remains readable after the target is gone.
    """

    ACTION_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("created", "Created"),
        ("edited", "Edited"),
        ("deleted", "Deleted"),
    ]

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="history_entries",
    )
    target_user_public_id_copy = models.CharField(max_length=36, default="")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    time = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    _changes = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["target_user"]),
            models.Index(fields=["time"]),
        ]
        ordering: ClassVar[list[str]] = ["-time"]

    def to_user_history_entry_item(self) -> UserHistoryEntryItem:
        content = (
            UserHistoryContent.model_validate(self._changes)
            if self._changes
            else UserHistoryContent()
        )
        return UserHistoryEntryItem(
            public_id=self.public_id,
            action=cast(Literal["created", "edited", "deleted"], self.action),
            time=self.time.isoformat(),
            changes=content,
        )

    @classmethod
    def record_created(
        cls,
        target_user: User,
        user: User | None,
        snapshot: UserSnapshot,
    ) -> UserHistory:
        return cls.objects.create(
            target_user=target_user,
            target_user_public_id_copy=target_user.public_id,
            user=user,
            action="created",
            _changes=snapshot.as_new().model_dump(mode="json"),
        )

    @classmethod
    def record_edited(
        cls,
        target_user: User,
        user: User | None,
        old_snapshot: UserSnapshot,
        new_snapshot: UserSnapshot,
    ) -> UserHistory:
        diff = old_snapshot.difference(new_snapshot)
        return cls.objects.create(
            target_user=target_user,
            target_user_public_id_copy=target_user.public_id,
            user=user,
            action="edited",
            _changes=diff.model_dump(mode="json"),
        )

    @classmethod
    def record_deleted(
        cls,
        target_user: User,
        user: User | None,
    ) -> UserHistory:
        return cls.objects.create(
            target_user=target_user,
            target_user_public_id_copy=target_user.public_id,
            user=user,
            action="deleted",
            _changes={},
        )
