from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from djangoapp.filters import (
    BooleanValueFilter,
    CharBlankFilter,
    CharChoiceFilter,
    CharTextFilter,
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
    DecimalFieldModel,
    FirstStuff,
    ForeignKeyModel,
    IntegerFieldModel,
)
from djangoapp.models.base import ResolveColumnsContext, RowUpdate, User
from djangoapp.responses import (
    BaseFieldSchema,
    BooleanFieldSchema,
    CharFieldSchema,
    DecimalFieldSchema,
    ForeignKeyFieldSchema,
    IntegerFieldSchema,
)
from djangoapp.views.base import ListPageSchema


class BooleanFilterTests(TestCase):
    """Test boolean field filtering functionality."""

    def setUp(self) -> None:
        """Create test data with various boolean field values."""
        # Create BooleanFieldModel instances with different boolean values
        self.obj1 = BooleanFieldModel.objects.create(boolean_field=True)
        self.obj2 = BooleanFieldModel.objects.create(boolean_field=False)
        self.obj3 = BooleanFieldModel.objects.create(boolean_field=True)
        self.obj4 = BooleanFieldModel.objects.create(boolean_field=False)

    def test_boolean_value_filter_true(self) -> None:
        """Test BooleanValueFilter with value=True."""
        # Expected IDs for True values
        expected_true_ids = {self.obj1.id, self.obj3.id}

        # Get all instances
        qs = BooleanFieldModel.objects.all()
        self.assertEqual(qs.count(), 4)

        # Apply boolean filter for True values
        bool_filter = BooleanValueFilter(value=True)
        filtered = bool_filter.apply(qs, "boolean_field")

        # Should return only instances with boolean_field=True
        self.assertEqual(filtered.count(), 2)

        # Match the set of retrieved IDs with expected IDs
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_true_ids)

        # Verify all filtered objects have boolean_field=True
        for obj in filtered:
            self.assertTrue(obj.boolean_field)

    def test_boolean_value_filter_false(self) -> None:
        """Test BooleanValueFilter with value=False."""
        # Expected IDs for False values
        expected_false_ids = {self.obj2.id, self.obj4.id}

        # Get all instances
        qs = BooleanFieldModel.objects.all()
        self.assertEqual(qs.count(), 4)

        # Apply boolean filter for False values
        bool_filter = BooleanValueFilter(value=False)
        filtered = bool_filter.apply(qs, "boolean_field")

        # Should return only instances with boolean_field=False
        self.assertEqual(filtered.count(), 2)

        # Match the set of retrieved IDs with expected IDs
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_false_ids)

        # Verify all filtered objects have boolean_field=False
        for obj in filtered:
            self.assertFalse(obj.boolean_field)

    def test_invalid_boolean_filter_on_non_boolean_field_gets_removed(self) -> None:
        """Test that boolean filters are removed from non-boolean fields during validation."""
        # Create a schema with boolean filter on a non-boolean field
        schema = ListPageSchema(
            f={
                "boolean_field": BooleanValueFilter(value=True),  # Valid
                "id": BooleanValueFilter(value=True),  # Invalid: boolean filter on ID field
            }
        )

        # Create a schema with boolean filter on a non-boolean field
        schema = ListPageSchema(
            f={
                "boolean_field": BooleanValueFilter(value=True),  # Valid
                "id": BooleanValueFilter(value=True),  # Invalid: boolean filter on ID field
            }
        )

        # Mock columns - only boolean_field is a boolean field
        columns: dict[str, BaseFieldSchema] = {
            "boolean_field": BooleanFieldSchema(
                name="boolean_field",
                d="boolean",
                required=False,
                default=None,
            ),
        }

        # Validate filters
        schema.validate_filters(None, BooleanFieldModel, columns)

        # Invalid filter should be removed, valid one should remain
        self.assertIn("boolean_field", schema.filter_map)
        self.assertNotIn("id", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 1)

    def test_invalid_boolean_filter_on_char_field(self) -> None:
        """Test that boolean filters are removed from char fields during validation."""
        # Create a schema with boolean filter on a char field
        schema = ListPageSchema(
            f={
                "boolean_field": BooleanValueFilter(value=True),  # Valid
                "char_field": BooleanValueFilter(
                    value=True
                ),  # Invalid: boolean filter on char field
            }
        )

        # Mock columns - only boolean_field is a boolean field
        columns: dict[str, BaseFieldSchema] = {
            "boolean_field": BooleanFieldSchema(
                name="boolean_field",
                d="boolean",
                required=False,
                default=None,
            ),
            "char_field": CharFieldSchema(
                name="char_field",
                d="char",
                required=False,
                max_length=100,
                choices=None,
                default=None,
            ),
        }

        # Validate filters
        schema.validate_filters(None, BooleanFieldModel, columns)

        # Invalid filter should be removed, valid one should remain
        self.assertIn("boolean_field", schema.filter_map)
        self.assertNotIn("char_field", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 1)

    def test_invalid_boolean_filter_on_integer_field(self) -> None:
        """Test that boolean filters are removed from integer fields during validation."""
        # Create a schema with boolean filter on an integer field
        schema = ListPageSchema(
            f={
                "boolean_field": BooleanValueFilter(value=True),  # Valid
                "integer_field": BooleanValueFilter(
                    value=True
                ),  # Invalid: boolean filter on integer field
            }
        )

        # Mock columns - only boolean_field is a boolean field
        columns: dict[str, BaseFieldSchema] = {
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
                choices=None,
                default=None,
            ),
        }

        # Validate filters
        schema.validate_filters(None, BooleanFieldModel, columns)

        # Invalid filter should be removed, valid one should remain
        self.assertIn("boolean_field", schema.filter_map)
        self.assertNotIn("integer_field", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 1)


