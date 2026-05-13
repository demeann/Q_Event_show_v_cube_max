"""Проверка корпоративного email по whitelist доменов (без OTP в MVP)."""

from __future__ import annotations

from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email


@dataclass(frozen=True)
class EmailCheckResult:
    """Результат проверки строки email."""

    ok: bool
    reason: str
    normalized_email: str | None = None
    domain: str | None = None


def check_corporate_email(raw: str, allowed_domains: list[str]) -> EmailCheckResult:
    """Пустая строка, синтаксис RFC и домен из ``allowed_domains`` (уже в lowercase).

    ``reason``: ``ok`` | ``empty`` | ``invalid_format`` | ``domain_not_allowed``.
    """
    text = (raw or "").strip()
    if not text:
        return EmailCheckResult(ok=False, reason="empty")

    allowed = {d.strip().lower().lstrip("@") for d in allowed_domains if str(d).strip()}

    try:
        parsed = validate_email(text, check_deliverability=False)
    except EmailNotValidError:
        return EmailCheckResult(ok=False, reason="invalid_format")

    normalized = parsed.normalized
    domain = normalized.split("@", 1)[-1].lower()

    if domain not in allowed:
        return EmailCheckResult(
            ok=False,
            reason="domain_not_allowed",
            normalized_email=normalized,
            domain=domain,
        )

    return EmailCheckResult(
        ok=True,
        reason="ok",
        normalized_email=normalized,
        domain=domain,
    )
