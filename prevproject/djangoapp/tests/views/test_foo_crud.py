"""Tests for the self-contained FooView CRUD system (AllColumnsView at /allcolumns)."""

from typing import Any, cast

from django.test import TestCase

from djangoapp.models.app import AllColumns
from djangoapp.views.base import BaseView
from djangoapp.views.crud import FooView
from djangoapp.views.foo import SomeBase  # ensures CBV machinery importable


class FooCrudTests(TestCase):
    """AllColumnsView endpoints: create/update/details/list/download + columns rules.

    - test_list: /allcolumns lists rows as links
    - test_create_get: /create form includes createonly columns
    - test_create_post: /create POST saves a row and returns its public id
    - test_update_get_excludes_createonly: /update hides createonly columns
    - test_update_post: /update POST edits a row
    - test_details: /id/<public_id> shows all columns
    - test_download_no_file: download of an empty file field is 404
    """

    def setUp(self) -> None:
        self.row = AllColumns.objects.create(char_field="hello", text_field="world")

    def _props(self, url: str) -> dict[str, Any]:
        response = self.client.get(url, HTTP_X_INERTIA="true")
        self.assertEqual(response.status_code, 200)
        # Inertia page JSON nests the page props under "props", and this app's
        # pages further nest data under a "props" key (see FooView InertiaResponse).
        return cast(dict[str, Any], response.json()["props"]["props"])

    def test_list(self) -> None:
        """/allcolumns returns a row link per row."""
        props = self._props("/allcolumns")
        ids = [r["id"] for r in props["rows"]]
        self.assertIn(self.row.public_id, ids)

    def test_create_get(self) -> None:
        """/create form includes createonly columns (char_field, file_field)."""
        props = self._props("/allcolumns/create")
        self.assertIn("char_field", props["fields"])
        self.assertIn("file_field", props["fields"])

    def test_create_post(self) -> None:
        """/create POST saves a row and returns its public id."""
        response = self.client.post(
            "/allcolumns/create",
            data={"char_field": "abc", "text_field": "txt", "integer_field": "5"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["d"], "success")
        self.assertTrue(AllColumns.objects.filter(public_id=body["id"]).exists())

    def test_update_get_excludes_createonly(self) -> None:
        """/update form hides createonly columns (char_field, file_field)."""
        props = self._props(f"/allcolumns/update/{self.row.public_id}")
        self.assertNotIn("char_field", props["fields"])
        self.assertNotIn("file_field", props["fields"])
        self.assertIn("text_field", props["fields"])

    def test_update_post(self) -> None:
        """/update POST edits a row."""
        response = self.client.post(
            f"/allcolumns/update/{self.row.public_id}",
            data={"text_field": "changed"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["d"], "success")
        self.row.refresh_from_db()
        self.assertEqual(self.row.text_field, "changed")

    def test_details(self) -> None:
        """/id/<public_id> shows all declared columns."""
        props = self._props(f"/allcolumns/id/{self.row.public_id}")
        self.assertIn("char_field", props["cell_values"])
        self.assertIn("text_field", props["cell_values"])

    def test_download_no_file(self) -> None:
        """Downloading an empty file field returns 404."""
        response = self.client.get(f"/allcolumns/id/{self.row.public_id}/download/file_field")
        self.assertEqual(response.status_code, 404)

    def test_view_not_baseview(self) -> None:
        """FooView is built on the CBV SomeBase, not BaseView."""
        self.assertTrue(issubclass(FooView, SomeBase))
        self.assertNotIn(BaseView, FooView.__mro__)


class FooViewSmokeTests(TestCase):
    """Smoke checks for the `columns` declaration.

    - test_missing_columns_raises: a concrete FooView without `columns` fails
    """

    def test_missing_columns_raises(self) -> None:
        """Defining a FooView with a model but no columns raises TypeError."""
        with self.assertRaises(TypeError):

            class _Bad(FooView):
                model = AllColumns
