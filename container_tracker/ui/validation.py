"""Validation for the SetupDialog fields.

Returns per-field error dicts (`{field_key: message}`) so the UI can surface
errors inline under each field. An empty dict means all fields are valid.
"""
from __future__ import annotations

import re


# Spec §5.3: API key regex is ^[0-9a-fA-F-]{30,40}$
API_KEY_PATTERN = re.compile(r"^[0-9a-fA-F\-]{30,40}$")

# Email: single @ and at least one . in the domain, no whitespace.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_setup_fields(company: str, api_key: str, email: str) -> dict[str, str]:
    """Validate the three setup fields. Returns `{field_key: message}` of failures.

    Empty dict means all valid — save button should be enabled.
    """
    errors: dict[str, str] = {}
    if not company.strip():
        errors["company"] = "Company name is required."
    if not api_key.strip():
        errors["api_key"] = "ShipsGo API key is required."
    elif not API_KEY_PATTERN.match(api_key.strip()):
        errors["api_key"] = (
            "That API key doesn't look right — check for extra spaces or missing characters."
        )
    if not email.strip():
        errors["email"] = "Contact email is required."
    elif not EMAIL_PATTERN.match(email.strip()):
        errors["email"] = "Enter a valid email address."
    return errors
