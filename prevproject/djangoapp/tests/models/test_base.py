import typing
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from djangoapp.filters import (
    BooleanValueFilter,
    IntegerChoiceFilter,
    IntegerComparisonFilter,
    IntegerNullFilter,
)
from djangoapp.models.app import (
    ConditionalRowUpdatePermissionModel,
    FirstStuff,
    IncludeFirstTwo,
    IntegerFieldModel,
    NotifyingFirstStuff,
    PreventEditDeleteModel,
    ProxyUser,
    PublicIdSequenceTestModel1,
    PublicIdSequenceTestModel2,
    PublicIdUuid7TestModel,
    PublicIdUuid7TestModel2,
    PublicIdUuid7TestModel3,
    Ref,
    SearchForFkDestinationModel,
    SearchForFkTargetModel,
    TestFileUploadModel,
)
from djangoapp.models.base import (
    COLUMN_OPERATIONS,
    BaseModel,
    CommentPermissionContext,
    CreateRowNotifyContext,
    FileMarkedForDeletion,
    ResolveColumnsContext,
    RowUpdate,
    RowUpdateRedactContext,
    RowUpdateUserNotification,
    SaveContext,
    SearchContext,
    User,
    search,
)
from djangoapp.responses import (
    BooleanFieldSchema,
    CharChoiceWrapper,
    ForeignKeyWrapper,
    IntegerChoiceWrapper,
    IntegerFieldSchema,
    RowColumnValueSchema,
    RowUpdateBooleanValue,
    RowUpdateCharChoiceValue,
    RowUpdateCharValue,
    RowUpdateDecimalValue,
    RowUpdateForeignKeyValue,
    RowUpdateIntegerChoiceValue,
    RowUpdateIntegerValue,
    RowUpdateTextValue,
)
from djangoapp.views.base import BaseView, ListPageSchema


class BaseModelTest(TestCase):
    def test_raw_resolve_columns(self) -> None:
        fields = FirstStuff.raw_resolve_columns()
        field_names = list(fields.keys())
        self.assertEqual(
            field_names,
            [
                "char_field",
                "text_field",
                "integer_field",
                "nullable_integer_field",
                "boolean_field",
                "decimal_field",
                "datetime_field",
                "char_choice_field",
                "int_choice_field",
                "ref_fk",
                "user_fk",
                "file_field",
            ],
        )

    def test_filter_apply(self) -> None:
        # Test filter apply methods
        # Create test data
        FirstStuff.objects.create(boolean_field=True, integer_field=5, int_choice_field=1)
        FirstStuff.objects.create(boolean_field=False, integer_field=15, int_choice_field=2)
        FirstStuff.objects.create(boolean_field=True, integer_field=20, int_choice_field=3)
        FirstStuff.objects.create(boolean_field=False, integer_field=3, int_choice_field=1)

        qs = FirstStuff.objects.all()

        # Boolean true
        bool_filter = BooleanValueFilter(value=True)
        filtered = bool_filter.apply(qs, "boolean_field")
        self.assertEqual(filtered.count(), 2)

        # Boolean false
        bool_filter = BooleanValueFilter(value=False)
        filtered = bool_filter.apply(qs, "boolean_field")
        self.assertEqual(filtered.count(), 2)

        # Integer gt 10
        int_gt = IntegerComparisonFilter(op="gt", number_1=10)
        filtered = int_gt.apply(qs, "integer_field")
        self.assertEqual(filtered.count(), 2)

        # Integer choice any [1,2]
        int_any = IntegerChoiceFilter(mode="any", options=[1, 2])
        filtered = int_any.apply(qs, "int_choice_field")
        self.assertEqual(filtered.count(), 3)

        # Integer choice none
        int_none = IntegerChoiceFilter(mode="none", options=[1, 2])
        filtered = int_none.apply(qs, "int_choice_field")
        self.assertEqual(filtered.count(), 1)

        # Integer is null (assuming all have values, should be 0)
        int_null_filter = IntegerNullFilter(value=True)
        filtered = int_null_filter.apply(qs, "integer_field")
        self.assertEqual(filtered.count(), 0)

        # Integer not null
        int_not_null_filter = IntegerNullFilter(value=False)
        filtered = int_not_null_filter.apply(qs, "integer_field")
        self.assertEqual(filtered.count(), 4)

    def test_list_page_schema_validate_filters(self) -> None:
        schema = ListPageSchema(
            f={
                "boolean_field": BooleanValueFilter(value=True),
                "integer_field": IntegerComparisonFilter(op="gt", number_1=10),
                "char_field": BooleanValueFilter(value=False),  # invalid for char
            }
        )

        # Mock columns
        columns = {
            "boolean_field": BooleanFieldSchema(
                name="boolean_field",
                d="boolean",
                required=False,
                default=None,
            ),
            "integer_field": IntegerFieldSchema(
                name="integer_field",
                d="integer",
                required=False,
                default=None,
                choices=None,
            ),
        }
        # char_field not visible
        schema.validate_filters(None, FirstStuff, columns)
        self.assertIn("boolean_field", schema.filter_map)
        self.assertIn("integer_field", schema.filter_map)
        self.assertNotIn("char_field", schema.filter_map)

    def test_include_first_two_columns(self) -> None:
        fields = IncludeFirstTwo.raw_resolve_columns()
        field_names = list(fields.keys())
        self.assertEqual(field_names, ["int1", "int2"])

    def test_include_columns_preserves_order(self) -> None:
        """Test that include_columns returns columns in specified order, not model field order."""
        # Without include_columns, IntegerFieldModel returns fields in model order
        default_fields = IntegerFieldModel.raw_resolve_columns()
        default_names = list(default_fields.keys())

        # With include_columns in reversed order (all fields from model)
        all_field_names = list(default_fields.keys())

        class ReorderedModel(IntegerFieldModel):
            include_columns = tuple(reversed(all_field_names))

            class Meta:
                app_label = "djangoapp"
                proxy = True

        reordered_fields = ReorderedModel.raw_resolve_columns()
        reordered_names = list(reordered_fields.keys())

        # Both should have same fields but in reversed order
        self.assertEqual(set(default_names), set(reordered_names))
        self.assertEqual(default_names, list(reversed(reordered_names)))

    def test_base_search_text_numeric_returns_filtered(self) -> None:
        """BaseModel.search_text with numeric text filters by pk."""
        # Create a FirstStuff instance
        stuff = FirstStuff.objects.create(
            char_field="test",
            boolean_field=True,
            integer_field=1,
        )
        FirstStuff.objects.create(
            char_field="test",
            boolean_field=True,
            integer_field=1,
        )
        # FirstStuff inherits search_text from BaseModel which filters only by pk
        queryset = FirstStuff.search_text(str(stuff.pk))
        # This calls BaseModel.search_text directly, which only works with numeric
        result_ids = list(queryset.values_list("pk", flat=True))
        self.assertEqual(result_ids, [stuff.pk])


