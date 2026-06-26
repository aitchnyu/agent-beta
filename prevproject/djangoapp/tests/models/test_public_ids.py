import re
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from django.test import TestCase

from djangoapp.models.base import BaseModel
from djangoapp.models.public_ids import (
    generate_sequence_id,
    validate_public_id_format,
)


def _dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


class ValidatePublicIdFormatTests(TestCase):
    def test_accepts_alphanumeric(self) -> None:
        validate_public_id_format("abc123")

    def test_accepts_hyphens_underscores(self) -> None:
        validate_public_id_format("hello_world-test")

    def test_accepts_uuid_format(self) -> None:
        validate_public_id_format(str(uuid.uuid7()))

    def test_rejects_spaces(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_id_format("hello world")

    def test_rejects_special_chars(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_id_format("hello@world")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_id_format("")


class GenerateUuid7IdTests(TestCase):
    def test_returns_string(self) -> None:
        result = BaseModel.generate_uuid7_id()
        self.assertIsInstance(result, str)

    def test_is_valid_uuid7(self) -> None:
        result = BaseModel.generate_uuid7_id()
        parsed = uuid.UUID(result)
        self.assertEqual(parsed.version, 7)

    def test_unique(self) -> None:
        ids = {BaseModel.generate_uuid7_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


class GenerateSequenceIdTests(TestCase):
    def test_basic_format(self) -> None:
        with patch("djangoapp.models.public_ids.timezone") as mock_tz:
            mock_tz.now.return_value = _dt(2026, 4, 30)
            result1 = generate_sequence_id("%Y-%m-%d-ID")()
            result2 = generate_sequence_id("%Y-%m-%d-ID")()
        self.assertTrue(result1.startswith("2026-04-30-"))
        self.assertTrue(result2.startswith("2026-04-30-"))
        seq1 = int(result1.split("-")[-1])
        seq2 = int(result2.split("-")[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_month_format(self) -> None:
        with patch("djangoapp.models.public_ids.timezone") as mock_tz:
            mock_tz.now.return_value = _dt(2026, 4, 15)
            result = generate_sequence_id("%Y-%m-ID")()
        self.assertRegex(result, r"2026-04-\d+")

    def test_start_parameter(self) -> None:
        with patch("djangoapp.models.public_ids.timezone") as mock_tz:
            mock_tz.now.return_value = _dt(2026, 4, 30)
            result = generate_sequence_id("%Y-%m-%d-ID", start=100)()
        self.assertTrue(result.startswith("2026-04-30-"))
        seq = int(result.split("-")[-1])
        self.assertGreaterEqual(seq, 100)

    def test_no_id_placeholder_raises(self) -> None:
        with self.assertRaises(ValueError):
            generate_sequence_id("%Y-%m-%d")

    def test_multiple_id_placeholders_raises(self) -> None:
        with self.assertRaises(ValueError):
            generate_sequence_id("ID-ID")

    def test_different_dates_different_sequences(self) -> None:
        with patch("djangoapp.models.public_ids.timezone") as mock_tz:
            mock_tz.now.return_value = _dt(2026, 4, 30)
            r1 = generate_sequence_id("%Y-%m-%d-ID")()
            mock_tz.now.return_value = _dt(2026, 5, 1)
            r2 = generate_sequence_id("%Y-%m-%d-ID")()
        self.assertTrue(r1.startswith("2026-04-30-"))
        self.assertTrue(r2.startswith("2026-05-01-"))

    def test_strftime_codes_supported(self) -> None:
        with patch("djangoapp.models.public_ids.timezone") as mock_tz:
            mock_tz.now.return_value = _dt(2026, 4, 30, 14, 30)
            result = generate_sequence_id("%Y-%m-%d-%H-ID")()
        self.assertRegex(result, r"2026-04-30-14-\d+")

    def test_url_friendly_output(self) -> None:
        with patch("djangoapp.models.public_ids.timezone") as mock_tz:
            mock_tz.now.return_value = _dt(2026, 4, 30)
            result = generate_sequence_id("%Y-%m-%d-ID")()
        self.assertTrue(re.fullmatch(r"[a-zA-Z0-9_\-]+", result))
