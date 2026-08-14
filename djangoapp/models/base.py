from __future__ import annotations

import typing
import uuid
from typing import Any, ClassVar, Literal, cast

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import TrigramSimilarity
from django.db import models, transaction
from django.utils import timezone
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


# Full URL prefix for the superuser-only models-management pages. The routes in
# djangoapp/views/manage.py mount under ``manage`` + ``/models/...`` and must
# match this prefix. Lives in the model layer (not views) so BaseModel owns the
# URL its rows link to, without models importing views.
MANAGE_MODELS_URL_PREFIX = "/manage/models"


class BaseModel(models.Model):
    """Abstract base for the concrete models in ourapp/.

    Rows are addressed by their ``public_id`` (UUID7 by default; a subclass may
    use friendlier names). Audit fields track who created/last-touched each row;
    :meth:`save_with_logs`/:meth:`delete_with_logs` write one ``BaseModelUpdateLog``
    entry per create/update/delete.
    """

    public_id = models.CharField(
        max_length=100, db_index=True, editable=False, default=generate_uuid7_id
    )
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Set explicitly in save_with_logs (NOT auto_now) so the stamp never drifts
    # from the matching BaseModelUpdateLog.performed_* pair.
    last_updated_at = models.DateTimeField(null=True, blank=True)
    last_updated_by = models.ForeignKey(
        # RESTRICT (repo default) blocks deleting a user who touched a row;
        # BaseModelUpdateLog.performed_by is SET_NULL instead so the permanent
        # audit log survives actor deletion even when the row blocks the delete.
        User,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="+",
    )

    # Override on a subclass to log under a stable name regardless of class
    # rename or module path (the default is ``"<module>.<ClassName>"``). The same
    # value is used on write (save_with_logs/delete_with_logs) and on read (the
    # row-detail logs query), so a row's log stream resolves consistently even
    # when the test fixture app's module path differs from prod's.
    log_as_name: ClassVar[str | None] = None

    class Meta:
        abstract = True

    def __str__(self) -> str:
        """Override per-model for a friendlier label."""
        return self.public_id

    def get_absolute_url(self) -> str:
        """Superuser-only models-management detail URL for this row.

        Built from the concrete class name + ``public_id``; must match the route
        in ``djangoapp/views/manage.py``
        (``MANAGE_MODELS_URL_PREFIX/<model>/id/<id>``).
        """
        return f"{MANAGE_MODELS_URL_PREFIX}/{type(self).__name__}/id/{self.public_id}"

    @classmethod
    def log_model_name(cls) -> str:
        """Stable identifier stored on ``BaseModelUpdateLog.model``."""
        return cls.log_as_name or f"{cls.__module__}.{cls.__name__}"

    # --- audit-log helpers -------------------------------------------------

    @classmethod
    def _log_fields(cls) -> list[models.Field[Any, Any]]:
        """All concrete columns except the auto pk (builtins included)."""
        return [f for f in cls._meta.fields if not f.primary_key]

    @classmethod
    def _log_fk_field_names(cls) -> list[str]:
        """FK column names to select_related when reading the pre-edit snapshot."""
        return [f.name for f in cls._log_fields() if isinstance(f, models.ForeignKey)]

    def _log_values_snapshot(self) -> dict[str, Any]:
        """Return the current supported-column values as JSON-safe audit data.

        Builtins and user fields are treated identically; unsupported column
        kinds (file/json/m2m/binary/...) are omitted via the ``_OMIT`` sentinel.
        """
        out: dict[str, Any] = {}
        for f in self._log_fields():
            v = self._log_field_value(f)
            if v is not _OMIT:
                out[f.name] = v
        return out

    def _log_field_value(self, field: models.Field[Any, Any]) -> object:  # noqa: PLR0911 # one return per supported column kind reads clearer than a dispatch table
        """Map this row's column value to its JSON-safe audit shape, or ``_OMIT``.

        Shapes: bool→bool; char/text→str; int/decimal/float→str (string carries
        big ints/decimals losslessly); datetime/date→ISO str; FK→{id,url,name}.
        """
        value = getattr(self, field.name)
        if isinstance(field, models.BooleanField):
            return None if value is None else bool(value)
        if isinstance(field, (models.CharField, models.TextField)):
            return None if value is None else str(value)
        if isinstance(field, (models.IntegerField, models.DecimalField, models.FloatField)):
            return None if value is None else str(value)
        if isinstance(field, models.DateTimeField):
            return None if value is None else value.isoformat()
        if isinstance(field, models.DateField):
            return None if value is None else value.isoformat()
        if isinstance(field, models.ForeignKey):
            return _log_fk_value(value)
        return _OMIT

    def save_with_logs(self, *, actor: User | None) -> None:
        """Persist and write one ``BaseModelUpdateLog`` (``created`` or ``updated``).

        ``actor`` is who performed the write (recorded as ``performed_by`` and
        stamped on ``created_by``/``last_updated_by``)

        Create: ``old_values={}``, ``new_values`` = full snapshot.
        Update: only **changed** columns appear in old/new_values; a no-op edit
        writes no log row. ``last_updated_at``/``last_updated_by`` are stamped
        here so they match the log's ``performed_*`` exactly. Save + log share
        one transaction (no audit-less writes). It calls ``super().save()`` (not
        ``self.save()``): this avoids recursing back into ``save_with_logs`` if a
        subclass overrides ``save()``, so subclass domain side-effects belong in a
        dedicated method rather than a ``save()`` override.
        """
        now = timezone.now()
        if self._state.adding:
            self.created_by = actor
            self.last_updated_by = actor
            self.last_updated_at = now
            with transaction.atomic():
                super().save()
                BaseModelUpdateLog.objects.create(
                    performed_by=actor,
                    performed_at=now,
                    model=type(self).log_model_name(),
                    model_pk=self.pk,
                    action="created",
                    old_values={},
                    new_values=self._log_values_snapshot(),
                )
            return
        self.last_updated_by = actor
        self.last_updated_at = now
        with transaction.atomic():
            # Read the pre-edit snapshot inside the txn so a concurrent edit
            # between read and save can't slip in un-logged — the audit's
            # before/after must match the row state at save time.
            old = (
                type(self)
                .objects.select_related(  # type: ignore[attr-defined] # concrete subclass carries objects; abstract BaseModel doesn't
                    *self._log_fk_field_names()
                )
                .get(pk=self.pk)
            )
            old_values = old._log_values_snapshot()  # noqa: SLF001 # peer-instance audit snapshot
            super().save()
            new_values = self._log_values_snapshot()
            diff_old, diff_new = _diff_snapshots(old_values, new_values)
            # last_updated_at/by are always re-stamped above (and recorded
            # separately as performed_at/performed_by), so drop them from the
            # diff — otherwise every edit logs timestamp churn and a true no-op
            # (no data column changed) never skips.
            diff_old.pop("last_updated_at", None)
            diff_new.pop("last_updated_at", None)
            diff_old.pop("last_updated_by", None)
            diff_new.pop("last_updated_by", None)
            if diff_old:  # no-op edit → no log row
                BaseModelUpdateLog.objects.create(
                    performed_by=actor,
                    performed_at=now,
                    model=type(self).log_model_name(),
                    model_pk=self.pk,
                    action="updated",
                    old_values=diff_old,
                    new_values=diff_new,
                )

    def delete_with_logs(self, *, actor: User | None) -> BaseModelUpdateLog:
        """Delete and write a ``deleted`` log with empty old/new values.

        A delete records only that the row was removed (action + model + pk) — no
        field snapshot is stored; the row is gone, and the log outlives it keyed by
        model + integer pk.
        """
        now = timezone.now()
        with transaction.atomic():
            log = BaseModelUpdateLog.objects.create(
                performed_by=actor,
                performed_at=now,
                model=type(self).log_model_name(),
                model_pk=self.pk,
                action="deleted",
                old_values={},
                new_values={},
            )
            super().delete()
        return log


