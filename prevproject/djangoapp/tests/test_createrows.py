# from __future__ import annotations

from typing import cast

from django.core.management import call_command
from django.db.models import QuerySet
from django.test import TestCase

from djangoapp.models.app import FirstStuff
from djangoapp.models.base import User


class CreateRowsCommandTest(TestCase):
    def test_create_rows(self) -> None:
        User.objects.create_user(
            username="testuser",
            email="foo@example.com",
        )

        call_command("createrows", email="foo@example.com")

        # Check that 20 rows were created
        rows: QuerySet[FirstStuff] = cast(QuerySet[FirstStuff], FirstStuff.objects.all())
        assert rows.count() == 200  # noqa: PLR2004 # Magic number

        # Check the values
        for i, row in enumerate(rows):
            assert row.char_field == "aaa"
            assert row.text_field == "bbb"
            assert row.integer_field == i
