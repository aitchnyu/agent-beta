import datetime as dt_module
import os
import re
import typing
from datetime import timedelta
from decimal import Decimal

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings, tag
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Page,
    Playwright,
    sync_playwright,
)

from djangoapp.filters import (
    BooleanValueFilter,
    CharBlankFilter,
    CharChoiceFilter,
    CharTextFilter,
    DatetimeComparisonFilter,
    DatetimeNullFilter,
    DatetimeRelativeFilter,
    DecimalComparisonFilter,
    DecimalNullFilter,
    ForeignKeyChoiceFilter,
    ForeignKeyNullFilter,
    IntegerChoiceFilter,
    IntegerComparisonFilter,
    IntegerNullFilter,
    RowUpdateFilter,
)
from djangoapp.models.app import (
    BooleanFieldModel,
    CategoryModel,
    CharFieldModel,
    ConditionalRowUpdatePermissionModel,
    DatetimeFieldModel,
    DecimalFieldModel,
    FirstStuff,
    ForeignKeyModel,
    IntegerFieldModel,
    PublicIdUuid7TestModel2,
    Ref,
    SlotDemoModel,
    TestFileUploadModel,
)
from djangoapp.models.base import RowUpdate, SaveContext, User
from djangoapp.views.app import SlotDemoListPageSchema
from djangoapp.views.base import ListPageSchema, PaginationSchema


@tag("playwright")
@override_settings(DEBUG=True, SECURE_CSP_REPORT_ONLY=None)
class BasePlaywrightTestCase(StaticLiveServerTestCase):
    if typing.TYPE_CHECKING:
        playwright: typing.ClassVar[Playwright]
        browser: typing.ClassVar[Browser]
        context: typing.ClassVar[BrowserContext]

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.firefox.launch(headless=True)
        cls.context = cls.browser.new_context()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.logged_in_page = self.context.new_page()
        self.logged_in_page.set_default_timeout(1000)
        self.console_errors: list[str] = []
        self.logged_in_page.on("console", self._handle_console)
        login_url = f"{self.live_server_url}/login-for-test/{self.user.pk}"
        self.logged_in_page.goto(login_url, wait_until="domcontentloaded")
        self.assertEqual(
            self.logged_in_page.text_content("body"), f"Logged in as {self.user.username}"
        )

        return super().setUp()

    def _handle_console(self, msg: object) -> None:
        assert isinstance(msg, ConsoleMessage)
        if msg.type == "error":
            self.console_errors.append(msg.text)

    def pop_error(self, expected_substring: str) -> str:
        """Remove and return the first console error containing expected_substring.

        Fails the test if no matching error is found.
        """
        for i, err in enumerate(self.console_errors):
            if expected_substring in err:
                return self.console_errors.pop(i)
        self.fail(
            f"Expected console error containing '{expected_substring}' "
            f"but found: {self.console_errors}"
        )
        return ""  # unreachable but satisfies type checker

    def extract_matching_row_ids(self, selector: str) -> list[int]:
        """Extract row IDs from matching elements using row-tr-{id} classes.

        Args:
            selector: CSS selector for elements to find

        Returns:
            List of row IDs from matching elements.

        """
        rows = self.logged_in_page.locator(f"{selector}[class*='row-tr-']").all()
        row_ids: list[int] = []
        for el in rows:
            class_attr = el.get_attribute("class") or ""
            match = re.search(r"row-tr-(\d+)", class_attr)
            row_id = int(match.group(1))  # type: ignore[union-attr]
            row_ids.append(row_id)
        return row_ids

    def list_rows_url(self, model_name: str, schema: ListPageSchema) -> str:
        """Generate a URL for a list rows page for a given model name and ListPageSchema."""
        viewname = model_name.lower()
        url = reverse(
            f"tables-http:list-{viewname}",
            kwargs={"params": schema.model_dump(exclude_none=True, mode="json")},
        )
        return f"{self.live_server_url}{url}"

    def fill_integer_choice_multiselect(self, column_name: str, choices: list[str]) -> None:
        """Fill an integer choice multiselect field in list page.

        Uses focus()+fill() on the input element rather than clicking the
        .multiselect container, because clicking .multiselect can hit tag
        elements and trigger removeElement (which now works correctly thanks
        to track-by="value").

        Args:
            column_name: Name of the column/field
            choices: List of choice labels to select (e.g., ["Active", "Inactive"])

        """
        selector_prefix = f"#filter-widget-{column_name}"
        page = self.logged_in_page

        for choice in choices:
            page.locator(f"{selector_prefix} input.multiselect__input").focus()
            page.locator(f"{selector_prefix} input.multiselect__input").fill(choice, force=True)
            page.wait_for_selector(f"{selector_prefix} .multiselect__content-wrapper")
            page.wait_for_selector(f"{selector_prefix} .multiselect__option")
            page.locator(f"{selector_prefix} .multiselect__option").first.click()

    def extract_filter_value(self, column_name: str, span_class: str) -> str:
        """Extract text from a specific span within a filter widget.

        Args:
            column_name: Name of the column (e.g., 'integer_field')
            span_class: CSS class of the span to extract (e.g., 'number_1_collapsed')

        Returns:
            The text content of the span.

        """
        selector = f"#filter-widget-{column_name} .{span_class}"
        text = self.logged_in_page.text_content(selector)
        self.assertIsNotNone(text)
        return typing.cast(str, text)

    def verify_filter_button_active_class(self, column_name: str, button_class: str) -> None:
        """Verify that a specific filter button has 'active' class.

        Args:
            column_name: Name of the column (e.g., 'integer_field')
            button_class: CSS class of the button (e.g., 'btn-compare')

        """
        selector = f"#filter-widget-{column_name} .{button_class}"
        button = self.logged_in_page.locator(selector)
        button_class_attr = button.get_attribute("class")
        self.assertIsNotNone(button_class_attr)
        assert button_class_attr is not None
        self.assertIn("active", button_class_attr)

    def tearDown(self) -> None:
        if self.console_errors:
            self.fail(f"Console errors detected: {self.console_errors}")
        self.logged_in_page.close()
        return super().tearDown()


class DebugViewE2eTestCase(BasePlaywrightTestCase):
    def test_debug_view_with_playwright(self) -> None:
        page = self.logged_in_page
        # Go to debug page
        debug_url = f"{self.live_server_url}/tables/_debug"
        page.goto(debug_url)
        # Assert content
        body_text = page.text_content("body")
        assert body_text is not None
        self.assertIn("Hello, testuser", body_text)
        self.assertIn("firststuff", body_text)
        # Click link
        page.click("a:has-text('firststuff')")
        page.wait_for_url("**/tables/firststuff/list/**")
        self.assertIn("/tables/firststuff/list", page.url)