# Sentinel returned by ``_log_field_value`` for columns we can't audit-serialise
# (FileField, JSONField, ManyToMany, BinaryField, DurationField, UUIDField, ...).
_OMIT: object = object()


def user_profile(user: User | None) -> UserProfile | None:
    """Build a pk-free profile for an audit actor / FK→User target, or None."""
    if user is None:
        return None
    return UserProfile(public_id=user.public_id, title=user.display_name)


# Not a BaseModel method: the FK target may be a User or any non-BaseModel row,
# so it takes the target as a plain object (only BaseModel/User carry a public_id).
def _log_fk_value(related: object) -> object:
    """Serialise a FK target as ``{id, url, name}`` (pk-free), or OMIT/None.

    ``id`` is the target's ``public_id`` (never its integer pk); only BaseModel /
    User targets carry one, so a FK to anything else is omitted (no pk leak).
    """
    if related is None:
        return None
    public_id = getattr(related, "public_id", None)
    if not public_id:
        return _OMIT
    url = ""
    getter = getattr(related, "get_absolute_url", None)
    if callable(getter):
        try:
            url = getter() or ""
        except Exception:  # noqa: BLE001 # any URL-build failure → blank, not a 500
            url = ""
    name = related.display_name if isinstance(related, User) else str(related)
    return {"id": public_id, "url": url, "name": name}


def _diff_snapshots(
    old: dict[str, Any], new: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return only the columns that differ between two snapshots (old, new)."""
    changed_old: dict[str, Any] = {}
    changed_new: dict[str, Any] = {}
    for key in old.keys() | new.keys():
        ov, nv = old.get(key), new.get(key)
        if ov != nv:
            changed_old[key] = ov
            changed_new[key] = nv
    return changed_old, changed_new


class UpdateLogEntryItem(PydanticBaseModel):
    """Client-facing shape of one ``BaseModelUpdateLog`` row (pk-free)."""

    id: str
    action: Literal["created", "updated", "deleted"]
    performed_by: UserProfile | None
    performed_at: str
    old_values: dict[str, Any]
    new_values: dict[str, Any]


class BaseModelUpdateLog(models.Model):
    """Generic CRUD audit log for ``BaseModel`` rows (one row per create/update/delete).

    ``model`` + ``model_pk`` reference the target polymorphically (no
    ``GenericForeignKey``) so a log survives the target row's deletion.
    ``model_pk`` is the integer pk — server-side only; it is never sent to
    clients (the response carries the log's own uuid7 ``id`` instead). FK values
    inside ``old_values``/``new_values`` use the target's ``public_id``.
    """

    ACTION_CHOICES: ClassVar[list[tuple[str, str]]] = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("deleted", "Deleted"),
    ]

    id = models.UUIDField(primary_key=True, default=generate_uuid7_id, editable=False)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    performed_at = models.DateTimeField(default=timezone.now)
    model = models.CharField(max_length=255)
    model_pk = models.BigIntegerField()
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["model", "model_pk"]),
            models.Index(fields=["performed_at"]),
        ]
        ordering: ClassVar[list[str]] = ["-performed_at"]

    def to_entry_item(self) -> UpdateLogEntryItem:
        return UpdateLogEntryItem(
            id=str(self.pk),
            action=cast(Literal["created", "updated", "deleted"], self.action),
            performed_by=user_profile(self.performed_by),
            performed_at=self.performed_at.isoformat(),
            old_values=self.old_values,
            new_values=self.new_values,
        )
