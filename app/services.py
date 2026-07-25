from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError

from app.config import Settings
from app.db import Database

logger = logging.getLogger(__name__)

MONTH_SECONDS = 30 * 24 * 60 * 60


class SubscriptionLinkError(RuntimeError):
    """Raised when Telegram cannot create a paid channel invite link."""


class SubscriptionLinkService:
    def __init__(self, bot: Bot, db: Database, settings: Settings) -> None:
        self.bot = bot
        self.db = db
        self.settings = settings
        self._lock = asyncio.Lock()

    @property
    def storage_key(self) -> str:
        return f"subscription_link:{self.settings.channel_id}:{self.settings.subscription_price}"

    async def get_or_create(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            if not force_refresh:
                cached = await self.db.get_value(self.storage_key)
                if cached:
                    return cached

            try:
                link = await self.bot.create_chat_subscription_invite_link(
                    chat_id=self.settings.channel_id,
                    name=self.settings.subscription_link_name,
                    subscription_period=MONTH_SECONDS,
                    subscription_price=self.settings.subscription_price,
                )
            except TelegramAPIError as exc:
                logger.exception("Failed to create Telegram channel subscription link")
                raise SubscriptionLinkError(str(exc)) from exc

            await self.db.set_value(self.storage_key, link.invite_link)
            return link.invite_link

    async def validate_channel_access(self) -> None:
        """Fail early when the configured chat or bot permissions are incorrect."""
        me = await self.bot.get_me()
        chat = await self.bot.get_chat(self.settings.channel_id)
        member = await self.bot.get_chat_member(self.settings.channel_id, me.id)

        if chat.type != ChatType.CHANNEL:
            raise SubscriptionLinkError("CHANNEL_ID must point to a Telegram channel")

        can_invite = getattr(member, "can_invite_users", False)
        if not can_invite:
            raise SubscriptionLinkError(
                "The bot must be a channel administrator with permission to invite users"
            )
