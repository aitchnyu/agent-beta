from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import connection, models
from django.db.models import F
from django.http import Http404

from djangoapp.models.base import User, generate_uuid7_id
from djangoapp.utils import sanitize_html

if TYPE_CHECKING:
    from djangoapp.apps.dynamic_module import DynamicModule

# Identity/display names for collections/apps/tables: start with a letter,
# then alphanumeric only. Leading digit/underscore would collide with the
# underscore-prefixed built-in column namespace and is rejected. Names are
# the identity (used directly in physical table names and URLs), so they are
# validated up front instead of being slugified.
ALPHANUMERIC_RE = r"^[A-Za-z][A-Za-z0-9]*$"

# User-defined column names: must start with a letter and contain only
# letters/digits (no underscore). Built-in BaseTable columns are
# underscore-prefixed (_public_id, _created_by, ...), so the two namespaces
# can never collide.
COLUMN_NAME_RE = r"^[A-Za-z][A-Za-z0-9]*$"

alphanumeric_validator = RegexValidator(
    ALPHANUMERIC_RE,
    "Must start with a letter and contain only letters and digits.",
)
column_name_validator = RegexValidator(
    COLUMN_NAME_RE,
    "Column names must start with a letter and contain only letters and digits.",
)


class ColumnType(StrEnum):
    """The set of column types a user may declare on an ApplicationTable.

    Value-only: the stored value is also the value sent to the client, so no
    separate human "label" is kept. ``user`` is a ForeignKey to the project
    ``User`` model; every other type maps to a single Django field kind.
    """

    CHAR = "char"
    TEXT = "text"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DECIMAL = "decimal"
    DATETIME = "datetime"
    USER = "user"


class BaseTable(models.Model):
    """Abstract base for every dynamically-generated application table.

    Built-in columns are underscore-prefixed so they sit in a separate
    namespace from user columns (which must start with a letter). Each
    generated table subclasses this and gains one field per declared
    ApplicationTableColumn.
    """

    _public_id = models.CharField(
        max_length=100, db_index=True, editable=False, default=generate_uuid7_id
    )
    _created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="+",
    )
    _created_at = models.DateTimeField(auto_now_add=True)
    _edited_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ApplicationCollection(models.Model):
    """Top-level grouping of applications.

    ``name`` is both the display name and the identity used in physical
    table names (``zz_<collection_name>_<table_name>``) and URLs.
    """

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    name = models.CharField(max_length=100, unique=True, validators=[alphanumeric_validator])

    class Meta:
        db_table = "application_collection"
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self) -> str:
        """Display name."""
        return self.name


class Application(models.Model):
    """A single application within a collection.

    Holds a rich-text ``description`` (nh3-sanitized on save). ``name`` is
    unique within its collection; it may be renamed, but renaming only
    changes the display name (the physical table name omits the app).
    """

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    application_collection = models.ForeignKey(
        ApplicationCollection,
        on_delete=models.RESTRICT,
        related_name="applications",
    )
    name = models.CharField(max_length=100, validators=[alphanumeric_validator])
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "application"
        ordering: ClassVar[list[str]] = ["name"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                models.F("application_collection"),
                models.F("name"),
                name="application_collection_name_unique",
            ),
        ]

    def __str__(self) -> str:
        """Display name."""
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        # Rich text: sanitize on every write so stored HTML is always clean,
        # mirroring how UserUpdateSchema sanitizes description.
        self.description = sanitize_html(self.description)
        super().save(*args, **kwargs)  # type: ignore[arg-type] # Django Model.save is loosely typed

    @classmethod
    def get_by_names(cls, collection_name: str, app_name: str) -> Application:
        """Fetch an app by collection + app name (raises ``DoesNotExist``)."""
        return cls.objects.get(application_collection__name=collection_name, name=app_name)

    @classmethod
    def app_or_404(cls, collection_name: str, app_name: str) -> Application:
        """Fetch an app by collection + app name, raising ``Http404`` if absent."""
        try:
            return cls.get_by_names(collection_name, app_name)
        except cls.DoesNotExist as exc:
            msg = f"No app '{collection_name}/{app_name}'."
            raise Http404(msg) from exc

    # aihere no properties for this class
    @property
    def script_path(self) -> Path:
        """Absolute path to the app's ``app.py`` (``<apps_root>/<collection>/<app>``)."""
        from djangoapp.apps.dynamic_module import (  # noqa: PLC0415 # deferred: avoid applications <-> dynamic_module cycle
            apps_root,
        )

        return (apps_root() / self.application_collection.name / self.name / "app.py").resolve()

    @property
    def static_folder(self) -> Path:
        """Absolute dir the app's vite build writes to (derived from names)."""
        return (
            Path(str(settings.BASE_DIR))
            / "djangoapp"
            / "static"
            / "djangoapp"
            / "apps"
            / self.application_collection.name
            / self.name
        )

    @property
    def frontend_dir(self) -> Path:
        """The ``frontend/`` sibling of the app's ``app.py``."""
        return self.script_path.parent / "frontend"

    @property
    def app_bundle(self) -> tuple[str, str]:
        """``(static_url_base, cache_bust)`` for base.html to load the app's bundle.

        ``static_url_base`` is ``STATIC_URL`` + the static folder relative to the
        djangoapp app's static dir; ``cache_bust`` is the apps generation (bumped
        by ``setup``/``buildapp``), so a rebuild forces browsers to refetch.
        """
        static_root = Path(str(settings.BASE_DIR)) / "djangoapp" / "static"
        rel = self.static_folder.relative_to(static_root).as_posix()
        url_base = f"{settings.STATIC_URL}{rel}".rstrip("/")
        return url_base, str(AppsGeneration.current())

    def module(self) -> DynamicModule:
        """Load + return this app's :class:`DynamicModule` (its tagged functions)."""
        from djangoapp.apps.dynamic_module import (  # noqa: PLC0415 deferred: avoid applications <-> dynamic_module cycle
            app_modules,
        )

        return app_modules.load(self.script_path)

    # aihere should be .table_as_model(name)
    def get_table(self, name: str) -> Any:  # noqa: ANN401 # dynamic model: fields/manager not statically known
        """Return the dynamic model for one of this app's tables.

        Typed ``Any``: the model is built at runtime, so its fields/manager are
        not statically known.
        """
        return self.tables.get(name=name).as_model()