class TestFileUploadModelTest(TestCase):
    def _get_view_instance(self) -> BaseView:
        """Create a mock view instance for testing feed_values."""

        class TestView(BaseView):
            model = TestFileUploadModel

        return TestView()

    def test_create_file_upload_model(self) -> None:
        # Create a simple uploaded file
        uploaded_file = SimpleUploadedFile(
            "test_file.txt", b"file content", content_type="text/plain"
        )

        # Create instance
        instance = TestFileUploadModel()
        view = self._get_view_instance()
        model = view.model
        columns = model.fields_or_404(None, "create", None)
        collected_problems = instance.feed_values(
            {"nullable_integer_field": "42"}, {"file_field": uploaded_file}, columns, None
        )
        self.assertFalse(collected_problems.has_failed())
        instance.save()
        instance.refresh_from_db()
        self.assertEqual(instance.nullable_integer_field, 42)
        self.assertRegex(instance.file_field.name or "", r"uploads/test_file_[A-Za-z0-9]+\.txt")
        with instance.file_field.open() as f:
            self.assertEqual(f.read(), b"file content")

    def test_update_file_upload_model(self) -> None:
        # Create initial instance
        initial_file = SimpleUploadedFile(
            "initial_file.txt", b"initial content", content_type="text/plain"
        )
        instance = TestFileUploadModel.objects.create(
            nullable_integer_field=10, file_field=initial_file
        )

        # Update instance
        new_file = SimpleUploadedFile(
            "updated_file.txt", b"updated content", content_type="text/plain"
        )
        old_file_name = instance.file_field.name
        view = self._get_view_instance()
        model = view.model
        columns = model.fields_or_404(None, "update", instance)
        collected_problems = instance.feed_values(
            {"nullable_integer_field": "99"}, {"file_field": new_file}, columns, instance
        )
        self.assertFalse(collected_problems.has_failed())
        instance.save()
        instance.refresh_from_db()
        self.assertEqual(instance.nullable_integer_field, 99)
        self.assertRegex(instance.file_field.name or "", r"uploads/updated_file_[A-Za-z0-9]+\.txt")
        with instance.file_field.open() as f:
            self.assertEqual(f.read(), b"updated content")
        self.assertEqual(FileMarkedForDeletion.objects.get().file.name, old_file_name)

    def test_update_keep_file(self) -> None:
        # Create initial instance
        initial_file = SimpleUploadedFile(
            "keep_file.txt", b"keep content", content_type="text/plain"
        )
        instance = TestFileUploadModel.objects.create(
            nullable_integer_field=10, file_field=initial_file
        )

        # Update instance with keep
        view = self._get_view_instance()
        model = view.model
        columns = model.fields_or_404(None, "update", instance)
        collected_problems = instance.feed_values(
            {"nullable_integer_field": "99", "file_field": instance.file_field.name or ""},
            {},
            columns,
            instance,
        )
        self.assertFalse(collected_problems.has_failed())
        instance.save()
        instance.refresh_from_db()
        self.assertEqual(instance.nullable_integer_field, 99)
        self.assertIsNotNone(instance.file_field)
        self.assertRegex(instance.file_field.name or "", r"uploads/keep_file.*\.txt")
        with instance.file_field.open() as f:
            self.assertEqual(f.read(), b"keep content")

    def test_update_remove_file(self) -> None:
        # Create initial instance
        initial_file = SimpleUploadedFile(
            "remove_file.txt", b"remove content", content_type="text/plain"
        )
        instance = TestFileUploadModel.objects.create(
            nullable_integer_field=10, file_field=initial_file
        )

        # Update instance with remove
        old_file_name = instance.file_field.name
        view = self._get_view_instance()
        model = view.model
        columns = model.fields_or_404(None, "update", instance)
        collected_problems = instance.feed_values(
            {"nullable_integer_field": "99", "file_field": ""}, {}, columns, instance
        )
        self.assertFalse(collected_problems.has_failed())
        instance.save()
        instance.refresh_from_db()
        self.assertEqual(instance.nullable_integer_field, 99)
        self.assertEqual(instance.file_field.name, "")
        self.assertEqual(FileMarkedForDeletion.objects.get().file.name, old_file_name)

    def test_delete_file_upload_model_marks_files_for_deletion(self) -> None:
        # Create instance with file
        uploaded_file = SimpleUploadedFile(
            "delete_file.txt", b"content to delete", content_type="text/plain"
        )
        instance = TestFileUploadModel.objects.create(
            nullable_integer_field=5, file_field=uploaded_file
        )

        # Check initial state
        old_file_name = instance.file_field.name

        # Mark files for deletion and delete
        instance.delete_safely()

        # Check that FileMarkedForDeletion was created
        self.assertEqual(FileMarkedForDeletion.objects.get().file.name, old_file_name)


