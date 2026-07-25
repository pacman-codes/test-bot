from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import suppress

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, ErrorEvent, Message

from app import content, keyboards
from app.config import ConfigError, Settings
from app.db import Database
from app.services import SubscriptionLinkError, SubscriptionLinkService

logger = logging.getLogger(__name__)
router = Router()


def format_support(settings: Settings) -> str:
    if settings.support_username:
        return f'Поддержка: <a href="https://t.me/{settings.support_username}">@{settings.support_username}</a>'
    return content.NO_SUPPORT


async def save_step(db: Database, message: Message, step: str, event: str | None = None) -> None:
    user = message.from_user
    if user is None:
        return
    await db.touch_user(user.id, user.username, user.first_name, step)
    if event:
        await db.log_event(user.id, event)


async def save_callback_step(
    db: Database,
    callback: CallbackQuery,
    step: str,
    event: str | None = None,
) -> None:
    user = callback.from_user
    await db.touch_user(user.id, user.username, user.first_name, step)
    if event:
        await db.log_event(user.id, event)


async def edit_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
    await callback.answer()


@router.message(CommandStart())
async def start(message: Message, db: Database) -> None:
    await save_step(db, message, "start", "start")
    first_name = message.from_user.first_name if message.from_user else ""
    await message.answer(
        content.WELCOME.format(first_name=first_name),
        reply_markup=keyboards.welcome_keyboard(),
    )


@router.callback_query(F.data == "funnel:start")
async def funnel_start(callback: CallbackQuery, db: Database) -> None:
    await save_callback_step(db, callback, "start")
    await edit_callback_message(
        callback,
        content.WELCOME.format(first_name=callback.from_user.first_name),
        keyboards.welcome_keyboard(),
    )


@router.callback_query(F.data == "funnel:details")
async def funnel_details(callback: CallbackQuery, db: Database) -> None:
    await save_callback_step(db, callback, "details", "details_view")
    await edit_callback_message(callback, content.DETAILS, keyboards.details_keyboard())


@router.callback_query(F.data == "funnel:proof")
async def funnel_proof(callback: CallbackQuery, db: Database) -> None:
    await save_callback_step(db, callback, "proof", "proof_view")
    await edit_callback_message(callback, content.PROOF, keyboards.proof_keyboard())


@router.callback_query(F.data == "funnel:offer")
async def funnel_offer(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    await save_callback_step(db, callback, "offer", "offer_view")
    await edit_callback_message(
        callback,
        content.OFFER.format(price=settings.subscription_price),
        keyboards.offer_keyboard(settings.subscription_price),
    )


@router.callback_query(F.data == "funnel:subscribe")
async def funnel_subscribe(
    callback: CallbackQuery,
    db: Database,
    link_service: SubscriptionLinkService,
    settings: Settings,
) -> None:
    await save_callback_step(db, callback, "subscribe", "subscription_link_requested")
    await callback.answer("Готовлю ссылку…")

    try:
        url = await link_service.get_or_create()
    except SubscriptionLinkError:
        logger.exception("Could not prepare subscription link for user %s", callback.from_user.id)
        if isinstance(callback.message, Message):
            await callback.message.answer(
                f"{content.PAYMENT_ERROR}\n\n{format_support(settings)}"
            )
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            content.PAYMENT_READY,
            reply_markup=keyboards.subscription_keyboard(url),
        )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(content.HELP)


@router.message(Command("paysupport"))
async def payment_support(message: Message, settings: Settings) -> None:
    await message.answer(format_support(settings))


@router.message(Command("stats"))
async def stats(message: Message, db: Database, settings: Settings) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return
    data = await db.get_stats()
    await message.answer(
        "<b>Воронка</b>\n\n"
        f"Пользователи: <b>{data.total_users}</b>\n"
        f"Посмотрели описание: <b>{data.reached_details}</b>\n"
        f"Дошли до оффера: <b>{data.reached_offer}</b> ({data.offer_conversion:.1f}%)\n"
        f"Запросили ссылку: <b>{data.requested_link}</b> ({data.link_conversion:.1f}%)"
    )


@router.message(Command("refresh_link"))
async def refresh_link(
    message: Message,
    settings: Settings,
    link_service: SubscriptionLinkService,
) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return
    try:
        await link_service.get_or_create(force_refresh=True)
    except SubscriptionLinkError as exc:
        await message.answer(f"Не удалось обновить ссылку: <code>{exc}</code>")
        return
    await message.answer("Новая ссылка на подписку создана и сохранена.")


@router.error()
async def error_handler(event: ErrorEvent) -> bool:
    logger.error(
        "Unhandled update error: %s",
        event.exception,
        exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
    )
    return True


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать сначала"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="paysupport", description="Вопрос по оплате"),
        ]
    )


async def notify_admins(bot: Bot, settings: Settings, text: str) -> None:
    for admin_id in settings.admin_ids:
        with suppress(Exception):
            await bot.send_message(admin_id, text)


async def run() -> None:
    settings = Settings.from_env()
    db = Database(settings.database_path)
    await db.init()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    link_service = SubscriptionLinkService(bot, db, settings)
    dispatcher = Dispatcher(
        db=db,
        settings=settings,
        link_service=link_service,
    )
    dispatcher.include_router(router)

    await set_commands(bot)
    try:
        await link_service.validate_channel_access()
    except Exception as exc:
        logger.error("Channel configuration check failed: %s", exc)
        await notify_admins(
            bot,
            settings,
            "⚠️ Проверка закрытого канала не пройдена:\n"
            f"<code>{exc}</code>\n\n"
            "Бот продолжил работу, но платная ссылка может не создаваться.",
        )

    logger.info("Bot started")
    try:
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        asyncio.run(run())
    except ConfigError as exc:
        logger.critical("Configuration error: %s", exc)
        sys.exit(2)
    except KeyboardInterrupt:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()
