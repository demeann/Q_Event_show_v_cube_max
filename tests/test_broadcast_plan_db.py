"""Legacy: планировщик массовых рассылок отключён."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ensure_planned_broadcasts_is_noop(db_session):
    from datetime import datetime

    from app.services.broadcast_plan import ensure_planned_broadcasts

    n = await ensure_planned_broadcasts(db_session, now_naive=datetime(2026, 6, 1))
    assert n == 0
