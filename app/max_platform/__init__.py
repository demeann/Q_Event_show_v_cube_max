"""Транспорт мессенджера MAX (Platform API)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.max_platform.client import MaxPlatformClient

__all__ = ["MaxPlatformClient"]


def __getattr__(name: str):
    if name == "MaxPlatformClient":
        from app.max_platform.client import MaxPlatformClient

        return MaxPlatformClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