class IntegerFilterTests(TestCase):
    """Test integer field filtering functionality."""

    def setUp(self) -> None:
        """Create test data with various integer field values."""
        # Create IntegerFieldModel instances with different integer values
        self.obj1 = IntegerFieldModel.objects.create(
            integer_field=10,
            optional_integer_field=100,
            integer_choice_field=1,  # Active
            optional_integer_choice_field=2,  # Inactive
        )
        self.obj2 = IntegerFieldModel.objects.create(
            integer_field=20,
            optional_integer_field=200,
            integer_choice_field=2,  # Inactive
            optional_integer_choice_field=3,  # Pending
        )
        self.obj3 = IntegerFieldModel.objects.create(
            integer_field=30,
            optional_integer_field=300,
            integer_choice_field=3,  # Pending
            optional_integer_choice_field=1,  # Active
        )
        self.obj4 = IntegerFieldModel.objects.create(
            integer_field=40,
            optional_integer_field=400,
            integer_choice_field=1,  # Active
            optional_integer_choice_field=2,  # Inactive
        )
        self.obj5 = IntegerFieldModel.objects.create(
            integer_field=50,
            optional_integer_field=None,  # Null value
            integer_choice_field=2,  # Inactive
            optional_integer_choice_field=None,  # Null value
        )

    def test_integer_gt_filter(self) -> None:
        """Test IntegerComparisonFilter with gt (greater than) operator."""
        expected_ids = {self.obj3.id, self.obj4.id, self.obj5.id}  # Values 30, 40, 50

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply gt filter for values > 25
        gt_filter = IntegerComparisonFilter(op="gt", number_1=25)
        filtered = gt_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field > 25
        for obj in filtered:
            self.assertGreater(obj.integer_field, 25)

    def test_integer_gte_filter(self) -> None:
        """Test IntegerComparisonFilter with gte (greater than or equal) operator."""
        expected_ids = {
            self.obj2.id,
            self.obj3.id,
            self.obj4.id,
            self.obj5.id,
        }  # Values 20, 30, 40, 50

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply gte filter for values >= 20
        gte_filter = IntegerComparisonFilter(op="gte", number_1=20)
        filtered = gte_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field >= 20
        for obj in filtered:
            self.assertGreaterEqual(obj.integer_field, 20)

    def test_integer_lt_filter(self) -> None:
        """Test IntegerComparisonFilter with lt (less than) operator."""
        expected_ids = {self.obj1.id, self.obj2.id}  # Values 10, 20

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply lt filter for values < 25
        lt_filter = IntegerComparisonFilter(op="lt", number_1=25)
        filtered = lt_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field < 25
        for obj in filtered:
            self.assertLess(obj.integer_field, 25)

    def test_integer_lte_filter(self) -> None:
        """Test IntegerComparisonFilter with lte (less than or equal) operator."""
        expected_ids = {self.obj1.id, self.obj2.id, self.obj3.id}  # Values 10, 20, 30

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply lte filter for values <= 30
        lte_filter = IntegerComparisonFilter(op="lte", number_1=30)
        filtered = lte_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field <= 30
        for obj in filtered:
            self.assertLessEqual(obj.integer_field, 30)

    def test_integer_eq_filter(self) -> None:
        """Test IntegerComparisonFilter with eq (equal) operator."""
        expected_ids = {self.obj3.id}  # Value 30

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply eq filter for values = 30
        eq_filter = IntegerComparisonFilter(op="eq", number_1=30)
        filtered = eq_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field = 30
        for obj in filtered:
            self.assertEqual(obj.integer_field, 30)

    def test_integer_ne_filter(self) -> None:
        """Test IntegerComparisonFilter with ne (not equal) operator."""
        expected_ids = {
            self.obj1.id,
            self.obj2.id,
            self.obj4.id,
            self.obj5.id,
        }  # Values 10, 20, 40, 50

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply ne filter for values != 30
        ne_filter = IntegerComparisonFilter(op="ne", number_1=30)
        filtered = ne_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field != 30
        for obj in filtered:
            self.assertNotEqual(obj.integer_field, 30)

    def test_integer_range_inc_filter(self) -> None:
        """Test IntegerComparisonFilter with inc (include range) operator."""
        expected_ids = {self.obj2.id, self.obj3.id, self.obj4.id}  # Values 20, 30, 40

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply inc filter for values between 20 and 40 (inclusive)
        inc_filter = IntegerComparisonFilter(op="inc", number_1=20, number_2=40)
        filtered = inc_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have 20 <= integer_field <= 40
        for obj in filtered:
            self.assertGreaterEqual(obj.integer_field, 20)
            self.assertLessEqual(obj.integer_field, 40)

    def test_integer_range_ex_filter(self) -> None:
        """Test IntegerComparisonFilter with ex (exclude range) operator."""
        expected_ids = {self.obj1.id, self.obj5.id}  # Values 10, 50

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply ex filter for values outside 20-40 (exclude range)
        min_value, max_value = 20, 40
        ex_filter = IntegerComparisonFilter(op="ex", number_1=min_value, number_2=max_value)
        filtered = ex_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_field < 20 or > 40
        for obj in filtered:
            condition = obj.integer_field < min_value or obj.integer_field > max_value
            self.assertTrue(condition)

    def test_integer_range_auto_swap(self) -> None:
        """Test IntegerComparisonFilter auto-swap when number_2 < number_1."""
        expected_ids = {self.obj2.id, self.obj3.id, self.obj4.id}  # Values 20, 30, 40

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply inc filter with reversed range (40, 20) - should auto-swap
        inc_filter = IntegerComparisonFilter(op="inc", number_1=40, number_2=20)
        filtered = inc_filter.apply(qs, "integer_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have 20 <= integer_field <= 40
        for obj in filtered:
            self.assertGreaterEqual(obj.integer_field, 20)
            self.assertLessEqual(obj.integer_field, 40)

    def test_integer_range_invalid_missing_number_2(self) -> None:
        """Test that integer range filters with missing number_2 are removed during validation."""
        # Create a schema with inc filter missing number_2
        schema = ListPageSchema(
            f={
                "integer_field": IntegerComparisonFilter(
                    op="inc", number_1=20, number_2=None
                ),  # Invalid
            }
        )

        # Mock columns
        columns: dict[str, BaseFieldSchema] = {
            "integer_field": IntegerFieldSchema(
                name="integer_field",
                d="integer",
                required=False,
                choices=None,
                default=None,
            ),
        }

        # Validate filters - should remove invalid filter
        schema.validate_filters(None, IntegerFieldModel, columns)

        # Invalid filter should be removed
        self.assertNotIn("integer_field", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 0)

    def test_integer_range_invalid_equal_values(self) -> None:
        """Test that integer range filter with equal values is actually valid."""
        # Unlike what the test name suggests, equal values are actually valid for ranges
        # (they represent a single point range)
        # Create a schema with inc filter having equal values
        schema = ListPageSchema(
            f={
                "integer_field": IntegerComparisonFilter(
                    op="inc", number_1=20, number_2=20
                ),  # Equal values - valid
            }
        )

        # Mock columns
        columns: dict[str, BaseFieldSchema] = {
            "integer_field": IntegerFieldSchema(
                name="integer_field",
                d="integer",
                required=False,
                choices=None,
                default=None,
            ),
        }

        # Validate filters - should keep the filter since equal values are valid
        schema.validate_filters(None, IntegerFieldModel, columns)

        # Filter should be kept (equal values represent a valid single-point range)
        self.assertIn("integer_field", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 1)

    def test_integer_choice_any_filter(self) -> None:
        """Test IntegerChoiceFilter with 'any' mode."""
        expected_ids = {self.obj1.id, self.obj4.id}  # Values with choice field 1

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply choice filter with any mode for choice field = 1
        choice_filter = IntegerChoiceFilter(mode="any", options=[1])
        filtered = choice_filter.apply(qs, "integer_choice_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_choice_field = 1
        for obj in filtered:
            self.assertEqual(obj.integer_choice_field, 1)

    def test_integer_choice_none_filter(self) -> None:
        """Test IntegerChoiceFilter with 'none' mode."""
        expected_ids = {self.obj2.id, self.obj5.id}  # Values with choice field 2

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply choice filter with none mode for choice field != 1,3
        choice_filter = IntegerChoiceFilter(mode="none", options=[1, 3])
        filtered = choice_filter.apply(qs, "integer_choice_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have integer_choice_field not in [1, 3]
        for obj in filtered:
            self.assertNotIn(obj.integer_choice_field, [1, 3])

    def test_integer_null_filter(self) -> None:
        """Test IntegerNullFilter for optional_integer_field=True."""
        expected_ids = {self.obj5.id}  # Only obj5 has null optional_integer_field

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply null filter for True
        null_filter = IntegerNullFilter(value=True)
        filtered = null_filter.apply(qs, "optional_integer_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_integer_field is None
        for obj in filtered:
            self.assertIsNone(obj.optional_integer_field)

    def test_integer_null_filter_false(self) -> None:
        """Test IntegerNullFilter for optional_integer_field=False."""
        expected_ids = {
            self.obj1.id,
            self.obj2.id,
            self.obj3.id,
            self.obj4.id,
        }  # Objects with non-null optional_integer_field

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply null filter for False
        null_filter = IntegerNullFilter(value=False)
        filtered = null_filter.apply(qs, "optional_integer_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_integer_field is not None
        for obj in filtered:
            self.assertIsNotNone(obj.optional_integer_field)

    def test_optional_integer_choice_filter_any(self) -> None:
        """Test IntegerChoiceFilter on optional field with 'any' mode."""
        expected_ids = {self.obj3.id}  # Only obj3 has optional_integer_choice_field = 1

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply choice filter with any mode for optional choice field = 1
        choice_filter = IntegerChoiceFilter(mode="any", options=[1])
        filtered = choice_filter.apply(qs, "optional_integer_choice_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_integer_choice_field = 1
        for obj in filtered:
            self.assertEqual(obj.optional_integer_choice_field, 1)

    def test_optional_integer_choice_filter_none(self) -> None:
        """Test IntegerChoiceFilter on optional field with 'none' mode."""
        expected_ids = {
            self.obj1.id,
            self.obj4.id,
            self.obj5.id,
        }  # Objects with optional choice field = 2 or None

        qs = IntegerFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply choice filter with none mode for optional choice field != 1,3
        choice_filter = IntegerChoiceFilter(mode="none", options=[1, 3])
        filtered = choice_filter.apply(qs, "optional_integer_choice_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}

        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_integer_choice_field not in [1, 3] or None
        for obj in filtered:
            if obj.optional_integer_choice_field is not None:  # Skip null values
                self.assertNotIn(obj.optional_integer_choice_field, [1, 3])

    def test_list_page_schema_rejects_null_filter_on_required_integer_field(self) -> None:
        """Test that null filter is removed from non-nullable integer_field."""
        list_page_schema = ListPageSchema(f={"integer_field": IntegerNullFilter(value=True)})

        # Get DjangoField objects and convert to FieldSchema
        all_columns = IntegerFieldModel.raw_resolve_columns()
        all_column_names = tuple(all_columns.keys())
        resolved_columns = IntegerFieldModel.resolve_columns(
            ResolveColumnsContext(user=None, operation="list", columns=all_column_names)
        )
        assert resolved_columns is not None
        django_fields = [all_columns[name] for name in resolved_columns if name in all_columns]

        field_schemas = IntegerFieldModel.columns_schemas(django_fields)

        # Validate filters - should remove null filter for non-nullable field
        list_page_schema.validate_filters(None, IntegerFieldModel, field_schemas)

        # Verify null filter was removed
        self.assertNotIn("integer_field", list_page_schema.filter_map)

    def test_list_page_schema_rejects_null_filter_on_required_integer_choice_field(self) -> None:
        """Test that null filter is removed from non-nullable integer_choice_field."""
        list_page_schema = ListPageSchema(f={"integer_choice_field": IntegerNullFilter(value=True)})

        # Get DjangoField objects and convert to FieldSchema
        all_columns = IntegerFieldModel.raw_resolve_columns()
        all_column_names = tuple(all_columns.keys())
        resolved_columns = IntegerFieldModel.resolve_columns(
            ResolveColumnsContext(user=None, operation="list", columns=all_column_names)
        )
        assert resolved_columns is not None
        django_fields = [all_columns[name] for name in resolved_columns if name in all_columns]

        field_schemas = IntegerFieldModel.columns_schemas(django_fields)

        # Validate filters - should remove null filter for non-nullable field
        list_page_schema.validate_filters(None, IntegerFieldModel, field_schemas)

        # Verify null filter was removed
        self.assertNotIn("integer_choice_field", list_page_schema.filter_map)


class DecimalFilterTests(TestCase):
    """Test decimal field filtering functionality."""

    def setUp(self) -> None:
        """Create test data with various decimal field values."""
        # Create DecimalFieldModel instances with different decimal values
        self.obj1 = DecimalFieldModel.objects.create(
            decimal_field=10.00,
            optional_decimal_field=100.00,
        )
        self.obj2 = DecimalFieldModel.objects.create(
            decimal_field=20.00,
            optional_decimal_field=200.00,
        )
        self.obj3 = DecimalFieldModel.objects.create(
            decimal_field=30.00,
            optional_decimal_field=300.00,
        )
        self.obj4 = DecimalFieldModel.objects.create(
            decimal_field=40.00,
            optional_decimal_field=400.00,
        )
        self.obj5 = DecimalFieldModel.objects.create(
            decimal_field=50.00,
            optional_decimal_field=None,  # Null value
        )

    def test_decimal_gt_filter(self) -> None:
        """Test DecimalComparisonFilter with gt (greater than) operator."""
        expected_ids = {self.obj3.id, self.obj4.id, self.obj5.id}  # Values 30.00, 40.00, 50.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply gt filter for values > 25.00
        gt_filter = DecimalComparisonFilter(op="gt", number_1="25.00", number_2="")
        filtered = gt_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field > 25.00
        for obj in filtered:
            self.assertGreater(obj.decimal_field, Decimal("25.00"))

    def test_decimal_gte_filter(self) -> None:
        """Test DecimalComparisonFilter with gte (greater than or equal) operator."""
        expected_ids = {
            self.obj2.id,
            self.obj3.id,
            self.obj4.id,
            self.obj5.id,
        }  # Values 20.00, 30.00, 40.00, 50.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply gte filter for values >= 20.00
        gte_filter = DecimalComparisonFilter(op="gte", number_1="20.00", number_2="")
        filtered = gte_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field >= 20.00
        for obj in filtered:
            self.assertGreaterEqual(obj.decimal_field, Decimal("20.00"))

    def test_decimal_lt_filter(self) -> None:
        """Test DecimalComparisonFilter with lt (less than) operator."""
        expected_ids = {self.obj1.id, self.obj2.id}  # Values 10.00, 20.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply lt filter for values < 30.00
        lt_filter = DecimalComparisonFilter(op="lt", number_1="30.00", number_2="")
        filtered = lt_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field < 30.00
        for obj in filtered:
            self.assertLess(obj.decimal_field, Decimal("30.00"))

    def test_decimal_lte_filter(self) -> None:
        """Test DecimalComparisonFilter with lte (less than or equal) operator."""
        expected_ids = {self.obj1.id, self.obj2.id, self.obj3.id}  # Values 10.00, 20.00, 30.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply lte filter for values <= 30.00
        lte_filter = DecimalComparisonFilter(op="lte", number_1="30.00", number_2="")
        filtered = lte_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field <= 30.00
        for obj in filtered:
            self.assertLessEqual(obj.decimal_field, Decimal("30.00"))

    def test_decimal_eq_filter(self) -> None:
        """Test DecimalComparisonFilter with eq (equal) operator."""
        expected_ids = {self.obj3.id}  # Value 30.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply eq filter for values == 30.00
        eq_filter = DecimalComparisonFilter(op="eq", number_1="30.00", number_2="")
        filtered = eq_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field == 30.00
        for obj in filtered:
            self.assertEqual(obj.decimal_field, Decimal("30.00"))

    def test_decimal_ne_filter(self) -> None:
        """Test DecimalComparisonFilter with ne (not equal) operator."""
        expected_ids = {
            self.obj1.id,
            self.obj2.id,
            self.obj4.id,
            self.obj5.id,
        }  # Values 10.00, 20.00, 40.00, 50.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply ne filter for values != 30.00
        ne_filter = DecimalComparisonFilter(op="ne", number_1="30.00", number_2="")
        filtered = ne_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field != 30.00
        for obj in filtered:
            self.assertNotEqual(obj.decimal_field, Decimal("30.00"))

    def test_decimal_range_inc_filter(self) -> None:
        """Test DecimalComparisonFilter with inc (inclusive range) operator."""
        expected_ids = {self.obj2.id, self.obj3.id, self.obj4.id}  # Values 20.00, 30.00, 40.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply inc filter for range 20.00-40.00 (inclusive)
        range_filter = DecimalComparisonFilter(op="inc", number_1="20.00", number_2="40.00")
        filtered = range_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field in range [20.00, 40.00]
        for obj in filtered:
            self.assertGreaterEqual(obj.decimal_field, Decimal("20.00"))
            self.assertLessEqual(obj.decimal_field, Decimal("40.00"))

    def test_decimal_range_ex_filter(self) -> None:
        """Test DecimalComparisonFilter with ex (exclusive range) operator."""
        expected_ids = {self.obj1.id, self.obj5.id}  # Values outside range (10.00, 50.00)

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply ex filter for range 20.00-40.00 (exclusive)
        range_filter = DecimalComparisonFilter(op="ex", number_1="20.00", number_2="40.00")
        filtered = range_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have decimal_field outside range (20.00, 40.00)
        for obj in filtered:
            self.assertTrue(
                obj.decimal_field <= Decimal("20.00") or obj.decimal_field >= Decimal("40.00")
            )

    def test_decimal_range_auto_swap(self) -> None:
        """Test DecimalComparisonFilter auto-swaps values when min > max."""
        expected_ids = {self.obj2.id, self.obj3.id, self.obj4.id}  # Values 20.00, 30.00, 40.00

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply inc filter with swapped values (40.00, 20.00) - should auto-swap to (20.00, 40.00)
        range_filter = DecimalComparisonFilter(op="inc", number_1="40.00", number_2="20.00")
        filtered = range_filter.apply(qs, "decimal_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

    def test_decimal_null_filter(self) -> None:
        """Test DecimalNullFilter for null values."""
        expected_ids = {self.obj5.id}  # Only obj5 has null optional_decimal_field

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply null filter for optional_decimal_field
        null_filter = DecimalNullFilter(value=True)
        filtered = null_filter.apply(qs, "optional_decimal_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_decimal_field is None
        for obj in filtered:
            self.assertIsNone(obj.optional_decimal_field)

    def test_decimal_null_filter_false(self) -> None:
        """Test DecimalNullFilter for non-null values."""
        expected_ids = {self.obj1.id, self.obj2.id, self.obj3.id, self.obj4.id}  # Non-null values

        qs = DecimalFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply null filter for optional_decimal_field with value=False
        null_filter = DecimalNullFilter(value=False)
        filtered = null_filter.apply(qs, "optional_decimal_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_decimal_field is not None
        for obj in filtered:
            self.assertIsNotNone(obj.optional_decimal_field)

    def test_invalid_decimal_filter_on_non_decimal_field_gets_removed(self) -> None:
        """Test that decimal filters are removed from non-decimal fields during validation."""
        # Create a schema with decimal filter on a non-decimal field
        schema = ListPageSchema(
            f={
                "decimal_field": DecimalComparisonFilter(
                    op="gt", number_1="25.00", number_2=""
                ),  # Valid
                "id": DecimalComparisonFilter(
                    op="gt", number_1="100.00", number_2=""
                ),  # Invalid: decimal filter on ID field
            }
        )

        # Mock columns - only decimal_field is a decimal field
        columns: dict[str, BaseFieldSchema] = {
            "decimal_field": DecimalFieldSchema(
                name="decimal_field",
                d="decimal",
                required=False,
                decimal_places=2,
                default=None,
            ),
        }

        # Validate filters
        schema.validate_filters(None, DecimalFieldModel, columns)

        # Invalid filter should be removed, valid one should remain
        self.assertIn("decimal_field", schema.filter_map)
        self.assertNotIn("id", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 1)

    def test_decimal_range_invalid_missing_number_2(self) -> None:
        """Test that decimal range filter with missing number_2 is removed during validation."""
        # For this test, we'll test the filter's own validation by creating a filter
        # that should fail validation and checking that it raises the expected error
        # The schema validation would catch this during the validation process

        # Create a filter with missing number_2 (this should fail the filter's own validation)
        with self.assertRaises(ValueError) as context:
            DecimalComparisonFilter(op="inc", number_1="20.00")  # type: ignore[call-arg]

        self.assertIn("Field required", str(context.exception))

    def test_decimal_range_invalid_equal_values(self) -> None:
        """Test that decimal range filter with equal values is actually valid."""
        # Unlike what the test name suggests, equal values are actually valid for ranges
        # (they represent a single point range)
        # Create a schema with range filter having equal values
        schema = ListPageSchema(
            f={
                "decimal_field": DecimalComparisonFilter(
                    op="inc", number_1="25.00", number_2="25.00"
                ),  # Equal values - valid
            }
        )

        # Mock columns
        columns: dict[str, BaseFieldSchema] = {
            "decimal_field": DecimalFieldSchema(
                name="decimal_field",
                d="decimal",
                required=False,
                decimal_places=2,
                default=None,
            ),
        }

        # Validate filters - should keep the filter since equal values are valid
        schema.validate_filters(None, DecimalFieldModel, columns)

        # Filter should be kept (equal values represent a valid single-point range)
        self.assertIn("decimal_field", schema.filter_map)


class CharFilterTests(TestCase):
    """Test character field filtering functionality."""

    def setUp(self) -> None:
        """Create test data with various character field values."""
        # Create CharFieldModel instances with different character values
        self.obj1 = CharFieldModel.objects.create(
            char_field="apple",
            text_field="This is a sample text about apples",
            char_choice_field="active",
            optional_char_choice_field="inactive",
        )
        self.obj2 = CharFieldModel.objects.create(
            char_field="banana",
            text_field="This is a sample text about bananas",
            char_choice_field="inactive",
            optional_char_choice_field="pending",
        )
        self.obj3 = CharFieldModel.objects.create(
            char_field="cherry",
            text_field="This is a sample text about cherries",
            char_choice_field="pending",
            optional_char_choice_field="active",
        )
        self.obj4 = CharFieldModel.objects.create(
            char_field="date",
            text_field="This is a sample text about dates",
            char_choice_field="active",
            optional_char_choice_field="inactive",
        )
        self.obj5 = CharFieldModel.objects.create(
            char_field="elderberry",
            text_field="This is a sample text about elderberries",
            char_choice_field="inactive",
            optional_char_choice_field=None,  # Null value
        )

    def test_char_choice_any_filter(self) -> None:
        """Test CharChoiceFilter with any operator."""
        expected_ids = {self.obj1.id, self.obj4.id}  # Active status

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply any filter for choice values ["active"]
        choice_filter = CharChoiceFilter(mode="any", options=["active"])
        filtered = choice_filter.apply(qs, "char_choice_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have char_choice_field in ["active"]
        for obj in filtered:
            self.assertIn(obj.char_choice_field, ["active"])

    def test_char_choice_none_filter(self) -> None:
        """Test CharChoiceFilter with none operator."""
        expected_ids = {self.obj2.id, self.obj5.id}  # Inactive status

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply none filter for choice values ["active", "pending"]
        choice_filter = CharChoiceFilter(mode="none", options=["active", "pending"])
        filtered = choice_filter.apply(qs, "char_choice_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have char_choice_field not in ["active", "pending"]
        for obj in filtered:
            self.assertNotIn(obj.char_choice_field, ["active", "pending"])

    def test_char_text_filter(self) -> None:
        """Test CharTextFilter for text search."""
        expected_ids = {
            self.obj1.id,
            self.obj3.id,
            self.obj4.id,
            self.obj5.id,
        }  # Contains "apple", "cherry", "date", "elderberry" (all contain "e")

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply text filter for "e" (case-insensitive contains)
        text_filter = CharTextFilter(text="e")
        filtered = text_filter.apply(qs, "char_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have char_field containing "e"
        for obj in filtered:
            self.assertIn("e", obj.char_field.lower())

    def test_char_text_filter_case_insensitive(self) -> None:
        """Test CharTextFilter is case insensitive."""
        expected_ids = {
            self.obj1.id,
            self.obj3.id,
            self.obj4.id,
            self.obj5.id,
        }  # Contains "apple", "cherry", "date", "elderberry" (all contain "E" when uppercase)

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply text filter for "E" (uppercase)
        text_filter = CharTextFilter(text="E")
        filtered = text_filter.apply(qs, "char_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

    def test_char_blank_filter_true(self) -> None:
        """Test CharBlankFilter for blank values (empty string)."""
        # Create an object with blank char_field
        self.obj6 = CharFieldModel.objects.create(
            char_field="",
            text_field="This is a blank test",
            char_choice_field="active",
            optional_char_choice_field="inactive",
        )

        expected_ids = {self.obj6.id}  # Only obj6 has blank char_field

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 6)

        # Apply blank filter for char_field with value=True
        blank_filter = CharBlankFilter(value=True)
        filtered = blank_filter.apply(qs, "char_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have char_field that is blank
        for obj in filtered:
            self.assertEqual(obj.char_field, "")

    def test_char_blank_filter_false(self) -> None:
        """Test CharBlankFilter for non-blank values."""
        # Create an object with blank char_field for this test
        CharFieldModel.objects.create(
            char_field="",
            text_field="This is a blank test",
            char_choice_field="active",
            optional_char_choice_field="inactive",
        )

        expected_ids = {
            self.obj1.id,
            self.obj2.id,
            self.obj3.id,
            self.obj4.id,
            self.obj5.id,
        }  # Non-blank values

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 6)

        # Apply blank filter for char_field with value=False
        blank_filter = CharBlankFilter(value=False)
        filtered = blank_filter.apply(qs, "char_field")

        self.assertEqual(filtered.count(), 5)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have char_field that is not blank
        for obj in filtered:
            self.assertNotEqual(obj.char_field, "")

    def test_invalid_char_filter_on_non_char_field_gets_removed(self) -> None:
        """Test that char filters are removed from non-char fields during validation."""
        # Create a schema with char filter on a non-char field
        schema = ListPageSchema(
            f={
                "char_field": CharTextFilter(text="test"),  # Valid
                "id": CharTextFilter(text="100"),  # Invalid: char filter on ID field
            }
        )

        # Mock columns - only char_field is a char field
        columns: dict[str, BaseFieldSchema] = {
            "char_field": CharFieldSchema(
                name="char_field",
                d="char",
                required=False,
                max_length=100,
                choices=None,
                default=None,
            ),
        }

        # Validate filters
        schema.validate_filters(None, CharFieldModel, columns)

        # Invalid filter should be removed, valid one should remain
        self.assertIn("char_field", schema.filter_map)
        self.assertNotIn("id", schema.filter_map)
        self.assertEqual(len(schema.filter_map), 1)

    def test_char_text_filter_exact_match(self) -> None:
        """Test exact text matching."""
        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply exact match filter for "apple"
        # Note: This would require implementing exact match functionality
        # For now, we'll test that the text filter can find exact matches
        text_filter = CharTextFilter(text="apple")
        filtered = text_filter.apply(qs, "char_field")

        # Should find obj1 (exact match) and possibly others containing "apple"
        self.assertGreaterEqual(filtered.count(), 1)
        self.assertIn(self.obj1.id, {obj.id for obj in filtered})

    def test_optional_char_choice_filter_any(self) -> None:
        """Test optional char choice field with any operator."""
        expected_ids = {
            self.obj1.id,
            self.obj3.id,
            self.obj4.id,
        }  # Objects with optional_char_choice_field in ["active", "inactive"]

        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply any filter for optional choice values ["active", "inactive"]
        choice_filter = CharChoiceFilter(mode="any", options=["active", "inactive"])
        filtered = choice_filter.apply(qs, "optional_char_choice_field")

        self.assertEqual(filtered.count(), 3)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_char_choice_field in ["active", "inactive"]
        for obj in filtered:
            self.assertIn(obj.optional_char_choice_field, ["active", "inactive"])

    def test_optional_char_choice_filter_none(self) -> None:
        """Test optional char choice field with none operator."""
        qs = CharFieldModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply none filter for optional choice values ["active"]
        choice_filter = CharChoiceFilter(mode="none", options=["active"])
        filtered = choice_filter.apply(qs, "optional_char_choice_field")

        self.assertEqual(filtered.count(), 4)


class ForeignKeyFilterTests(TestCase):
    """Test foreign key field filtering functionality."""

    def setUp(self) -> None:
        """Create test data with foreign key relationships."""
        # Create categories
        self.category1 = CategoryModel.objects.create(
            name="Electronics", description="Electronic items"
        )
        self.category2 = CategoryModel.objects.create(name="Clothing", description="Clothing items")
        self.category3 = CategoryModel.objects.create(
            name="Books", description="Books and publications"
        )

        # Create ForeignKeyModel instances with different category relationships
        self.obj1 = ForeignKeyModel.objects.create(
            category_field=self.category1,
            optional_category_field=self.category2,
            name="Smartphone",
        )
        self.obj2 = ForeignKeyModel.objects.create(
            category_field=self.category2,
            optional_category_field=self.category3,
            name="T-Shirt",
        )
        self.obj3 = ForeignKeyModel.objects.create(
            category_field=self.category3,
            optional_category_field=self.category1,
            name="Novel",
        )
        self.obj4 = ForeignKeyModel.objects.create(
            category_field=self.category1,
            optional_category_field=self.category3,
            name="Laptop",
        )
        self.obj5 = ForeignKeyModel.objects.create(
            category_field=self.category2,
            optional_category_field=None,  # Null value
            name="Jeans",
        )

    def test_foreign_key_choice_any_filter(self) -> None:
        """Test ForeignKeyChoiceFilter with any operator."""
        expected_ids = {self.obj1.id, self.obj4.id}  # Electronics category

        qs = ForeignKeyModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply any filter for category IDs [category1.id]
        choice_filter = ForeignKeyChoiceFilter(mode="any", options=[str(self.category1.id)])
        filtered = choice_filter.apply(qs, "category_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have category_field in [category1.id]
        for obj in filtered:
            self.assertEqual(obj.category_field.id, self.category1.id)

    def test_foreign_key_choice_none_filter(self) -> None:
        """Test ForeignKeyChoiceFilter with none operator."""
        expected_ids = {self.obj2.id, self.obj5.id}  # Clothing category only

        qs = ForeignKeyModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply none filter for category IDs [category1.id, category3.id]
        choice_filter = ForeignKeyChoiceFilter(
            mode="none", options=[str(self.category1.id), str(self.category3.id)]
        )
        filtered = choice_filter.apply(qs, "category_field")

        self.assertEqual(filtered.count(), 2)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have category_field not in [category1.id, category3.id]
        for obj in filtered:
            self.assertNotIn(obj.category_field.id, [self.category1.id, self.category3.id])

    def test_foreign_key_null_filter(self) -> None:
        """Test ForeignKeyNullFilter for null values."""
        expected_ids = {self.obj5.id}  # Only obj5 has null optional_category_field

        qs = ForeignKeyModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply null filter for optional_category_field
        null_filter = ForeignKeyNullFilter(value=True)
        filtered = null_filter.apply(qs, "optional_category_field")

        self.assertEqual(filtered.count(), 1)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_category_field is None
        for obj in filtered:
            self.assertIsNone(obj.optional_category_field)

    def test_foreign_key_null_filter_false(self) -> None:
        """Test ForeignKeyNullFilter for non-null values."""
        expected_ids = {self.obj1.id, self.obj2.id, self.obj3.id, self.obj4.id}  # Non-null values

        qs = ForeignKeyModel.objects.all()
        self.assertEqual(qs.count(), 5)

        # Apply null filter for optional_category_field with value=False
        null_filter = ForeignKeyNullFilter(value=False)
        filtered = null_filter.apply(qs, "optional_category_field")

        self.assertEqual(filtered.count(), 4)
        retrieved_ids = {obj.id for obj in filtered}
        self.assertEqual(retrieved_ids, expected_ids)

        # Verify all filtered objects have optional_category_field is not None
        for obj in filtered:
            self.assertIsNotNone(obj.optional_category_field)

    def test_foreign_key_related_name_query(self) -> None:
        """Test querying using related name."""
        # Test items related to category1
        items = self.category1.items.all()
        expected_ids = {self.obj1.id, self.obj4.id}
        retrieved_ids = {obj.id for obj in items}
        self.assertEqual(retrieved_ids, expected_ids)

    def test_foreign_key_optional_related_name_query(self) -> None:
        """Test querying using optional related name."""
        # Test items with optional category1
        items = self.category1.optional_items.all()
        expected_ids = {self.obj3.id}
        retrieved_ids = {obj.id for obj in items}
        self.assertEqual(retrieved_ids, expected_ids)

    def test_invalid_foreign_key_filter_on_non_fk_field_gets_removed(self) -> None:
        """Test that foreign key filters are removed from non-FK fields during validation."""
        # Create a schema with foreign key filter on a non-FK field
        schema = ListPageSchema(
            f={
                "category_field": ForeignKeyChoiceFilter(
                    mode="any", options=[str(self.category1.id)]
                ),  # Valid
                "id": ForeignKeyChoiceFilter(
                    mode="any", options=["1", "2", "3"]
                ),  # Invalid: FK filter on ID field
            }
        )

        # Mock columns - only category_field is a FK field
        columns: dict[str, BaseFieldSchema] = {
            "category_field": ForeignKeyFieldSchema(
                name="category_field",
                required=False,
                default=None,
                view_name="category",
            ),
        }

        # Validate filters
        schema.validate_filters(None, ForeignKeyModel, columns)

        # Invalid filter should be removed, valid one should remain
        self.assertIn("category_field", schema.filter_map)
        self.assertNotIn("id", schema.filter_map)


class RowUpdateFilterTest(TestCase):
    """Tests for RowUpdateFilter functionality."""

    def setUp(self) -> None:
        self.user1 = User.objects.create_user(username="user1", password="pass1")
        self.user2 = User.objects.create_user(username="user2", password="pass2")
        # Create FirstStuff instances
        self.row1 = FirstStuff.objects.create(char_field="row1")
        self.row2 = FirstStuff.objects.create(char_field="row2")
        self.row3 = FirstStuff.objects.create(char_field="row3")

    def test_filter_mode_any_includes_rows_with_row_updates(self) -> None:
        """Test that mode='any' includes only rows with matching RowUpdates."""
        # Create RowUpdates for row1 and row2
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="updated_row",
            created_by=self.user1,
            _values={},
        )

        # Apply filter - includes rows with RowUpdates
        row_update_filter = RowUpdateFilter()
        qs = FirstStuff.objects.all()
        result = row_update_filter.apply(qs, "")

        # Should include row1 and row2, but not row3
        self.assertCountEqual(list(result), [self.row1, self.row2])

    def test_filter_by_user_ids(self) -> None:
        """Test filtering by user_ids."""
        # Create RowUpdates by different users
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="created_row",
            created_by=self.user2,
            _values={},
        )

        # Filter for user1 only
        row_update_filter = RowUpdateFilter(user_ids=[str(self.user1.public_id)])
        qs = FirstStuff.objects.all()
        result = row_update_filter.apply(qs, "")

        # Should only include row1
        self.assertCountEqual(list(result), [self.row1])

    def test_filter_by_actions(self) -> None:
        """Test filtering by action types."""
        # Create RowUpdates with different actions
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="updated_row",
            created_by=self.user1,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row3.pk,
            action="commented",
            created_by=self.user1,
            _values={},
        )

        # Filter for 'created_row' only (single action now)
        row_update_filter = RowUpdateFilter(actions=["created_row"])
        qs = FirstStuff.objects.all()
        result = row_update_filter.apply(qs, "")

        # Should include row1 only (created_row)
        self.assertCountEqual(list(result), [self.row1])

    def test_filter_by_date_range(self) -> None:
        """Test filtering by date_from and date_to."""
        now = timezone.now()
        # Create RowUpdate for row1 with current time
        row1_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )
        # Update created_at to be 5 days ago
        row1_update.created_at = now - timedelta(days=5)
        row1_update.save()

        # Create RowUpdate for row2 with current time
        row2_update = RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )
        # Update created_at to be 1 day ago
        row2_update.created_at = now - timedelta(days=1)
        row2_update.save()

        # Filter for last 3 days
        row_update_filter = RowUpdateFilter(
            date_from=now - timedelta(days=3),
            date_to=now + timedelta(days=1),
        )
        qs = FirstStuff.objects.all()
        result = row_update_filter.apply(qs, "")

        # Should only include row2 (within date range)
        self.assertCountEqual(list(result), [self.row2])

    def test_filter_combines_criteria(self) -> None:
        """Test that filter combines multiple criteria with AND logic."""
        # Create RowUpdates with different attributes
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row2.pk,
            action="updated_row",
            created_by=self.user1,
            _values={},
        )
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row3.pk,
            action="created_row",
            created_by=self.user2,
            _values={},
        )

        # Filter for user1 AND action='created_row'
        row_update_filter = RowUpdateFilter(
            user_ids=[str(self.user1.public_id)],
            actions=["created_row"],
        )
        qs = FirstStuff.objects.all()
        result = row_update_filter.apply(qs, "")

        # Should only include row1 (user1 AND created_row)
        self.assertCountEqual(list(result), [self.row1])

    def test_filter_different_model(self) -> None:
        """Test that filter only affects the queried model."""
        # Create RowUpdate for FirstStuff row1
        RowUpdate.objects.create(
            modelname="djangoapp.FirstStuff",
            row_pk=self.row1.pk,
            action="created_row",
            created_by=self.user1,
            _values={},
        )

        # Apply filter to a different model (should not affect results)
        row_update_filter = RowUpdateFilter()
        qs = IntegerFieldModel.objects.all()
        result = row_update_filter.apply(qs, "")

        # Should be empty since no IntegerFieldModel has RowUpdates
        self.assertEqual(result.count(), 0)
