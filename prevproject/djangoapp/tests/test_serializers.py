import decimal
import typing
from typing import cast

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.test import TestCase
from django.utils import timezone

from djangoapp.models.app import SerializerTestModel
from djangoapp.models.base import annotate_fk_titles
from djangoapp.responses import (
    BooleanFieldContent,
    BooleanFieldInputSchema,
    BooleanFieldSchema,
    CharFieldContent,
    CharFieldInputSchema,
    CharFieldSchema,
    DateTimeFieldInputSchema,
    DateTimeFieldSchema,
    DecimalFieldInputSchema,
    DecimalFieldSchema,
    FileFieldInputSchema,
    FileFieldSchema,
    ForeignKeyFieldInputSchema,
    ForeignKeyFieldSchema,
    IntegerFieldContent,
    IntegerFieldInputSchema,
    IntegerFieldSchema,
    NullContent,
    TextFieldInputSchema,
    TextFieldSchema,
)
from djangoapp.serializers import (
    SCHEMA_SERIALIZERS,
    ForeignKeyTitleData,
    _default_val,
    _get_choice_title,
)


class SerializerHelperTests(TestCase):
    """Tests for serializer helper functions: _default_val, _get_choice_title."""

    def test_default_val_no_default_returns_none(self) -> None:
        """Field with no default returns None."""
        field = SerializerTestModel.raw_resolve_columns()["char_field"]
        result = _default_val(field)
        self.assertIsNone(result)

    def test_default_val_non_callable_returns_value(self) -> None:
        """Field with non-callable default returns the value."""
        field = SerializerTestModel.raw_resolve_columns()["char_with_default"]
        result = _default_val(field)
        self.assertEqual(result, "default_value")

    def test_default_val_callable_returns_called_result(self) -> None:
        """Field with callable default calls it and returns result."""
        field = SerializerTestModel.raw_resolve_columns()["integer_with_callable_default"]
        result = _default_val(field)
        self.assertEqual(result, 99)

    def test_get_choice_title_none_value_returns_none(self) -> None:
        """Returns None when value is None."""
        field = SerializerTestModel.raw_resolve_columns()["char_choice_field"]
        result = _get_choice_title(None, field)
        self.assertIsNone(result)

    def test_get_choice_title_no_choices_returns_none(self) -> None:
        """Returns None when field has no choices."""
        field = SerializerTestModel.raw_resolve_columns()["char_field"]
        result = _get_choice_title("a", field)
        self.assertIsNone(result)

    def test_get_choice_title_value_found_returns_label(self) -> None:
        """Returns label when value matches a choice."""
        field = SerializerTestModel.raw_resolve_columns()["char_choice_field"]
        result = _get_choice_title("a", field)
        self.assertEqual(result, "Option A")

    def test_get_choice_title_value_not_found_returns_none(self) -> None:
        """Returns None when value is not in choices."""
        field = SerializerTestModel.raw_resolve_columns()["char_choice_field"]
        result = _get_choice_title("z", field)
        self.assertIsNone(result)


