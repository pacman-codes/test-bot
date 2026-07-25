from pathlib import Path

import pytest

from bot.db import Database


@pytest.mark.asyncio
async def test_database_tracks_funnel_and_settings(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.init()

    await db.upsert_user(1, "alice", "Alice")
    await db.set_step(1, "inside", event="inside_view")
    await db.set_step(1, "offer", event="offer_view")
    await db.set_step(1, "subscription_link", event="subscription_link_requested")
    await db.set_setting("paid_link", "https://t.me/+example")

    assert await db.get_setting("paid_link") == "https://t.me/+example"

    stats = await db.get_stats()
    assert stats.total_users == 1
    assert stats.reached_inside == 1
    assert stats.reached_offer == 1
    assert stats.requested_subscription == 1
    assert stats.percent(1, 1) == 100.0
    assert stats.percent(0, 0) == 0.0
