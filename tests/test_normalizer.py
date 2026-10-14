"""Unit tests for Russian phone number normalization."""

import re
import pytest
from app.normalizer import normalize_russian_phone


class TestRussianPhoneNormalization:
    @pytest.mark.parametrize(
        "raw_input, expected",
        [
            # Sample data formats
            ("+7 999 123-45-67", "+79991234567"),
            ("8 (999) 123 45 67", "+79991234567"),
            ("79991234567", "+79991234567"),
            ("8-916-000-00-01", "+79160000001"),
            ("+7 (916) 000 00 01", "+79160000001"),
            ("8 903 111 22 33", "+79031112233"),
            ("+79219998877", "+79219998877"),
            ("8 921 999 88 77", "+79219998877"),
            ("+7-926-123-45-67", "+79261234567"),
            ("8 (926) 123-45-67", "+79261234567"),
            ("8 999 111 00 00", "+79991110000"),
            ("+7 916 445 56 67", "+79164455667"),
            # Punctuation variations with dots and hyphens
            ("+7.926.123.45.67", "+79261234567"),
            ("8.926.123.45.67", "+79261234567"),
            ("+7(926)123-45-67", "+79261234567"),
            ("8(926)1234567", "+79261234567"),
        ],
    )
    def test_valid_11_digit_formats(self, raw_input, expected):
        normalized = normalize_russian_phone(raw_input)
        assert normalized == expected
        assert isinstance(normalized, str)
        assert normalized.startswith("+7")
        assert len(normalized) == 12
        assert normalized[1:].isdigit() and len(normalized[1:]) == 11
        assert re.match(r"^\+7[3-9]\d{9}$", normalized)

    @pytest.mark.parametrize(
        "raw_input, expected",
        [
            ("9005551212", "+79005551212"),
            ("(900) 555-12-12", "+79005551212"),
            ("916.000.00.01", "+79160000001"),
            ("4951234567", "+74951234567"),
            ("(495) 123-45-67", "+74951234567"),
            ("812-345-67-89", "+78123456789"),
            ("343-222-33-44", "+73432223344"),
        ],
    )
    def test_valid_10_digit_national_normalization(self, raw_input, expected):
        normalized = normalize_russian_phone(raw_input)
        assert normalized == expected
        assert isinstance(normalized, str)
        assert normalized.startswith("+7")
        assert len(normalized) == 12
        assert normalized[1:].isdigit() and len(normalized[1:]) == 11
        assert re.match(r"^\+7[3-9]\d{9}$", normalized)

    @pytest.mark.parametrize(
        "invalid_10_digit",
        [
            "0123456789",  # Starts with 0
            "1234567890",  # Starts with 1
            "2345678901",  # Starts with 2
            "(095) 123-45-67",
        ],
    )
    def test_invalid_10_digit_prefixes(self, invalid_10_digit):
        assert normalize_russian_phone(invalid_10_digit) is None

    @pytest.mark.parametrize(
        "raw_input",
        [
            "",
            "   ",
            None,
            12345,  # non-string type
            "123",
            "+7 999",
            "899",
            "799912345",  # 9 digits
        ],
    )
    def test_empty_and_short_phones(self, raw_input):
        assert normalize_russian_phone(raw_input) is None

    @pytest.mark.parametrize(
        "raw_input",
        [
            "не указан",
            "нет телефона",
            "call me",
            "N/A",
            "8 (999) 123-45-67 доб 12",
            "+7 999 123-45-6a",
            "phone: 79991234567",
            "+7 (999) 123-45-67!",
            "+7 (999) 123-45-67#",
        ],
    )
    def test_alphabetic_and_garbage_characters_rejected(self, raw_input):
        assert normalize_russian_phone(raw_input) is None

    @pytest.mark.parametrize(
        "raw_input",
        [
            "+1 555 123 4567",  # US 11-digit starting with 1
            "+44 7911 123456",  # UK 12-digit
            "+380 50 123 4567",  # Ukraine 12-digit
            "+7 999 123-45-67-89",  # 13 digits
            "799912345678",  # 12 digits
            "99991234567",  # 11 digits starting with 9
            "59991234567",  # 11 digits starting with 5
            "19991234567",  # 11 digits starting with 1
        ],
    )
    def test_unsupported_prefixes_and_too_long_phones(self, raw_input):
        assert normalize_russian_phone(raw_input) is None
