"""Tests for setup-field validation."""
from __future__ import annotations

import pytest

from container_tracker.ui.validation import (
    API_KEY_PATTERN,
    EMAIL_PATTERN,
    validate_setup_fields,
)


class TestApiKeyPattern:
    @pytest.mark.parametrize("key", [
        "12345678-1234-1234-1234-123456789012",  # 36 chars with dashes
        "1234567890abcdefABCDEF1234567890abcd",  # 36 chars, mixed hex
        "a" * 30,                                 # 30 chars minimum
        "a" * 40,                                 # 40 chars maximum
        "ABCDEF1234567890" * 2 + "ABCDEF12",     # 40 chars exactly
    ])
    def test_accepts_valid_keys(self, key: str) -> None:
        assert API_KEY_PATTERN.match(key)

    @pytest.mark.parametrize("key", [
        "",
        "short",
        "a" * 29,           # too short
        "a" * 41,           # too long
        "contains-invalid-character-X-here!!",
        "12345 678 contains spaces",
    ])
    def test_rejects_invalid_keys(self, key: str) -> None:
        assert not API_KEY_PATTERN.match(key)


class TestEmailPattern:
    @pytest.mark.parametrize("email", [
        "user@example.com",
        "a.b@c.d",
        "first.last+tag@sub.example.co.uk",
    ])
    def test_accepts_valid_emails(self, email: str) -> None:
        assert EMAIL_PATTERN.match(email)

    @pytest.mark.parametrize("email", [
        "",
        "no-at-sign",
        "no-dot@example",
        "user@ example.com",   # space
        "@example.com",        # no local part
    ])
    def test_rejects_invalid_emails(self, email: str) -> None:
        assert not EMAIL_PATTERN.match(email)


class TestValidateSetupFields:
    def test_all_valid_returns_none(self) -> None:
        assert validate_setup_fields(
            company="Acme Imports",
            api_key="12345678-1234-1234-1234-123456789012",
            email="ops@acme.test",
        ) == {}

    def test_missing_company_returns_error_on_company_key(self) -> None:
        errors = validate_setup_fields(
            company="",
            api_key="12345678-1234-1234-1234-123456789012",
            email="ops@acme.test",
        )
        assert "company" in errors
        assert "required" in errors["company"].lower()

    def test_missing_api_key_returns_error_on_api_key(self) -> None:
        errors = validate_setup_fields(
            company="Acme",
            api_key="",
            email="ops@acme.test",
        )
        assert "api_key" in errors

    def test_malformed_api_key_returns_error_on_api_key(self) -> None:
        errors = validate_setup_fields(
            company="Acme",
            api_key="not-a-uuid",
            email="ops@acme.test",
        )
        assert "api_key" in errors

    def test_malformed_email_returns_error_on_email(self) -> None:
        errors = validate_setup_fields(
            company="Acme",
            api_key="12345678-1234-1234-1234-123456789012",
            email="not-an-email",
        )
        assert "email" in errors

    def test_multiple_errors_all_returned(self) -> None:
        errors = validate_setup_fields(company="", api_key="", email="")
        assert "company" in errors
        assert "api_key" in errors
        assert "email" in errors

    def test_whitespace_only_company_treated_as_missing(self) -> None:
        errors = validate_setup_fields(
            company="   ",
            api_key="12345678-1234-1234-1234-123456789012",
            email="ops@acme.test",
        )
        assert "company" in errors