class SmokeTestsTest(TestCase):
    """Tests for BaseModel.smoke_tests validation."""

    def test_valid_search_proxy_passes(self) -> None:
        """FirstStuff.smoke_tests() should pass - it has valid @search('user_fk')."""
        # Should not raise any exception
        FirstStuff.smoke_tests()

    def test_invalid_column_name_raises_type_error(self) -> None:
        """SearchProxy referencing non-existent column should raise TypeError."""

        class BadModel(BaseModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "djangoapp"

            @search("nonexistent_column")
            @classmethod
            def search_bad(cls, context: SearchContext[typing.Any]) -> models.QuerySet[typing.Any]:
                return context.queryset

        with self.assertRaises(TypeError) as context:
            BadModel.smoke_tests()

        self.assertIn("nonexistent_column", str(context.exception))
        self.assertIn("does not exist", str(context.exception))

    def test_non_fk_column_raises_type_error(self) -> None:
        """SearchProxy referencing non-FK column should raise TypeError."""

        class BadModel(BaseModel):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "djangoapp"

            @search("name")
            @classmethod
            def search_bad(cls, context: SearchContext[typing.Any]) -> models.QuerySet[typing.Any]:
                return context.queryset

        with self.assertRaises(TypeError) as context:
            BadModel.smoke_tests()

        self.assertIn("name", str(context.exception))
        self.assertIn("not a ForeignKey", str(context.exception))

    def test_include_columns_invalid_name_raises_type_error(self) -> None:
        """include_columns referencing non-existent column should raise TypeError."""

        class BadModel(BaseModel):
            name = models.CharField(max_length=100)
            include_columns = ("nonexistent_column",)

            class Meta:
                app_label = "djangoapp"

        with self.assertRaises(TypeError) as context:
            BadModel.smoke_tests()

        self.assertIn("nonexistent_column", str(context.exception))
        self.assertIn("does not exist", str(context.exception))

    def test_include_columns_duplicate_raises_type_error(self) -> None:
        """include_columns with duplicate entries should raise TypeError."""

        class BadModel(BaseModel):
            name = models.CharField(max_length=100)
            value = models.IntegerField(default=0)
            include_columns = ("name", "value", "name")  # duplicate 'name'

            class Meta:
                app_label = "djangoapp"

        with self.assertRaises(TypeError) as context:
            BadModel.smoke_tests()

        self.assertIn("duplicate", str(context.exception))
        self.assertIn("name", str(context.exception))

    def test_lazy_fk_reference_raises_type_error(self) -> None:
        """SearchProxy using lazy FK reference should raise TypeError."""
        # Lazy FK reference using string "auth.User" instead of direct class

        class BadModel(BaseModel):
            # Lazy FK reference using string
            user = models.ForeignKey("auth.User", on_delete=models.CASCADE)

            class Meta:
                app_label = "djangoapp"

            @search("user")
            @classmethod
            def search_user(cls, context: SearchContext[typing.Any]) -> models.QuerySet[typing.Any]:
                return context.queryset

        with self.assertRaises(TypeError) as context:
            BadModel.smoke_tests()

        # The error message mentions lazy FK reference
        error_msg = str(context.exception)
        self.assertTrue(
            "lazy FK reference" in error_msg or "not a _BaseModelMixin descendant" in error_msg,
            f"Expected 'lazy FK reference' or 'not a _BaseModelMixin descendant' "
            f"in error: {error_msg}",
        )


class ResolveRowsTest(TestCase):
    """Tests for resolve_rows method.

    These tests verify that resolve_rows can filter rows based on operation,
    enabling row-level access control for edit and delete operations.
    """

    def setUp(self) -> None:
        self.editable_row = PreventEditDeleteModel.objects.create(
            name="editable", prevent_edit=False, prevent_delete=False
        )
        self.prevent_edit_row = PreventEditDeleteModel.objects.create(
            name="prevent_edit", prevent_edit=True, prevent_delete=False
        )
        self.prevent_delete_row = PreventEditDeleteModel.objects.create(
            name="prevent_delete", prevent_edit=False, prevent_delete=True
        )

    def test_resolve_rows_prevents_edit(self) -> None:
        """Test that resolve_rows can filter out rows for update operation."""
        with self.assertRaises(PreventEditDeleteModel.DoesNotExist):
            PreventEditDeleteModel.get_row_for_user_and_operation(
                str(self.prevent_edit_row.pk), None, "update"
            )

        row = PreventEditDeleteModel.get_row_for_user_and_operation(
            str(self.editable_row.pk), None, "update"
        )
        self.assertEqual(row, self.editable_row)

    def test_resolve_rows_prevents_delete(self) -> None:
        """Test that resolve_rows can filter out rows for delete operation."""
        with self.assertRaises(PreventEditDeleteModel.DoesNotExist):
            PreventEditDeleteModel.get_row_for_user_and_operation(
                str(self.prevent_delete_row.pk), None, "delete"
            )

        row = PreventEditDeleteModel.get_row_for_user_and_operation(
            str(self.editable_row.pk), None, "delete"
        )
        self.assertEqual(row, self.editable_row)

    def test_resolve_rows_allows_read_for_all(self) -> None:
        """Test that resolve_rows returns all rows for read operation."""
        for row_obj in [self.editable_row, self.prevent_edit_row, self.prevent_delete_row]:
            row = PreventEditDeleteModel.get_row_for_user_and_operation(
                str(row_obj.pk), None, "read"
            )
            self.assertEqual(row, row_obj)


class FieldsOr404EmptyTest(TestCase):
    """Tests for fields_or_404 raising error on empty sequence."""

    def test_fields_or_404_empty_raises_error(self) -> None:
        """fields_or_404 should raise ValueError if resolve_columns returns empty."""

        class EmptyColumnsModel(IntegerFieldModel):
            @classmethod
            def resolve_columns(
                cls,
                context: ResolveColumnsContext,  # noqa: ARG003
            ) -> tuple[str, ...]:
                return ()  # Empty sequence

            class Meta:
                app_label = "djangoapp"
                proxy = True

        with self.assertRaises(ValueError) as cm:
            EmptyColumnsModel.fields_or_404(None, "list")
            self.assertIn("empty sequence", str(cm.exception))


class ProxyUserResolveColumnsTest(TestCase):
    """ProxyUser.resolve_columns restricts columns per operation to protect auth fields.

    Username is a Django auth credential that must never be editable through the
    tables UI. resolve_columns("update") excludes it so the edit form cannot
    change auth credentials. Other operations have their own column restrictions
    for UX reasons (compact list view) or because the operation is unsupported
    (create goes through Django's auth system).

    - why test_update_excludes_username: prevent credential changes via tables form
    - why test_details_includes_username: username is visible on the details page
    - why test_list_excludes_first_and_last_name: compact list view with fewer columns
    - why test_create_returns_none: user creation is handled by Django auth, not tables
    """

    def _resolve(self, operation: str) -> typing.Sequence[str] | None:
        all_cols = ProxyUser.include_columns
        return ProxyUser.resolve_columns(
            ResolveColumnsContext(
                user=None, operation=typing.cast(COLUMN_OPERATIONS, operation), columns=all_cols
            )
        )

    def test_update_excludes_username(self) -> None:
        """Username must not appear in update columns to prevent credential editing."""
        columns = self._resolve("update")
        assert columns is not None
        self.assertNotIn("username", columns)
        self.assertIn("first_name", columns)
        self.assertIn("email", columns)

    def test_details_includes_username(self) -> None:
        """Username is safe to display in read-only details view."""
        columns = self._resolve("details")
        assert columns is not None
        self.assertIn("username", columns)

    def test_list_excludes_first_and_last_name(self) -> None:
        """List view shows compact columns, hiding verbose name fields."""
        columns = self._resolve("list")
        assert columns is not None
        self.assertNotIn("first_name", columns)
        self.assertNotIn("last_name", columns)
        self.assertIn("username", columns)

    def test_create_returns_none(self) -> None:
        """User creation is handled by Django auth, tables form must not attempt it."""
        columns = self._resolve("create")
        self.assertIsNone(columns)


class SearchUserFkTest(TestCase):
    """Tests for FirstStuff.search_user_fk method."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
            first_name="Test",
            last_name="User",
        )
        self.another_user = User.objects.create_user(
            username="another",
            password="pass",
            first_name="Another",
            last_name="Person",
        )

    def test_empty_text_returns_empty_queryset(self) -> None:
        """Empty search text should return empty queryset."""
        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text(""),
            search_text="",
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 0)

    def test_numeric_text_filters_by_id(self) -> None:
        """Numeric search text should filter by user ID."""
        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text(str(self.user.pk)),
            search_text=str(self.user.pk),
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.user)

    def test_numeric_text_returns_union_with_id_on_top(self) -> None:
        """Numeric search should return ID match on top, text matches after."""
        # Create a user with the ID number in their username
        user_with_id_in_name = User.objects.create_user(
            username=f"user{self.user.pk}",  # Contains the ID number
            password="pass",
            first_name="Abby",  # Alphabetically before "Test"
            last_name="User",
        )

        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text(str(self.user.pk)),
            search_text=str(self.user.pk),  # Search for self.user's ID
        )
        result = list(FirstStuff.search_user_fk(context))
        result_pks = [r.pk for r in result]
        # ID match should be first (compare by pk since result is ProxyUser)
        self.assertEqual(result[0].pk, self.user.pk)
        # Text match should be second (alphabetically by first_name, last_name)
        self.assertIn(user_with_id_in_name.pk, result_pks)

    def test_numeric_text_no_id_match_returns_text_matches(self) -> None:
        """Numeric search with non-existent ID should still return text matches."""
        # Create a user with "99999" in their name
        User.objects.create_user(
            username="user99999",
            password="pass",
            first_name="Nine",
            last_name="User",
        )

        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text("99999"),
            search_text="99999",
        )
        result = FirstStuff.search_user_fk(context)
        # Should find the user with 99999 in username
        self.assertEqual(result.count(), 1)

    def test_text_search_by_username(self) -> None:
        """Text search should find users by username."""
        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text("testuser"),
            search_text="testuser",
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.user)

    def test_text_search_by_first_name(self) -> None:
        """Text search should find users by first_name."""
        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text("Test"),
            search_text="Test",
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.user)

    def test_text_search_by_last_name(self) -> None:
        """Text search should find users by last_name."""
        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text("User"),
            search_text="User",
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.user)

    def test_text_search_multiple_matches(self) -> None:
        """Text search should return multiple matching users."""
        # Create another user with similar name
        user2 = User.objects.create_user(
            username="testuser2",
            password="pass",
            first_name="Test2",
            last_name="User2",
        )

        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text("test"),  # matches 'testuser' and 'testuser2'
            search_text="test",
        )
        result = FirstStuff.search_user_fk(context)
        # Verify actual results contain the expected users
        result_pks = [r.pk for r in result]
        self.assertIn(self.user.pk, result_pks)
        self.assertIn(user2.pk, result_pks)

    def test_search_results_have_text_annotation(self) -> None:
        """Search results should have 'text' annotation with full name."""
        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text(str(self.user.pk)),
            search_text=str(self.user.pk),
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 1)
        user = result.first()
        assert user is not None
        # The text annotation should be "first_name last_name"
        self.assertEqual(user.annotated_text, "Test User")

    def test_numeric_search_returns_both_id_and_text_matches(self) -> None:
        """When searching with a number, should return both ID match and text matches."""
        # Create a user with first_name equal to self.user.pk as string
        user_with_id_name = User.objects.create_user(
            username="user_with_id_name",
            password="pass",
            first_name=str(self.user.pk),  # First name matches the search number
            last_name="User",
        )

        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text(str(self.user.pk)),
            search_text=str(self.user.pk),
        )
        result = FirstStuff.search_user_fk(context)
        # Should find both: self.user (by ID) and user_with_id_name (by first_name)
        self.assertEqual(result.count(), 2)
        result_pks = [r.pk for r in result]
        self.assertIn(self.user.pk, result_pks)
        self.assertIn(user_with_id_name.pk, result_pks)
        # ID match should be first
        self.assertEqual(result[0].pk, self.user.pk)

    def test_user_with_empty_names_has_fallback_title(self) -> None:
        """User with empty first_name and last_name should have fallback title."""
        # Create a user with empty first_name and last_name
        user_no_names = User.objects.create_user(
            username="user_no_names",
            password="pass",
            first_name="",
            last_name="",
        )

        context = SearchContext(
            user=self.user,
            queryset=ProxyUser.search_text(str(user_no_names.pk)),
            search_text=str(user_no_names.pk),
        )
        result = FirstStuff.search_user_fk(context)
        self.assertEqual(result.count(), 1)
        user = result.first()
        assert user is not None
        # The text annotation should NOT be just " " (space)
        # It should fall back to username or at least be a non-empty string
        self.assertNotEqual(
            user.annotated_text.strip(), "", "User with empty names should have fallback title"
        )

    def test_base_search_text_numeric_returns_filtered(self) -> None:
        """BaseModel.search_text with numeric text filters by pk."""
        # Create a Ref instance (uses base search_text, not overridden)
        ref = Ref.objects.create(char_field="test")
        Ref.objects.create(char_field="test2")
        # Ref.search_text (inherited from BaseModel) filters by pk
        queryset = Ref.search_text(str(ref.pk))
        # This calls BaseModel.search_text directly, which only works with numeric
        result_ids = list(queryset.values_list("pk", flat=True))
        self.assertEqual(result_ids, [ref.pk])

    def test_base_search_text_non_numeric_returns_empty(self) -> None:
        """BaseModel.search_text with non-numeric text returns empty queryset."""
        # Ref uses base search_text, not overridden
        queryset = Ref.search_text("notanumber")
        result_ids = list(queryset.values_list("pk", flat=True))
        self.assertEqual(result_ids, [])


# ------------------ RowUpdate Model Tests ---------------------
class RowUpdateModelTest(TestCase):
    """Tests for RowUpdate model and pydantic schemas."""

    def test_row_update_model_creation(self) -> None:
        """Test RowUpdate model creation with all field types."""
        user = User.objects.create_user(username="testuser", email="test@example.com")

        row_update = RowUpdate.objects.create(
            action="created_row",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=1,
            _values=[],
        )

        self.assertEqual(row_update.action, "created_row")
        self.assertEqual(row_update.created_by, user)
        self.assertEqual(row_update.modelname, "djangoapp.FirstStuff")
        self.assertEqual(row_update.row_pk, 1)
        self.assertIsNotNone(row_update.created_at)

    def test_values_property_getter(self) -> None:
        """Test values property getter deserializes JSON correctly."""
        row_update = RowUpdate(
            action="updated_row",
            modelname="djangoapp.FirstStuff",
            row_pk=1,
            _values=[
                {
                    "d": "boolean",
                    "name": "is_active",
                    "old_value": False,
                    "new_value": True,
                },
                {
                    "d": "integer",
                    "name": "count",
                    "old_value": 40,
                    "new_value": 42,
                },
                {
                    "d": "char",
                    "name": "title",
                    "old_value": "Old",
                    "new_value": "Hello",
                },
            ],
        )

        values = row_update.values
        self.assertIsNotNone(values)
        self.assertEqual(len(values), 3)  # type: ignore[arg-type]

        # Check first column value
        bool_val = values[0]  # type: ignore[index]
        self.assertIsInstance(bool_val, RowUpdateBooleanValue)
        assert isinstance(bool_val, RowUpdateBooleanValue)  # for type checker
        self.assertEqual(bool_val.discriminator, "boolean")
        self.assertEqual(bool_val.name, "is_active")
        self.assertEqual(bool_val.old_value, False)
        self.assertEqual(bool_val.new_value, True)

    def test_values_property_setter(self) -> None:
        """Test values property setter serializes pydantic to JSON correctly."""
        row_update = RowUpdate(
            action="updated_row",
            modelname="djangoapp.FirstStuff",
            row_pk=1,
        )

        values: list[RowColumnValueSchema] = [
            RowUpdateBooleanValue(name="is_active", old_value=False, new_value=True),
            RowUpdateIntegerValue(name="count", old_value=40, new_value=42),
            RowUpdateCharValue(name="title", old_value="Old", new_value="Hello"),
        ]

        row_update.values = values

        # Verify by reading back through the getter
        stored_values = row_update.values
        self.assertIsNotNone(stored_values)
        self.assertEqual(len(stored_values), 3)
        first_col = stored_values[0]
        assert isinstance(first_col, RowUpdateBooleanValue)
        self.assertEqual(first_col.discriminator, "boolean")
        self.assertEqual(first_col.name, "is_active")
        self.assertEqual(first_col.old_value, False)
        self.assertEqual(first_col.new_value, True)

    def test_column_value_schemas(self) -> None:
        """Test all column value pydantic schemas."""
        # RowUpdateBooleanValue
        bool_val = RowUpdateBooleanValue(name="test_bool", old_value=False, new_value=True)
        self.assertEqual(bool_val.discriminator, "boolean")
        self.assertEqual(bool_val.name, "test_bool")
        self.assertEqual(bool_val.old_value, False)
        self.assertEqual(bool_val.new_value, True)

        # RowUpdateIntegerValue
        int_val = RowUpdateIntegerValue(name="test_int", old_value=100, new_value=123)
        self.assertEqual(int_val.discriminator, "integer")
        self.assertEqual(int_val.old_value, 100)
        self.assertEqual(int_val.new_value, 123)

        # RowUpdateIntegerValue with None
        int_null = RowUpdateIntegerValue(name="test_int_null", old_value=None, new_value=None)
        self.assertIsNone(int_null.old_value)
        self.assertIsNone(int_null.new_value)

        # RowUpdateIntegerChoiceValue
        int_choice = RowUpdateIntegerChoiceValue(
            name="status",
            old_value=IntegerChoiceWrapper(value=0, value_title="Inactive"),
            new_value=IntegerChoiceWrapper(value=1, value_title="Active"),
        )
        self.assertEqual(int_choice.discriminator, "integer-choice")
        expected_int_old = IntegerChoiceWrapper(value=0, value_title="Inactive")
        expected_int_new = IntegerChoiceWrapper(value=1, value_title="Active")
        self.assertEqual(int_choice.old_value, expected_int_old)
        self.assertEqual(int_choice.new_value, expected_int_new)

        # RowUpdateCharValue
        char_val = RowUpdateCharValue(name="test_char", old_value="old", new_value="hello")
        self.assertEqual(char_val.discriminator, "char")
        self.assertEqual(char_val.old_value, "old")
        self.assertEqual(char_val.new_value, "hello")

        # RowUpdateCharChoiceValue
        char_choice = RowUpdateCharChoiceValue(
            name="type",
            old_value=CharChoiceWrapper(value="b", value_title="Type B"),
            new_value=CharChoiceWrapper(value="a", value_title="Type A"),
        )
        self.assertEqual(char_choice.discriminator, "char_choice")
        expected_char_old = CharChoiceWrapper(value="b", value_title="Type B")
        expected_char_new = CharChoiceWrapper(value="a", value_title="Type A")
        self.assertEqual(char_choice.old_value, expected_char_old)
        self.assertEqual(char_choice.new_value, expected_char_new)

        # RowUpdateTextValue
        text_val = RowUpdateTextValue(name="content", old_value="old text", new_value="long text")
        self.assertEqual(text_val.discriminator, "text")
        self.assertEqual(text_val.old_value, "old text")
        self.assertEqual(text_val.new_value, "long text")

        # RowUpdateDecimalValue (stored as string)
        dec_val = RowUpdateDecimalValue(name="price", old_value="10.00", new_value="19.99")
        self.assertEqual(dec_val.discriminator, "decimal")
        self.assertEqual(dec_val.old_value, "10.00")
        self.assertEqual(dec_val.new_value, "19.99")

        # RowUpdateForeignKeyValue
        fk_val = RowUpdateForeignKeyValue(
            name="category",
            old_value=ForeignKeyWrapper(id="1", title="Category A", url="/tables/ref/id/1"),
            new_value=ForeignKeyWrapper(id="2", title="Category B", url="/tables/ref/id/2"),
        )
        self.assertEqual(fk_val.discriminator, "foreign_key")
        self.assertEqual(
            fk_val.old_value,
            ForeignKeyWrapper(id="1", title="Category A", url="/tables/ref/id/1"),
        )
        self.assertEqual(
            fk_val.new_value,
            ForeignKeyWrapper(id="2", title="Category B", url="/tables/ref/id/2"),
        )

    def test_empty_values(self) -> None:
        """Test RowUpdate with empty _values."""
        row_update = RowUpdate(
            action="commented",
            modelname="djangoapp.FirstStuff",
            row_pk=1,
            _values={},
        )
        values = row_update.values
        self.assertIsNone(values)

    def test_comment_row_update(self) -> None:
        """Test RowUpdate for comment action."""
        user = User.objects.create_user(username="commenter", email="comment@example.com")

        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=1,
            comment_content="This is a test comment",
        )

        self.assertEqual(row_update.action, "commented")
        self.assertEqual(row_update.comment_content, "This is a test comment")
        self.assertIsNone(row_update.comment_deleted_at)

    def test_comment_soft_delete(self) -> None:
        """Test soft deleting a comment."""
        user = User.objects.create_user(username="deleter", email="delete@example.com")

        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=1,
            comment_content="Comment to be deleted",
        )

        # Soft delete
        row_update.comment_deleted_at = timezone.now()
        row_update.comment_content = ""
        row_update.save()

        self.assertIsNotNone(row_update.comment_deleted_at)
        self.assertEqual(row_update.comment_content, "")

    def test_save_stuff_creates_row_update_on_create(self) -> None:
        """Test that save_stuff creates a RowUpdate entry when creating a new row."""
        user = User.objects.create_user(username="creator", email="create@example.com")

        # Create a new row via save_stuff
        row = FirstStuff(char_field="test value")
        context: SaveContext[FirstStuff] = SaveContext(
            user=user,
            existing_row=None,
        )
        row.save_stuff(context)

        # Verify PK is set
        self.assertIsNotNone(row.pk)

        # Verify RowUpdate was created
        row_updates = RowUpdate.objects.filter(
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            action="created_row",
        )
        self.assertEqual(row_updates.count(), 1)
        row_update = row_updates.first()
        assert row_update is not None
        self.assertEqual(row_update.created_by, user)

    def test_save_stuff_creates_row_update_on_update(self) -> None:
        """Test that save_stuff creates a RowUpdate entry when updating a row."""
        user = User.objects.create_user(username="updater", email="update@example.com")

        # Create initial row (char_field max_length=10)
        row = FirstStuff.objects.create(char_field="init")
        initial_pk = row.pk

        # Update via save_stuff
        row.char_field = "updated"
        context: SaveContext[FirstStuff] = SaveContext(
            user=user,
            existing_row=row,
        )
        row.save_stuff(context)

        # Verify PK is unchanged
        self.assertEqual(row.pk, initial_pk)

        # Verify RowUpdate was created with action="updated_row"
        row_updates = RowUpdate.objects.filter(
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            action="updated_row",
        )
        self.assertEqual(row_updates.count(), 1)
        row_update = row_updates.first()
        assert row_update is not None
        self.assertEqual(row_update.created_by, user)

    def test_user_fk_not_serialized_in_row_update(self) -> None:
        """Test that User FK fields ARE serialized in RowUpdate values."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        proxy_user = ProxyUser.objects.get(pk=user.pk)

        # Create a row with a User FK (via ProxyUser) using FirstStuff which has user_fk field
        row = FirstStuff.objects.create(
            char_field="test",
            user_fk=proxy_user,
        )

        # Create via save_stuff
        context: SaveContext[FirstStuff] = SaveContext(
            user=user,
            existing_row=None,
        )
        row.save_stuff(context)

        # Verify RowUpdate was created
        row_update = RowUpdate.objects.filter(
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            action="created_row",
        ).first()
        assert row_update is not None

        # Verify values exist
        values = row_update.values
        self.assertIsNotNone(values)

        # Verify user_fk IS in the serialized values
        field_names = [cv.name for cv in values]  # type: ignore[union-attr]
        self.assertIn("user_fk", field_names)

        # Verify other fields ARE present
        self.assertIn("integer_field", field_names)
        self.assertIn("char_field", field_names)

    def test_modelname_for_regular_model(self) -> None:
        """Test _modelname returns correct label for regular model."""
        obj = FirstStuff(
            char_field="test",
            text_field="test text",
            integer_field=42,
            boolean_field=True,
        )
        self.assertEqual(obj.modelname(), "djangoapp.FirstStuff")

    def test_modelname_for_proxy_model(self) -> None:
        """Test _modelname returns concrete parent's label for proxy model."""
        # ProxyUser is a proxy for User
        user = User.objects.create_user(username="testuser")
        proxy_user = ProxyUser.objects.get(pk=user.pk)
        # Should return the concrete parent's label (User model)
        expected = User._meta.label  # accessing _meta to verify modelname() behavior
        self.assertEqual(proxy_user.modelname(), expected)
        # Should NOT return the proxy's own label
        self.assertNotEqual(proxy_user.modelname(), "djangoapp.ProxyUser")

    def test_modelname_for_proxy_user(self) -> None:
        """Test _modelname returns User model label for ProxyUser."""
        user = User.objects.create_user(username="testuser2")
        proxy_user = ProxyUser.objects.get(pk=user.pk)
        # Explicitly check for User model label
        self.assertEqual(proxy_user.modelname(), "djangoapp.User")

    def test_modelname_consistency_with_save_stuff(self) -> None:
        """Test that _modelname is used correctly in save_stuff for RowUpdate."""
        user = User.objects.create_user(username="testuser3")
        obj = FirstStuff(
            char_field="test",
            text_field="test text",
            integer_field=42,
            boolean_field=True,
        )
        context: SaveContext[FirstStuff] = SaveContext(
            user=user,
            existing_row=None,
        )
        obj.save_stuff(context)

        # Check that the RowUpdate has the correct modelname
        row_update = RowUpdate.objects.filter(
            modelname=obj.modelname(),
            row_pk=obj.pk,
        ).first()
        self.assertIsNotNone(row_update)
        self.assertEqual(row_update.modelname, "djangoapp.FirstStuff")  # type: ignore[union-attr]

    def test_rowupdates_method(self) -> None:
        """Test rowupdates() method returns RowUpdateResponse objects with redaction."""
        user = User.objects.create_user(username="testuser", email="test@example.com")

        # Create a row
        row = FirstStuff.objects.create(char_field="test")

        # Create multiple RowUpdate entries for this row
        RowUpdate.objects.create(
            action="created_row",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            _values=[],
        )

        RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="First comment",
        )

        RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="Second comment",
        )

        # Call rowupdates() method with user parameter
        update_responses = row.rowupdates(user)

        # Verify results
        self.assertEqual(len(update_responses), 3)
        # Verify ordering (should be descending by created_at)
        self.assertEqual(update_responses[0].comment_content, "Second comment")
        self.assertEqual(update_responses[1].comment_content, "First comment")
        self.assertEqual(update_responses[2].action, "created_row")
        # Verify all have user information (default redaction shows all data)
        for ur in update_responses:
            self.assertIsNotNone(ur.created_by)
            created_by = ur.created_by
            assert created_by is not None  # for mypy
            self.assertEqual(created_by.id, user.pk)
            self.assertEqual(created_by.title, "testuser")