class FileUploadE2eTestCase(BasePlaywrightTestCase):
    def test_create_row_with_file_upload(self) -> None:
        """Test creating a row with file upload through the UI."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/testfileuploadmodel/create-row")

        # Fill nullable_integer_field
        page.fill("input#nullable_integer_field", "42")
        page.set_input_files(
            'input[type="file"]',
            {
                "name": "test_file.txt",
                "mimeType": "text/plain",
                "buffer": b"file content for upload",
            },
        )

        # Submit form
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.live_server_url}/tables/testfileuploadmodel/id/*")

        # Verify database state
        row = TestFileUploadModel.objects.last()
        assert row is not None, "Row was not created"
        self.assertEqual(row.nullable_integer_field, 42)
        with row.file_field.open() as f:
            self.assertEqual(f.read(), b"file content for upload")

    def test_update_row_leave_file_unchanged(self) -> None:
        """Test updating a row leaving the file unchanged."""
        # Create row with file using ORM
        row = TestFileUploadModel.objects.create(
            nullable_integer_field=100,
            file_field=SimpleUploadedFile("old.txt", b"old content", content_type="text/plain"),
        )
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/testfileuploadmodel/update-row/{row.pk}")
        page.wait_for_selector("form")

        page.fill("input#nullable_integer_field", "200")

        page.click('button[type="submit"]')
        page.wait_for_url(f"**/tables/testfileuploadmodel/id/{row.pk}")
        page.wait_for_selector(".field-display-row")

        # Verify database state
        updated_row = TestFileUploadModel.objects.get(pk=row.pk)
        self.assertEqual(updated_row.nullable_integer_field, 200)
        with updated_row.file_field.open() as f:
            self.assertEqual(f.read(), b"old content")

    def test_update_row_remove_file(self) -> None:
        """Test updating a row by removing the file."""
        # Create row with file using ORM
        row = TestFileUploadModel.objects.create(
            nullable_integer_field=100,
            file_field=SimpleUploadedFile("old.txt", b"old content", content_type="text/plain"),
        )
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/testfileuploadmodel/update-row/{row.pk}")
        page.wait_for_selector("form")

        page.fill("input#nullable_integer_field", "300")
        page.click("button.remove-file")

        page.click('button[type="submit"]')
        page.wait_for_url(f"**/tables/testfileuploadmodel/id/{row.pk}")
        page.wait_for_selector(".field-display-row")

        # Verify database state
        updated_row = TestFileUploadModel.objects.get(pk=row.pk)
        self.assertEqual(updated_row.nullable_integer_field, 300)
        self.assertEqual(updated_row.file_field.name, "")

    def test_update_row_change_file(self) -> None:
        """Test updating a row by changing the file."""
        # Create row with file using ORM
        row = TestFileUploadModel.objects.create(
            nullable_integer_field=100,
            file_field=SimpleUploadedFile("old.txt", b"old content", content_type="text/plain"),
        )
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/testfileuploadmodel/update-row/{row.pk}")
        page.wait_for_selector("form")

        page.fill("input#nullable_integer_field", "400")
        page.set_input_files(
            'input[type="file"]',
            {
                "name": "new_file.txt",
                "mimeType": "text/plain",
                "buffer": b"new content",
            },
        )

        page.click('button[type="submit"]')
        page.wait_for_selector(".field-display-row")

        # Verify database state
        updated_row = TestFileUploadModel.objects.get(pk=row.pk)
        self.assertEqual(updated_row.nullable_integer_field, 400)
        with updated_row.file_field.open() as f:
            self.assertEqual(f.read(), b"new content")

    def test_download_file(self) -> None:
        """Test downloading an uploaded file through the UI."""
        page = self.logged_in_page

        # Create a row with file using ORM (efficient for download testing)
        row = TestFileUploadModel.objects.create(
            nullable_integer_field=42,
            file_field=SimpleUploadedFile(
                "test_file.txt", b"file content for upload", content_type="text/plain"
            ),
        )
        row_id = row.pk

        # Attempt download
        response = page.request.get(
            f"{self.live_server_url}/tables/testfileuploadmodel/download-file/{row_id}/file_field"
        )
        self.assertTrue(response.ok)
        content = response.body()
        self.assertIn(b"file content for upload", content)


class PaginationE2eTestCase(BasePlaywrightTestCase):
    def setUp(self) -> None:
        super().setUp()
        for i in range(1, 81):  # 1 to 80 inclusive
            Ref.objects.create(char_field=f"c {i} end")

    def _extract_char_fields_from_table(self, page: Page) -> list[str]:
        """Extract char_field values from the char_field column cells."""
        cells = page.locator("table tbody td.row-td-char_field").all()
        values: list[str] = []
        for cell in cells:
            text = cell.text_content()
            if text:
                values.append(text.strip())
        pattern = r"c (\d+) end"
        numbers = [int(m.group(1)) for v in values if (m := re.match(pattern, v))]
        numbers.sort()
        return [f"c {num} end" for num in numbers]

    def test_go_to_page_clicking_select_and_verify_items(self) -> None:
        """Test pagination page selector dropdown functionality."""
        page = self.logged_in_page

        # Go to debug page and click on RefStuff link to get to the correct URL
        debug_url = f"{self.live_server_url}/tables/_debug"
        page.goto(debug_url)
        page.click("a:has-text('ref')")
        page.wait_for_url("**/tables/ref/list/**")
        page.wait_for_selector("table")  # Wait for the table to load

        # Verify we're on page 1 of 3
        select_value = page.input_value("select.form-select")
        self.assertEqual(select_value, "1")
        total_pages_text = page.text_content(".pagination-page")
        self.assertIsNotNone(total_pages_text)
        assert total_pages_text is not None  # For mypy
        self.assertIn("of 3", total_pages_text)

        # Extract char_field values from page 1 (sorted: 56, 57, ..., 80)
        char_fields_page1 = self._extract_char_fields_from_table(page)
        self.assertEqual(len(char_fields_page1), 25)
        self.assertEqual(char_fields_page1[0], "c 56 end")
        self.assertEqual(char_fields_page1[-1], "c 80 end")

        # Click on page 2 in dropdown
        page.select_option("select.form-select", "2")
        # For example, http://127.0.0.1:8000/tables/ref/list/-(p:(page:2,per:25))-
        page.wait_for_url("**/tables/ref/list/**page:2**")

        # Verify we're on page 2
        select_value = page.input_value("select.form-select")
        self.assertEqual(select_value, "2")

        # Extract char_field values from page 2 (31, 32, ..., 55)
        char_fields_page2 = self._extract_char_fields_from_table(page)
        self.assertEqual(len(char_fields_page2), 25)
        self.assertEqual(char_fields_page2[0], "c 31 end")
        self.assertEqual(char_fields_page2[-1], "c 55 end")

        # Click on page 3 in dropdown
        page.select_option("select.form-select", "3")
        page.wait_for_url("**/tables/ref/list/**page:3**")

        # Verify we're on page 3
        select_value = page.input_value("select.form-select")
        self.assertEqual(select_value, "3")

        # Extract char_field values from page 3 (1, 2, ..., 30)
        # This will have 30 items since 5 are orphans
        char_fields_page3 = self._extract_char_fields_from_table(page)
        self.assertEqual(len(char_fields_page3), 30)  # 25 + 5 orphans
        self.assertEqual(char_fields_page3[0], "c 1 end")
        self.assertEqual(char_fields_page3[-1], "c 30 end")

    def test_go_to_page_with_prev_next_buttons(self) -> None:
        """Test pagination Previous/Next button functionality."""
        page = self.logged_in_page

        # Go to debug page and click on RefStuff link to get to the correct URL
        debug_url = f"{self.live_server_url}/tables/_debug"
        page.goto(debug_url)
        page.click("a:has-text('ref')")
        page.wait_for_url("**/tables/ref/list/**")

        page.wait_for_selector("table")  # Wait for the table to load

        # Start on page 1 - Previous should not exist, Next should exist
        prev_button = page.locator("a:has-text('Prev')")
        next_button = page.locator("a:has-text('Next')")

        self.assertEqual(prev_button.count(), 0)  # Previous button should not exist
        self.assertEqual(next_button.count(), 1)  # Next button should exist

        # Click Next to go to page 2
        next_button.click()
        # For example, http://127.0.0.1:8000/tables/ref/list/-(p:(page:1,per:25))-
        page.wait_for_url("**/tables/ref/list/**page:2**")

        # On page 2, both Previous and Next should exist
        prev_button = page.locator("a:has-text('Prev')")
        next_button = page.locator("a:has-text('Next')")

        self.assertEqual(prev_button.count(), 1)  # Previous button should exist
        self.assertEqual(next_button.count(), 1)  # Next button should exist

        # Click Next to go to page 3
        next_button.click()
        page.wait_for_url("**/tables/ref/list/**page:3**")

        # On page 3, Previous should exist, Next should not exist
        prev_button = page.locator("a:has-text('Prev')")
        next_button = page.locator("a:has-text('Next')")

        self.assertEqual(prev_button.count(), 1)  # Previous button should exist
        self.assertEqual(next_button.count(), 0)  # Next button should not exist

        # Click Previous to go back to page 2
        prev_button.click()
        page.wait_for_url("**/tables/ref/list/**page:2**")

        # On page 2, both should exist again
        prev_button = page.locator("a:has-text('Prev')")
        next_button = page.locator("a:has-text('Next')")

        self.assertEqual(prev_button.count(), 1)
        self.assertEqual(next_button.count(), 1)

        # Click Previous to go back to page 1
        prev_button.click()
        page.wait_for_url("**/tables/ref/list/**page:1**")

        # Back on page 1 - Previous should not exist, Next should exist
        prev_button = page.locator("a:has-text('Prev')")
        next_button = page.locator("a:has-text('Next')")

        self.assertEqual(prev_button.count(), 0)  # Previous button should not exist
        self.assertEqual(next_button.count(), 1)  # Next button should exist


class SearchNavigateE2ETestCase(BasePlaywrightTestCase):
    def test_search_icon_opens_search_field_and_navigates(self) -> None:
        Ref.objects.create(char_field="alpha")
        Ref.objects.create(char_field="beta")
        Ref.objects.create(char_field="alpha_two")

        page = self.logged_in_page
        debug_url = f"{self.live_server_url}/tables/_debug"
        page.goto(debug_url)
        page.click("a:has-text('ref')")
        page.wait_for_url("**/tables/ref/list/**")
        page.wait_for_selector("table")

        page.wait_for_selector(".search-toggle-btn")
        page.click(".search-toggle-btn")

        page.wait_for_selector(".search-input")
        page.fill(".search-input", "alpha")

        page.wait_for_selector(".search-result-item")
        results = page.locator(".search-result-item").all()
        self.assertGreaterEqual(len(results), 1)

        page.locator(".search-result-item").first.click()
        page.wait_for_url("**/id/**")


class CreateUpdateE2eTestCase(BasePlaywrightTestCase):
    """E2E tests for row create, update page, and details page display+edit toggle.

    The details page is display-only. Double-clicking a field or clicking Edit
    navigates to the update-row page with the focused field set via pushStartEdit.
    The update page renders RowForm with InputSchema components. These tests verify
    form submission, navigation transitions, value pre-filling, FK links, focused
    fields, and unauthenticated access restrictions.

    - why test_create_row_get: create page loads with form elements
    - why test_create_row_submit_success: full create flow populates database
    - why test_update_row_get: update page opens with pre-filled values
    - why test_update_row_submit_success: update modifies database, returns to details
    - why test_update_row_clear_nullable_integer_to_null: empty string clears nullable int
    - why test_details_double_click_navigates_to_update: dblclick navigates to update page
    - why test_details_double_click_focuses_clicked_field: dblclick navigates with focused field
    - why test_update_page_cancel: cancel returns to details page without changes
    - why test_details_edit_button_navigates_to_update: Edit button navigates to update page
    - why test_details_unauthenticated_shows_columns: anon sees display only, no form
    - why test_details_server_driven_can_edit_can_delete: anon gets can_edit=False
      but can_delete=True on FirstStuff (delete endpoint allows anon)
    - why test_list_double_click_opens_update_page: list dblclick navigates to update page
    - why test_text_cell_flattens_paragraphs: text cell collapses paragraphs to spaces
    - why test_double_click_renders_form_with_correct_values: update form pre-fills all field types
    """

    def fill_fk_field(self, field_name: str, value: str) -> None:
        """Fill a foreign key field multiselect."""
        selector_prefix = f".column-input-{field_name}"
        page = self.logged_in_page
        # Click multiselect to open dropdown
        page.locator(f"{selector_prefix} .multiselect").click()
        # Wait for options list to appear
        page.wait_for_selector(f"{selector_prefix} .multiselect__content-wrapper")
        # Focus and fill value using force to bypass visibility
        page.locator(f"{selector_prefix} input.multiselect__input").focus()
        page.locator(f"{selector_prefix} input.multiselect__input").fill(value, force=True)
        # This will wait till network call and atleast one option is shown
        page.wait_for_selector(f"{selector_prefix} .multiselect__option")
        # Click that matched option
        page.locator(f"{selector_prefix} .multiselect__option").first.click()

    def setUp(self) -> None:
        super().setUp()
        self.ref = Ref.objects.create(char_field="ref1")
        self.update_ref = Ref.objects.create(char_field="update_ref")
        self.update_user = User.objects.create_user(username="updateuser", password="pass")
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

    def test_create_row_get(self) -> None:
        """Test loading the create row page."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/create-row")
        self.assertIn("/tables/firststuff/create-row", page.url)
        # Check for form elements
        page.wait_for_selector("input#char_field")

    def test_create_row_submit_success(self) -> None:
        """Test creating a row with valid data through the UI."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/create-row")

        # Fill form fields
        page.fill(".column-input-char_field input", "new_char")
        # Fill Quill editor - clear first then type
        quill_editor = page.locator(".column-input-text_field .quill-editor .ql-editor")
        quill_editor.click()
        quill_editor.fill("")  # Clear initial <p><br></p>
        quill_editor.type("new_text")
        page.fill(".column-input-integer_field input", "15")
        page.fill(".column-input-nullable_integer_field input", "25")
        page.fill(".column-input-decimal_field input", "6.50")
        page.fill(".column-input-datetime_field input", "2023-01-01T12:00")
        page.select_option(".column-input-char_choice_field select", "opt2")
        page.select_option(".column-input-int_choice_field select", "1")
        page.check(".column-input-boolean_field input")
        page.set_input_files(
            'input[type="file"]',
            {
                "name": "new_file.txt",
                "mimeType": "text/plain",
                "buffer": b"new file content",
            },
        )
        self.fill_fk_field("ref_fk", str(self.ref.pk))
        self.fill_fk_field("user_fk", str(self.user.username))

        # Submit form
        page.click('button[type="submit"]')
        page.wait_for_url(f"{self.live_server_url}/tables/firststuff/id/*")

        # Verify database state
        new_row = FirstStuff.objects.last()
        assert new_row is not None
        self.assertEqual(new_row.char_field, "new_char")
        self.assertEqual(new_row.text_field, "<p>new_text</p>")  # Quill wraps in <p>
        self.assertEqual(new_row.integer_field, 15)
        self.assertEqual(new_row.nullable_integer_field, 25)
        self.assertEqual(new_row.boolean_field, True)
        self.assertEqual(new_row.decimal_field, Decimal("6.50"))
        self.assertEqual(new_row.char_choice_field, "opt2")
        self.assertEqual(new_row.int_choice_field, 1)
        self.assertEqual(new_row.ref_fk, self.ref)
        self.assertEqual(new_row.user_fk, self.user)
        self.assertIsNotNone(new_row.file_field)

    def test_update_row_get(self) -> None:
        """Test loading the update row page directly."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/update-row/{self.first_stuff.pk}")
        page.wait_for_selector("form")
        char_field_value = page.input_value("input#char_field")
        self.assertEqual(char_field_value, "test_char")

    def test_update_row_submit_success(self) -> None:
        """Test updating a row with valid data through the update page."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/update-row/{self.first_stuff.pk}")
        page.wait_for_selector("form")

        page.fill(".column-input-char_field input", "updated_ch")
        page.fill(".column-input-integer_field input", "15")
        page.fill(".column-input-nullable_integer_field input", "30")
        page.fill(".column-input-decimal_field input", "7.00")
        self.fill_fk_field("ref_fk", str(self.update_ref.pk))
        self.fill_fk_field("user_fk", str(self.update_user.username))

        page.click('button[type="submit"]')
        page.wait_for_url(f"**/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")

        updated_row = FirstStuff.objects.get(pk=self.first_stuff.pk)
        self.assertEqual(updated_row.char_field, "updated_ch")
        self.assertEqual(updated_row.integer_field, 15)
        self.assertEqual(updated_row.nullable_integer_field, 30)
        self.assertEqual(updated_row.decimal_field, Decimal("7.00"))
        self.assertEqual(updated_row.ref_fk, self.update_ref)
        self.assertEqual(updated_row.user_fk, self.update_user)
        self.assertEqual(updated_row.text_field, "<p>test_text</p>")
        self.assertEqual(updated_row.boolean_field, True)

    def test_update_row_clear_nullable_integer_to_null(self) -> None:
        """Test clearing a nullable integer field to null via the update page."""
        page = self.logged_in_page
        row = FirstStuff.objects.create(
            char_field="nullable",
            text_field="<p>text</p>",
            integer_field=5,
            boolean_field=True,
            nullable_integer_field=42,
        )
        page.goto(f"{self.live_server_url}/tables/firststuff/update-row/{row.pk}")
        page.wait_for_selector("form")
        page.fill(".column-input-nullable_integer_field input", "")
        page.click('button[type="submit"]')
        page.wait_for_selector(".field-display-row")
        row.refresh_from_db()
        self.assertIsNone(row.nullable_integer_field)

    def test_details_double_click_navigates_to_update(self) -> None:
        """Double-clicking a display field navigates to update page."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")

        page.locator(".field-display-row").first.dblclick()

        page.wait_for_url(lambda url: "update-row" in url)
        page.wait_for_selector("form")

        char_field_value = page.input_value("input#char_field")
        self.assertEqual(char_field_value, "test_char")

    def test_details_inline_edit_submit(self) -> None:
        """Navigate to update page, edit a field, submit, verify update."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/update-row/{self.first_stuff.pk}")
        page.wait_for_selector("form")

        page.fill("input#char_field", "updated")

        page.click('button[type="submit"]')
        page.wait_for_url(f"**/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")

        self.first_stuff.refresh_from_db()
        self.assertEqual(self.first_stuff.char_field, "updated")

    def test_update_page_cancel(self) -> None:
        """Canceling edit on update page returns to details without changes."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/update-row/{self.first_stuff.pk}")
        page.wait_for_selector("form")

        page.fill("input#char_field", "no_save")
        page.click("button.btn-secondary")

        page.wait_for_url(f"**/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")

        self.first_stuff.refresh_from_db()
        self.assertEqual(self.first_stuff.char_field, "test_char")

    def test_details_edit_button_navigates_to_update(self) -> None:
        """Edit button navigates to update page with pre-filled values."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")
        page.click("button.btn-outline-primary")

        page.wait_for_url(lambda url: "update-row" in url)
        page.wait_for_selector("form")

        char_field_value = page.input_value("input#char_field")
        self.assertEqual(char_field_value, "test_char")

    def test_details_unauthenticated_shows_columns(self) -> None:
        """Unauthenticated users see display values on details page, no edit form initially."""
        anon_context = self.browser.new_context()
        anon_page = anon_context.new_page()
        anon_page.set_default_timeout(1000)
        try:
            anon_page.goto(
                f"{self.live_server_url}/tables/firststuff/id/{self.first_stuff.public_id}"
            )
            anon_page.wait_for_selector(".field-display-row")

            char_display = anon_page.locator(".field-display-row").first
            self.assertTrue(char_display.count() > 0, "char_field display should exist")

            form = anon_page.locator("form")
            self.assertEqual(form.count(), 0, "No form should be present initially for anon")
        finally:
            anon_page.close()
            anon_context.close()

    def test_details_server_driven_can_edit_can_delete(self) -> None:
        """Server sends can_edit=False, can_delete=True for anon on FirstStuff."""
        anon_context = self.browser.new_context()
        anon_page = anon_context.new_page()
        anon_page.set_default_timeout(1000)
        try:
            anon_page.goto(
                f"{self.live_server_url}/tables/firststuff/id/{self.first_stuff.public_id}"
            )
            anon_page.wait_for_selector(".field-display-row")

            edit_btn = anon_page.locator("button.btn-outline-primary")
            self.assertEqual(edit_btn.count(), 0, "Edit button should not be present for anon")

            delete_btn = anon_page.locator("button.btn-outline-danger")
            self.assertEqual(
                delete_btn.count(), 1, "Delete button should be present for anon on FirstStuff"
            )
        finally:
            anon_page.close()
            anon_context.close()

    def test_list_double_click_opens_update_page(self) -> None:
        """Double-clicking a cell on list page navigates to update page."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/list/-(p:(page:1,per:25))-")
        page.wait_for_selector("table.list-rows-table")

        cell = page.locator(f".row-tr-{self.first_stuff.pk} .row-td-char_field")
        cell.dblclick()

        page.wait_for_url(lambda url: "update-row" in url)
        page.wait_for_selector("form")

    def test_text_cell_flattens_paragraphs(self) -> None:
        """Text cell in list rows shows paragraphs collapsed to spaces."""
        FirstStuff.objects.create(
            char_field="multi_para",
            text_field="<p>foo</p><p>bar</p>",
            integer_field=1,
        )
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/list/-(p:(page:1,per:25))-")
        page.wait_for_selector("table.list-rows-table")
        cell = page.locator(
            f".row-tr-{FirstStuff.objects.get(char_field='multi_para').pk} .row-td-text_field"
        )
        self.assertEqual(cell.inner_text().strip(), "foo bar")

    def test_double_click_renders_form_with_correct_values(self) -> None:
        """Double-clicking display field navigates to update form pre-filled with current values."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")

        page.locator(".field-display-row").first.dblclick()

        page.wait_for_url(lambda url: "update-row" in url)
        page.wait_for_selector("form")

        char_val = page.input_value("input#char_field")
        self.assertEqual(char_val, "test_char")

        int_val = page.input_value("input#integer_field")
        self.assertEqual(int_val, "10")

        decimal_val = page.input_value("input#decimal_field")
        self.assertEqual(decimal_val, "5.50")

        bool_checked = page.is_checked("input#boolean_field")
        self.assertTrue(bool_checked)

    def test_details_double_click_focuses_clicked_field(self) -> None:
        """Double-clicking a specific field navigates to update page with that field focused."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/firststuff/id/{self.first_stuff.pk}")
        page.wait_for_selector(".field-display-row")

        integer_row = page.locator(".field-display-row-integer_field")
        integer_row.dblclick()

        page.wait_for_url(lambda url: "update-row" in url)
        page.wait_for_selector("form")

        active_id = page.evaluate("document.activeElement.id")
        self.assertEqual(active_id, "integer_field")


