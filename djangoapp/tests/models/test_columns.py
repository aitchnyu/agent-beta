from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from djangoapp.models.applications import ColumnType
from djangoapp.models.columns import (
    BooleanColumn,
    CharColumn,
    DateTimeColumn,
    DecimalColumn,
    ForeignKeyColumn,
    IntegerColumn,
    TextColumn,
    UserColumn,
)


class ColumnClassTests(SimpleTestCase):
    """Validation + row rendering for the typed Column classes.

    - test_name_is_positional_others_keyword_only, name positional; type opts keyword-only
    - test_char_requires_max_length, CharColumn without max_length raises TypeError
    - test_decimal_requires_precision, DecimalColumn without max_digits/places raises TypeError
    - test_decimal_places_exceeding_max_digits_rejected, places > digits raises ValueError
    - test_char_min_length_exceeding_max_length_rejected, min_length > max_length raises ValueError
    - test_invalid_name_rejected, names not matching COLUMN_NAME_RE raise ValueError
    - test_column_type_is_reported, each class reports its ColumnType
    - test_row_renders_char_fields, CharColumn.row() populates the char/text fields
    - test_row_renders_decimal_default, DecimalColumn.row() coerces default to Decimal
    - test_foreign_key_target_shape_validated, ForeignKeyColumn rejects a malformed target triple
    """

    def test_name_is_positional_others_keyword_only(self) -> None:
        """``name`` is positional; every other option is keyword-only."""
        col = CharColumn("code", max_length=10, default="X", nullable=True)
        self.assertEqual(col.name, "code")
        self.assertTrue(col.nullable)
        self.assertEqual(col.default, "X")

    def test_char_requires_max_length(self) -> None:
        """CharColumn without max_length raises (the field is required)."""
        with self.assertRaises(TypeError):
            CharColumn("code")  # type: ignore[call-arg]

    def test_decimal_requires_precision(self) -> None:
        """DecimalColumn requires both max_digits and decimal_places."""
        with self.assertRaises(TypeError):
            DecimalColumn("price")  # type: ignore[call-arg]

    def test_decimal_places_exceeding_max_digits_rejected(self) -> None:
        """decimal_places greater than max_digits is rejected."""
        with self.assertRaises(ValueError):
            DecimalColumn("price", max_digits=4, decimal_places=6)

    def test_char_min_length_exceeding_max_length_rejected(self) -> None:
        """min_length greater than max_length is rejected."""
        with self.assertRaises(ValueError):
            CharColumn("code", max_length=3, min_length=10)

    def test_invalid_name_rejected(self) -> None:
        """Names not matching COLUMN_NAME_RE (leading digit/punct/empty) raise ValueError."""
        for bad in ["1bad", "_x", "co-de"]:
            with self.subTest(name=bad), self.assertRaises(ValueError):
                CharColumn(bad, max_length=10)
        # Empty name is not a valid str for the positional name field.
        with self.assertRaises(ValueError):
            CharColumn("", max_length=10)

    def test_column_type_is_reported(self) -> None:
        """Each class reports the ColumnType it realises."""
        self.assertEqual(CharColumn("c", max_length=1).column_type, ColumnType.CHAR)
        self.assertEqual(TextColumn("c").column_type, ColumnType.TEXT)
        self.assertEqual(IntegerColumn("c").column_type, ColumnType.INTEGER)
        self.assertEqual(BooleanColumn("c").column_type, ColumnType.BOOLEAN)
        self.assertEqual(
            DecimalColumn("c", max_digits=5, decimal_places=2).column_type, ColumnType.DECIMAL
        )
        self.assertEqual(DateTimeColumn("c").column_type, ColumnType.DATETIME)
        self.assertEqual(UserColumn("c").column_type, ColumnType.USER)
        self.assertEqual(
            ForeignKeyColumn("c", target=("col", "app", "t")).column_type, ColumnType.FOREIGN_KEY
        )

    def test_row_renders_char_fields(self) -> None:
        """CharColumn.row() populates the shared char/text fields with its options."""
        row = CharColumn("code", max_length=12, default="X", min_length=2, choices=["X", "Y"]).row()
        self.assertEqual(row["name"], "code")
        self.assertEqual(row["type"], "char")
        self.assertEqual(row["text_max_length"], 12)
        self.assertEqual(row["text_min_length"], 2)
        self.assertEqual(row["text_default"], "X")
        self.assertEqual(row["char_choices"], ["X", "Y"])

    def test_row_renders_decimal_default(self) -> None:
        """DecimalColumn.row() coerces the default to Decimal and stores precision."""
        row = DecimalColumn("price", max_digits=8, decimal_places=2, default="1.50").row()
        self.assertEqual(row["type"], "decimal")
        self.assertEqual(row["decimal_default"], Decimal("1.50"))
        self.assertEqual(row["decimal_max_digits"], 8)
        self.assertEqual(row["decimal_places"], 2)

    def test_foreign_key_target_shape_validated(self) -> None:
        """Rejects a target that isn't a 3-tuple (values checked later, at resolve)."""
        for bad in [
            ("col", "app"),  # too few parts
            ("col", "app", "t", "x"),  # too many parts
            ["col", "app", "t"],  # a list, not a tuple
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ForeignKeyColumn("c", target=bad)  # type: ignore[arg-type]