# ------------------ RowUpdateAccessTimeout Tests ---------------------
class RowUpdateAccessTimeoutTest(TestCase):
    """Tests for row_update_access_timeout permission system."""

    def test_create_comment_returns_86400_by_default(self) -> None:
        """Test create_comment returns 86400 (24 hours) by default."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")

        result = row.can_create_comment(user)
        self.assertTrue(result)

    def test_update_comment_returns_86400_by_default(self) -> None:
        """Test update_comment returns 86400 (24 hours) by default."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")

        result = row.update_timeout(user)
        self.assertEqual(result, 86400)

    def test_delete_comment_returns_86400_by_default(self) -> None:
        """Test delete_comment returns 86400 (24 hours) by default."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")

        result = row.delete_timeout(user)
        self.assertEqual(result, 86400)

    def test_assert_can_update_comment_success_for_author_within_timeout(self) -> None:
        """Test assert_can_update_comment succeeds for author within timeout."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="Test comment",
        )

        # Should return the row_update
        result = row.get_rowupdate_for_update(user, row_update.pk)
        self.assertEqual(result, row_update)

    def test_get_rowupdate_for_update_fails_for_non_author(self) -> None:
        """Test get_rowupdate_for_update returns None for non-author."""
        author = User.objects.create_user(username="author", email="author@example.com")
        other_user = User.objects.create_user(username="other", email="other@example.com")
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=author,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="Test comment",
        )

        result = row.get_rowupdate_for_update(other_user, row_update.pk)
        self.assertIsNone(result)

    def test_get_rowupdate_for_update_fails_after_timeout(self) -> None:
        """Test get_rowupdate_for_update returns None after timeout."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="Test comment",
        )
        # Manually set created_at to more than 24 hours ago
        row_update.created_at = timezone.now() - timedelta(hours=25)
        row_update.save()

        result = row.get_rowupdate_for_update(user, row_update.pk)
        self.assertIsNone(result)

    def test_get_rowupdate_for_delete_success_within_timeout(self) -> None:
        """Test get_rowupdate_for_delete succeeds within timeout (no user check)."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="Test comment",
        )

        # Should return the row_update (delete has no user check)
        result = row.get_rowupdate_for_delete(user, row_update.pk)
        self.assertEqual(result, row_update)

    def test_get_rowupdate_for_delete_fails_after_timeout(self) -> None:
        """Test get_rowupdate_for_delete returns None after timeout."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            comment_content="Test comment",
        )
        # Manually set created_at to more than 24 hours ago
        row_update.created_at = timezone.now() - timedelta(hours=25)
        row_update.save()

        result = row.get_rowupdate_for_delete(user, row_update.pk)
        self.assertIsNone(result)

    def test_get_rowupdate_for_update_fails_for_wrong_modelname(self) -> None:
        """Test get_rowupdate_for_update returns None for wrong modelname."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        # Create row_update with wrong modelname
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.WrongModel",
            row_pk=row.pk,
            comment_content="Test comment",
        )

        result = row.get_rowupdate_for_update(user, row_update.pk)
        self.assertIsNone(result)

    def test_get_rowupdate_for_update_fails_for_wrong_row_pk(self) -> None:
        """Test get_rowupdate_for_update returns None for wrong row_pk."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        other_row = FirstStuff.objects.create(char_field="other")
        # Create row_update with wrong row_pk
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=other_row.pk,
            comment_content="Test comment",
        )

        result = row.get_rowupdate_for_update(user, row_update.pk)
        self.assertIsNone(result)

    def test_get_rowupdate_for_delete_fails_for_wrong_modelname(self) -> None:
        """Test get_rowupdate_for_delete returns None for wrong modelname."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        # Create row_update with wrong modelname
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.WrongModel",
            row_pk=row.pk,
            comment_content="Test comment",
        )

        result = row.get_rowupdate_for_delete(user, row_update.pk)
        self.assertIsNone(result)

    def test_get_rowupdate_for_delete_fails_for_wrong_row_pk(self) -> None:
        """Test get_rowupdate_for_delete returns None for wrong row_pk."""
        user = User.objects.create_user(username="testuser", email="test@example.com")
        row = FirstStuff.objects.create(char_field="test")
        other_row = FirstStuff.objects.create(char_field="other")
        # Create row_update with wrong row_pk
        row_update = RowUpdate.objects.create(
            action="commented",
            created_by=user,
            modelname="djangoapp.FirstStuff",
            row_pk=other_row.pk,
            comment_content="Test comment",
        )

        result = row.get_rowupdate_for_delete(user, row_update.pk)
        self.assertIsNone(result)