class ApplicationTable(models.Model):
    """A table definition inside an application.

    ``column_order`` records the user-facing order of column names. The
    physical table is created via the dynamic-model factory using
    ``zz_<physical_name>`` as its db_table. ``physical_name`` is an immutable,
    creation-time identifier (``<tablename><unix-seconds>``), so renaming the
    collection or the table's display ``name`` never touches the physical
    table. Because the display name is unique within the whole collection
    (it omits the app in URLs), that scoping is enforced in ``clean`` since
    UniqueConstraint cannot span the app->collection relation.
    """

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.RESTRICT,
        related_name="tables",
    )
    name = models.CharField(max_length=100, validators=[alphanumeric_validator])
    # Immutable physical identity; decoupled from display name so renames
    # need no DDL.
    physical_name = models.CharField(max_length=200, unique=True, editable=False)
    column_order = models.JSONField(default=list)

    class Meta:
        db_table = "application_table"
        ordering: ClassVar[list[str]] = ["name"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # App-scoped uniqueness is the strongest relation-spanning
            # guarantee the DB gives us; collection-scoped uniqueness is
            # reinforced in clean() to prevent physical table-name clashes.
            models.UniqueConstraint(
                models.F("application"),
                models.F("name"),
                name="application_table_app_name_unique",
            ),
        ]

    def __str__(self) -> str:
        """Display name."""
        return self.name

    @property
    def collection(self) -> ApplicationCollection:
        return self.application.application_collection

    def ordered_columns(self) -> list[ApplicationTableColumn]:
        """Return this table's columns in ``column_order``.

        ``column_order`` is the source of truth for display order and is
        always in sync with the table's columns, so a plain dict lookup
        suffices.
        """
        by_name = {c.name: c for c in self.columns.all()}
        return [by_name[name] for name in self.column_order]

    def as_model(self) -> type[BaseTable]:
        """Return the generated dynamic model for this table (built + cached by the registry).

        Thin delegate: the registry owns the cache and rebuild-on-miss logic
        (see ``dynamic_models.get_model``); the table contributes its identity
        (``physical_name``). Deferred import breaks the dynamic.py cycle.
        """
        from djangoapp.models.dynamic import (  # noqa: PLC0415 circular import with dynamic.py
            dynamic_models,
        )

        return dynamic_models.get_model(self.physical_name)

    def does_physical_table_exist(self) -> bool:
        """Whether this table's physical Postgres table exists."""
        # dynamic_db_table lives in dynamic.py, which imports this module, so
        # the import must be deferred to avoid a circular import at load time.
        from djangoapp.models.dynamic import (  # noqa: PLC0415 circular import with dynamic.py
            dynamic_db_table,
        )

        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", [dynamic_db_table(self.physical_name)])
            return cur.fetchone()[0] is not None

    def physical_columns(self) -> list[str]:
        """Ordered column names of this table's physical Postgres table."""
        # See does_physical_table_exist: deferred to break the dynamic.py cycle.
        from djangoapp.models.dynamic import (  # noqa: PLC0415 circular import with dynamic.py
            dynamic_db_table,
        )

        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                [dynamic_db_table(self.physical_name)],
            )
            return [r[0] for r in cur.fetchall()]

    def clean(self) -> None:
        super().clean()
        # Collection-scoped uniqueness of the display name (URL identity).
        siblings = ApplicationTable.objects.filter(
            application__application_collection=self.collection,
        ).exclude(pk=self.pk)
        if self.name and siblings.filter(name=self.name).exists():
            msg = f"A table named '{self.name}' already exists in collection '{self.collection.name}'."  # noqa: E501 let user-facing message stay on one line
            raise ValidationError({"name": msg})

    @staticmethod
    def make_physical_name(name: str) -> str:
        """Build an immutable physical name: ``<tablename><unix-seconds>``.

        On a (rare) second-granularity collision, the timestamp is bumped by
        one second and retried (no separate suffix), so every physical name
        keeps the same ``<name><seconds>`` shape and the field's global
        uniqueness holds.
        """
        stamp = int(time.time())
        candidate = f"{name}{stamp}"
        while ApplicationTable.objects.filter(physical_name=candidate).exists():
            stamp += 1
            candidate = f"{name}{stamp}"
        return candidate


