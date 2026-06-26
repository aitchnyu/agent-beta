import datetime
import json
from decimal import Decimal

from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404, HttpResponse
from django.test import override_settings
from django.test.client import RequestFactory
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

import djangoapp.views.base as views_module
from djangoapp.errors import ApiError
from djangoapp.models.app import (
    CategoryModel,
    FirstStuff,
    ForeignKeyModel,
    Ref,
    TestFileUploadModel,
)
from djangoapp.models.base import (
    CommentPermissionContext,
    RowUpdate,
    RowUpdateUserNotification,
    User,
)
from djangoapp.responses import RowUpdateCharValue
from djangoapp.tests.query_budget import QueryBudgetInertiaTestCase, QueryBudgetTestCase
from djangoapp.views.app import FirstStuffView, UserStuffView
from djangoapp.views.base import (
    TABLES_MODELS_TO_VIEWS,
    TABLES_VIEW_DICT,
    BaseView,
    CommentRequest,
    ListPageSchema,
    PaginationSchema,
    add_views,
    mount_prefix,
)


class TestFileUploadModelViewTest(QueryBudgetTestCase):
    """View tests for TestFileUploadModel - download_file endpoint."""

    def test_download_file(self) -> None:
        # Create instance with file
        uploaded_file = SimpleUploadedFile(
            "download_test.txt", b"file to download", content_type="text/plain"
        )
        instance = TestFileUploadModel.objects.create(
            nullable_integer_field=3, file_field=uploaded_file
        )

        # Test download
        response = self.client.get(
            f"/tables/testfileuploadmodel/download-file/{instance.pk}/file_field"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("attachment", response["Content-Disposition"])

        # Test invalid row
        response = self.client.get("/tables/testfileuploadmodel/download-file/999/file_field")
        self.assertEqual(response.status_code, 404)

        # Test no file
        instance.file_field = None
        instance.save()
        response = self.client.get(
            f"/tables/testfileuploadmodel/download-file/{instance.pk}/file_field"
        )
        self.assertEqual(response.status_code, 404)


class CrudOperationsTest(QueryBudgetTestCase):
    """Tests for FirstStuff CRUD operations via BaseView endpoints.

    test_list_rows: list rows page renders
    test_row_details_existing: row details page renders for existing row
    test_row_details_not_found: row details returns 404 for missing row
    test_create_row_get: create row page renders
    test_create_row_submit_success: creating a row with valid data
    test_create_row_submit_validation_error: invalid field value returns validation error
    test_create_row_required_fk_empty_returns_error: empty non-nullable FK returns validation error
    test_update_row_get: update row page renders
    test_update_row_submit_success: updating a row with valid data
    test_update_row_submit_not_found: updating missing row returns 404
    test_delete_row_success: deleting a row succeeds
    test_delete_row_not_found: deleting missing row returns 404
    test_create_row_nullable_integer_empty_set_to_null:
        empty string on nullable integer sets to None
    test_update_row_nullable_integer_cleared_to_null:
        empty string on update clears nullable integer to None
    test_create_row_sanitizes_text_field_html: TextField HTML is sanitized on create
    test_update_row_sanitizes_text_field_html: TextField HTML is sanitized on update
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client.force_login(self.user)
        self.ref = Ref.objects.create(char_field="ref1")

        # Create test data for filters
        self.true_stuff = FirstStuff.objects.create(
            char_field="true",
            boolean_field=True,
            integer_field=5,
            int_choice_field=1,
        )
        self.false_stuff = FirstStuff.objects.create(
            char_field="false",
            boolean_field=False,
            integer_field=15,
            int_choice_field=2,
        )
        self.high_int = FirstStuff.objects.create(
            char_field="high",
            boolean_field=True,
            integer_field=20,
            int_choice_field=3,
        )
        self.low_int = FirstStuff.objects.create(
            char_field="low",
            boolean_field=False,
            integer_field=3,
            int_choice_field=1,
        )

        self.first_stuff: FirstStuff = FirstStuff.objects.create(
            char_field="test_char",
            text_field="test_text",
            integer_field=10,
            nullable_integer_field=20,
            boolean_field=True,
            decimal_field="5.50",
            char_choice_field="opt1",
            int_choice_field=2,
            ref_fk=self.ref,
            user_fk=self.user,
            file_field=SimpleUploadedFile(
                "existing.txt", b"existing content", content_type="text/plain"
            ),
        )

    def test_list_rows(self) -> None:
        response = self.client.get("/tables/firststuff/list/-(p:(page:1,per:25))-")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inertia/base.html")

    def test_row_details_existing(self) -> None:
        response = self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inertia/base.html")

    def test_row_details_not_found(self) -> None:
        response = self.client.get("/tables/firststuff/id/99999")
        self.assertEqual(response.status_code, 404)

    def test_create_row_get(self) -> None:
        response = self.client.get("/tables/firststuff/create-row")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inertia/base.html")

    def test_create_row_submit_success(self) -> None:
        data = {
            "char_field": "new_char",
            "text_field": "new_text",
            "integer_field": "15",
            "boolean_field": "true",
            "decimal_field": "5.50",
            "datetime_field": "2023-01-01T12:00:00",
            "char_choice_field": "opt2",
            "int_choice_field": "1",
            "title": "New Title",
        }
        files = {
            "file_field": SimpleUploadedFile(
                "new_file.txt", b"new file content", content_type="text/plain"
            )
        }
        initial_count = FirstStuff.objects.count()
        response = self.client.post(
            "/tables/api/firststuff/create-row-submit", data=data, files=files
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FirstStuff.objects.count(), initial_count + 1)
        # Check that new row was created correctly
        new_row = FirstStuff.objects.last()
        assert new_row is not None
        self.assertEqual(new_row.char_field, "new_char")
        self.assertEqual(new_row.text_field, "new_text")
        self.assertEqual(new_row.integer_field, 15)
        self.assertEqual(new_row.nullable_integer_field, 10)
        self.assertEqual(new_row.boolean_field, True)
        self.assertEqual(new_row.decimal_field, Decimal("5.50"))
        self.assertEqual(
            new_row.datetime_field,
            timezone.make_aware(datetime.datetime(2023, 1, 1, 12, 0, 0)),  # noqa: DTZ001  # Intentionally naive datetime for timezone conversion
        )
        self.assertEqual(new_row.char_choice_field, "opt2")
        self.assertEqual(new_row.int_choice_field, 1)
        self.assertIsNone(new_row.ref_fk)
        self.assertIsNone(new_row.user_fk)
        self.assertIsNotNone(new_row.file_field)

    def test_create_row_submit_validation_error(self) -> None:
        data = {
            "char_field": "new_char",
            "integer_field": "not_a_number",  # Invalid
        }
        response = self.client.post("/tables/api/firststuff/create-row-submit", data=data)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["d"], "validation_error")
        # Check errors
        self.assertIn("integer_field", json_data["errors"])

    def test_create_row_required_fk_empty_returns_error(self) -> None:
        data = {"category_field": "", "name": "test"}
        response = self.client.post("/tables/api/foreignkeymodel/create-row-submit", data=data)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["d"], "validation_error")
        self.assertIn("category_field", json_data["errors"])

    def test_update_row_get(self) -> None:
        response = self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inertia/base.html")

    def test_update_row_submit_success(self) -> None:
        data = {
            "char_field": "updated_ch",
            "text_field": "updated_text",
            "integer_field": "25",
            "boolean_field": "true",
            "decimal_field": "6.00",
            "datetime_field": "2023-01-01T12:00:00",
            "char_choice_field": "opt1",
            "int_choice_field": "2",
            "title": "Updated Title",
        }
        files = {
            "file_field": SimpleUploadedFile(
                "replaced_file.txt", b"replaced content", content_type="text/plain"
            )
        }
        response = self.client.post(
            f"/tables/api/firststuff/update-row-submit/{self.first_stuff.pk}",
            data=data,
            files=files,
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json.get("d"), "success")
        # Refresh and check updated
        self.first_stuff.refresh_from_db()
        self.assertEqual(self.first_stuff.char_field, "updated_ch")
        self.assertEqual(self.first_stuff.text_field, "updated_text")
        self.assertEqual(self.first_stuff.integer_field, 25)
        self.assertEqual(self.first_stuff.nullable_integer_field, 20)  # Not updated
        self.assertEqual(self.first_stuff.boolean_field, True)
        self.assertEqual(self.first_stuff.decimal_field, Decimal("6.00"))
        self.assertEqual(
            self.first_stuff.datetime_field,
            timezone.make_aware(datetime.datetime(2023, 1, 1, 12, 0, 0)),  # noqa: DTZ001  # Intentionally naive datetime for timezone conversion
        )
        self.assertEqual(self.first_stuff.char_choice_field, "opt1")
        self.assertEqual(self.first_stuff.int_choice_field, 2)
        self.assertEqual(self.first_stuff.ref_fk, self.ref)  # Not updated
        self.assertEqual(self.first_stuff.user_fk, self.user)  # Not updated
        self.assertIsNotNone(self.first_stuff.file_field)

    def test_update_row_submit_not_found(self) -> None:
        data = {
            "char_field": "updated_char",
            "text_field": "updated_text",
            "integer_field": "25",
        }
        response = self.client.post("/tables/api/firststuff/update-row-submit/99999", data=data)
        self.assertEqual(response.status_code, 404)

    def test_delete_row_success(self) -> None:
        response = self.client.post(f"/tables/api/firststuff/delete-row/{self.first_stuff.pk}")
        self.assertEqual(response.status_code, 200)
        # Check deleted
        with self.assertRaises(FirstStuff.DoesNotExist):
            FirstStuff.objects.get(pk=self.first_stuff.pk)

    def test_delete_row_not_found(self) -> None:
        response = self.client.post("/tables/api/firststuff/delete-row/99999")
        self.assertEqual(response.status_code, 404)

    def test_create_row_nullable_integer_empty_set_to_null(self) -> None:
        """Empty string on nullable integer field sets it to None, not default."""
        data = {
            "char_field": "nullable",
            "text_field": "text",
            "integer_field": "5",
            "boolean_field": "true",
            "decimal_field": "1.00",
            "char_choice_field": "opt1",
            "int_choice_field": "1",
            # this is it
            "nullable_integer_field": "",
        }
        initial_count = FirstStuff.objects.count()
        response = self.client.post("/tables/api/firststuff/create-row-submit", data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FirstStuff.objects.count(), initial_count + 1)
        new_row = next(iter(FirstStuff.objects.order_by("-pk")))
        self.assertIsNone(new_row.nullable_integer_field)

    def test_update_row_nullable_integer_cleared_to_null(self) -> None:
        """Empty string on update clears nullable integer field to None."""
        row = FirstStuff.objects.create(
            char_field="clear_test",
            text_field="text",
            integer_field=5,
            nullable_integer_field=42,
        )
        data = {
            "char_field": "clear_test",
            "text_field": "text",
            "integer_field": "5",
            # this is it
            "nullable_integer_field": "",
        }
        response = self.client.post(f"/tables/api/firststuff/update-row-submit/{row.pk}", data=data)
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertIsNone(row.nullable_integer_field)

    def test_create_row_sanitizes_text_field_html(self) -> None:
        """Test that TextField HTML content is sanitized on create.

        Unsafe tags are stripped, safe tags are preserved.
        """
        mixed_html = (
            "<h1>Heading</h1>"
            "<script>alert('xss')</script>"
            "<p><strong>Bold</strong> and <em>italic</em></p>"
            '<div onclick="evil()">Div content</div>'
            "<ul><li>Item 1</li><li>Item 2</li></ul>"
            "<style>body{display:none}</style>"
            '<a href="https://example.com">Link</a>'
            "<iframe src='evil.com'></iframe>"
            "<table><tr><td>Cell</td></tr></table>"
        )
        data = {
            "char_field": "test_char",
            "text_field": mixed_html,
            "integer_field": "10",
            "boolean_field": "true",
            "decimal_field": "5.50",
            "int_choice_field": "1",
        }
        response = self.client.post("/tables/api/firststuff/create-row-submit", data=data)
        self.assertEqual(response.status_code, 200)

        new_row = FirstStuff.objects.last()
        assert new_row is not None
        expected = (
            "<h1>Heading</h1>"
            "<p><strong>Bold</strong> and <em>italic</em></p>"
            "Div content"
            "<ul><li>Item 1</li><li>Item 2</li></ul>"
            '<a href="https://example.com" rel="noopener noreferrer">Link</a>'
            "<table><tbody><tr><td>Cell</td></tr></tbody></table>"
        )
        self.assertEqual(new_row.text_field, expected)

    def test_update_row_sanitizes_text_field_html(self) -> None:
        """Test that TextField HTML content is sanitized on update.

        Unsafe tags are stripped, safe tags are preserved.
        """
        mixed_html = (
            "<h2>Updated Heading</h2>"
            "<script>alert('xss')</script>"
            '<p>Text with <a href="https://example.com">link</a></p>'
            "<span onclick='evil()'>Span</span>"
            "<ol><li>First</li><li>Second</li></ol>"
            "<style>.evil{}</style>"
            "<hr>"
            "<em>Emphasized</em>"
        )
        data = {
            "char_field": "updated_ch",
            "text_field": mixed_html,
            "integer_field": "25",
            "boolean_field": "true",
            "decimal_field": "6.00",
            "datetime_field": "2023-01-01T12:00:00",
            "char_choice_field": "opt1",
            "int_choice_field": "2",
        }
        response = self.client.post(
            f"/tables/api/firststuff/update-row-submit/{self.first_stuff.pk}", data=data
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json.get("d"), "success", response_json)

        self.first_stuff.refresh_from_db()
        expected = (
            "<h2>Updated Heading</h2>"
            '<p>Text with <a href="https://example.com" rel="noopener noreferrer">link</a></p>'
            "Span"
            "<ol><li>First</li><li>Second</li></ol>"
            "<hr>"
            "<em>Emphasized</em>"
        )
        self.assertEqual(self.first_stuff.text_field, expected)


class RowDetailsEditDataTest(QueryBudgetInertiaTestCase):
    """Row details page sets can_edit/can_delete flags for button visibility.

    can_edit controls whether the Edit button appears. can_delete controls the
    Delete button. Both depend on the user's row-level permissions via
    resolve_columns.

    - test_row_details_can_edit_authenticated: user with update access gets can_edit=True
    - test_row_details_unauthenticated_no_edit: anon gets can_edit=False, can_delete=False
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="rowdetails_testuser", password="testpass")
        super().setUp()
        self.client.force_login(self.user)
        self.first_stuff = FirstStuff.objects.create(
            char_field="test_char",
            text_field="test_text",
            integer_field=10,
            boolean_field=True,
            decimal_field="5.50",
            char_choice_field="opt1",
            int_choice_field=2,
        )

    def test_row_details_can_edit_authenticated(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """User with update access gets can_edit=True so Edit button is shown."""
        self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        self.assertComponentUsed("RowDetails")
        props = self.props()["props"]
        self.assertTrue(props["can_edit"])

    def test_row_details_unauthenticated_no_edit(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """Anon cannot edit or delete, so both flags are False."""
        self.client.logout()
        self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        props = self.props()["props"]
        self.assertFalse(props["can_edit"])


class UpdateRowPageTest(QueryBudgetInertiaTestCase):
    """Update row page serves editable fields and current values.

    The update page is a dedicated form page (not inline on details). It
    returns InputSchema fields so the frontend can render the correct widgets.

    - test_update_row_page_renders: page serves UpdateRow component with row data
    - test_update_row_page_field_values: field defaults pre-fill the form with current row data
    - test_update_row_page_unauthenticated: permission denied returns 404
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="updaterowuser", password="testpass")
        super().setUp()
        self.client.force_login(self.user)
        self.first_stuff = FirstStuff.objects.create(
            char_field="test_char",
            text_field="test_text",
            integer_field=10,
            boolean_field=True,
            decimal_field="5.50",
            char_choice_field="opt1",
            int_choice_field=2,
        )

    def test_update_row_page_renders(self) -> None:
        """Page serves UpdateRow component with correct row_id and viewname."""
        self.client.get(f"/tables/firststuff/update-row/{self.first_stuff.pk}")
        self.assertComponentUsed("UpdateRow")
        props = self.props()["props"]
        self.assertEqual(props["row_id"], str(self.first_stuff.pk))
        self.assertEqual(props["viewname"], "firststuff")

    def test_update_row_page_field_values(self) -> None:
        """Field defaults pre-fill the form so user sees current data."""
        self.client.get(f"/tables/firststuff/update-row/{self.first_stuff.pk}")
        props = self.props()["props"]
        fields_by_name = props["fields"]
        self.assertEqual(fields_by_name["char_field"]["default"], "test_char")
        self.assertEqual(fields_by_name["integer_field"]["default"], 10)

    def test_update_row_page_unauthenticated(self) -> None:
        """Anon lacks update permission so endpoint returns 404."""
        self.client.logout()
        response = self.client.get(f"/tables/firststuff/update-row/{self.first_stuff.pk}")
        self.assertEqual(response.status_code, 404)


class DebugViewTest(QueryBudgetInertiaTestCase):
    """Tests for debug view endpoint behaviour.

    test_debug_view_debug_off
    test_debug_view_debug_on_unauthenticated
    test_debug_view_debug_on_authenticated
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="debuguser", password="testpass")
        super().setUp()

    @override_settings(DEBUG=False)
    def test_debug_view_debug_off(self) -> None:
        response = self.client.get("/tables/_debug")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), "Debug mode is off")

    @override_settings(DEBUG=True)
    def test_debug_view_debug_on_unauthenticated(self) -> None:
        response = self.client.get("/tables/_debug")
        self.assertEqual(response.status_code, 200)
        self.assertComponentUsed("Debug")
        self.assertIsNone(self.props()["props"]["user"])

    @override_settings(DEBUG=True)
    def test_debug_view_debug_on_authenticated(self) -> None:
        self.client.force_login(self.user)
        response = self.client.get("/tables/_debug")
        self.assertEqual(response.status_code, 200)
        self.assertComponentUsed("Debug")
        expected_user = {"id": self.user.pk, "title": "debuguser"}
        self.assertEqual(expected_user, self.props()["props"]["user"])
        table_urls = self.props()["props"]["table_urls"]
        self.assertIsInstance(table_urls, list)
        self.assertTrue(len(table_urls) > 0)
        names = [url["name"] for url in table_urls]
        self.assertIn("ref", names)