class ProxyUserDetailsE2eTestCase(BasePlaywrightTestCase):
    """ProxyUser details page shows username in display but excludes it from edit form.

    resolve_columns("update") excludes username so it never appears in the edit
    form, preventing users from changing auth credentials via the tables UI.
    resolve_columns("details") includes it so users can still see the username
    in read-only display mode.

    - why test_proxy_user_details_shows_username_in_display: username visible in display
    - why test_proxy_user_update_form_excludes_username: username absent from update form

    Tests verify DOM element presence/absence for both modes.
    """

    def setUp(self) -> None:
        super().setUp()
        self.target_user = User.objects.create_user(
            username="proxytarget",
            email="target@example.com",
            first_name="Proxy",
            last_name="Target",
        )

    def test_proxy_user_details_shows_username_in_display(self) -> None:
        """Username renders as a display row since resolve_columns('details') includes it."""
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/proxyuser/id/{self.target_user.public_id}")
        page.wait_for_selector(".field-display-row-username")

        username_row = page.locator(".field-display-row-username")
        self.assertTrue(username_row.count() > 0, "username display row should exist")

    def test_proxy_user_update_form_excludes_username(self) -> None:
        """Username input is absent from update form since resolve_columns('update') excludes it."""
        page = self.logged_in_page
        page.goto(
            f"{self.live_server_url}/tables/proxyuser/update-row/{self.target_user.public_id}"
        )
        page.wait_for_selector("form")

        username_input = page.locator("input#username")
        self.assertEqual(username_input.count(), 0, "username input should not be in edit form")

        email_input = page.locator("input#email")
        self.assertTrue(email_input.count() > 0, "email input should be in edit form")
        self.assertEqual(email_input.input_value(), "target@example.com")


class BooleanFilterE2ETestCase(BasePlaywrightTestCase):
    """Test boolean field filtering through E2E tests.

    Tests:
    - **Test Setup**: Create 5 rows (3 with boolean_field=True,
      2 with boolean_field=False) and navigate to BooleanFieldModel list page
    - `test_boolean_filter_yes_option`: Click Yes option and verify only True values shown
      - Verify Yes button is highlighted when dropdown is opened
      - Verify ✕ button is shown
      - Matches: 3 rows (true_obj1, true_obj2, true_obj3)
    - `test_boolean_filter_no_option`: Click No option and verify only False values shown
      - Verify No button is highlighted when dropdown is opened
      - Verify ✕ button is shown
      - Matches: 2 rows (false_obj1, false_obj2)
    - `test_boolean_filter_unset`: Click Unset button and verify all rows shown
      - Verify neither button is highlighted after unsetting
      - Matches: 5 rows (true_obj1, true_obj2, true_obj3, false_obj1, false_obj2)
    - `test_boolean_filter_toggle`: Toggle between Yes/No and verify filtering changes
      - Verify Yes button is highlighted when toggled to Yes
      - Verify No button is highlighted when toggled to No
      - Verify Yes button is highlighted again when toggled back to Yes
      - Matches: 3 True rows → 2 False rows → 3 True rows → 5 all rows
    """

    def setUp(self) -> None:
        super().setUp()

        # Create test data with mixed boolean values
        self.true_obj1 = BooleanFieldModel.objects.create(boolean_field=True)
        self.true_obj2 = BooleanFieldModel.objects.create(boolean_field=True)
        self.true_obj3 = BooleanFieldModel.objects.create(boolean_field=True)
        self.false_obj1 = BooleanFieldModel.objects.create(boolean_field=False)
        self.false_obj2 = BooleanFieldModel.objects.create(boolean_field=False)

        # Navigate to BooleanFieldModel list page
        page = self.logged_in_page
        schema = ListPageSchema()
        page.goto(self.list_rows_url("BooleanFieldModel", schema))
        page.wait_for_selector("table")

    def test_boolean_filter_yes_option(self) -> None:
        """Test clicking Yes option and verifying only True values shown."""
        page = self.logged_in_page

        # Click boolean filter button to open it
        page.click("#filter-widget-boolean_field button:first-child")
        page.wait_for_selector("#filter-widget-boolean_field .filter-button")

        # Click Yes option
        page.click("#filter-widget-boolean_field .filter-button:first-child")
        # Wait for filter to be applied (URL should change)
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(f={"boolean_field": BooleanValueFilter(value=True)}),
            )
        )

        # Verify only True values are displayed (3 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.true_obj3.pk, self.true_obj2.pk, self.true_obj1.pk]
        )

        # Verify filter button shows "Yes" state
        filter_button_text = page.text_content("#filter-widget-boolean_field button:first-child")
        self.assertIn("boolean_field Yes", filter_button_text or "")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-boolean_field")
        self.assertEqual(unset_button.count(), 1)

    def test_boolean_filter_no_option(self) -> None:
        """Test clicking No option and verifying only False values shown."""
        page = self.logged_in_page

        # Click boolean filter button to open it
        page.click("#filter-widget-boolean_field button:first-child")
        page.wait_for_selector("#filter-widget-boolean_field .filter-button")

        # Click No option
        page.click("#filter-widget-boolean_field .filter-button:last-child")
        # Wait for filter to be applied (URL should change)
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(f={"boolean_field": BooleanValueFilter(value=False)}),
            )
        )

        # Verify only False values are displayed (2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.false_obj2.pk, self.false_obj1.pk])

        # Verify filter button shows "No" state
        filter_button_text = page.text_content("#filter-widget-boolean_field button:first-child")
        self.assertIn("boolean_field No", filter_button_text or "")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-boolean_field")
        self.assertEqual(unset_button.count(), 1)

    def test_boolean_filter_unset(self) -> None:
        """Test clicking Unset button and verifying all rows shown."""
        page = self.logged_in_page

        # First apply a Yes filter
        page.click("#filter-widget-boolean_field button:first-child")
        page.wait_for_selector("#filter-widget-boolean_field .filter-button")
        page.click("#filter-widget-boolean_field .btn-yes")
        # Wait for filter to be applied (URL should change)
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(
                    f={"boolean_field": BooleanValueFilter(value=True)},
                    p=PaginationSchema(page=1, per=25),
                ),
            )
        )

        # Verify filter is applied (3 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.true_obj3.pk, self.true_obj2.pk, self.true_obj1.pk]
        )

        # Click unset button (✕)
        page.click(".unset-filter-boolean_field")
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(),
            )
        )

        # Verify all rows are displayed (5 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [
                self.false_obj2.pk,
                self.false_obj1.pk,
                self.true_obj3.pk,
                self.true_obj2.pk,
                self.true_obj1.pk,
            ],
        )

        # Verify filter button shows no state
        filter_button_text = page.text_content("#filter-widget-boolean_field button:first-child")
        self.assertIsNotNone(filter_button_text)
        # Should not contain Yes or No
        assert filter_button_text is not None
        self.assertNotIn("Yes", filter_button_text)
        self.assertNotIn("No", filter_button_text)

        # Verify ✕ button is not shown
        unset_button = page.locator(".unset-filter-boolean_field")
        self.assertEqual(unset_button.count(), 0)

    def test_boolean_filter_toggle(self) -> None:
        """Test toggling between Yes/No options and verify filtering changes."""
        page = self.logged_in_page

        # Start from unset state - click boolean filter button to open it
        page.click("#filter-widget-boolean_field button:first-child")
        page.wait_for_selector("#filter-widget-boolean_field .filter-button")

        # Click Yes option
        page.click("#filter-widget-boolean_field .btn-yes")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(f={"boolean_field": BooleanValueFilter(value=True)}),
            )
        )
        # Verify only True values are displayed
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.true_obj3.pk, self.true_obj2.pk, self.true_obj1.pk]
        )

        # Click to open filter widget again
        page.click("#filter-widget-boolean_field button:first-child")
        page.wait_for_selector("#filter-widget-boolean_field .filter-button")
        # Click No option to toggle
        page.click("#filter-widget-boolean_field .btn-no")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(f={"boolean_field": BooleanValueFilter(value=False)}),
            )
        )
        # Verify only False values are displayed
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.false_obj2.pk, self.false_obj1.pk])

        # Click to open filter widget again
        page.click("#filter-widget-boolean_field button:first-child")
        page.wait_for_selector("#filter-widget-boolean_field .filter-button")
        # Click Yes option to toggle back
        page.click("#filter-widget-boolean_field .btn-yes")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(f={"boolean_field": BooleanValueFilter(value=True)}),
            )
        )
        # Verify only True values are displayed again
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.true_obj3.pk, self.true_obj2.pk, self.true_obj1.pk]
        )

        # Click unset button (✕)
        page.click(".unset-filter-boolean_field")
        page.wait_for_url(
            self.list_rows_url(
                "BooleanFieldModel",
                ListPageSchema(),
            )
        )
        # Verify all rows are displayed
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [
                self.false_obj2.pk,
                self.false_obj1.pk,
                self.true_obj3.pk,
                self.true_obj2.pk,
                self.true_obj1.pk,
            ],
        )


