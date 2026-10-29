from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection

from djangoapp.models import User


class Command(BaseCommand):
    """Read-only snapshot of the app database: tables, migrations, rows.

    Exists because sessions kept hand-rolling ``python -c`` introspection
    probes (each one a permission prompt) just to answer "what state is
    the DB in". Covers the three questions the probes asked: which tables
    exist, which migrations are recorded, how many rows ourapp's tables
    hold.

    Example output (truncated):

        TABLES
          account_emailaddress  ~0 rows
          auth_user  ~3 rows
          ourapp_chore  ~2 rows
        MIGRATIONS (ourapp / djangoapp / auth / contenttypes)
          djangoapp: 28 applied; last = 0028_backupmarker
          ourapp: 1 applied; last = 0001_initial
        USERS  4 total, 3 superuser(s)
    """

    help = "Read-only DB snapshot: tables (estimated rows), applied migrations, users."

    def handle(self, **_options: Any) -> None:  # noqa: ANN401 # Django passes **options as untyped command flags
        with connection.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            tables = [row[0] for row in cur.fetchall()]
            cur.execute(
                """
                SELECT app, name FROM django_migrations
                WHERE app IN ('ourapp', 'djangoapp', 'auth', 'contenttypes')
                ORDER BY app, id
                """
            )
            migrations = cur.fetchall()

            self.stdout.write("TABLES (estimated rows)")
            if not tables:
                self.stdout.write("  (no tables)")
            else:
                cur.execute(
                    """
                    SELECT relname, GREATEST(reltuples, 0)::bigint AS estimate
                    FROM pg_class
                    WHERE relnamespace = 'public'::regnamespace AND relname = ANY(%s)
                    ORDER BY relname
                    """,
                    [tables],
                )
                for name, estimate in cur.fetchall():
                    self.stdout.write(f"  {name}  ~{estimate} rows")

            self.stdout.write("MIGRATIONS (ourapp / djangoapp / auth / contenttypes)")
            per_app: dict[str, list[str]] = {}
            for app, name in migrations:
                per_app.setdefault(app, []).append(name)
            for app, names in per_app.items():
                self.stdout.write(f"  {app}: {len(names)} applied; last = {names[-1]}")

        users = User.objects.count()
        superusers = User.objects.filter(is_superuser=True).count()
        self.stdout.write(f"USERS  {users} total, {superusers} superuser(s)")