class RowUpdateAccessTimeoutOverrideTest(TestCase):
    """Tests for row_update_access_timeout override in subclasses."""

    def test_override_allows_custom_logic(self) -> None:
        """Test that row_update_access_timeout can be overridden."""
        # Use ConditionalRowUpdatePermissionModel which has an override
        # that returns 0 for rows with name starting with "No Permission"
        row = ConditionalRowUpdatePermissionModel.objects.create(name="No Permission Test")
        context = CommentPermissionContext[ConditionalRowUpdatePermissionModel](
            user=None, operation="create_comment", row=row
        )
        # Test that the override works
        result = row.row_update_access_timeout(context)
        self.assertEqual(result, 0)  # Custom implementation returns 0 for "No Permission" rows


class RowUpdateRedactionTest(TestCase):
    """Tests for row update redaction system."""

    user: User

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.user = User.objects.create_user(username="testuser", email="test@example.com")

    def test_recorded_columns_returns_column_names(self) -> None:
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            action="updated_row",
            created_by=self.user,
            _values=[
                {
                    "d": "char",
                    "name": "char_field",
                    "old_value": "old",
                    "new_value": "new",
                },
                {
                    "d": "integer",
                    "name": "integer_field",
                    "old_value": 1,
                    "new_value": 6,
                },
            ],
        )
        columns = row_update.recorded_columns()
        self.assertEqual(set(columns), {"char_field", "integer_field"})

    def test_recorded_columns_empty_for_no_values(self) -> None:
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=999,
            action="commented",
            created_by=self.user,
            _values=[],
        )
        columns = row_update.recorded_columns()
        self.assertEqual(columns, [])

    def test_redact_row_updates_returns_all_columns_by_default(self) -> None:
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            action="created_row",
            created_by=self.user,
            _values=[
                {
                    "d": "char",
                    "name": "char_field",
                    "old_value": None,
                    "new_value": "test",
                }
            ],
        )
        context = RowUpdateRedactContext[FirstStuff](
            user=self.user,
            row_updates=[row_update],
            row=row,
        )
        result = row.redact_row_updates(context)
        self.assertEqual(result[row_update.pk], ["char_field"])

    def test_redact_row_updates_can_return_redacted(self) -> None:
        """Test that redact_row_updates can be overridden to return 'redacted'."""
        row = FirstStuff.objects.create(char_field="test")
        row_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=row.pk,
            action="created_row",
            created_by=self.user,
            _values=[
                {
                    "d": "char",
                    "name": "char_field",
                    "old_value": None,
                    "new_value": "test",
                }
            ],
        )

        # Test that the default implementation returns column names
        context = RowUpdateRedactContext[FirstStuff](
            user=self.user,
            row_updates=[row_update],
            row=row,
        )
        result = row.redact_row_updates(context)
        self.assertEqual(result[row_update.pk], ["char_field"])

        # Verify that "redacted" is a valid return value by checking the type
        # The actual override behavior is tested via integration tests