class ApplicationTableColumn(models.Model):
    """A single column definition on an ApplicationTable.

    Only the fields relevant to a column's ``type`` are meaningful; the
    others are ignored. Per-type defaults (``text_default``, ``int_default``,
    ``boolean_default``, ``decimal_default``) and decimal precision
    (``decimal_max_digits``/``decimal_places``) are stored here and applied
    when the dynamic model field is built.
    """

    TYPE_CHOICES: ClassVar[list[tuple[str, str]]] = [(t.value, t.value) for t in ColumnType]

    public_id = models.CharField(
        max_length=36,
        unique=True,
        editable=False,
        default=generate_uuid7_id,
    )
    application_table = models.ForeignKey(
        ApplicationTable,
        on_delete=models.RESTRICT,
        related_name="columns",
    )
    name = models.CharField(max_length=100, validators=[column_name_validator])
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    char_choices = models.JSONField(default=list, blank=True)
    text_default = models.TextField(blank=True, default="")
    text_min_length = models.PositiveIntegerField(default=0)
    text_max_length = models.PositiveIntegerField(default=1000)
    nullable = models.BooleanField(default=False)
    int_default = models.IntegerField(null=True, blank=True)
    boolean_default = models.BooleanField(default=False)
    decimal_default = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        null=True,
        blank=True,
    )
    decimal_max_digits = models.PositiveIntegerField(default=10)
    decimal_places = models.PositiveIntegerField(default=2)

    class Meta:
        db_table = "application_table_column"
        ordering: ClassVar[list[str]] = ["name"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                models.F("application_table"),
                models.F("name"),
                name="application_table_column_name_unique",
            ),
        ]

    def __str__(self) -> str:
        """Table-qualified column label."""
        return f"{self.application_table.name}.{self.name} ({self.type})"

    def clean(self) -> None:
        super().clean()
        # char/text share text_* fields; char_choices only valid for char.
        if self.type != ColumnType.CHAR and self.char_choices:
            msg = "char_choices is only valid for char columns."
            raise ValidationError({"char_choices": msg})
        if self.text_max_length < self.text_min_length:
            msg = "text_max_length cannot be less than text_min_length."
            raise ValidationError({"text_max_length": msg})
        if self.decimal_places > self.decimal_max_digits:
            msg = "decimal_places cannot exceed decimal_max_digits."
            raise ValidationError({"decimal_places": msg})


# aihere remove middleware reference
class AppsGeneration(models.Model):
    """Singleton counter tracking the installed-apps generation.

    ``setup`` bumps it on a successful install. The invalidation middleware
    compares each worker's last-seen value to the live one and, on a change,
    resets the dynamic-model + app-module caches — so a running devserver or
    gunicorn worker picks up the latest installed app/models without a restart.
    Cross-worker/hosts-safe via the shared DB (no in-process cache).
    """

    value = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "apps_generation"

    _PK: ClassVar[int] = 1

    @classmethod
    def current(cls) -> int:
        """Return the live generation (creating the singleton row if absent)."""
        obj, _ = cls.objects.get_or_create(pk=cls._PK)
        return obj.value

    @classmethod
    def bump(cls) -> None:
        """Atomically increment the generation (called by ``setup`` on success)."""
        cls.objects.get_or_create(pk=cls._PK)
        cls.objects.filter(pk=cls._PK).update(value=F("value") + 1)


__all__ = [
    "ALPHANUMERIC_RE",
    "COLUMN_NAME_RE",
    "Application",
    "ApplicationCollection",
    "ApplicationTable",
    "ApplicationTableColumn",
    "AppsGeneration",
    "BaseTable",
    "ColumnType",
]