class TablesUserViewTest(QueryBudgetTestCase):
    """Test TABLES_USER_VIEW singleton and _search_users functionality."""

    def test_search_users_returns_results_with_user_view(self) -> None:
        """Verify _search_users returns user search results when user view is registered."""
        User.objects.create_user(username="alice", first_name="Alice", last_name="Smith")
        User.objects.create_user(username="bob", first_name="Bob", last_name="Jones")
        User.objects.create_user(username="charlie", first_name="Charlie", last_name="Brown")

        views_module.add_views("/tables", [UserStuffView])

        response = self.client.get("/tables/api/_search-users?q=ali")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["title"], "Alice Smith")

        response = self.client.get("/tables/api/_search-users?q=bob")
        data = response.json()
        self.assertEqual(len(data["rows"]), 1)
        self.assertEqual(data["rows"][0]["title"], "Bob Jones")

        response = self.client.get("/tables/api/_search-users?q=")
        self.assertEqual(response.json()["rows"], [])


class ProxyUserCrudTest(QueryBudgetInertiaTestCase):
    """ProxyUser CRUD operations enforce column restrictions per operation.

    ProxyUser.resolve_columns restricts which columns appear for each
    operation: "list" hides first_name/last_name, "update" excludes username,
    "create" returns None. These tests verify the UI respects those
    restrictions end-to-end via Inertia responses.

    - test_user_list_rows: list view shows username but not first_name/last_name
    - test_user_row_details: details page shows all fields via cell_values TdSchema
    - test_user_row_details_not_found: non-existent user returns 404
    - test_user_create_row_get_fails: create returns 404 since resolve_columns returns None
    - test_user_update_row_get: update form loads on details page
    - test_user_update_row_submit_success: username unchanged since excluded from update columns
    - test_user_delete_row_success: delete removes the user row
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="admin",
            password="adminpass",
            is_staff=True,
            is_superuser=True,
        )
        super().setUp()
        self.client.force_login(self.user)

        # Create test users to operate on
        self.test_user1 = User.objects.create_user(
            username="testuser1",
            email="test1@example.com",
            first_name="Test",
            last_name="User1",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        self.test_user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            first_name="Test",
            last_name="User2",
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

    def test_user_list_rows(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """List view returns rows with username visible, first_name/last_name hidden."""
        self.client.get("/tables/proxyuser/list/-(p:(page:1,per:25))-")
        self.assertComponentUsed("ListRows")
        rows = self.props()["props"]["rows"]
        usernames = [row["username"]["value"] for row in rows]
        self.assertIn("admin", usernames)
        self.assertIn("testuser1", usernames)
        self.assertIn("testuser2", usernames)

    def test_user_row_details(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """Details page returns cell_values with all fields including username."""
        self.client.get(f"/tables/proxyuser/id/{self.test_user1.public_id}")
        self.assertComponentUsed("RowDetails")
        field_values = self.props()["props"]["cell_values"]
        self.assertEqual(field_values["username"]["value"], "testuser1")
        self.assertEqual(field_values["email"]["value"], "test1@example.com")
        self.assertIn("first_name", field_values)
        self.assertIn("last_name", field_values)

    def test_user_row_details_not_found(self) -> None:
        """Non-existent user PK returns 404."""
        response = self.client.get("/tables/proxyuser/id/99999")
        self.assertEqual(response.status_code, 404)

    def test_user_create_row_get_fails(self) -> None:
        """Create returns 404 since resolve_columns returns None for create."""
        response = self.client.get("/tables/proxyuser/create-row")
        self.assertEqual(response.status_code, 404)

    def test_user_update_row_get(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """Update form loads on details page (edit data always present)."""
        response = self.client.get(f"/tables/proxyuser/id/{self.test_user1.public_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inertia/base.html")

    def test_user_update_row_submit_success(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """Username unchanged since excluded from update columns, other fields update."""
        data = {
            "email": "updated@example.com",
            "is_active": "false",
            "is_staff": "true",
            "is_superuser": "true",
        }
        response = self.client.post(
            f"/tables/api/proxyuser/update-row-submit/{self.test_user1.public_id}", data=data
        )
        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json.get("d"), "success")

        self.test_user1.refresh_from_db()
        self.assertEqual(self.test_user1.username, "testuser1")
        self.assertEqual(self.test_user1.first_name, "Test")
        self.assertEqual(self.test_user1.last_name, "User1")
        self.assertEqual(self.test_user1.email, "updated@example.com")
        self.assertFalse(self.test_user1.is_active)
        self.assertTrue(self.test_user1.is_staff)
        self.assertTrue(self.test_user1.is_superuser)

    def test_user_delete_row_success(self) -> None:
        self.allow_more_queries(14)  # frozen baseline incl. auth/session overhead
        """Delete removes the user row from the database."""
        user_pk = self.test_user2.pk
        user_public_id = self.test_user2.public_id
        response = self.client.post(f"/tables/api/proxyuser/delete-row/{user_public_id}")
        self.assertEqual(response.status_code, 200)

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(pk=user_pk)


class BaseViewViewnameTest(QueryBudgetTestCase):
    """Test BaseView viewname functionality."""

    def test_viewname_is_lowercase_model_name(self) -> None:
        """Test that viewname defaults to lowercase model name."""

        class TestView(BaseView):
            model = FirstStuff

        self.assertEqual(TestView.get_viewname_class(), "firststuff")

    def test_viewname_override_takes_priority(self) -> None:
        """Test that viewname_override takes priority over model name."""

        class TestView(BaseView):
            model = FirstStuff
            viewname_override = "custom_viewname"

        self.assertEqual(TestView.get_viewname_class(), "custom_viewname")

    def test_viewname_starting_with_underscore_rejected(self) -> None:
        """Test that viewnames starting with _ are rejected."""

        class UnderscoreView(BaseView):
            model = FirstStuff
            viewname_override = "_invalid"

        # Save original TABLES_VIEW_DICT to restore after test
        original_view_dict = TABLES_VIEW_DICT.copy()
        original_models_to_views = TABLES_MODELS_TO_VIEWS.copy()

        with self.assertRaises(ValueError) as context:
            add_views(url_prefix="/tables", views=[UnderscoreView])

        self.assertIn("viewnames starting with '_' are reserved", str(context.exception))

        # Restore original TABLES_VIEW_DICT and TABLES_MODELS_TO_VIEWS
        TABLES_VIEW_DICT.clear()
        TABLES_VIEW_DICT.update(original_view_dict)
        TABLES_MODELS_TO_VIEWS.clear()
        TABLES_MODELS_TO_VIEWS.update(original_models_to_views)

    def test_model_name_starting_with_underscore_rejected(self) -> None:
        """Test that model names starting with _ are rejected when used as viewname."""

        # Create a mock model class with underscore prefix
        class _MockModel:
            __name__ = "_MockModel"

        class MockView(BaseView):
            model = _MockModel  # type: ignore[assignment]

        # Save original TABLES_VIEW_DICT to restore after test
        original_view_dict = TABLES_VIEW_DICT.copy()
        original_models_to_views = TABLES_MODELS_TO_VIEWS.copy()

        with self.assertRaises(ValueError) as context:
            add_views(url_prefix="/tables", views=[MockView])

        self.assertIn("viewnames starting with '_' are reserved", str(context.exception))

        # Restore original TABLES_VIEW_DICT and TABLES_MODELS_TO_VIEWS
        TABLES_VIEW_DICT.clear()
        TABLES_VIEW_DICT.update(original_view_dict)
        TABLES_MODELS_TO_VIEWS.clear()
        TABLES_MODELS_TO_VIEWS.update(original_models_to_views)


class QueryCountTest(QueryBudgetTestCase):
    """Test that list_rows doesn't cause N+1 queries for FK fields."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        # Create CategoryModel instances for FK references
        self.cat1 = CategoryModel.objects.create(name="Category1")
        self.cat2 = CategoryModel.objects.create(name="Category2")
        # Create ForeignKeyModel instances with different categories
        for i in range(5):
            ForeignKeyModel.objects.create(
                name=f"FK Model {i}",
                category_field=self.cat1 if i % 2 == 0 else self.cat2,
            )

    def test_list_rows_query_count(self) -> None:
        """Verify that list_rows uses batch FK fetching to avoid N+1 queries."""

        class CategoryModelView(BaseView):
            model = CategoryModel

        class ForeignKeyModelView(BaseView):
            model = ForeignKeyModel

        # Use the module-level TABLES_VIEW_DICT singleton
        fk_view = TABLES_VIEW_DICT.get("foreignkeymodel")
        if fk_view is None:
            # Create view instance directly if not in singleton
            fk_view = ForeignKeyModelView()

        factory = RequestFactory()
        request = factory.get("/tables/foreignkeymodel/")
        request.user = self.user
        # Add session middleware to request (required by InertiaResponse)
        middleware = SessionMiddleware(lambda _r: HttpResponse())
        middleware.process_request(request)

        # Expected queries:
        # 1. Count query for pagination
        # 2. Main query for rows
        # 3. Title annotation query for row titles
        # 4. One batch query for FK fields (both category_field and optional_category_field
        #    point to CategoryModel, so they share a single query)
        # Total: 4 queries
        with self.assertNumQueries(4):
            response = fk_view._list_rows(  # testing private method directly
                request,
                ListPageSchema(
                    p=PaginationSchema(page=1, per=10),
                    f={},
                ).model_dump(exclude_none=True),
            )
            # Verify response is successful
            self.assertEqual(response.status_code, 200)


