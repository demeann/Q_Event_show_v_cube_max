"""Тесты whitelist-доменов для email."""

from __future__ import annotations

import pytest

from app.services.email_validation import check_corporate_email

_ALLOWED = ["pmru.com", "contracted.pmru.com"]


@pytest.mark.parametrize(
    ("raw", "ok", "reason", "domain"),
    [
        ("user@pmru.com", True, "ok", "pmru.com"),
        ("USER@PMRU.COM", True, "ok", "pmru.com"),
        ("  u@contracted.pmru.com ", True, "ok", "contracted.pmru.com"),
        ("", False, "empty", None),
        ("   ", False, "empty", None),
        ("not-an-email", False, "invalid_format", None),
        ("user@gmail.com", False, "domain_not_allowed", "gmail.com"),
        ("user@evilpmru.com", False, "domain_not_allowed", "evilpmru.com"),
        ("user@sub.pmru.com", False, "domain_not_allowed", "sub.pmru.com"),
    ],
)
def test_check_corporate_email(raw: str, ok: bool, reason: str, domain: str | None) -> None:
    r = check_corporate_email(raw, _ALLOWED)
    assert r.ok is ok
    assert r.reason == reason
    if r.ok:
        assert r.domain == domain
        assert r.normalized_email is not None