class SchemaSerializerTests(TestCase):
    """Tests for SCHEMA_SERIALIZERS dictionary functions.

    Tests use dictionary lookups: SCHEMA_SERIALIZERS[type(field)](field)

    Returns BaseFieldSchema subclasses with field metadata for frontend rendering:
    - CharFieldSchema: name, required, max_length, choices (value/label pairs), default
    - TextFieldSchema: name, required, length, default
    - IntegerFieldSchema: name, required, choices (string values), default
    - BooleanFieldSchema: name, required, default
    - DecimalFieldSchema: name, required, decimal_places, default
    - DateTimeFieldSchema: name, required, default
    - FileFieldSchema: name, required
    - ForeignKeyFieldSchema: name, required, view_name

    Tests verify correct schema type, field name, required status, and type-specific attributes.
    """

    # ----- CharField Schema Tests -----
    def test_char_field_to_schema_basic(self) -> None:
        """Basic CharField without choices."""
        field = SerializerTestModel.raw_resolve_columns()["char_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, CharFieldSchema)
        assert isinstance(result, CharFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "char_field")
        self.assertFalse(result.required)
        self.assertEqual(result.max_length, 100)
        self.assertIsNone(result.choices)
        self.assertIsNone(result.default)

    def test_char_field_to_schema_with_choices(self) -> None:
        """CharField with choices."""
        field = SerializerTestModel.raw_resolve_columns()["char_choice_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, CharFieldSchema)
        assert isinstance(result, CharFieldSchema)  # type narrowing for mypy
        self.assertEqual(
            result.choices,
            [{"value": "a", "label": "Option A"}, {"value": "b", "label": "Option B"}],
        )

    def test_char_field_to_schema_with_default(self) -> None:
        """CharField with default value."""
        field = SerializerTestModel.raw_resolve_columns()["char_with_default"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, CharFieldSchema)
        assert isinstance(result, CharFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.default, "default_value")

    # ----- TextField Schema Tests -----
    def test_text_field_to_schema_basic(self) -> None:
        """Basic TextField."""
        field = SerializerTestModel.raw_resolve_columns()["text_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, TextFieldSchema)
        assert isinstance(result, TextFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "text_field")
        self.assertFalse(result.required)
        self.assertEqual(result.length, 1000)
        self.assertIsNone(result.default)

    # ----- IntegerField Schema Tests -----
    def test_integer_field_to_schema_basic(self) -> None:
        """IntegerField without choices."""
        field = SerializerTestModel.raw_resolve_columns()["integer_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, IntegerFieldSchema)
        assert isinstance(result, IntegerFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "integer_field")
        self.assertFalse(result.required)
        self.assertIsNone(result.choices)
        self.assertIsNone(result.default)

    def test_integer_field_to_schema_with_choices(self) -> None:
        """IntegerField with choices."""
        field = SerializerTestModel.raw_resolve_columns()["integer_choice_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, IntegerFieldSchema)
        assert isinstance(result, IntegerFieldSchema)  # type narrowing for mypy
        self.assertEqual(
            result.choices, [{"value": "1", "label": "One"}, {"value": "2", "label": "Two"}]
        )

    def test_integer_field_to_schema_with_default(self) -> None:
        """IntegerField with default value."""
        field = SerializerTestModel.raw_resolve_columns()["integer_with_default"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, IntegerFieldSchema)
        assert isinstance(result, IntegerFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.default, 42)

    # ----- BooleanField Schema Tests -----
    def test_boolean_field_to_schema(self) -> None:
        """BooleanField with default."""
        field = SerializerTestModel.raw_resolve_columns()["boolean_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, BooleanFieldSchema)
        assert isinstance(result, BooleanFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "boolean_field")
        self.assertEqual(result.default, False)

    # ----- DecimalField Schema Tests -----
    def test_decimal_field_to_schema(self) -> None:
        """DecimalField with decimal_places."""
        field = SerializerTestModel.raw_resolve_columns()["decimal_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, DecimalFieldSchema)
        assert isinstance(result, DecimalFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "decimal_field")
        self.assertFalse(result.required)
        self.assertEqual(result.decimal_places, 2)
        self.assertIsNone(result.default)

    # ----- DateTimeField Schema Tests -----
    def test_datetime_field_to_schema(self) -> None:
        """DateTimeField nullable."""
        field = SerializerTestModel.raw_resolve_columns()["datetime_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, DateTimeFieldSchema)
        assert isinstance(result, DateTimeFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "datetime_field")
        self.assertFalse(result.required)
        self.assertIsNone(result.default)

    # ----- FileField Schema Tests -----
    def test_file_field_to_schema(self) -> None:
        """FileField nullable."""
        field = SerializerTestModel.raw_resolve_columns()["file_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, FileFieldSchema)
        assert isinstance(result, FileFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "file_field")
        self.assertFalse(result.required)

    # ----- ForeignKey Schema Tests -----
    def test_foreignkey_field_to_schema(self) -> None:
        """ForeignKey with model_to_viewname."""
        field = SerializerTestModel.raw_resolve_columns()["fk_field"]
        result = SCHEMA_SERIALIZERS[type(field)](field)
        self.assertIsInstance(result, ForeignKeyFieldSchema)
        assert isinstance(result, ForeignKeyFieldSchema)  # type narrowing for mypy
        self.assertEqual(result.name, "fk_field")
        self.assertFalse(result.required)
        # SerializerTestModel not registered with add_views(), so view_name is unregistered
        self.assertEqual(result.view_name, "__unregistered_SerializerTestModel__")


# ------------------ ValueWrapper Tests ---------------------


class ValueWrapperAsJsonTests(TestCase):
    """Tests for ValueWrapper.as_json() via value_wrappers().

    Each wrapper's as_json() returns a JSON-serializable value matching
    what the old JSON_VALUE_SERIALIZERS dict produced.

    - test_char_value: CharField returns the string or None
    - test_text_value: TextField returns the string or None
    - test_integer_value: IntegerField returns the int or None
    - test_boolean_value: BooleanField returns the bool or None
    - test_decimal_value_none: DecimalField returns None when null
    - test_decimal_value_present: DecimalField returns str(value)
    - test_datetime_value_none: DateTimeField returns None when null
    - test_datetime_value_aware: DateTimeField returns ISO string
    - test_file_value_none: FileField returns None when no file
    - test_file_value_present: FileField returns {filename, download_url}
    - test_fk_value_none: ForeignKey returns None when null
    - test_fk_value_present: ForeignKey returns {id, text} via fallback query
    """

    def _wrappers(self, instance: SerializerTestModel) -> dict[str, typing.Any]:
        columns = list(instance.raw_resolve_columns().values())
        return instance.value_wrappers(columns)

    def test_char_value(self) -> None:
        """CharField wrapper returns string value."""
        instance = SerializerTestModel(char_field="hello")
        wrappers = self._wrappers(instance)
        self.assertEqual(wrappers["char_field"].as_json(), "hello")

    def test_text_value(self) -> None:
        """TextField wrapper returns string value."""
        instance = SerializerTestModel(text_field="long text")
        wrappers = self._wrappers(instance)
        self.assertEqual(wrappers["text_field"].as_json(), "long text")

    def test_integer_value(self) -> None:
        """IntegerField wrapper returns int value."""
        instance = SerializerTestModel(integer_field=42)
        wrappers = self._wrappers(instance)
        self.assertEqual(wrappers["integer_field"].as_json(), 42)

    def test_boolean_value(self) -> None:
        """BooleanField wrapper returns bool value."""
        instance = SerializerTestModel(boolean_field=True)
        wrappers = self._wrappers(instance)
        self.assertEqual(wrappers["boolean_field"].as_json(), True)

    def test_decimal_value_none(self) -> None:
        """DecimalField wrapper returns None when null."""
        instance = SerializerTestModel(decimal_field=None)
        wrappers = self._wrappers(instance)
        self.assertIsNone(wrappers["decimal_field"].as_json())

    def test_decimal_value_present(self) -> None:
        """DecimalField wrapper returns stringified decimal."""
        instance = SerializerTestModel(decimal_field=decimal.Decimal("19.99"))
        wrappers = self._wrappers(instance)
        self.assertEqual(wrappers["decimal_field"].as_json(), "19.99")

    def test_datetime_value_none(self) -> None:
        """DateTimeField wrapper returns None when null."""
        instance = SerializerTestModel(datetime_field=None)
        wrappers = self._wrappers(instance)
        self.assertIsNone(wrappers["datetime_field"].as_json())

    def test_datetime_value_aware(self) -> None:
        """DateTimeField wrapper returns ISO format string."""
        aware_dt = timezone.now()
        instance = SerializerTestModel(datetime_field=aware_dt)
        wrappers = self._wrappers(instance)
        result = wrappers["datetime_field"].as_json()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("T", str(result))

    def test_file_value_none(self) -> None:
        """FileField wrapper returns None when no file."""
        instance = SerializerTestModel(file_field=None)
        wrappers = self._wrappers(instance)
        self.assertIsNone(wrappers["file_field"].as_json())

    def test_file_value_present(self) -> None:
        """FileField wrapper returns dict with filename and download_url."""
        uploaded_file = SimpleUploadedFile("test.txt", b"content")
        instance = SerializerTestModel.objects.create(file_field=uploaded_file)
        wrappers = self._wrappers(instance)
        result = wrappers["file_field"].as_json()
        self.assertIsNotNone(result)
        result_dict = cast(dict[str, str], result)
        self.assertIn("filename", result_dict)
        self.assertIn("download_url", result_dict)
        instance.delete()

    def test_fk_value_none(self) -> None:
        """ForeignKey wrapper returns None when null."""
        instance = SerializerTestModel(fk_field=None)
        wrappers = self._wrappers(instance)
        self.assertIsNone(wrappers["fk_field"].as_json())

    def test_fk_value_present(self) -> None:
        """ForeignKey wrapper returns {id, text} via annotate_fk_titles."""
        related = SerializerTestModel.objects.create(char_field="related")
        instance = SerializerTestModel.objects.create(fk_field=related)
        columns = list(instance.raw_resolve_columns().values())
        annotate_fk_titles(columns, [instance])
        wrappers = instance.value_wrappers(columns)
        result = wrappers["fk_field"].as_json()
        self.assertIsNotNone(result)
        result_dict = cast(dict[str, typing.Any], result)
        self.assertEqual(result_dict["id"], related.public_id)
        self.assertIn("text", result_dict)
        instance.delete()
        related.delete()


class ValueWrapperAsTdTests(TestCase):
    """Tests for ValueWrapper.as_td() via value_wrappers().

    Each wrapper's as_td() returns a BaseContent pydantic model suitable
    for table cell rendering, or NullContent when the value is None.

    - test_char_td: CharField produces CharFieldContent
    - test_char_td_none: None produces NullContent
    - test_integer_td: IntegerField produces IntegerFieldContent
    - test_boolean_td: BooleanField produces BooleanFieldContent
    """

    def _wrappers(self, instance: SerializerTestModel) -> dict[str, typing.Any]:
        columns = list(instance.raw_resolve_columns().values())
        return instance.value_wrappers(columns)

    def test_char_td(self) -> None:
        """CharField produces CharFieldContent with value."""
        instance = SerializerTestModel(char_field="hello")
        wrappers = self._wrappers(instance)
        td = wrappers["char_field"].as_td()
        self.assertIsInstance(td, CharFieldContent)

    def test_null_td(self) -> None:
        """None value produces NullContent."""
        instance = SerializerTestModel(integer_field=None)
        wrappers = self._wrappers(instance)
        td = wrappers["integer_field"].as_td()
        self.assertIsInstance(td, NullContent)

    def test_empty_char_td(self) -> None:
        """Empty string still produces CharFieldContent."""
        instance = SerializerTestModel(char_field="")
        wrappers = self._wrappers(instance)
        td = wrappers["char_field"].as_td()
        self.assertIsInstance(td, CharFieldContent)

    def test_integer_td(self) -> None:
        """IntegerField produces IntegerFieldContent."""
        instance = SerializerTestModel(integer_field=42)
        wrappers = self._wrappers(instance)
        td = wrappers["integer_field"].as_td()
        self.assertIsInstance(td, IntegerFieldContent)

    def test_boolean_td(self) -> None:
        """BooleanField produces BooleanFieldContent."""
        instance = SerializerTestModel(boolean_field=True)
        wrappers = self._wrappers(instance)
        td = wrappers["boolean_field"].as_td()
        self.assertIsInstance(td, BooleanFieldContent)


class ValueWrapperAsInputTests(TestCase):
    """Tests for ValueWrapper.as_input() via value_wrappers().

    Each wrapper's as_input() returns an InputSchema with a default field
    carrying the current value (or schema default).

    - test_char_input: CharField input has max_length and default from value
    - test_text_input: TextField input has length
    - test_integer_input: IntegerField input has no choices for plain field
    - test_integer_choice_input: IntegerField with choices preserves them
    - test_boolean_input: BooleanField input has correct default
    - test_decimal_input: DecimalField input has decimal_places and stringified default
    - test_datetime_input: DateTimeField input has ISO default or None
    - test_file_input_none: FileField input has None default when no file
    - test_file_input_present: FileField input has dict default with file info
    - test_fk_input: ForeignKey input has view_name

    Tests verify correct InputSchema variant type, component path, field name,
    discriminator, and type-specific fields including default from instance.
    """

    def _wrappers(self, instance: SerializerTestModel) -> dict[str, typing.Any]:
        columns = list(instance.raw_resolve_columns().values())
        return instance.value_wrappers(columns)

    def test_char_input(self) -> None:
        """CharField input preserves max_length and carries value as default."""
        instance = SerializerTestModel(char_field="test")
        wrappers = self._wrappers(instance)
        result = wrappers["char_field"].as_input()
        self.assertIsInstance(result, CharFieldInputSchema)
        assert isinstance(result, CharFieldInputSchema)
        self.assertEqual(result.name, "char_field")
        self.assertEqual(result.discriminator, "char")
        self.assertEqual(result.max_length, 100)
        self.assertEqual(result.default, "test")

    def test_text_input(self) -> None:
        """TextField input has length and value as default."""
        instance = SerializerTestModel(text_field="some text")
        wrappers = self._wrappers(instance)
        result = wrappers["text_field"].as_input()
        self.assertIsInstance(result, TextFieldInputSchema)
        assert isinstance(result, TextFieldInputSchema)
        self.assertEqual(result.name, "text_field")
        self.assertEqual(result.length, 1000)
        self.assertEqual(result.default, "some text")

    def test_integer_input(self) -> None:
        """IntegerField input has no choices and carries value as default."""
        instance = SerializerTestModel(integer_field=42)
        wrappers = self._wrappers(instance)
        result = wrappers["integer_field"].as_input()
        self.assertIsInstance(result, IntegerFieldInputSchema)
        assert isinstance(result, IntegerFieldInputSchema)
        self.assertEqual(result.name, "integer_field")
        self.assertIsNone(result.choices)
        self.assertEqual(result.default, 42)

    def test_integer_choice_input(self) -> None:
        """IntegerField with choices preserves them in input."""
        instance = SerializerTestModel(integer_choice_field=2)
        wrappers = self._wrappers(instance)
        result = wrappers["integer_choice_field"].as_input()
        self.assertIsInstance(result, IntegerFieldInputSchema)
        assert isinstance(result, IntegerFieldInputSchema)
        self.assertIsNotNone(result.choices)
        assert result.choices is not None
        self.assertEqual(len(result.choices), 2)

    def test_boolean_input(self) -> None:
        """BooleanField input carries current value as default."""
        instance = SerializerTestModel(boolean_field=True)
        wrappers = self._wrappers(instance)
        result = wrappers["boolean_field"].as_input()
        self.assertIsInstance(result, BooleanFieldInputSchema)
        assert isinstance(result, BooleanFieldInputSchema)
        self.assertEqual(result.default, True)

    def test_decimal_input(self) -> None:
        """DecimalField input has decimal_places and stringified default."""
        instance = SerializerTestModel(decimal_field=decimal.Decimal("5.50"))
        wrappers = self._wrappers(instance)
        result = wrappers["decimal_field"].as_input()
        self.assertIsInstance(result, DecimalFieldInputSchema)
        assert isinstance(result, DecimalFieldInputSchema)
        self.assertEqual(result.decimal_places, 2)
        self.assertEqual(result.default, "5.50")

    def test_datetime_input(self) -> None:
        """DateTimeField input has ISO string default or None."""
        instance = SerializerTestModel(datetime_field=None)
        wrappers = self._wrappers(instance)
        result = wrappers["datetime_field"].as_input()
        self.assertIsInstance(result, DateTimeFieldInputSchema)
        assert isinstance(result, DateTimeFieldInputSchema)
        self.assertIsNone(result.default)

    def test_file_input_none(self) -> None:
        """FileField input has None default when no file."""
        instance = SerializerTestModel(file_field=None)
        wrappers = self._wrappers(instance)
        result = wrappers["file_field"].as_input()
        self.assertIsInstance(result, FileFieldInputSchema)
        assert isinstance(result, FileFieldInputSchema)
        self.assertIsNone(result.default)

    def test_file_input_present(self) -> None:
        """FileField input has dict default with file info."""
        uploaded_file = SimpleUploadedFile("doc.txt", b"hello")
        instance = SerializerTestModel.objects.create(file_field=uploaded_file)
        wrappers = self._wrappers(instance)
        result = wrappers["file_field"].as_input()
        self.assertIsInstance(result, FileFieldInputSchema)
        assert isinstance(result, FileFieldInputSchema)
        self.assertIsNotNone(result.default)
        assert result.default is not None
        self.assertIn("filename", result.default)
        self.assertIn("download_url", result.default)
        instance.delete()

    def test_fk_input(self) -> None:
        """ForeignKey input has view_name."""
        instance = SerializerTestModel(fk_field=None)
        wrappers = self._wrappers(instance)
        result = wrappers["fk_field"].as_input()
        self.assertIsInstance(result, ForeignKeyFieldInputSchema)
        assert isinstance(result, ForeignKeyFieldInputSchema)
        self.assertEqual(result.name, "fk_field")
        self.assertEqual(result.discriminator, "foreignkey")
        self.assertEqual(result.view_name, "__unregistered_SerializerTestModel__")
        self.assertIsNone(result.default)


class AnnotateFkTitlesTests(TestCase):
    """Tests for annotate_fk_titles() standalone function.

    - test_populates_fk_titles: batch-fetches FK titles onto instances
    - test_nested_lookup: titles stored as nested dict by field name then pk
    - test_no_fk_columns: function is a no-op when no FK columns
    """

    def test_populates_fk_titles(self) -> None:
        """annotate_fk_titles populates _fk_titles on each row."""
        related = SerializerTestModel.objects.create(char_field="target")
        row1 = SerializerTestModel.objects.create(fk_field=related)
        row2 = SerializerTestModel.objects.create(fk_field=related)
        columns = list(SerializerTestModel.raw_resolve_columns().values())
        annotate_fk_titles(columns, [row1, row2])
        fk_titles = row1._fk_titles
        self.assertIsNotNone(fk_titles)
        assert fk_titles is not None
        field_titles = fk_titles.get("fk_field")
        self.assertIsNotNone(field_titles)
        assert field_titles is not None
        title_data = field_titles.get(related.pk)
        self.assertIsInstance(title_data, ForeignKeyTitleData)
        assert title_data is not None
        self.assertEqual(title_data.public_id, related.public_id)
        row1.delete()
        row2.delete()
        related.delete()

    def test_nested_lookup(self) -> None:
        """Titles stored as nested dict: _fk_titles[field_name][pk]."""
        related = SerializerTestModel.objects.create(char_field="nested")
        row = SerializerTestModel.objects.create(fk_field=related)
        columns = list(SerializerTestModel.raw_resolve_columns().values())
        annotate_fk_titles(columns, [row])
        fk_titles = row._fk_titles
        assert fk_titles is not None
        self.assertIn("fk_field", fk_titles)
        self.assertIn(related.pk, fk_titles["fk_field"])
        row.delete()
        related.delete()

    def test_no_fk_columns(self) -> None:
        """Function is a no-op when no FK columns present."""
        row = SerializerTestModel.objects.create()
        non_fk_columns = [
            f
            for f in SerializerTestModel.raw_resolve_columns().values()
            if not isinstance(f, models.ForeignKey)
        ]
        annotate_fk_titles(non_fk_columns, [row])
        fk_titles = row._fk_titles
        self.assertIsNotNone(fk_titles)
        assert fk_titles is not None
        self.assertEqual(len(fk_titles), 0)
        row.delete()