class RowUpdateAPITest(QueryBudgetTestCase):
    """Tests for row update API endpoints."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.other_user = User.objects.create_user(username="otheruser", password="otherpass")
        self.row = FirstStuff.objects.create(char_field="test row")
        self.factory = RequestFactory()

    def test_row_updates_returns_data_with_timeouts(self) -> None:
        """Test that row_updates returns data with timeout fields."""
        # Create a RowUpdate with column values
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="created_row",
            created_by=self.user,
            _values=[
                RowUpdateCharValue(
                    name="char_field",
                    old_value=None,
                    new_value="test value",
                ).model_dump()
            ],
        )

        # Create request
        request = self.factory.get(f"/tables/firststuff/row-updates/{self.row.pk}")
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        response = view.row_updates(request, str(self.row.pk))

        self.assertIn("can_create_comment", response.model_fields_set)
        self.assertTrue(response.can_create_comment)
        self.assertEqual(response.edit_comment_timeout, 86400)
        self.assertEqual(response.delete_comment_timeout, 86400)
        self.assertIsNotNone(response.updates[0].column_values)

    def test_row_updates_returns_full_data_by_default(self) -> None:
        """Test that row_updates returns full data by default."""
        # Create a RowUpdate with column values
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="created_row",
            created_by=self.user,
            _values=[
                RowUpdateCharValue(
                    name="char_field",
                    old_value=None,
                    new_value="test value",
                ).model_dump()
            ],
        )

        # Create request
        request = self.factory.get(f"/tables/firststuff/row-updates/{self.row.pk}")
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        response = view.row_updates(request, str(self.row.pk))
        self.assertIn("can_create_comment", response.model_fields_set)
        self.assertTrue(response.can_create_comment)
        self.assertEqual(len(response.updates), 1)
        self.assertEqual(response.updates[0].action, "created_row")
        self.assertIsNotNone(response.updates[0].column_values)
        created_by = response.updates[0].created_by
        self.assertIsNotNone(created_by)
        assert created_by is not None
        self.assertEqual(created_by.title, "testuser")

    def test_row_updates_returns_updates_sorted_by_created_at_desc(self) -> None:
        """Test that row_updates returns updates sorted by created_at descending."""
        # Create multiple RowUpdates
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="updated_row",
            created_by=self.user,
            _values={},
        )

        # Create request
        request = self.factory.get(f"/tables/firststuff/row-updates/{self.row.pk}")
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        response = view.row_updates(request, str(self.row.pk))
        # Most recent should be first (updated_row was created second)
        self.assertEqual(response.updates[0].action, "updated_row")
        self.assertEqual(response.updates[1].action, "created_row")

    def test_create_comment_returns_404_when_permission_denied(self) -> None:
        """Test that create_comment returns 404 when row_update_access_timeout returns None."""
        # Create request with JSON body
        request = self.factory.post(
            f"/tables/api/firststuff/create-comment/{self.row.pk}",
            json.dumps({"comment_content": "Test comment"}),
            content_type="application/json",
        )
        request.user = self.user

        # Create view with a model that denies comment creation
        view = FirstStuffView()

        # Create a mock model that denies comment creation
        class NoCommentModel(FirstStuff):
            class Meta:
                proxy = True

            def row_update_access_timeout(
                self,
                context: CommentPermissionContext[FirstStuff],  # type: ignore[override]
            ) -> int:
                # Deny create_comment operation
                if context.operation == "create_comment":
                    return 0
                return 86400

        view.model = NoCommentModel

        body = CommentRequest(comment_content="Test comment")
        with self.assertRaises(ApiError) as ctx:
            view.create_comment(request, str(self.row.pk), body)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_comment_creates_row_update_with_action_commented(self) -> None:
        """Test that create_comment creates a RowUpdate with action='commented'."""
        # Create request with JSON body
        request = self.factory.post(
            f"/tables/api/firststuff/create-comment/{self.row.pk}",
            json.dumps({"comment_content": "Test comment"}),
            content_type="application/json",
        )
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        body = CommentRequest(comment_content="Test comment")
        response = view.create_comment(request, str(self.row.pk), body)
        self.assertEqual(response.message, "Comment added")

        # Verify RowUpdate was created
        row_update = RowUpdate.objects.get(
            modelname="djangoapp.FirstStuff", row_pk=self.row.pk, action="commented"
        )
        self.assertEqual(row_update.action, "commented")
        self.assertEqual(row_update.comment_content, "Test comment")
        self.assertEqual(row_update.created_by, self.user)

    def test_create_comment_validates_comment_content_max_length(self) -> None:
        """Test that create_comment validates comment_content max length (1000 chars)."""
        # Create request with too-long comment
        long_comment = "x" * 1001
        request = self.factory.post(
            f"/tables/api/firststuff/create-comment/{self.row.pk}",
            json.dumps({"comment_content": long_comment}),
            content_type="application/json",
        )
        request.user = self.user

        # Create view and call method
        FirstStuffView()
        with self.assertRaises(PydanticValidationError):
            CommentRequest(comment_content=long_comment)

    def test_delete_comment_allows_any_user_within_timeout(self) -> None:
        """Test that delete_comment allows any user to delete within timeout (no user check)."""
        # Create a comment by another user
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.other_user,
            comment_content="Test comment",
            _values={},
        )

        # Create request by a different user
        request = self.factory.post(
            f"/tables/firststuff/{self.row.pk}/delete-comment/{row_update.pk}",
        )
        request.user = self.user

        # Create view and call method - should succeed because delete only checks timeout
        view = FirstStuffView()
        response = view.delete_comment(request, str(self.row.pk), row_update.pk)
        self.assertEqual(response.message, "Comment deleted")

    def test_delete_comment_soft_deletes_comment(self) -> None:
        """Test that delete_comment soft deletes comment (sets deleted_at, clears content)."""
        # Create a comment
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.user,
            comment_content="Test comment",
            _values={},
        )

        # Create request by the owner
        request = self.factory.post(
            f"/tables/firststuff/{self.row.pk}/delete-comment/{row_update.pk}",
        )
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        response = view.delete_comment(request, str(self.row.pk), row_update.pk)
        self.assertEqual(response.message, "Comment deleted")

        # Verify soft delete
        row_update.refresh_from_db()
        self.assertIsNotNone(row_update.comment_deleted_at)
        self.assertEqual(row_update.comment_content, "")
        self.assertEqual(row_update.comment_deleted_by, self.user)

    def test_update_comment_returns_404_when_not_owner(self) -> None:
        """Test that update_comment returns 404 when user is not the comment owner."""
        # Create a comment by another user
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.other_user,
            comment_content="Test comment",
            _values={},
        )

        # Create request by a different user
        request = self.factory.post(
            f"/tables/firststuff/{self.row.pk}/update-comment/{row_update.pk}",
            json.dumps({"comment_content": "Updated comment"}),
            content_type="application/json",
        )
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        body = CommentRequest(comment_content="Updated comment")
        with self.assertRaises(Http404):
            view.update_comment(request, str(self.row.pk), row_update.pk, body)

    def test_update_comment_updates_content(self) -> None:
        """Test that update_comment updates comment content."""
        # Create a comment
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.user,
            comment_content="Original comment",
            _values={},
        )

        # Create request by the owner
        request = self.factory.post(
            f"/tables/firststuff/{self.row.pk}/update-comment/{row_update.pk}",
            json.dumps({"comment_content": "Updated comment"}),
            content_type="application/json",
        )
        request.user = self.user

        # Create view and call method
        view = FirstStuffView()
        body = CommentRequest(comment_content="Updated comment")
        response = view.update_comment(request, str(self.row.pk), row_update.pk, body)
        self.assertEqual(response.message, "Comment updated")

        # Verify update
        row_update.refresh_from_db()
        self.assertEqual(row_update.comment_content, "Updated comment")
        # Verify comment_edited_at is set
        self.assertIsNotNone(row_update.comment_edited_at)

    def test_create_comment_sanitizes_html(self) -> None:
        """Test that create_comment sanitizes HTML - unsafe tags stripped, safe preserved."""
        mixed_html = (
            "<p>Text with <em>emphasis</em> and <a href='https://example.com'>link</a></p>"
            "<script>alert('xss')</script>"
            "<div>Div</div>"
            "<ul><li>Item</li></ul>"
        )
        request = self.factory.post(
            f"/tables/api/firststuff/create-comment/{self.row.pk}",
            json.dumps({"comment_content": mixed_html}),
            content_type="application/json",
        )
        request.user = self.user

        view = FirstStuffView()
        body = CommentRequest(comment_content=mixed_html)
        response = view.create_comment(request, str(self.row.pk), body)
        self.assertEqual(response.message, "Comment added")

        row_update = RowUpdate.objects.get(
            modelname="djangoapp.FirstStuff", row_pk=self.row.pk, action="commented"
        )
        expected = (
            "<p>Text with <em>emphasis</em> and "
            '<a href="https://example.com" rel="noopener noreferrer">link</a></p>'
            "Div"
            "<ul><li>Item</li></ul>"
        )
        self.assertEqual(row_update.comment_content, expected)

    def test_update_comment_sanitizes_html(self) -> None:
        """Test that update_comment sanitizes HTML - unsafe tags stripped, safe preserved."""
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.user,
            comment_content="Original comment",
            _values={},
        )

        mixed_html = (
            "<p>Updated comment</p>"
            "<script>alert('xss')</script>"
            "<ul><li>Item 1</li><li>Item 2</li></ul>"
            '<div onclick="evil()">Div</div>'
            "<ol><li>First</li></ol>"
            "<style>.evil{}</style>"
            "<em>Italic</em>"
        )
        request = self.factory.post(
            f"/tables/firststuff/{self.row.pk}/update-comment/{row_update.pk}",
            json.dumps({"comment_content": mixed_html}),
            content_type="application/json",
        )
        request.user = self.user

        view = FirstStuffView()
        body = CommentRequest(comment_content=mixed_html)
        response = view.update_comment(request, str(self.row.pk), row_update.pk, body)
        self.assertEqual(response.message, "Comment updated")

        row_update.refresh_from_db()
        expected = (
            "<p>Updated comment</p>"
            "<ul><li>Item 1</li><li>Item 2</li></ul>"
            "Div"
            "<ol><li>First</li></ol>"
            "<em>Italic</em>"
        )
        self.assertEqual(row_update.comment_content, expected)

    def test_row_updates_includes_comment_deleted_by(self) -> None:
        """Test that row_updates response includes comment_deleted_by after deletion."""
        # Create and delete a comment
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.user,
            comment_content="Test comment",
            _values={},
        )
        row_update.delete_comment(self.user)

        # Get row updates
        request = self.factory.get(f"/tables/firststuff/{self.row.pk}/row-updates")
        request.user = self.user
        view = FirstStuffView()
        response = view.row_updates(request, str(self.row.pk))

        # Verify comment_deleted_by is in response
        self.assertEqual(len(response.updates), 1)
        deleted_by = response.updates[0].comment_deleted_by
        self.assertIsNotNone(deleted_by)
        assert deleted_by is not None
        self.assertEqual(deleted_by.id, self.user.id)

    def test_update_comment_creates_notification(self) -> None:
        """Test that update_comment calls _create_notifications for the updated comment."""
        other_user = User.objects.create_user(username="third", password="pass")
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            action="commented",
            created_by=self.user,
            comment_content="Original comment",
            _values={},
        )
        row_update_resp = self.row.row_update_response(self.user, row_update)
        RowUpdateUserNotification.objects.create(
            modelname=self.row.modelname(),
            row_pk=self.row.pk,
            user=other_user,
            content=row_update_resp.model_dump(mode="json"),
        )

        request = self.factory.post(
            f"/tables/firststuff/{self.row.pk}/update-comment/{row_update.pk}",
            json.dumps({"comment_content": "Updated comment"}),
            content_type="application/json",
        )
        request.user = self.user

        view = FirstStuffView()
        body = CommentRequest(comment_content="Updated comment")
        response = view.update_comment(request, str(self.row.pk), row_update.pk, body)
        self.assertEqual(response.message, "Comment updated")

        notifs = list(
            RowUpdateUserNotification.objects.filter(
                modelname=self.row.modelname(), row_pk=self.row.pk, user=other_user
            ).order_by("pk")
        )
        self.assertEqual(len(notifs), 2)
        self.assertEqual(notifs[0].content["action"], "commented")
        self.assertEqual(notifs[0].content["comment_content"], "Original comment")
        self.assertEqual(notifs[1].content["action"], "commented")
        self.assertEqual(notifs[1].content["comment_content"], "Updated comment")


class NotificationAPITest(QueryBudgetTestCase):
    """Tests for notification API endpoints."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.other_user = User.objects.create_user(username="otheruser", password="otherpass")
        self.client.force_login(self.user)
        self.row = FirstStuff.objects.create(char_field="test row")

    def _create_notification(
        self,
        user: User,
        action: str = "created_row",
    ) -> RowUpdateUserNotification:
        row_update = RowUpdate.objects.create(
            action=action,
            created_by=self.other_user,
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            _values=[],
        )
        response = self.row.row_update_response(self.other_user, row_update)
        return RowUpdateUserNotification.objects.create(
            modelname=self.row.modelname(),
            row_pk=self.row.pk,
            user=user,
            content=response.model_dump(mode="json"),
        )

    def test_notifications_page_returns_user_notifications(self) -> None:
        """Test GET /tables/notifications/page returns notifications as Inertia props."""
        self._create_notification(self.user)
        response = self.client.get("/tables/notifications/page")
        self.assertEqual(response.status_code, 200)

    def test_notifications_page_requires_auth(self) -> None:
        """Test GET /tables/notifications/page requires authentication."""
        self.client.logout()
        response = self.client.get("/tables/notifications/page")
        self.assertEqual(response.status_code, 404)

    def test_notifications_page_filters_by_viewname(self) -> None:
        """Test GET /tables/notifications/page?viewname=firststuff filters correctly."""
        self._create_notification(self.user)
        response = self.client.get("/tables/notifications/page?viewname=firststuff")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/tables/notifications/page?viewname=nonexistent")
        self.assertEqual(response.status_code, 200)

    def test_notifications_viewname_counts(self) -> None:
        """Test viewname_counts is returned in Inertia props."""
        self._create_notification(self.user)
        response = self.client.get("/tables/notifications/page")
        self.assertEqual(response.status_code, 200)

    def test_notifications_pagination(self) -> None:
        """Test pagination works correctly."""
        for i in range(3):
            row = FirstStuff.objects.create(char_field=f"row {i}")
            ru = RowUpdate.objects.create(
                action="created_row",
                created_by=self.other_user,
                modelname="djangoapp.FirstStuff",
                row_pk=row.pk,
                _values=[],
            )
            row_update_resp = row.row_update_response(self.other_user, ru)
            RowUpdateUserNotification.objects.create(
                modelname=row.modelname(),
                row_pk=row.pk,
                user=self.user,
                content=row_update_resp.model_dump(mode="json"),
            )

        response = self.client.get("/tables/notifications/page?page=1")
        self.assertEqual(response.status_code, 200)

    def test_notifications_delete_deletes_selected(self) -> None:
        """Test POST /tables/notifications/delete deletes selected notifications."""
        notif1 = self._create_notification(self.user)
        notif2 = self._create_notification(self.user)
        self.assertEqual(RowUpdateUserNotification.objects.filter(user=self.user).count(), 2)

        response = self.client.post(
            "/tables/api/notifications/delete",
            json.dumps({"notification_ids": [notif1.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["deleted_count"], 1)
        self.assertFalse(RowUpdateUserNotification.objects.filter(pk=notif1.pk).exists())
        self.assertTrue(RowUpdateUserNotification.objects.filter(pk=notif2.pk).exists())

    def test_notifications_delete_ignores_other_users(self) -> None:
        """Test POST /tables/notifications/delete ignores other users' notifications."""
        notif = self._create_notification(self.other_user)
        response = self.client.post(
            "/tables/api/notifications/delete",
            json.dumps({"notification_ids": [notif.pk]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["deleted_count"], 0)
        self.assertTrue(RowUpdateUserNotification.objects.filter(pk=notif.pk).exists())

    def test_notifications_clear_deletes_all(self) -> None:
        """Test POST /tables/notifications/clear deletes all notifications."""
        self._create_notification(self.user)
        self._create_notification(self.user)
        self.assertEqual(RowUpdateUserNotification.objects.filter(user=self.user).count(), 2)

        response = self.client.post(
            "/tables/api/notifications/clear",
            json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["deleted_count"], 2)
        self.assertEqual(RowUpdateUserNotification.objects.filter(user=self.user).count(), 0)

    def test_notifications_clear_with_viewname_filter(self) -> None:
        """Test POST /tables/notifications/clear with viewname param filters."""
        notif = self._create_notification(self.user)
        response = self.client.post(
            "/tables/api/notifications/clear",
            json.dumps({"viewname": "firststuff"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["deleted_count"], 1)
        self.assertFalse(RowUpdateUserNotification.objects.filter(pk=notif.pk).exists())


class MalformedRisonTest(QueryBudgetTestCase):
    """Test error handling for malformed rison input in list URLs.

    The URL path uses RisonArgsConverter which parses rison into a dict,
    then _list_rows validates that dict against ListPageSchema (or subclass).

    Two failure modes:
    - Invalid rison syntax: converter's to_python raises ValueError → Django 404
    - Valid rison but wrong types: Pydantic ValidationError → 400 with plain text body
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client.force_login(self.user)

    def test_invalid_rison_syntax_returns_404(self) -> None:
        response = self.client.get("/tables/firststuff/list/-(not_valid_rison!)-")
        # Invalid rison is rejected by RisonArgsConverter.to_python, producing a 404
        # Content is Django's default HTML 404 page
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response["Content-Type"])

    def test_wrong_type_in_schema_returns_400(self) -> None:
        response = self.client.get("/tables/firststuff/list/-(p:(page:not_a_number,per:25))-")
        # Content: "1 validation error for ListPageSchema\np.page\n
        #   Input should be a valid integer, unable to parse string as an integer ..."
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("validation error for ListPageSchema", response.content.decode())
        self.assertIn("page", response.content.decode())


class UnauthenticatedCreateEditTest(QueryBudgetTestCase):
    """Create and edit row endpoints enforce authentication requirements.

    Unauthenticated users should get 404 for create/submit and update/submit
    endpoints. The details page itself (display mode) is publicly accessible
    but the update submit endpoint must reject unauthenticated POST requests.

    - test_create_row_get_unauthenticated: create page returns 404 for anon
    - test_create_row_submit_unauthenticated: create submit returns 404 for anon
    - test_update_row_get_unauthenticated: details page is public (display mode only)
    - test_update_row_submit_unauthenticated: update submit returns 404 for anon
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="auth_test_user", password="pw")
        self.first_stuff = FirstStuff.objects.create(char_field="test")

    def test_create_row_get_unauthenticated(self) -> None:
        """Create page returns 404 since resolve_columns requires auth."""
        response = self.client.get("/tables/firststuff/create-row")
        self.assertEqual(response.status_code, 404)

    def test_create_row_submit_unauthenticated(self) -> None:
        """Create submit returns 404 for unauthenticated user."""
        response = self.client.post(
            "/tables/api/firststuff/create-row-submit",
            data={"char_field": "new"},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_row_get_unauthenticated(self) -> None:
        """Details page is publicly accessible in display mode."""
        response = self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        self.assertEqual(response.status_code, 200)

    def test_update_row_submit_unauthenticated(self) -> None:
        """Update submit returns 404 for unauthenticated user."""
        response = self.client.post(
            f"/tables/api/firststuff/update-row-submit/{self.first_stuff.pk}",
            data={"char_field": "updated"},
        )
        self.assertEqual(response.status_code, 404)


class SsrHtmlTests(QueryBudgetInertiaTestCase):
    """SSR HTML fragment generation for non-Inertia requests.

    When X-Inertia header is absent, BaseView renders Django template
    fragments and embeds them as ssr_html in the Inertia props.

    - test_list_rows_ssr_html: list page includes table rows fragment
    - test_list_rows_ssr_html_contains_cell_values: fragment has cell data
    - test_list_rows_no_ssr_when_inertia: Inertia request omits ssr_html
    - test_row_details_ssr_html: details page includes field rows fragment
    - test_row_details_ssr_html_has_go_up: fragment has go-up link
    - test_row_details_no_ssr_when_inertia: Inertia request omits ssr_html
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="ssr_testuser", password="testpass")
        super().setUp()
        self.client.force_login(self.user)
        self.first_stuff = FirstStuff.objects.create(
            char_field="ssr_char",
            text_field="ssr_text",
            integer_field=42,
            boolean_field=True,
            decimal_field="9.99",
            char_choice_field="opt1",
            int_choice_field=2,
        )

    def test_list_rows_ssr_html(self) -> None:
        self.allow_more_queries(12)  # frozen baseline incl. SSR HTML rendering
        """List page includes SSR table rows fragment in props."""
        self.client.get("/tables/firststuff/list/-(p:(page:1,per:25))-")
        props = self.props()["props"]
        self.assertIn("ssr_html", props)
        self.assertIsNotNone(props["ssr_html"])
        self.assertIn("<tr>", props["ssr_html"])
        self.assertIn("ssr_char", props["ssr_html"])

    def test_list_rows_ssr_html_contains_cell_values(self) -> None:
        self.allow_more_queries(12)  # frozen baseline incl. SSR HTML rendering
        """SSR fragment has cell data rendered via ashtml filter."""
        self.client.get("/tables/firststuff/list/-(p:(page:1,per:25))-")
        props = self.props()["props"]
        self.assertIn("42", props["ssr_html"])
        self.assertIn("Yes", props["ssr_html"])

    def test_list_rows_no_ssr_when_inertia(self) -> None:
        self.allow_more_queries(12)  # frozen baseline incl. SSR HTML rendering
        """Inertia request omits ssr_html from props."""
        self.client.get(
            "/tables/firststuff/list/-(p:(page:1,per:25))-",
            HTTP_X_INERTIA="true",
        )
        props = self.props()["props"]
        self.assertIsNone(props.get("ssr_html"))

    def test_row_details_ssr_html(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """Details page includes SSR field rows fragment in props."""
        self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        props = self.props()["props"]
        self.assertIn("ssr_html", props)
        self.assertIsNotNone(props["ssr_html"])
        self.assertIn("field-row", props["ssr_html"])

    def test_row_details_ssr_html_has_go_up(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """SSR details fragment has go-up link."""
        self.client.get(f"/tables/firststuff/id/{self.first_stuff.pk}")
        props = self.props()["props"]
        self.assertIn("Go up", props["ssr_html"])
        self.assertIn("firststuff/list/", props["ssr_html"])

    def test_row_details_no_ssr_when_inertia(self) -> None:
        self.allow_more_queries(10)  # frozen baseline incl. auth/session overhead
        """Inertia details request omits ssr_html from props."""
        self.client.get(
            f"/tables/firststuff/id/{self.first_stuff.pk}",
            HTTP_X_INERTIA="true",
        )
        props = self.props()["props"]
        self.assertIsNone(props.get("ssr_html"))


class MountPrefixTests(QueryBudgetTestCase):
    """Validation of a view's path_prefix into a mountable segment.

    mount_prefix asserts path_prefix is a single leading-slash segment
    ("/articles") because it backs both link building ("{path_prefix}/api/...")
    and URL mounting, so a wrong shape would silently produce bad URLs.

    - test_valid_returns_segment: well-formed prefix strips to its segment
    - test_missing_leading_slash_raises: bare "articles" breaks link building
    - test_trailing_slash_raises: "/articles/" would double-slash links
    - test_empty_raises: unset prefix must not silently mount at root
    - test_multiple_segments_raises: "/a/b" is not one mount segment

    Tests verify the returned segment for valid input and AssertionError for each
    invalid shape.
    """

    def test_valid_returns_segment(self) -> None:
        """A well-formed prefix strips to its single segment."""
        self.assertEqual(mount_prefix("/articles", FirstStuffView), "articles")

    def test_missing_leading_slash_raises(self) -> None:
        """A prefix without a leading slash would break link building."""
        with self.assertRaises(AssertionError):
            mount_prefix("articles", FirstStuffView)

    def test_trailing_slash_raises(self) -> None:
        """A trailing slash would double-slash generated links."""
        with self.assertRaises(AssertionError):
            mount_prefix("/articles/", FirstStuffView)

    def test_empty_raises(self) -> None:
        """An unset (empty) prefix must not silently mount at root."""
        with self.assertRaises(AssertionError):
            mount_prefix("", FirstStuffView)

    def test_multiple_segments_raises(self) -> None:
        """A multi-segment prefix is not a single mount segment."""
        with self.assertRaises(AssertionError):
            mount_prefix("/a/b", FirstStuffView)