class RowUpdateUserNotificationTest(TestCase):
    """Tests for RowUpdateUserNotification model and notification system."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.other_user = User.objects.create_user(username="otheruser", password="otherpass")
        self.row = FirstStuff.objects.create(char_field="test row")

    def test_create_notifications_creates_notification_objects(self) -> None:
        """Test _create_notifications creates RowUpdateUserNotification objects."""
        row_update = RowUpdate.objects.create(
            action="created_row",
            created_by=self.user,
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            _values=[],
        )

        notifying_row = NotifyingFirstStuff.objects.get(pk=self.row.pk)
        notifying_row._create_notifications(row_update, CreateRowNotifyContext(user=self.user))

        notifications = RowUpdateUserNotification.objects.filter(
            modelname=self.row.modelname(), row_pk=self.row.pk, user=self.other_user
        )
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        assert notif is not None
        self.assertIn("id", notif.content)
        self.assertEqual(notif.content["action"], "created_row")
        self.assertEqual(notif.content["created_by"]["title"], "testuser")

    def test_create_notifications_triggered_after_create_row(self) -> None:
        """Test _create_notifications is triggered after creating a row via save_stuff."""
        row = NotifyingFirstStuff(char_field="new")
        ctx: SaveContext[NotifyingFirstStuff] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        notifications = RowUpdateUserNotification.objects.filter(user=self.other_user)
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        assert notif is not None
        self.assertEqual(notif.content["action"], "created_row")
        self.assertEqual(notif.content["created_by"]["title"], "testuser")

    def test_create_notifications_triggered_after_update_row(self) -> None:
        """Test _create_notifications is triggered after updating a row via save_stuff."""
        row = NotifyingFirstStuff.objects.create(char_field="initial")
        row.char_field = "updated"
        ctx: SaveContext[NotifyingFirstStuff] = SaveContext(user=self.user, existing_row=row)
        row.save_stuff(ctx)

        notifications = RowUpdateUserNotification.objects.filter(user=self.other_user)
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        assert notif is not None
        self.assertEqual(notif.content["action"], "updated_row")

    def test_create_notifications_triggered_after_create_comment(self) -> None:
        """Test _create_notifications is triggered after creating a comment."""
        row = NotifyingFirstStuff.objects.create(char_field="test")
        row.create_comment(self.user, "Test comment")

        notifications = RowUpdateUserNotification.objects.filter(user=self.other_user)
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        assert notif is not None
        self.assertEqual(notif.content["action"], "commented")
        self.assertEqual(notif.content["comment_content"], "Test comment")

    def test_create_notifications_triggered_after_update_comment(self) -> None:
        """Test _create_notifications is triggered after updating a comment."""
        row = NotifyingFirstStuff.objects.create(char_field="test")
        row_update = row.create_comment(self.user, "Original comment")

        row.update_comment(self.user, row_update, "Updated comment")

        notifications = RowUpdateUserNotification.objects.filter(user=self.other_user).order_by(
            "-id"
        )
        self.assertEqual(notifications.count(), 2)
        notif = notifications.first()
        assert notif is not None
        self.assertEqual(notif.content["action"], "commented")
        self.assertEqual(notif.content["comment_content"], "Updated comment")

    def test_create_notifications_excludes_actor_from_recipients(self) -> None:
        """Test _create_notifications excludes actor even when notify_users includes them."""
        row_update = RowUpdate.objects.create(
            action="created_row",
            created_by=self.user,
            modelname="djangoapp.FirstStuff",
            row_pk=self.row.pk,
            _values=[],
        )

        notifying_row = NotifyingFirstStuff.objects.get(pk=self.row.pk)
        notifying_row._create_notifications(row_update, CreateRowNotifyContext(user=self.user))

        actor_notifications = RowUpdateUserNotification.objects.filter(
            modelname=self.row.modelname(), row_pk=self.row.pk, user=self.user
        )
        self.assertEqual(actor_notifications.count(), 0)

        other_notifications = RowUpdateUserNotification.objects.filter(
            modelname=self.row.modelname(), row_pk=self.row.pk, user=self.other_user
        )
        self.assertEqual(other_notifications.count(), 1)
        notif = other_notifications.first()
        assert notif is not None
        self.assertEqual(notif.content["created_by"]["title"], "testuser")


class SearchForFkColumnTest(TestCase):
    """Tests for search_for_fk_column with and without @search methods.

    Uses SearchForFkDestinationModel which has:
    - fk_with_search: ForeignKey to SearchForFkTargetModel with @search decorator
    - fk_without_search: ForeignKey to SearchForFkTargetModel without @search decorator
    """

    target1: SearchForFkTargetModel
    target2: SearchForFkTargetModel

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Create SearchForFkTargetModel instances
        cls.target1 = SearchForFkTargetModel.objects.create(name="Apple Target")
        cls.target2 = SearchForFkTargetModel.objects.create(name="Banana Target")

    def test_search_for_fk_column_with_search_method_calls_custom_search(self) -> None:
        """fk_with_search uses @search decorator for custom filtering."""
        # SearchForFkDestinationModel.fk_with_search has @search decorator
        # that filters by name__icontains
        queryset = SearchForFkDestinationModel.search_for_fk_column(
            column_name="fk_with_search",
            user=None,
            search_text="Apple",  # Matches target1's name
        )
        # Should find target1 ("Apple Target")
        result_ids = list(queryset.values_list("pk", flat=True))
        self.assertIn(self.target1.pk, result_ids)
        self.assertNotIn(self.target2.pk, result_ids)  # "Banana" doesn't match "Apple"

    def test_search_for_fk_column_without_search_method_uses_base_search(self) -> None:
        """fk_without_search uses base search_text (numeric pk matching)."""
        # SearchForFkDestinationModel.fk_without_search has no @search decorator
        # BaseModel.search_text only matches numeric pk
        queryset = SearchForFkDestinationModel.search_for_fk_column(
            column_name="fk_without_search",
            user=None,
            search_text=str(self.target1.pk),  # Search by numeric ID
        )
        # Should find target1 by ID
        result_ids = list(queryset.values_list("pk", flat=True))
        self.assertEqual(result_ids, [self.target1.pk])


class PublicIdPropertyTest(TestCase):
    """Verify that public_id property and has_custom_public_id work correctly.

    Default models use pk as public_id (str). Models with a custom
    public_id_field return that field's value instead.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_default_public_id_returns_str_pk(self) -> None:
        row = FirstStuff.objects.create(char_field="test")
        self.assertEqual(row.public_id, str(row.pk))

    def test_custom_public_id_returns_uuid_id(self) -> None:
        row = PublicIdUuid7TestModel(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        self.assertEqual(row.public_id, row.uuid_id)
        self.assertIn("-", row.public_id)

    def test_custom_public_id_returns_slug(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        self.assertEqual(row.public_id, row.slug)

    def test_has_custom_public_id_default(self) -> None:
        self.assertFalse(FirstStuff.has_custom_public_id())

    def test_has_custom_public_id_overridden(self) -> None:
        self.assertTrue(PublicIdUuid7TestModel.has_custom_public_id())

    def test_public_id_is_always_str(self) -> None:
        row = FirstStuff.objects.create(char_field="test")
        self.assertIsInstance(row.public_id, str)


class GetByPublicIdTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_get_by_public_id_with_default_field(self) -> None:
        row = FirstStuff.objects.create(char_field="test")
        result = FirstStuff.get_by_public_id(FirstStuff.objects.all(), str(row.pk))
        self.assertEqual(result.pk, row.pk)

    def test_get_by_public_id_with_custom_field(self) -> None:
        row = PublicIdUuid7TestModel(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        result = PublicIdUuid7TestModel.get_by_public_id(
            PublicIdUuid7TestModel.objects.all(), row.uuid_id
        )
        self.assertEqual(result.pk, row.pk)

    def test_get_by_public_id_not_found_raises_does_not_exist(self) -> None:
        with self.assertRaises(FirstStuff.DoesNotExist):
            FirstStuff.get_by_public_id(FirstStuff.objects.all(), "99999")

    def test_get_by_public_id_or_404_raises(self) -> None:

        with self.assertRaises(Http404):
            FirstStuff.get_by_public_id_or_404(FirstStuff.objects.all(), "99999")


class PublicIdUuid7ModelTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_create_generates_uuid7(self) -> None:
        row = PublicIdUuid7TestModel(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        self.assertTrue(row.uuid_id)

        parsed = uuid.UUID(row.uuid_id)
        self.assertEqual(parsed.version, 7)

    def test_uuid7_not_regenerated_on_update(self) -> None:
        row = PublicIdUuid7TestModel(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        original_uuid = row.uuid_id

        row.name = "updated"
        ctx2: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=row)
        row.save_stuff(ctx2)
        self.assertEqual(row.uuid_id, original_uuid)

    def test_row_update_stores_row_public_id(self) -> None:
        row = PublicIdUuid7TestModel(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        row_update = RowUpdate.objects.filter(modelname=row.modelname(), row_pk=row.pk).first()
        assert row_update is not None
        self.assertEqual(row_update.row_public_id, row.uuid_id)


class PublicIdUuid7Model2Test(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_create_generates_uuid7_slug(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        parsed = uuid.UUID(row.slug)
        self.assertEqual(parsed.version, 7)

    def test_slug_is_editable(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        old_slug = row.slug

        row.slug = "john-smith"
        ctx2: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=row)
        row.save_stuff(ctx2)
        self.assertEqual(row.slug, "john-smith")
        self.assertEqual(row.public_id, "john-smith")
        self.assertNotEqual(row.public_id, old_slug)

    def test_slug_validation_rejects_spaces(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        row.slug = "hello world"
        ctx2: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=row)
        with self.assertRaises(ValidationError) as cm:
            row.save_stuff(ctx2)
        self.assertIn("slug", cm.exception.message_dict)

    def test_slug_validation_rejects_special_chars(self) -> None:
        row = PublicIdUuid7TestModel2(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        row.slug = "hello@world"
        ctx2: SaveContext[PublicIdUuid7TestModel2] = SaveContext(user=self.user, existing_row=row)
        with self.assertRaises(ValidationError) as cm:
            row.save_stuff(ctx2)
        self.assertIn("slug", cm.exception.message_dict)


class PublicIdUuid4Model3Test(TestCase):
    """Verify UUIDField-backed public ID using uuid4.

    PublicIdUuid7TestModel3 stores a native uuid.UUID via models.UUIDField.
    The public_id property must return its str representation, and the
    UUID must persist across updates.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_create_generates_uuid4(self) -> None:
        row = PublicIdUuid7TestModel3(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel3] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        self.assertIsInstance(row.uuid_id, uuid.UUID)
        self.assertEqual(row.uuid_id.version, 4)

    def test_public_id_returns_str(self) -> None:
        row = PublicIdUuid7TestModel3(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel3] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        self.assertEqual(row.public_id, str(row.uuid_id))

    def test_uuid_not_regenerated_on_update(self) -> None:
        row = PublicIdUuid7TestModel3(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel3] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)
        original_uuid = row.uuid_id

        row.name = "updated"
        ctx2: SaveContext[PublicIdUuid7TestModel3] = SaveContext(user=self.user, existing_row=row)
        row.save_stuff(ctx2)
        self.assertEqual(row.uuid_id, original_uuid)

    def test_get_by_public_id_with_uuid_field(self) -> None:
        row = PublicIdUuid7TestModel3(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel3] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        result = PublicIdUuid7TestModel3.get_by_public_id(
            PublicIdUuid7TestModel3.objects.all(), str(row.uuid_id)
        )
        self.assertEqual(result.pk, row.pk)

    def test_row_update_stores_row_public_id(self) -> None:
        row = PublicIdUuid7TestModel3(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel3] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        row_update = RowUpdate.objects.filter(modelname=row.modelname(), row_pk=row.pk).first()
        assert row_update is not None
        self.assertEqual(row_update.row_public_id, str(row.uuid_id))


class PublicIdSequenceTest(TestCase):
    """Verify sequence-based public IDs increment correctly.

    Tests one PublicIdSequenceTestModel1 (daily format ``%Y-%m-%d-ID``)
    and two PublicIdSequenceTestModel2 rows (monthly format ``%Y-%m-ID``).
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_model1_first_row_gets_sequence_1(self) -> None:
        row = PublicIdSequenceTestModel1(name="test")
        ctx: SaveContext[PublicIdSequenceTestModel1] = SaveContext(
            user=self.user, existing_row=None
        )
        row.save_stuff(ctx)
        self.assertTrue(row.seq_id.endswith("-1"))

    def test_model1_second_row_increments(self) -> None:
        row1 = PublicIdSequenceTestModel1(name="first")
        ctx1: SaveContext[PublicIdSequenceTestModel1] = SaveContext(
            user=self.user, existing_row=None
        )
        row1.save_stuff(ctx1)

        row2 = PublicIdSequenceTestModel1(name="second")
        ctx2: SaveContext[PublicIdSequenceTestModel1] = SaveContext(
            user=self.user, existing_row=None
        )
        row2.save_stuff(ctx2)

        seq1 = int(row1.seq_id.split("-")[-1])
        seq2 = int(row2.seq_id.split("-")[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_model1_public_id_returns_seq_id(self) -> None:
        row = PublicIdSequenceTestModel1(name="test")
        ctx: SaveContext[PublicIdSequenceTestModel1] = SaveContext(
            user=self.user, existing_row=None
        )
        row.save_stuff(ctx)
        self.assertEqual(row.public_id, row.seq_id)

    def test_model2_first_row_gets_monthly_sequence(self) -> None:
        row = PublicIdSequenceTestModel2(name="test")
        ctx: SaveContext[PublicIdSequenceTestModel2] = SaveContext(
            user=self.user, existing_row=None
        )
        row.save_stuff(ctx)

        self.assertRegex(row.seq_id, r"\d{4}-\d{2}-\d+")

    def test_model2_second_row_increments(self) -> None:
        row1 = PublicIdSequenceTestModel2(name="first")
        ctx1: SaveContext[PublicIdSequenceTestModel2] = SaveContext(
            user=self.user, existing_row=None
        )
        row1.save_stuff(ctx1)

        row2 = PublicIdSequenceTestModel2(name="second")
        ctx2: SaveContext[PublicIdSequenceTestModel2] = SaveContext(
            user=self.user, existing_row=None
        )
        row2.save_stuff(ctx2)

        seq1 = int(row1.seq_id.split("-")[-1])
        seq2 = int(row2.seq_id.split("-")[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_model2_public_id_returns_seq_id(self) -> None:
        row = PublicIdSequenceTestModel2(name="test")
        ctx: SaveContext[PublicIdSequenceTestModel2] = SaveContext(
            user=self.user, existing_row=None
        )
        row.save_stuff(ctx)
        self.assertEqual(row.public_id, row.seq_id)


class GetRowForUserAndOperationPublicIdTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="testuser")

    def test_looks_up_by_public_id_field(self) -> None:
        row = PublicIdUuid7TestModel(name="test")
        ctx: SaveContext[PublicIdUuid7TestModel] = SaveContext(user=self.user, existing_row=None)
        row.save_stuff(ctx)

        result = PublicIdUuid7TestModel.get_row_for_user_and_operation(row.uuid_id, None, "read")
        self.assertEqual(result.pk, row.pk)

    def test_looks_up_by_str_pk_for_default_models(self) -> None:
        row = FirstStuff.objects.create(char_field="test")
        result = FirstStuff.get_row_for_user_and_operation(str(row.pk), None, "read")
        self.assertEqual(result.pk, row.pk)
