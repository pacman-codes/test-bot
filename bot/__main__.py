import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import settings
from bot.db import Database
from bot.handlers import router
from bot.subscriptions import SubscriptionLinkService

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in settings.admin_ids:
        with suppress(Exception):
            await bot.send_message(admin_id, text)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    db = Database(settings.database_path)
    await db.init()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    subscriptions = SubscriptionLinkService(bot, db, settings)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать сначала"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="paysupport", description="Вопрос по оплате"),
        ]
    )

    try:
        await subscriptions.validate_channel()
    except Exception as exc:
        logger.error("Channel configuration check failed: %s", exc)
        await notify_admins(
            bot,
            "⚠️ Проверка закрытого канала не пройдена:\n"
            f"<code>{exc}</code>\n\n"
            "Бот продолжил работу, но платная ссылка может не создаваться.",
        )

    logger.info("Bot started")
    try:
        await dispatcher.start_polling(
            bot,
            db=db,
            settings=settings,
            subscriptions=subscriptions,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