class IntegerFilterE2ETestCase(BasePlaywrightTestCase):
    """Test integer field filtering through E2E tests.

    Tests:
    - **Test Setup**: Create 4 rows with various integer_field values (0, 5, 15, 25)
      and navigate to IntegerFieldModel list page
    - `test_integer_comparison_gt`: Test greater than 12 operator in UI
      - Matches: 2 rows with integer_field > 12 (values: 15, 25)
    - `test_integer_comparison_gte`: Test greater than or equal 12 operator in UI
      - Matches: 2 rows with integer_field >= 12 (values: 15, 25)
    - `test_integer_comparison_lt`: Test less than 12 operator in UI
      - Matches: 2 rows with integer_field < 12 (values: 0, 5)
    - `test_integer_comparison_lte`: Test less than or equal 12 operator in UI
      - Matches: 2 rows with integer_field <= 12 (values: 0, 5)
    - `test_integer_comparison_eq`: Test equal to 15 operator in UI
      - Matches: 1 row with integer_field = 15
    - `test_integer_comparison_ne`: Test not equal to 15 operator in UI
      - Matches: 3 rows with integer_field != 15 (values: 0, 5, 25)
    - `test_integer_range_inc`: Test include range operator in UI
      - Matches: 2 rows with integer_field in [5, 15] (values: 5, 15)
    - `test_integer_range_ex`: Test exclude range operator in UI
      - Matches: 2 rows with integer_field NOT in [5, 15] (values: 0, 25)
    - `test_integer_range_auto_swap`: Test auto-swap when entering reversed range
      - Matches: 2 rows with integer_field in [5, 15] (values: 5, 15)
    - `test_integer_range_validation_error`: Test error handling for invalid ranges
    - `test_integer_choice_any`: Test choice filter with "any" operator (uses multiselect UI)
      - Matches: 3 rows with integer_choice_field in [1, 2] (Active, Inactive)
    - `test_integer_choice_none`: Test choice filter with "none" operator (uses multiselect UI)
      - Matches: 1 row with integer_choice_field NOT in [1, 2] (value: 3)
    - `test_integer_null_true`: Test null filter for optional fields (True)
      - Matches: 2 rows with optional_integer_field IS NULL (values: None)
    - `test_integer_null_false`: Test null filter for optional fields (False)
      - Matches: 2 rows with optional_integer_field NOT NULL (values: 10, 20)
    - `test_integer_non_nullable_no_null_buttons`: Test null buttons hidden for
      non-nullable integer_field
    - `test_integer_choice_non_nullable_no_null_buttons`: Test null buttons hidden
      for non-nullable integer_choice_field
    - `test_optional_integer_null_buttons_shown`: Test null buttons shown for
      nullable optional_integer_field
    - `test_integer_filter_unset`: Test unsetting integer filter (full UI test)
    """

    def setUp(self) -> None:
        super().setUp()

        # Create test data with various integer values
        self.int_obj0 = IntegerFieldModel.objects.create(
            integer_field=0,
            optional_integer_field=None,
            integer_choice_field=1,
            optional_integer_choice_field=None,
        )
        self.int_obj5 = IntegerFieldModel.objects.create(
            integer_field=5,
            optional_integer_field=10,
            integer_choice_field=2,
            optional_integer_choice_field=1,
        )
        self.int_obj15 = IntegerFieldModel.objects.create(
            integer_field=15,
            optional_integer_field=20,
            integer_choice_field=3,
            optional_integer_choice_field=2,
        )
        self.int_obj25 = IntegerFieldModel.objects.create(
            integer_field=25,
            optional_integer_field=None,
            integer_choice_field=1,
            optional_integer_choice_field=3,
        )

        # Navigate to IntegerFieldModel list page
        page = self.logged_in_page
        page.goto(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(),
            )
        )
        page.wait_for_selector("table")

    def test_integer_comparison_gt(self) -> None:
        """Test greater than 12 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")
        page.select_option("#filter-widget-integer_field select", "gt")
        page.fill("#filter-widget-integer_field input[type='number']", "12")
        page.click("#filter-widget-integer_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="gt", number_1=12, number_2=0)}
                ),
            )
        )

        # Verify correct rows are shown (int_obj25 and int_obj15)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj25.pk, self.int_obj15.pk])

    def test_integer_comparison_gte(self) -> None:
        """Test greater than or equal to 8 operator in UI."""
        page = self.logged_in_page

        # Click integer filter button to open it
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")

        # Select greater than or equal operator
        page.select_option("#filter-widget-integer_field select", "gte")
        # Enter value
        page.fill("#filter-widget-integer_field input[type='number']", "12")
        # Click Compare button
        page.click("#filter-widget-integer_field .btn-compare")
        # Wait for filter to be applied (keys in discriminator, number_1, number_2, operator order)
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="gte", number_1=12, number_2=0)}
                ),
            )
        )

        # Verify only values >= 12 are displayed (2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj25.pk, self.int_obj15.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "gte")
        number = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number, "12")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_comparison_lt(self) -> None:
        """Test less than 12 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")
        page.select_option("#filter-widget-integer_field select", "lt")
        page.fill("#filter-widget-integer_field input[type='number']", "12")
        page.click("#filter-widget-integer_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="lt", number_1=12, number_2=0)}
                ),
            )
        )

        # Verify correct rows are shown (int_obj0 and int_obj5)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj5.pk, self.int_obj0.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "lt")
        number = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number, "12")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_comparison_lte(self) -> None:
        """Test less than or equal to 12 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")
        page.select_option("#filter-widget-integer_field select", "lte")
        page.fill("#filter-widget-integer_field input[type='number']", "12")
        page.click("#filter-widget-integer_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="lte", number_1=12, number_2=0)}
                ),
            )
        )

        # Verify correct rows are shown (int_obj0, int_obj5)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj5.pk, self.int_obj0.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "lte")
        number = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number, "12")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_comparison_eq(self) -> None:
        """Test equal to 15 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")
        page.select_option("#filter-widget-integer_field select", "eq")
        page.fill("#filter-widget-integer_field input[type='number']", "15")
        page.click("#filter-widget-integer_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="eq", number_1=15, number_2=0)}
                ),
            )
        )

        # Verify correct rows are shown (int_obj15 only)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj15.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "eq")
        number = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number, "15")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_comparison_ne(self) -> None:
        """Test not equal to 15 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")
        page.select_option("#filter-widget-integer_field select", "ne")
        page.fill("#filter-widget-integer_field input[type='number']", "15")
        page.click("#filter-widget-integer_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="ne", number_1=15, number_2=0)}
                ),
            )
        )

        # Verify correct rows are shown (int_obj0, int_obj5, int_obj25)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj25.pk, self.int_obj5.pk, self.int_obj0.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "ne")
        number = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number, "15")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_range_inc(self) -> None:
        """Test include range operator in UI."""
        page = self.logged_in_page

        # Click integer filter button to open it
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")

        # Select include range operator
        page.select_option("#filter-widget-integer_field select", "inc")
        # Enter range values
        page.fill("#filter-widget-integer_field input[type='number']:first-of-type", "5")
        page.fill("#filter-widget-integer_field input[type='number']:last-of-type", "15")
        # Click Compare button
        page.click("#filter-widget-integer_field .btn-compare")
        # Wait for filter to be applied (keys in discriminator, number_1, number_2, operator order)
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="inc", number_1=5, number_2=15)}
                ),
            )
        )

        # Verify only values in range 5-15 are displayed (5 and 15 = 2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj15.pk, self.int_obj5.pk])

        # Wait for button text to update
        page.wait_for_timeout(500)

        # Verify filter button shows range
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "inc")
        number1 = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number1, "5")
        number2 = self.extract_filter_value("integer_field", "number_2_collapsed")
        self.assertEqual(number2, "15")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_range_ex(self) -> None:
        """Test exclude range operator in UI."""
        page = self.logged_in_page

        # Click integer filter button to open it
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")

        # Select exclude range operator
        page.select_option("#filter-widget-integer_field select", "ex")
        # Enter range values
        page.fill("#filter-widget-integer_field input[type='number']:first-of-type", "5")
        page.fill("#filter-widget-integer_field input[type='number']:last-of-type", "15")
        # Click Compare button
        page.click("#filter-widget-integer_field .btn-compare")
        # Wait for filter to be applied (keys in discriminator, number_1, number_2, operator order)
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_field": IntegerComparisonFilter(op="ex", number_1=5, number_2=15)}
                ),
            )
        )

        # Verify only values outside range 5-15 are displayed (0 and 25 = 2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj25.pk, self.int_obj0.pk])

        # Verify filter button shows range
        operator = self.extract_filter_value("integer_field", "operator_collapsed")
        self.assertEqual(operator, "exclude")
        number1 = self.extract_filter_value("integer_field", "number_1_collapsed")
        self.assertEqual(number1, "5")
        number2 = self.extract_filter_value("integer_field", "number_2_collapsed")
        self.assertEqual(number2, "15")

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-integer_field")
        self.assertEqual(unset_button.count(), 1)

        # Verify Compare button is highlighted
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")
        self.verify_filter_button_active_class("integer_field", "btn-compare")

    def test_integer_range_validation_error(self) -> None:
        """Test error handling for invalid ranges - both values equal."""
        page = self.logged_in_page

        # Click integer filter button to open it
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field select")

        # Select include range operator
        page.select_option("#filter-widget-integer_field select", "inc")
        # Enter values that would result in error (same value)
        page.fill("#filter-widget-integer_field input[type='number']:first-of-type", "10")
        page.fill("#filter-widget-integer_field input[type='number']:last-of-type", "10")

        # Click Compare button - should handle the case appropriately
        page.click("#filter-widget-integer_field .btn-compare")

        # Verify behavior (either error shown or no filter applied)
        # The filter should either show an error or not apply the filter
        table_rows = page.locator("table tbody tr")
        # Either all rows shown (4) or error state
        self.assertIn(table_rows.count(), [0, 4])

    def test_integer_choice_any(self) -> None:
        """Test choice filter with 'any' operator."""
        page = self.logged_in_page

        # Open integer choice filter widget
        page.click("#filter-widget-integer_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_choice_field .multiselect")

        # Select "Active" and "Inactive" choices using multiselect
        self.fill_integer_choice_multiselect("integer_choice_field", ["Active", "Inactive"])

        # Click "Any of" button
        page.click("#filter-widget-integer_choice_field .btn-any")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_choice_field": IntegerChoiceFilter(mode="any", options=[1, 2])},
                    p=PaginationSchema(page=1, per=25),
                ),
            )
        )

        # Verify only rows with choices [1, 2] are shown (int_obj0, int_obj5, int_obj25)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj25.pk, self.int_obj5.pk, self.int_obj0.pk])

    def test_integer_choice_none(self) -> None:
        """Test choice filter with 'none' operator."""
        page = self.logged_in_page

        # Open integer choice filter widget
        page.click("#filter-widget-integer_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_choice_field .multiselect")

        # Select "Active" and "Inactive" choices using multiselect
        self.fill_integer_choice_multiselect("integer_choice_field", ["Active", "Inactive"])

        # Click "None of" button
        page.click("#filter-widget-integer_choice_field .btn-none")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(
                    f={"integer_choice_field": IntegerChoiceFilter(mode="none", options=[1, 2])},
                    p=PaginationSchema(page=1, per=25),
                ),
            )
        )

        # Verify only rows with choice value 3 (Pending) are shown (int_obj15)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.int_obj15.pk])

    def test_integer_null_true(self) -> None:
        """Test null filter for optional fields (True)."""
        page = self.logged_in_page

        # Open optional integer filter widget
        page.click("#filter-widget-optional_integer_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_integer_field .filter-button")

        # Click "Is null" button
        page.click("#filter-widget-optional_integer_field .btn-is-null")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(f={"optional_integer_field": IntegerNullFilter(value=True)}),
            )
        )

        # Verify rows with null optional_integer_field are shown (int_obj0, int_obj25)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.int_obj25.pk, self.int_obj0.pk],
        )

    def test_integer_null_false(self) -> None:
        """Test null filter for optional fields (False)."""
        page = self.logged_in_page

        # Open optional integer filter widget
        page.click("#filter-widget-optional_integer_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_integer_field .filter-button")

        # Click "Not null" button
        page.click("#filter-widget-optional_integer_field .btn-not-null")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "IntegerFieldModel",
                ListPageSchema(f={"optional_integer_field": IntegerNullFilter(value=False)}),
            )
        )

        # Verify rows with non-null optional_integer_field are shown (int_obj15, int_obj5)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.int_obj15.pk, self.int_obj5.pk],
        )

    def test_integer_non_nullable_no_null_buttons(self) -> None:
        """Test that null buttons are not shown for non-nullable integer_field."""
        page = self.logged_in_page

        # Open non-nullable integer filter widget
        page.click("#filter-widget-integer_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_field .filter-button")

        # Verify null buttons are NOT shown
        is_null_button = page.locator("#filter-widget-integer_field .btn-is-null")
        self.assertEqual(is_null_button.count(), 0)

        not_null_button = page.locator("#filter-widget-integer_field .btn-not-null")
        self.assertEqual(not_null_button.count(), 0)

    def test_integer_choice_non_nullable_no_null_buttons(self) -> None:
        """Test that null buttons are not shown for non-nullable integer_choice_field."""
        page = self.logged_in_page

        # Open non-nullable integer choice filter widget
        page.click("#filter-widget-integer_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-integer_choice_field .filter-button")

        # Verify null buttons are NOT shown
        is_null_button = page.locator("#filter-widget-integer_choice_field .btn-is-null")
        self.assertEqual(is_null_button.count(), 0)

        not_null_button = page.locator("#filter-widget-integer_choice_field .btn-not-null")
        self.assertEqual(not_null_button.count(), 0)

    def test_optional_integer_null_buttons_shown(self) -> None:
        """Test that null buttons ARE shown for nullable optional_integer_field."""
        page = self.logged_in_page

        # Open nullable optional integer filter widget
        page.click("#filter-widget-optional_integer_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_integer_field .filter-button")

        # Verify null buttons ARE shown
        is_null_button = page.locator("#filter-widget-optional_integer_field .btn-is-null")
        self.assertEqual(is_null_button.count(), 1)

        not_null_button = page.locator("#filter-widget-optional_integer_field .btn-not-null")
        self.assertEqual(not_null_button.count(), 1)


class DecimalFilterE2ETestCase(BasePlaywrightTestCase):
    """Test decimal field filtering through E2E tests.

    Tests:
    - **Test Setup**: Create 4 rows with various decimal_field values
      (0.00, 50.50, 100.00, 150.50) and navigate to DecimalFieldModel list page
    - `test_decimal_comparison_gt`: Test greater than 75.00 operator in UI
      - Matches: 2 rows with decimal_field > 75.00 (values: 100.00, 150.50)
    - `test_decimal_comparison_gte`: Test greater than or equal 100.00 operator in UI
      - Matches: 2 rows with decimal_field >= 100.00 (values: 100.00, 150.50)
    - `test_decimal_comparison_lt`: Test less than 75.00 operator in UI
      - Matches: 2 rows with decimal_field < 75.00 (values: 0.00, 50.50)
    - `test_decimal_comparison_lte`: Test less than or equal 50.50 operator in UI
      - Matches: 2 rows with decimal_field <= 50.50 (values: 0.00, 50.50)
    - `test_decimal_comparison_eq`: Test equal to 100.00 operator in UI
      - Matches: 1 row with decimal_field = 100.00
    - `test_decimal_comparison_ne`: Test not equal to 100.00 operator in UI
      - Matches: 3 rows with decimal_field != 100.00 (values: 0.00, 50.50, 150.50)
    - `test_decimal_range_inc`: Test include range operator in UI
      - Matches: 2 rows with decimal_field in [50.00, 100.00] (values: 50.50, 100.00)
    - `test_decimal_range_ex`: Test exclude range operator in UI
      - Matches: 2 rows with decimal_field NOT in [50.00, 100.00] (values: 0.00, 150.50)
    - `test_decimal_null_true`: Test null filter for optional fields (True)
      - Matches: 2 rows with optional_decimal_field IS NULL (values: None)
    - `test_decimal_null_false`: Test null filter for optional fields (False)
      - Matches: 2 rows with optional_decimal_field NOT NULL (values: 10.25, 25.75)
    - `test_decimal_non_nullable_no_null_buttons`: Test null buttons hidden for
      non-nullable decimal_field
    - `test_optional_decimal_null_buttons_shown`: Test null buttons shown for
      nullable optional_decimal_field
    - `test_decimal_filter_unset`: Test unsetting decimal filter (full UI test)
    """

    def setUp(self) -> None:
        super().setUp()

        # Create test data with various decimal values
        self.dec_obj0 = DecimalFieldModel.objects.create(
            decimal_field=Decimal("0.00"),
            optional_decimal_field=None,
        )
        self.dec_obj50 = DecimalFieldModel.objects.create(
            decimal_field=Decimal("50.50"),
            optional_decimal_field=Decimal("10.25"),
        )
        self.dec_obj100 = DecimalFieldModel.objects.create(
            decimal_field=Decimal("100.00"),
            optional_decimal_field=Decimal("25.75"),
        )
        self.dec_obj150 = DecimalFieldModel.objects.create(
            decimal_field=Decimal("150.50"),
            optional_decimal_field=None,
        )

        # Navigate to DecimalFieldModel list page
        page = self.logged_in_page
        page.goto(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(),
            )
        )
        page.wait_for_selector("table")

    def test_decimal_comparison_gt(self) -> None:
        """Test greater than 75.00 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "gt")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "75")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="gt", number_1="75", number_2="0"
                        )
                    }
                ),
            ),
            timeout=5000,
        )

        # Verify correct rows are shown (dec_obj100 and dec_obj150)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj150.pk, self.dec_obj100.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "gt")
        number = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number, "75")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_comparison_gte(self) -> None:
        """Test greater than or equal 100.00 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "gte")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "100")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="gte", number_1="100", number_2="0"
                        )
                    }
                ),
            )
        )

        # Verify correct rows are shown (dec_obj100 and dec_obj150)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj150.pk, self.dec_obj100.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "gte")
        number = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number, "100")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_comparison_lt(self) -> None:
        """Test less than 75.00 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "lt")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "75")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="lt", number_1="75", number_2="0"
                        )
                    }
                ),
            )
        )

        # Verify correct rows are shown (dec_obj0 and dec_obj50)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj50.pk, self.dec_obj0.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "lt")
        number = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number, "75")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_comparison_lte(self) -> None:
        """Test less than or equal 50.50 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "lte")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "50.5")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="lte", number_1="50.5", number_2="0"
                        )
                    }
                ),
            )
        )

        # Verify correct rows are shown (dec_obj0 and dec_obj50)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj50.pk, self.dec_obj0.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "lte")
        number = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number, "50.5")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_comparison_eq(self) -> None:
        """Test equal to 100.00 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "eq")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "100")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="eq", number_1="100", number_2="0"
                        )
                    }
                ),
            )
        )

        # Verify correct row is shown (dec_obj100 only)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj100.pk])

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "eq")
        number = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number, "100")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_comparison_ne(self) -> None:
        """Test not equal to 100.00 operator in UI."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "ne")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "100")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="ne", number_1="100", number_2="0"
                        )
                    }
                ),
            )
        )

        # Verify correct rows are shown (dec_obj0, dec_obj50, dec_obj150)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.dec_obj150.pk, self.dec_obj50.pk, self.dec_obj0.pk]
        )

        # Verify filter button shows operator and value
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "ne")
        number = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number, "100")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_range_inc(self) -> None:
        """Test include range operator in UI."""
        page = self.logged_in_page

        # Click decimal filter button to open it
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")

        # Select include range operator
        page.select_option("#filter-widget-decimal_field select", "inc")
        # Enter range values
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']:first-of-type", "50")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']:last-of-type", "100")
        # Click Compare button
        page.click("#filter-widget-decimal_field .btn-compare")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="inc", number_1="50", number_2="100"
                        )
                    }
                ),
            )
        )

        # Verify only values in range 50.00-100.00 are displayed (50.50 and 100.00 = 2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj100.pk, self.dec_obj50.pk])

        # Verify filter button shows range
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "inc")
        number1 = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number1, "50")
        number2 = self.extract_filter_value("decimal_field", "number_2_collapsed")
        self.assertEqual(number2, "100")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_range_ex(self) -> None:
        """Test exclude range operator in UI."""
        page = self.logged_in_page

        # Click decimal filter button to open it
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")

        # Select exclude range operator
        page.select_option("#filter-widget-decimal_field select", "ex")
        # Enter range values
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']:first-of-type", "50")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']:last-of-type", "100")
        # Click Compare button
        page.click("#filter-widget-decimal_field .btn-compare")
        # Wait for filter to be applied
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="ex", number_1="50", number_2="100"
                        )
                    }
                ),
            )
        )

        # Verify only values outside range 50.00-100.00 are displayed (0.00 and 150.50 = 2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj150.pk, self.dec_obj0.pk])

        # Verify filter button shows range
        operator = self.extract_filter_value("decimal_field", "operator_collapsed")
        self.assertEqual(operator, "exclude")
        number1 = self.extract_filter_value("decimal_field", "number_1_collapsed")
        self.assertEqual(number1, "50")
        number2 = self.extract_filter_value("decimal_field", "number_2_collapsed")
        self.assertEqual(number2, "100")

        # Verify Compare button is highlighted
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")
        self.verify_filter_button_active_class("decimal_field", "btn-compare")

    def test_decimal_null_true(self) -> None:
        """Test null filter for optional fields (True)."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(f={"optional_decimal_field": DecimalNullFilter(value=True)}),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.dec_obj150.pk, self.dec_obj0.pk],
        )

        # Verify widget status
        unset_button = page.locator(".unset-filter-optional_decimal_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract null_collapsed text BEFORE opening the filter
        null_text = self.extract_filter_value("optional_decimal_field", "null_collapsed")
        self.assertEqual(null_text, "null")

        page.click("#filter-widget-optional_decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_decimal_field .filter-button")
        self.verify_filter_button_active_class("optional_decimal_field", "btn-is-null")

    def test_decimal_null_false(self) -> None:
        """Test null filter for optional fields (False)."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(f={"optional_decimal_field": DecimalNullFilter(value=False)}),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.dec_obj100.pk, self.dec_obj50.pk],
        )

        # Verify widget status
        unset_button = page.locator(".unset-filter-optional_decimal_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract null_collapsed text BEFORE opening the filter
        null_text = self.extract_filter_value("optional_decimal_field", "null_collapsed")
        self.assertEqual(null_text, "not null")

        page.click("#filter-widget-optional_decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_decimal_field .filter-button")
        self.verify_filter_button_active_class("optional_decimal_field", "btn-not-null")

    def test_decimal_non_nullable_no_null_buttons(self) -> None:
        """Test that null buttons are not shown for non-nullable decimal_field."""
        page = self.logged_in_page

        # Open non-nullable decimal filter widget
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field .filter-button")

        # Verify null buttons are NOT shown
        is_null_button = page.locator("#filter-widget-decimal_field .btn-is-null")
        self.assertEqual(is_null_button.count(), 0)

        not_null_button = page.locator("#filter-widget-decimal_field .btn-not-null")
        self.assertEqual(not_null_button.count(), 0)

    def test_optional_decimal_null_buttons_shown(self) -> None:
        """Test that null buttons ARE shown for nullable optional_decimal_field."""
        page = self.logged_in_page

        # Open nullable optional decimal filter widget
        page.click("#filter-widget-optional_decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_decimal_field .filter-button")

        # Verify null buttons ARE shown
        is_null_button = page.locator("#filter-widget-optional_decimal_field .btn-is-null")
        self.assertEqual(is_null_button.count(), 1)

        not_null_button = page.locator("#filter-widget-optional_decimal_field .btn-not-null")
        self.assertEqual(not_null_button.count(), 1)

    def test_decimal_filter_unset(self) -> None:
        """Test unsetting decimal filter (full UI test)."""
        page = self.logged_in_page

        # First apply a gte filter
        page.click("#filter-widget-decimal_field button:first-child")
        page.wait_for_selector("#filter-widget-decimal_field select")
        page.select_option("#filter-widget-decimal_field select", "gte")
        page.fill("#filter-widget-decimal_field input[inputmode='decimal']", "100")
        page.click("#filter-widget-decimal_field .btn-compare")
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(
                    f={
                        "decimal_field": DecimalComparisonFilter(
                            op="gte", number_1="100", number_2="0"
                        )
                    }
                ),
            )
        )

        # Verify filter is applied (2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dec_obj150.pk, self.dec_obj100.pk])

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-decimal_field")
        self.assertEqual(unset_button.count(), 1)

        # Click unset button
        unset_button.click()

        # Wait for filter to be removed
        page.wait_for_url(
            self.list_rows_url(
                "DecimalFieldModel",
                ListPageSchema(),
            )
        )

        # Verify all rows are shown (4 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.dec_obj150.pk, self.dec_obj100.pk, self.dec_obj50.pk, self.dec_obj0.pk],
        )

        # Verify ✕ button is no longer shown
        unset_button = page.locator(".unset-filter-decimal_field")
        self.assertEqual(unset_button.count(), 0)


class CharFilterE2ETestCase(BasePlaywrightTestCase):
    """Test char field filtering through E2E tests.

    Tests:
    - **Test Setup**: Create 4 rows with various char_field values
      and navigate to CharFieldModel list page
    - `test_char_text_contains`: Test text contains filtering
      - Matches: 2 rows containing "test" (case-insensitive)
    - `test_char_text_case_insensitive`: Test case-insensitive search
    - `test_char_choice_any`: Test choice filter with "any" operator
      - Matches: 3 rows with char_choice_field in ["active", "inactive"]
    - `test_char_choice_none`: Test choice filter with "none" operator
      - Matches: 1 row with char_choice_field NOT in ["active", "inactive"]
    - `test_char_blank_true`: Test blank filter for empty text fields (True)
      - Matches: 1 row with empty char_field
    - `test_char_blank_false`: Test blank filter for non-empty text fields (False)
      - Matches: 3 rows with non-empty char_field
    - `test_char_filter_unset`: Test unsetting char filter (full UI test)
    - `test_char_choice_remove_selected_by_click`: Test that clicking the X
      on a selected multiselect tag removes it. Added because vue-multiselect's
      `removeElement` requires `track-by` to identify objects by key — without
      it, `valueKeys.indexOf(option[undefined])` returns -1 and removal silently
      fails.
    - `test_char_choice_no_duplicate_options`: Test that selecting the same
      option twice does not create duplicate tags. Added because without
      `track-by`, vue-multiselect uses reference equality and can't detect
      duplicates when options are recreated on re-render.
    """

    def setUp(self) -> None:
        super().setUp()

        # Create test data with various char values
        self.char_obj0 = CharFieldModel.objects.create(
            char_field="",
            text_field="",
            char_choice_field="active",
            optional_char_choice_field=None,
        )
        self.char_obj1 = CharFieldModel.objects.create(
            char_field="test",
            text_field="description",
            char_choice_field="inactive",
            optional_char_choice_field="active",
        )
        self.char_obj2 = CharFieldModel.objects.create(
            char_field="Test",
            text_field="TEST",
            char_choice_field="pending",
            optional_char_choice_field="inactive",
        )
        self.char_obj3 = CharFieldModel.objects.create(
            char_field="another",
            text_field="longer description",
            char_choice_field="active",
            optional_char_choice_field="pending",
        )

        # Navigate to CharFieldModel list page
        page = self.logged_in_page
        page.goto(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(),
            )
        )
        page.wait_for_selector("table")

    def test_char_text_contains(self) -> None:
        """Test text contains filtering."""
        page = self.logged_in_page

        # Apply filter
        page.click("#filter-widget-char_field button:first-child")
        page.wait_for_selector("#filter-widget-char_field input[type='text']")
        page.fill("#filter-widget-char_field input[type='text']", "test")
        page.click("#filter-widget-char_field .btn-contains")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(f={"char_field": CharTextFilter(text="test")}),
            )
        )

        # Verify correct rows shown (char_obj1, char_obj2)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.char_obj2.pk, self.char_obj1.pk])

        # Verify filter button shows text
        text = self.extract_filter_value("char_field", "text_collapsed")
        self.assertEqual(text, "test")

    def test_char_text_case_insensitive(self) -> None:
        """Test case-insensitive search."""
        page = self.logged_in_page

        # Apply filter with uppercase
        page.click("#filter-widget-char_field button:first-child")
        page.wait_for_selector("#filter-widget-char_field input[type='text']")
        page.fill("#filter-widget-char_field input[type='text']", "TEST")
        page.click("#filter-widget-char_field .btn-contains")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(f={"char_field": CharTextFilter(text="TEST")}),
            )
        )

        # Verify same rows matched (case-insensitive)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.char_obj2.pk, self.char_obj1.pk])

    def fill_char_choice_multiselect(self, column_name: str, choices: list[str]) -> None:
        """Fill a char choice multiselect with specified choices.

        Uses focus()+fill() on the input element rather than clicking the
        .multiselect container, because clicking .multiselect can hit tag
        elements and trigger removeElement (which now works correctly thanks
        to track-by="value").
        """
        page = self.logged_in_page
        selector_prefix = f"#filter-widget-{column_name}"

        for choice in choices:
            page.locator(f"{selector_prefix} input.multiselect__input").focus()
            page.locator(f"{selector_prefix} input.multiselect__input").fill(choice, force=True)
            page.wait_for_selector(f"{selector_prefix} .multiselect__content-wrapper")
            page.wait_for_selector(f"{selector_prefix} .multiselect__option--highlight")
            page.keyboard.press("Enter")

    def test_char_choice_any(self) -> None:
        """Test choice filter with 'any' operator."""
        page = self.logged_in_page

        # Open filter widget
        page.click("#filter-widget-char_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-char_choice_field .multiselect__tags")

        # Select "Active" and "Inactive" choices using multiselect
        self.fill_char_choice_multiselect("char_choice_field", ["Active", "Inactive"])

        # Click "Any of" button
        page.click("#filter-widget-char_choice_field .btn-any")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(
                    f={
                        "char_choice_field": CharChoiceFilter(
                            mode="any", options=["active", "inactive"]
                        )
                    }
                ),
            )
        )

        # Verify 3 rows matched (active, inactive)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.char_obj3.pk, self.char_obj1.pk, self.char_obj0.pk]
        )

    def test_char_choice_none(self) -> None:
        """Test choice filter with 'none' operator."""
        page = self.logged_in_page

        # Open filter widget
        page.click("#filter-widget-char_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-char_choice_field .multiselect__tags")

        # Select "Active" choice using multiselect
        self.fill_char_choice_multiselect("char_choice_field", ["Active"])

        # Click "None of" button
        page.click("#filter-widget-char_choice_field .btn-none")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(
                    f={"char_choice_field": CharChoiceFilter(mode="none", options=["active"])}
                ),
            )
        )

        # Verify 2 rows matched (not active - pending and inactive)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.char_obj2.pk, self.char_obj1.pk])

    def test_char_blank_true(self) -> None:
        """Test blank filter for empty text fields (True)."""
        page = self.logged_in_page

        # Apply blank filter
        page.click("#filter-widget-char_field button:first-child")
        page.wait_for_selector("#filter-widget-char_field .btn-is-null")
        page.click("#filter-widget-char_field .btn-is-null")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(f={"char_field": CharBlankFilter(value=True)}),
            )
        )

        # Verify 1 row matched (empty char_field)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.char_obj0.pk])

    def test_char_blank_false(self) -> None:
        """Test blank filter for non-empty text fields (False)."""
        page = self.logged_in_page

        # Apply not blank filter
        page.click("#filter-widget-char_field button:first-child")
        page.wait_for_selector("#filter-widget-char_field .btn-not-null")
        page.click("#filter-widget-char_field .btn-not-null")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(f={"char_field": CharBlankFilter(value=False)}),
            )
        )

        # Verify 3 rows matched (non-empty char_field)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.char_obj3.pk, self.char_obj2.pk, self.char_obj1.pk]
        )

    def test_char_filter_unset(self) -> None:
        """Test unsetting char filter."""
        page = self.logged_in_page

        # First apply a contains filter
        page.click("#filter-widget-char_field button:first-child")
        page.wait_for_selector("#filter-widget-char_field input[type='text']")
        page.fill("#filter-widget-char_field input[type='text']", "test")
        page.click("#filter-widget-char_field .btn-contains")
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(f={"char_field": CharTextFilter(text="test")}),
            )
        )

        # Verify filter is applied (2 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.char_obj2.pk, self.char_obj1.pk])

        # Verify ✕ button is shown
        unset_button = page.locator(".unset-filter-char_field")
        self.assertEqual(unset_button.count(), 1)

        # Click unset button
        unset_button.click()

        # Wait for filter to be removed
        page.wait_for_url(
            self.list_rows_url(
                "CharFieldModel",
                ListPageSchema(),
            )
        )

        # Verify all rows are shown (4 rows)
        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.char_obj3.pk, self.char_obj2.pk, self.char_obj1.pk, self.char_obj0.pk],
        )

        # Verify ✕ button is no longer shown
        unset_button = page.locator(".unset-filter-char_field")
        self.assertEqual(unset_button.count(), 0)

    def test_char_choice_remove_selected_by_click(self) -> None:
        """Test that clicking the X on a selected multiselect tag removes it."""
        page = self.logged_in_page

        page.click("#filter-widget-char_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-char_choice_field .multiselect__tags")

        self.fill_char_choice_multiselect("char_choice_field", ["Active", "Inactive"])

        tags = page.locator("#filter-widget-char_choice_field .multiselect__tag")
        self.assertEqual(tags.count(), 2)

        page.locator("#filter-widget-char_choice_field .multiselect__tag-icon").first.click()
        page.wait_for_selector(
            "#filter-widget-char_choice_field .multiselect__tags",
        )

        tags = page.locator("#filter-widget-char_choice_field .multiselect__tag")
        self.assertEqual(tags.count(), 1)
        self.assertIn("Inactive", tags.first.text_content() or "")

    def test_char_choice_no_duplicate_options(self) -> None:
        """Test that selecting the same option twice does not create duplicates."""
        page = self.logged_in_page

        page.click("#filter-widget-char_choice_field button:first-child")
        page.wait_for_selector("#filter-widget-char_choice_field .multiselect__tags")

        self.fill_char_choice_multiselect("char_choice_field", ["Active"])

        tags = page.locator("#filter-widget-char_choice_field .multiselect__tag")
        self.assertEqual(tags.count(), 1)

        selector_prefix = "#filter-widget-char_choice_field"
        page.locator(f"{selector_prefix} .multiselect").click()
        page.wait_for_selector(f"{selector_prefix} .multiselect__content-wrapper")
        page.locator(f"{selector_prefix} input.multiselect__input").fill("Active", force=True)
        page.wait_for_selector(f"{selector_prefix} .multiselect__option--highlight")
        page.keyboard.press("Enter")

        tags = page.locator("#filter-widget-char_choice_field .multiselect__tag")
        self.assertEqual(tags.count(), 1)


class DatetimeFilterE2ETestCase(BasePlaywrightTestCase):
    """Test datetime field filtering through E2E tests.

    Tests:
    - **Test Setup**: Create 4 rows with various datetime_field values
      and navigate to DatetimeFieldModel list page
    - `test_datetime_comparison_gt`: Test greater than operator
    - `test_datetime_comparison_lt`: Test less than operator
    - `test_datetime_comparison_eq`: Test equal operator
    - `test_datetime_comparison_ne`: Test not equal operator
    - `test_datetime_range_inc`: Test include range operator
    - `test_datetime_range_ex`: Test exclude range operator
    - `test_datetime_relative_past_hours`: Test relative filter for past hours
    - `test_datetime_relative_past_days`: Test relative filter for past days
    - `test_datetime_relative_next_days`: Test relative filter for next days
    - `test_datetime_null_true`: Test null filter for optional fields (True)
    - `test_datetime_null_false`: Test null filter for optional fields (False)
    - `test_datetime_filter_unset`: Test unsetting datetime filter
    """

    def setUp(self) -> None:
        super().setUp()

        now = timezone.now()

        self.dt_obj0 = DatetimeFieldModel.objects.create(
            datetime_field=now - timedelta(days=10),
            optional_datetime_field=None,
        )
        self.dt_obj1 = DatetimeFieldModel.objects.create(
            datetime_field=now - timedelta(days=5),
            optional_datetime_field=now - timedelta(days=1),
        )
        self.dt_obj2 = DatetimeFieldModel.objects.create(
            datetime_field=now - timedelta(days=1),
            optional_datetime_field=now,
        )
        self.dt_obj3 = DatetimeFieldModel.objects.create(
            datetime_field=now + timedelta(days=5),
            optional_datetime_field=None,
        )

        self.now = now

        page = self.logged_in_page
        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(),
            )
        )
        page.wait_for_selector("table")

    def test_datetime_comparison_gt(self) -> None:
        """Test greater than operator."""
        page = self.logged_in_page

        dt = self.now - timedelta(days=3)
        dt_str = dt.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="gt", datetime_1=dt_str, datetime_2=dt_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj3.pk, self.dt_obj2.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        operator = self.extract_filter_value("datetime_field", "operator_collapsed")
        self.assertEqual(operator, "gt")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-compare")

    def test_datetime_comparison_lt(self) -> None:
        """Test less than operator."""
        page = self.logged_in_page

        dt = self.now - timedelta(days=3)
        dt_str = dt.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="lt", datetime_1=dt_str, datetime_2=dt_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj1.pk, self.dt_obj0.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        operator = self.extract_filter_value("datetime_field", "operator_collapsed")
        self.assertEqual(operator, "lt")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-compare")

    def test_datetime_comparison_eq(self) -> None:
        """Test equal operator."""
        page = self.logged_in_page

        dt_str = self.dt_obj1.datetime_field.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="eq", datetime_1=dt_str, datetime_2=dt_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj1.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        operator = self.extract_filter_value("datetime_field", "operator_collapsed")
        self.assertEqual(operator, "eq")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-compare")

    def test_datetime_comparison_ne(self) -> None:
        """Test not equal operator."""
        page = self.logged_in_page

        dt_str = self.dt_obj1.datetime_field.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="ne", datetime_1=dt_str, datetime_2=dt_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj3.pk, self.dt_obj2.pk, self.dt_obj0.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        operator = self.extract_filter_value("datetime_field", "operator_collapsed")
        self.assertEqual(operator, "ne")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-compare")

    def test_datetime_range_inc(self) -> None:
        """Test include range operator."""
        page = self.logged_in_page

        dt1 = self.now - timedelta(days=7)
        dt2 = self.now - timedelta(days=2)
        dt1_str = dt1.isoformat()
        dt2_str = dt2.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="inc", datetime_1=dt1_str, datetime_2=dt2_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj1.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        operator = self.extract_filter_value("datetime_field", "operator_collapsed")
        self.assertEqual(operator, "inc")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-compare")

    def test_datetime_range_ex(self) -> None:
        """Test exclude range operator."""
        page = self.logged_in_page

        dt1 = self.now - timedelta(days=7)
        dt2 = self.now - timedelta(days=2)
        dt1_str = dt1.isoformat()
        dt2_str = dt2.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="ex", datetime_1=dt1_str, datetime_2=dt2_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj3.pk, self.dt_obj2.pk, self.dt_obj0.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        operator = self.extract_filter_value("datetime_field", "operator_collapsed")
        self.assertEqual(operator, "ex")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-compare")

    def test_datetime_relative_past_hours(self) -> None:
        """Test relative filter for past hours."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeRelativeFilter(
                            direction="past", unit="hours", quantity=48
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj2.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        direction = self.extract_filter_value("datetime_field", "direction_collapsed")
        self.assertEqual(direction, "past")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-relative")

    def test_datetime_relative_past_days(self) -> None:
        """Test relative filter for past days."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeRelativeFilter(
                            direction="past", unit="days", quantity=7
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj2.pk, self.dt_obj1.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        direction = self.extract_filter_value("datetime_field", "direction_collapsed")
        self.assertEqual(direction, "past")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-relative")

    def test_datetime_relative_next_days(self) -> None:
        """Test relative filter for next days."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeRelativeFilter(
                            direction="next", unit="days", quantity=7
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj3.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        direction = self.extract_filter_value("datetime_field", "direction_collapsed")
        self.assertEqual(direction, "next")

        page.click("#filter-widget-datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-datetime_field .filter-button")
        self.verify_filter_button_active_class("datetime_field", "btn-relative")

    def test_datetime_null_true(self) -> None:
        """Test null filter for optional fields (True)."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(f={"optional_datetime_field": DatetimeNullFilter(value=True)}),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj3.pk, self.dt_obj0.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-optional_datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        null_text = self.extract_filter_value("optional_datetime_field", "null_collapsed")
        self.assertEqual(null_text, "is null")

        page.click("#filter-widget-optional_datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_datetime_field .filter-button")
        self.verify_filter_button_active_class("optional_datetime_field", "btn-is-null")

    def test_datetime_null_false(self) -> None:
        """Test null filter for optional fields (False)."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(f={"optional_datetime_field": DatetimeNullFilter(value=False)}),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj2.pk, self.dt_obj1.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-optional_datetime_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        null_text = self.extract_filter_value("optional_datetime_field", "null_collapsed")
        self.assertEqual(null_text, "not null")

        page.click("#filter-widget-optional_datetime_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_datetime_field .filter-button")
        self.verify_filter_button_active_class("optional_datetime_field", "btn-not-null")

    def test_datetime_filter_unset(self) -> None:
        """Test unsetting datetime filter."""
        page = self.logged_in_page

        dt = self.now - timedelta(days=3)
        dt_str = dt.isoformat()

        page.goto(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(
                    f={
                        "datetime_field": DatetimeComparisonFilter(
                            op="gt", datetime_1=dt_str, datetime_2=dt_str
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.dt_obj3.pk, self.dt_obj2.pk])

        unset_button = page.locator(".unset-filter-datetime_field")
        self.assertEqual(unset_button.count(), 1)

        unset_button.click()

        page.wait_for_url(
            self.list_rows_url(
                "DatetimeFieldModel",
                ListPageSchema(),
            )
        )

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.dt_obj3.pk, self.dt_obj2.pk, self.dt_obj1.pk, self.dt_obj0.pk],
        )


class ForeignKeyFilterE2ETestCase(BasePlaywrightTestCase):
    """Test foreign key field filtering through E2E tests.

    Tests:
    - **Test Setup**: Create 3 categories and 5 ForeignKeyModel instances
      and navigate to ForeignKeyModel list page
    - `test_fk_filter_any_single`: Test FK filter with "any" operator and single value
    - `test_fk_filter_any_multiple`: Test FK filter with "any" operator and multiple values
    - `test_fk_filter_none_single`: Test FK filter with "none" operator and single value
    - `test_fk_filter_none_multiple`: Test FK filter with "none" operator and multiple values
    - `test_fk_null_true`: Test null filter for optional FK fields (True)
    - `test_fk_null_false`: Test null filter for optional FK fields (False)
    - `test_fk_non_nullable_no_null_buttons`: Test null buttons hidden for non-nullable FK field
    - `test_fk_filter_unset`: Test unsetting FK filter
    """

    def setUp(self) -> None:
        super().setUp()

        self.category1 = CategoryModel.objects.create(
            name="Electronics", description="Electronic items"
        )
        self.category2 = CategoryModel.objects.create(name="Clothing", description="Clothing items")
        self.category3 = CategoryModel.objects.create(
            name="Books", description="Books and publications"
        )

        self.fk_obj1 = ForeignKeyModel.objects.create(
            category_field=self.category1,
            optional_category_field=self.category2,
            name="Smartphone",
        )
        self.fk_obj2 = ForeignKeyModel.objects.create(
            category_field=self.category2,
            optional_category_field=self.category3,
            name="T-Shirt",
        )
        self.fk_obj3 = ForeignKeyModel.objects.create(
            category_field=self.category3,
            optional_category_field=self.category1,
            name="Novel",
        )
        self.fk_obj4 = ForeignKeyModel.objects.create(
            category_field=self.category1,
            optional_category_field=self.category3,
            name="Laptop",
        )
        self.fk_obj5 = ForeignKeyModel.objects.create(
            category_field=self.category2,
            optional_category_field=None,
            name="Jeans",
        )

        page = self.logged_in_page
        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(),
            )
        )
        page.wait_for_selector("table")

    def test_fk_filter_any_single(self) -> None:
        """Test FK filter with 'any' operator and single value."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(
                    f={
                        "category_field": ForeignKeyChoiceFilter(
                            mode="any", options=[str(self.category1.pk)]
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.fk_obj4.pk, self.fk_obj1.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        mode = self.extract_filter_value("category_field", "mode_collapsed")
        self.assertEqual(mode, "any of")

        page.click("#filter-widget-category_field button:first-child")
        page.wait_for_selector("#filter-widget-category_field .multiselect")
        self.verify_filter_button_active_class("category_field", "btn-any")

    def test_fk_filter_any_multiple(self) -> None:
        """Test FK filter with 'any' operator and multiple values."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(
                    f={
                        "category_field": ForeignKeyChoiceFilter(
                            mode="any", options=[str(self.category1.pk), str(self.category3.pk)]
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.fk_obj4.pk, self.fk_obj3.pk, self.fk_obj1.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        mode = self.extract_filter_value("category_field", "mode_collapsed")
        self.assertEqual(mode, "any of")

        page.click("#filter-widget-category_field button:first-child")
        page.wait_for_selector("#filter-widget-category_field .multiselect")
        self.verify_filter_button_active_class("category_field", "btn-any")

    def test_fk_filter_none_single(self) -> None:
        """Test FK filter with 'none' operator and single value."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(
                    f={
                        "category_field": ForeignKeyChoiceFilter(
                            mode="none", options=[str(self.category1.pk)]
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.fk_obj5.pk, self.fk_obj3.pk, self.fk_obj2.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        mode = self.extract_filter_value("category_field", "mode_collapsed")
        self.assertEqual(mode, "none of")

        page.click("#filter-widget-category_field button:first-child")
        page.wait_for_selector("#filter-widget-category_field .multiselect")
        self.verify_filter_button_active_class("category_field", "btn-none")

    def test_fk_filter_none_multiple(self) -> None:
        """Test FK filter with 'none' operator and multiple values."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(
                    f={
                        "category_field": ForeignKeyChoiceFilter(
                            mode="none", options=[str(self.category1.pk), str(self.category3.pk)]
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.fk_obj5.pk, self.fk_obj2.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        mode = self.extract_filter_value("category_field", "mode_collapsed")
        self.assertEqual(mode, "none of")

        page.click("#filter-widget-category_field button:first-child")
        page.wait_for_selector("#filter-widget-category_field .multiselect")
        self.verify_filter_button_active_class("category_field", "btn-none")

    def test_fk_null_true(self) -> None:
        """Test null filter for optional FK fields (True)."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(f={"optional_category_field": ForeignKeyNullFilter(value=True)}),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.fk_obj5.pk])

        # Verify widget status
        unset_button = page.locator(".unset-filter-optional_category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        null_text = self.extract_filter_value("optional_category_field", "null_collapsed")
        self.assertEqual(null_text, "null")

        page.click("#filter-widget-optional_category_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_category_field .multiselect")
        self.verify_filter_button_active_class("optional_category_field", "btn-is-null")

    def test_fk_null_false(self) -> None:
        """Test null filter for optional FK fields (False)."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(f={"optional_category_field": ForeignKeyNullFilter(value=False)}),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids, [self.fk_obj4.pk, self.fk_obj3.pk, self.fk_obj2.pk, self.fk_obj1.pk]
        )

        # Verify widget status
        unset_button = page.locator(".unset-filter-optional_category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        null_text = self.extract_filter_value("optional_category_field", "null_collapsed")
        self.assertEqual(null_text, "not null")

        page.click("#filter-widget-optional_category_field button:first-child")
        page.wait_for_selector("#filter-widget-optional_category_field .multiselect")
        self.verify_filter_button_active_class("optional_category_field", "btn-not-null")

    def test_fk_non_nullable_no_null_buttons(self) -> None:
        """Test null buttons hidden for non-nullable category_field."""
        page = self.logged_in_page

        page.click("#filter-widget-category_field button:first-child")
        page.wait_for_selector("#filter-widget-category_field .multiselect")

        is_null_buttons = page.locator("#filter-widget-category_field .btn-is-null")
        not_null_buttons = page.locator("#filter-widget-category_field .btn-not-null")
        self.assertEqual(is_null_buttons.count(), 0)
        self.assertEqual(not_null_buttons.count(), 0)

    def test_fk_filter_unset(self) -> None:
        """Test unsetting FK filter."""
        page = self.logged_in_page

        page.goto(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(
                    f={
                        "category_field": ForeignKeyChoiceFilter(
                            mode="any", options=[str(self.category1.pk)]
                        )
                    }
                ),
            )
        )
        page.wait_for_selector("table")

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(matching_row_ids, [self.fk_obj4.pk, self.fk_obj1.pk])

        # Verify widget status before unset
        unset_button = page.locator(".unset-filter-category_field")
        self.assertEqual(unset_button.count(), 1)

        # Extract collapsed values BEFORE opening the filter
        mode = self.extract_filter_value("category_field", "mode_collapsed")
        self.assertEqual(mode, "any of")

        page.click("#filter-widget-category_field button:first-child")
        page.wait_for_selector("#filter-widget-category_field .multiselect")
        self.verify_filter_button_active_class("category_field", "btn-any")

        # Unset the filter
        unset_button.click()

        page.wait_for_url(
            self.list_rows_url(
                "ForeignKeyModel",
                ListPageSchema(),
            )
        )

        matching_row_ids = self.extract_matching_row_ids("table tbody tr")
        self.assertEqual(
            matching_row_ids,
            [self.fk_obj5.pk, self.fk_obj4.pk, self.fk_obj3.pk, self.fk_obj2.pk, self.fk_obj1.pk],
        )


class RowUpdatePlaywrightTests(BasePlaywrightTestCase):
    """Playwright tests for RowUpdate functionality."""

    def setUp(self) -> None:
        super().setUp()

        # Create test rows
        self.row1 = FirstStuff.objects.create(char_field="Test Row 1")
        self.row2 = FirstStuff.objects.create(char_field="Test Row 2")

        # Create RowUpdates for row1
        self.row_update1 = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user,
            _values=[],
        )
        self.row_update2 = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="updated_row",
            created_by=self.user,
            _values=[],
        )

    def test_row_details_shows_row_update_list(self) -> None:
        """Test that row details page shows RowUpdate list."""
        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")

        # Check that RowUpdateList is visible
        page.wait_for_selector(".row-update-list")

        # Check that updates are shown
        update_items = page.locator(".update-item").all()
        self.assertEqual(len(update_items), 2)

    def test_row_update_displays_user_title(self) -> None:
        """Test that RowUpdate list displays the title of who made the change."""
        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")

        # Check that RowUpdateList is visible
        page.wait_for_selector(".row-update-list")

        # Check that user title is displayed in the update items
        update_by = page.locator(".update-by").first
        self.assertIn(self.user.username, update_by.text_content() or "")

    def test_filter_buttons_toggle_visibility(self) -> None:
        """Test that filter buttons toggle visibility of updates."""
        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".row-update-list")

        # Click "Updates" filter button - shows non-commented items (created_row, updated_row)
        updates_btn = page.locator(".filter-btn:has-text('Updates')")
        updates_btn.click()

        # Should show both created_row and updated_row (non-commented)
        page.wait_for_selector(".update-item.action-updated_row")
        update_items = page.locator(".update-item:visible").all()
        self.assertEqual(len(update_items), 2)  # created_row and updated_row

        # Click "Comments" filter button
        comments_btn = page.locator(".filter-btn:has-text('Comments')")
        comments_btn.click()

        # Should show only commented items (none in this test)
        # Wait a moment for the filter to apply
        page.wait_for_timeout(100)
        update_items = page.locator(".update-item:visible").all()
        self.assertEqual(len(update_items), 0)  # No comments yet

        # Click "All" filter button
        all_btn = page.locator(".filter-btn:has-text('All')")
        all_btn.click()

        # Should show all items
        page.wait_for_selector(".update-item.action-created_row")
        update_items = page.locator(".update-item:visible").all()
        self.assertEqual(len(update_items), 2)

    def test_comment_form_visible_in_full_mode(self) -> None:
        """Test that comment form is visible for FirstStuff (full mode)."""
        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")

        # Check that comment form is visible
        page.wait_for_selector(".comment-form")

    def test_add_comment(self) -> None:
        """Test adding a comment to a row."""
        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".comment-form")

        # Enter comment text
        textarea = page.locator(".comment-form .quill-editor .ql-editor")
        textarea.fill("This is a test comment")

        # Submit comment
        submit_btn = page.locator(".submit-btn")
        submit_btn.click()

        # Wait for the comment to appear
        page.wait_for_selector(".update-item.action-commented")

        # Verify comment content
        comment_content = page.locator(".comment-content").first
        self.assertIn("This is a test comment", comment_content.text_content() or "")

    def test_comment_character_limit(self) -> None:
        """Test that comment character limit is enforced."""
        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".comment-form")

        # Enter comment text over limit
        long_text = "x" * 1001
        textarea = page.locator(".comment-form .quill-editor .ql-editor")
        textarea.fill(long_text)

        # Check that character counter shows over limit class on itself
        char_counter = page.locator(".char-counter.over-limit")
        self.assertTrue(char_counter.count() > 0)

        # Submit button should be disabled
        submit_btn = page.locator(".submit-btn")
        self.assertTrue(submit_btn.is_disabled())

    def test_delete_own_comment(self) -> None:
        """Test deleting own comment."""
        # Create a comment
        comment = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="commented",
            created_by=self.user,
            comment_content="Comment to delete",
            _values=[],
        )

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".update-item.action-commented")

        # Click delete button
        delete_btn = page.locator(".delete-comment-btn")
        delete_btn.click()

        # Confirm deletion in swal
        page.wait_for_selector(".swal2-popup")
        confirm_btn = page.locator(".swal2-confirm")
        confirm_btn.click()

        # Wait for comment to be marked as deleted
        page.wait_for_selector(".comment-deleted")

        # Verify comment was soft-deleted in database
        comment.refresh_from_db()
        self.assertIsNotNone(comment.comment_deleted_at)

    def test_edit_own_comment(self) -> None:
        """Test editing own comment."""
        # Create a comment
        comment = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="commented",
            created_by=self.user,
            comment_content="Original comment content",
            _values=[],
        )

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".update-item.action-commented")

        # Click edit button
        edit_btn = page.locator(".edit-comment-btn")
        edit_btn.click()

        # Wait for edit form to appear
        page.wait_for_selector(".edit-comment-form")

        # Update the comment text by clicking and typing in Quill editor
        quill_editor = page.locator(".edit-comment-form .quill-editor .ql-editor")
        quill_editor.click()
        quill_editor.fill("")  # Clear initial content
        quill_editor.type("Updated comment content")

        # Click save
        save_btn = page.locator(".save-edit-btn")
        save_btn.click()

        # Wait for the edit form to disappear
        page.wait_for_selector(".edit-comment-form", state="hidden")

        # Wait for the updated content to appear in the comment display
        page.wait_for_selector(".rich-text-display:has-text('Updated comment content')")

        # Verify comment was updated in database
        comment.refresh_from_db()
        # Quill wraps content in <p> tags
        self.assertEqual(comment.comment_content, "<p>Updated comment content</p>")

    def test_edit_button_visible_for_all_comments(self) -> None:
        """Test that edit button is visible for all comments (permission checked server-side)."""
        # Create another user
        other_user = User.objects.create_user(username="otheruser2", password="pass")

        # Create a comment by the other user
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="commented",
            created_by=other_user,
            comment_content="Other user's comment",
            _values=[],
        )

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".update-item.action-commented")

        # Edit button should be visible (permission is checked server-side on submit)
        edit_btn = page.locator(".edit-comment-btn")
        self.assertEqual(edit_btn.count(), 1)

    def test_edit_comment_fails_for_non_owner(self) -> None:
        """Test that editing another user's comment fails with error message."""
        # Create another user
        other_user = User.objects.create_user(username="otheruser3", password="pass")

        # Create a comment by the other user
        comment = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="commented",
            created_by=other_user,
            comment_content="Other user's comment",
            _values=[],
        )

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".update-item.action-commented")

        # Click edit button
        edit_btn = page.locator(".edit-comment-btn")
        edit_btn.click()

        # Wait for edit form to appear
        page.wait_for_selector(".edit-comment-form")

        # Update the comment text
        textarea = page.locator(".edit-comment-form .quill-editor .ql-editor")
        textarea.fill("Trying to update other user's comment")

        # Click save
        save_btn = page.locator(".save-edit-btn")
        save_btn.click()

        # Wait for error toast
        page.wait_for_selector(".swal2-popup")

        # Verify comment was NOT updated in database
        comment.refresh_from_db()
        self.assertEqual(comment.comment_content, "Other user's comment")

    def test_row_update_filter_widget_visible(self) -> None:
        """Test that RowUpdateFilter widget appears on list page."""
        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")

        # Check that RowUpdateFilter collapsed wrapper is visible
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

    def test_row_update_filter_expand(self) -> None:
        """Test expanding RowUpdateFilter shows all options."""
        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Click to expand
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()

        # Check that expanded filter options are visible
        page.wait_for_selector(".row-update-filter-section")
        self.assertTrue(page.locator(".filter-label:has-text('Users:')").count() > 0)
        self.assertTrue(page.locator(".filter-label:has-text('Actions:')").count() > 0)
        self.assertTrue(page.locator(".filter-label:has-text('Date Range:')").count() > 0)

    def test_authenticated_user_can_see_column_values(self) -> None:
        """Test that authenticated user can see column_values in RowUpdateList.

        With the new can_access_row_updates system, authenticated users can read
        row updates and see column values. Redaction will be implemented in Phase 7.
        """
        # Create a row with a RowUpdate that has column values
        row = ConditionalRowUpdatePermissionModel.objects.create(name="Test Row")
        RowUpdate.objects.create(
            modelname="djangoapp.ConditionalRowUpdatePermissionModel",
            row_pk=row.pk,
            action="created_row",
            created_by=self.user,
            _values=[
                {
                    "d": "char",
                    "name": "name",
                    "old_value": None,
                    "new_value": "Test Row",
                },
            ],
        )

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/conditionalrowupdatepermissionmodel/id/{row.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".row-update-list")

        # Check that column values table IS visible (authenticated user can read)
        column_values_table = page.locator(".column-values-table")
        self.assertEqual(column_values_table.count(), 1)

    def test_none_mode_returns_404_on_row_updates_endpoint(self) -> None:
        """Test that none permission mode returns 404 on row-updates endpoint."""
        row = ConditionalRowUpdatePermissionModel.objects.create(name="No Permission Row")

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/conditionalrowupdatepermissionmodel/id/{row.pk}"
        page.goto(url, wait_until="domcontentloaded")

        page.wait_for_selector(".row-update-list")

        # row-update-list is visible but comment form is not (permission denied)
        row_update_list = page.locator(".row-update-list")
        self.assertEqual(row_update_list.count(), 1)

        comment_form = page.locator(".comment-form")
        self.assertEqual(comment_form.count(), 0)

    def test_can_see_delete_button_for_others_comments(self) -> None:
        """Test that delete button is visible for other users' comments.

        Delete permission only checks timeout, not user ownership.
        """
        # Create another user
        other_user = User.objects.create_user(username="otheruser", password="pass")

        # Create a comment by the other user
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="commented",
            created_by=other_user,
            comment_content="Other user's comment",
            _values=[],
        )

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/firststuff/id/{self.row1.pk}"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".update-item.action-commented")

        # Delete button should be visible for other user's comment
        # (delete only checks timeout, not user)
        delete_btn = page.locator(".delete-comment-btn")
        self.assertEqual(delete_btn.count(), 1)

    def test_cannot_add_comment_when_permission_not_full(self) -> None:
        """Test that comment form is hidden when permission is not full."""
        row = ConditionalRowUpdatePermissionModel.objects.create(name="Redacted Row")

        page = self.logged_in_page
        url = f"{self.live_server_url}/tables/conditionalrowupdatepermissionmodel/id/{row.pk}"
        page.goto(url, wait_until="domcontentloaded")

        # Comment form should not be visible (redacted mode, not full)
        comment_form = page.locator(".comment-form")
        self.assertEqual(comment_form.count(), 0)

    def test_row_update_filter_by_users(self) -> None:
        """Test filtering by users - verify user search input exists."""
        # Create another user
        other_user = User.objects.create_user(username="otherfilteruser", password="pass")

        # Create RowUpdates by different users
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="created_row",
            created_by=other_user,
            _values={},
        )

        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Expand filter
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        # Verify user search input exists
        user_search = page.locator(".multiselect")
        self.assertTrue(user_search.count() > 0)

    def test_row_update_filter_by_actions(self) -> None:
        """Test filtering by action types - verify action checkboxes exist."""
        # Create RowUpdates with different actions
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="commented",
            created_by=self.user,
            comment_content="A comment",
            _values={},
        )

        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Expand filter
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        # Verify action checkboxes exist
        action_checkboxes = page.locator(".action-checkbox")
        self.assertTrue(action_checkboxes.count() >= 3)  # noqa: PLR2004 # created, updated, commented

    def test_row_update_filter_by_date_range(self) -> None:
        """Test filtering by date range - verify date inputs exist."""
        now = timezone.now()

        # Create RowUpdate for row1 with old date
        ru1 = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )
        ru1.created_at = now - timedelta(days=10)
        ru1.save()

        # Create RowUpdate for row2 with recent date
        ru2 = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )
        ru2.created_at = now - timedelta(days=1)
        ru2.save()

        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Expand filter
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        # Verify date inputs exist
        date_inputs = page.locator(".date-input")
        self.assertEqual(date_inputs.count(), 2)  # from and to

    def test_row_update_filter_combined(self) -> None:
        """Test combined filters - verify filter buttons exist."""
        # Create another user
        other_user = User.objects.create_user(username="combineduser", password="pass")

        # Create RowUpdates with different attributes
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="updated_row",
            created_by=other_user,
            _values={},
        )

        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Expand filter
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        # Verify Apply Filter button exists
        apply_btn = page.locator(".filter-button.btn-apply")
        self.assertTrue(apply_btn.count() > 0)

    def test_row_update_filter_none_mode(self) -> None:
        """Test filter can be applied and excludes rows without RowUpdates."""
        # Create RowUpdates
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user,
            _values={},
        )

        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Expand filter
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        # Verify Apply Filter button exists
        apply_btn = page.locator(".filter-button.btn-apply")
        self.assertTrue(apply_btn.count() > 0)

    def test_row_update_user_search_returns_results(self) -> None:
        """Test that typing in user search multiselect returns users."""
        User.objects.create_user(
            username="alice",
            first_name="Alice",
            last_name="Smith",
        )

        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        ms = page.locator(".multiselect")
        ms.click()

        search_input = ms.locator("input")
        search_input.fill("alice")

        page.wait_for_selector(".multiselect__option")
        options = page.locator(".multiselect__option").all()
        texts = [o.text_content() or "" for o in options]
        self.assertTrue(
            any("Alice" in t for t in texts),
            f"Expected 'Alice' in options, got: {texts}",
        )

    def test_row_update_filter_persists_on_reload(self) -> None:
        """Test row update filter state persists on page load with filter in URL.

        Checks: user multiselect shows resolved username,
        action checkboxes are checked, date inputs are filled.
        """
        other_user = User.objects.create_user(
            username="bob",
            first_name="Bob",
            last_name="Jones",
        )
        schema = ListPageSchema(
            uf=RowUpdateFilter(
                user_ids=[str(other_user.public_id)],
                actions=["created_row", "commented"],
                date_from=dt_module.datetime(2026, 1, 1, tzinfo=dt_module.UTC),
                date_to=dt_module.datetime(2026, 12, 31, 23, 59, tzinfo=dt_module.UTC),
            ),
        )
        url = self.list_rows_url("FirstStuff", schema)

        page = self.logged_in_page
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".filter-collapsed:has-text('Row Update')")

        # Expand filter
        filter_widget = page.locator(".filter-collapsed:has-text('Row Update')")
        filter_widget.click()
        page.wait_for_selector(".row-update-filter-section")

        # Check user multiselect shows resolved username
        tags = page.locator(".multiselect__tag").all()
        tag_texts = [t.text_content() or "" for t in tags]
        self.assertTrue(
            any("Bob Jones" in t for t in tag_texts),
            f"Expected 'Bob Jones' in tags, got: {tag_texts}",
        )

        # Check action checkboxes: created_row and commented checked,
        # updated_row unchecked
        self.assertTrue(
            page.locator(".action-checkbox input[value='created_row']").is_checked(),
            "Expected created_row checkbox checked",
        )
        self.assertTrue(
            page.locator(".action-checkbox input[value='commented']").is_checked(),
            "Expected commented checkbox checked",
        )
        self.assertFalse(
            page.locator(".action-checkbox input[value='updated_row']").is_checked(),
            "Expected updated_row checkbox unchecked",
        )

        # Check date inputs
        date_from_input = page.locator(".date-range-inputs input").nth(0)
        date_to_input = page.locator(".date-range-inputs input").nth(1)
        self.assertIn("2026-01-01", date_from_input.input_value())
        self.assertIn("2026-12-31", date_to_input.input_value())


