from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError

from bot.config import Settings
from bot.db import Database

logger = logging.getLogger(__name__)

SUBSCRIPTION_PERIOD_SECONDS = 30 * 24 * 60 * 60


class SubscriptionLinkError(RuntimeError):
    pass


class SubscriptionLinkService:
    def __init__(self, bot: Bot, db: Database, settings: Settings) -> None:
        self.bot = bot
        self.db = db
        self.settings = settings
        self._lock = asyncio.Lock()

    @property
    def cache_key(self) -> str:
        return (
            f"subscription_link:{self.settings.private_channel_id}:"
            f"{self.settings.subscription_price_stars}"
        )

    async def get_or_create(self, *, force: bool = False) -> str:
        async with self._lock:
            if not force:
                cached = await self.db.get_setting(self.cache_key)
                if cached:
                    return cached

            try:
                invite = await self.bot.create_chat_subscription_invite_link(
                    chat_id=self.settings.private_channel_id,
                    name=self.settings.subscription_link_name,
                    subscription_period=SUBSCRIPTION_PERIOD_SECONDS,
                    subscription_price=self.settings.subscription_price_stars,
                )
            except TelegramAPIError as exc:
                logger.exception("Telegram could not create a paid channel invite link")
                raise SubscriptionLinkError(str(exc)) from exc

            await self.db.set_setting(self.cache_key, invite.invite_link)
            return invite.invite_link

    async def validate_channel(self) -> None:
        me = await self.bot.get_me()
        chat = await self.bot.get_chat(self.settings.private_channel_id)
        member = await self.bot.get_chat_member(self.settings.private_channel_id, me.id)

        if chat.type != ChatType.CHANNEL:
            raise SubscriptionLinkError("PRIVATE_CHANNEL_ID должен указывать на канал")
        if not getattr(member, "can_invite_users", False):
            raise SubscriptionLinkError(
                "Бот должен быть администратором канала с правом приглашать пользователей"
            )
