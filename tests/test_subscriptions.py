from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.config import Settings
from bot.db import Database
from bot.subscriptions import SubscriptionLinkService


class FakeBot:
    def __init__(self) -> None:
        self.calls = 0

    async def create_chat_subscription_invite_link(self, **kwargs):
        self.calls += 1
        assert kwargs["chat_id"] == -100123
        assert kwargs["subscription_period"] == 2_592_000
        assert kwargs["subscription_price"] == 250
        return SimpleNamespace(invite_link=f"https://t.me/+paid-{self.calls}")


@pytest.mark.asyncio
async def test_subscription_link_is_cached(tmp_path: Path) -> None:
    db = Database(tmp_path / "bot.sqlite3")
    await db.init()
    settings = Settings(
        bot_token="token",
        private_channel_id=-100123,
        subscription_price_stars=250,
        _env_file=None,
    )
    bot = FakeBot()
    service = SubscriptionLinkService(bot, db, settings)  # type: ignore[arg-type]

    first = await service.get_or_create()
    second = await service.get_or_create()
    refreshed = await service.get_or_create(force=True)

    assert first == second == "https://t.me/+paid-1"
    assert refreshed == "https://t.me/+paid-2"
    assert bot.calls == 2