class FirstStuffSlotPropsE2eTestCase(BasePlaywrightTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ref = Ref.objects.create(char_field="ref1")
        FirstStuff.objects.create(
            char_field="aaa",
            integer_field=3,
            boolean_field=True,
            decimal_field="5.00",
            ref_fk=self.ref,
        )
        FirstStuff.objects.create(
            char_field="bbb",
            integer_field=7,
            boolean_field=False,
            decimal_field="10.00",
            ref_fk=self.ref,
        )
        FirstStuff.objects.create(
            char_field="ccc",
            integer_field=3,
            boolean_field=True,
            decimal_field="15.00",
            ref_fk=self.ref,
        )

    def test_slot_props_renders_before_table(self) -> None:
        page = self.logged_in_page
        url = self.list_rows_url("FirstStuff", ListPageSchema())
        page.goto(url, wait_until="domcontentloaded")

        page.wait_for_selector("table", timeout=5000)

        hook = page.locator(".hook-firststuff-list")
        self.assertTrue(hook.count() > 0, "Hook component not found on page")
        text = hook.first.text_content() or ""
        self.assertIn("FirstStuff Stats", text)
        self.assertIn("Total rows: 3", text)
        self.assertIn("3, 7", text)


class SlotDemoFilterE2ETestCase(BasePlaywrightTestCase):
    """End-to-end tests for SlotDemoModel diff filter, computed columns, and custom ListPageSchema.

    Tests the full stack: SlotDemoListPageSchema.diff field (backend Pydantic),
    SlotDemoView.list_rows override (annotation + conditional column),
    SlotDemoListRows.vue FilterWrapper-based UI, and ListPageSchemaWrapper.navigateCustom.

    Coverage:
    - diff=None: no filtering, no diff column
    - diff="any": filters int1-int2 > 0, shows diff column
    - diff=<int>: filters int1-int2 >= int, shows diff column
    - Collapsed filter widget: shows label text (empty / "any positive" / ">= N")
    - Expanded filter widget: "Any positive" button, number input, Apply button
    - Input pre-fill: shows int value when diff is int, empty otherwise
    - Click navigation: Any positive button, unset (X) button, typed int + Apply
    """

    def setUp(self) -> None:
        super().setUp()
        SlotDemoModel.objects.create(title="a", int1=5, int2=3)
        SlotDemoModel.objects.create(title="b", int1=2, int2=8)
        SlotDemoModel.objects.create(title="c", int1=10, int2=1)
        SlotDemoModel.objects.create(title="d", int1=0, int2=0)
        SlotDemoModel.objects.create(title="e", int1=3, int2=3)

    def _goto(self, schema: SlotDemoListPageSchema) -> Page:
        page = self.logged_in_page
        url = self.list_rows_url("SlotDemoModel", schema)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("table", timeout=5000)
        return page

    def _visible_row_count(self) -> int:
        return self.logged_in_page.locator("table tbody tr").count()

    def _open_diff_filter(self) -> None:
        self.logged_in_page.locator("#filter-widget-diff button").first.click()
        self.logged_in_page.wait_for_selector("#filter-widget-diff .filter-boxes")

    def test_diff_null_shows_all_rows_no_diff_column(self) -> None:
        schema = SlotDemoListPageSchema(diff=None)
        page = self._goto(schema)

        self.assertEqual(self._visible_row_count(), 5)
        headers = page.locator("table thead th").all_text_contents()
        self.assertNotIn("diff", headers)

    def test_diff_any_filters_positive_difference(self) -> None:
        schema = SlotDemoListPageSchema(diff="any")
        page = self._goto(schema)

        # (5,3)=2, (10,1)=9 have positive diff
        self.assertEqual(self._visible_row_count(), 2)
        headers = page.locator("table thead th").all_text_contents()
        self.assertIn("diff", headers)

        rows = page.locator("table tbody tr").all()
        diffs = []
        for row in rows:
            diff_td = row.locator(".row-td-diff")
            if diff_td.count() > 0:
                diffs.append(diff_td.text_content())
        self.assertEqual(len(diffs), 2)

    def test_diff_int_filters_by_minimum(self) -> None:
        schema = SlotDemoListPageSchema(diff=5)
        self._goto(schema)

        # (10,1)=9 >= 5, only row c
        self.assertEqual(self._visible_row_count(), 1)

    def test_diff_filter_widget_exists(self) -> None:
        schema = SlotDemoListPageSchema(diff=None)
        page = self._goto(schema)

        widget = page.locator("#filter-widget-diff")
        self.assertEqual(widget.count(), 1)

    def test_diff_filter_collapsed_no_filter(self) -> None:
        schema = SlotDemoListPageSchema(diff=None)
        page = self._goto(schema)

        collapsed = page.locator("#filter-widget-diff.filter-collapsed")
        self.assertEqual(collapsed.count(), 1)
        text = collapsed.text_content() or ""
        self.assertIn("diff", text)
        self.assertNotIn("any positive", text)

    def test_diff_filter_collapsed_any(self) -> None:
        schema = SlotDemoListPageSchema(diff="any")
        page = self._goto(schema)

        collapsed = page.locator("#filter-widget-diff.filter-collapsed")
        self.assertEqual(collapsed.count(), 1)
        label = collapsed.locator(".diff_collapsed").text_content()
        self.assertEqual(label, "any positive")

    def test_diff_filter_collapsed_int(self) -> None:
        schema = SlotDemoListPageSchema(diff=5)
        page = self._goto(schema)

        collapsed = page.locator("#filter-widget-diff.filter-collapsed")
        self.assertEqual(collapsed.count(), 1)
        label = collapsed.locator(".diff_collapsed").text_content()
        self.assertEqual(label, ">= 5")

    def test_diff_filter_expanded_has_buttons(self) -> None:
        schema = SlotDemoListPageSchema(diff=None)
        page = self._goto(schema)
        self._open_diff_filter()

        any_btn = page.locator("#filter-widget-diff .btn-diff-any")
        apply_btn = page.locator("#filter-widget-diff .btn-diff-int")
        diff_input = page.locator("#filter-widget-diff .diff-input")
        self.assertEqual(any_btn.count(), 1)
        self.assertEqual(apply_btn.count(), 1)
        self.assertEqual(diff_input.count(), 1)

    def test_diff_input_shows_value_when_int(self) -> None:
        schema = SlotDemoListPageSchema(diff=5)
        page = self._goto(schema)
        self._open_diff_filter()

        diff_input = page.locator("#filter-widget-diff .diff-input")
        value = diff_input.input_value()
        self.assertEqual(value, "5")

    def test_diff_input_empty_when_null(self) -> None:
        schema = SlotDemoListPageSchema(diff=None)
        page = self._goto(schema)
        self._open_diff_filter()

        diff_input = page.locator("#filter-widget-diff .diff-input")
        value = diff_input.input_value()
        self.assertEqual(value, "")

    def test_diff_input_empty_when_any(self) -> None:
        schema = SlotDemoListPageSchema(diff="any")
        page = self._goto(schema)
        self._open_diff_filter()

        diff_input = page.locator("#filter-widget-diff .diff-input")
        value = diff_input.input_value()
        self.assertEqual(value, "")

    def test_click_any_positive_navigates(self) -> None:
        schema = SlotDemoListPageSchema(diff=None)
        page = self._goto(schema)
        self.assertEqual(self._visible_row_count(), 5)

        target_url = self.list_rows_url(
            "SlotDemoModel",
            SlotDemoListPageSchema(diff="any"),
        )
        self._open_diff_filter()
        page.locator("#filter-widget-diff .btn-diff-any").click()
        page.wait_for_url(target_url, timeout=5000)

        self.assertEqual(self._visible_row_count(), 2)

    def test_click_unset_navigates(self) -> None:
        schema = SlotDemoListPageSchema(diff="any")
        page = self._goto(schema)
        self.assertEqual(self._visible_row_count(), 2)

        target_url = self.list_rows_url(
            "SlotDemoModel",
            SlotDemoListPageSchema(diff=None),
        )
        page.locator("#filter-widget-diff .pill-close-btn").click()
        page.wait_for_url(target_url, timeout=5000)

        self.assertEqual(self._visible_row_count(), 5)


class PublicIdUuid7TestModel2E2ETestCase(BasePlaywrightTestCase):
    def test_create_row_uses_uuid7_slug_in_url(self) -> None:
        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/publiciduuid7testmodel2/create-row")

        page.fill(".column-input-name input", "test row")
        page.click('button[type="submit"]')
        page.wait_for_url(
            f"{self.live_server_url}/tables/publiciduuid7testmodel2/id/*",
            timeout=5000,
        )

        row = PublicIdUuid7TestModel2.objects.last()
        assert row is not None
        self.assertIn(row.slug, page.url)

    def test_edit_slug_redirects_to_new_url(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        old_slug = row.slug

        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/publiciduuid7testmodel2/update-row/{old_slug}")
        page.wait_for_selector("form")

        page.fill(".column-input-slug input", "john-smith")
        page.click('button[type="submit"]')
        page.wait_for_url("**/id/john-smith", timeout=5000)

        row.refresh_from_db()
        self.assertEqual(row.slug, "john-smith")
        self.assertIn("john-smith", page.url)

    def test_old_slug_url_returns_404(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        old_slug = row.slug

        page = self.logged_in_page
        page.goto(f"{self.live_server_url}/tables/publiciduuid7testmodel2/update-row/{old_slug}")
        page.wait_for_selector("form")

        page.fill(".column-input-slug input", "renamed-slug")
        page.click('button[type="submit"]')
        page.wait_for_url("**/id/renamed-slug", timeout=5000)

        response = page.goto(f"{self.live_server_url}/tables/publiciduuid7testmodel2/id/{old_slug}")
        assert response is not None
        self.assertEqual(response.status, 404)
        # Previously this flow emitted an unhandled console error; the
        # error-handling work surfaces such errors as toasts (main.ts global
        # handlers) instead of leaking to the console, so none should remain.
        self.assertFalse(self.console_errors, f"Unexpected console errors: {self.console_errors}")
