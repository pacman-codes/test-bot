from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import Settings
from bot.db import Database
from bot.subscriptions import SubscriptionLinkError, SubscriptionLinkService

logger = logging.getLogger(__name__)
router = Router()


def callback_keyboard(*rows: tuple[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=callback_data)]
            for text, callback_data in rows
        ]
    )


def subscription_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Перейти к оплате", url=url)],
            [InlineKeyboardButton(text="Назад", callback_data="funnel:offer")],
        ]
    )


def support_text(settings: Settings) -> str:
    if settings.support_username:
        username = settings.support_username
        return f'Поддержка: <a href="https://t.me/{username}">@{username}</a>'
    return "По вопросам оплаты напиши владельцу бота."


async def remember_user(message: Message, db: Database) -> None:
    user = message.from_user
    if user:
        await db.upsert_user(user.id, user.username, user.first_name)


async def edit_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup,
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
    user = message.from_user
    if not user:
        return
    await remember_user(message, db)
    await db.set_step(user.id, "welcome", event="start")
    await message.answer(
        f"<b>Привет, {user.first_name}!</b> 👋\n\n"
        "Здесь находится закрытый канал с материалами и обновлениями, "
        "которых нет в открытом доступе.\n\n"
        "Покажу, что внутри, и затем ты сам решишь, нужен ли доступ.",
        reply_markup=callback_keyboard(("Посмотреть, что внутри", "funnel:inside")),
    )


@router.callback_query(F.data == "funnel:start")
async def show_start(callback: CallbackQuery, db: Database) -> None:
    await db.set_step(callback.from_user.id, "welcome")
    await edit_message(
        callback,
        f"<b>Привет, {callback.from_user.first_name}!</b> 👋\n\n"
        "Здесь находится закрытый канал с материалами и обновлениями, "
        "которых нет в открытом доступе.\n\n"
        "Покажу, что внутри, и затем ты сам решишь, нужен ли доступ.",
        callback_keyboard(("Посмотреть, что внутри", "funnel:inside")),
    )


@router.callback_query(F.data == "funnel:inside")
async def show_inside(callback: CallbackQuery, db: Database) -> None:
    await db.set_step(callback.from_user.id, "inside", event="inside_view")
    await edit_message(
        callback,
        "<b>Что находится внутри</b>\n\n"
        "• практические материалы без воды;\n"
        "• регулярные обновления;\n"
        "• разборы и готовые решения;\n"
        "• доступ ко всему архиву сразу.\n\n"
        "Вместо бесконечной ленты — компактная база, к которой можно возвращаться.",
        callback_keyboard(
            ("Почему канал закрытый", "funnel:why"),
            ("Назад", "funnel:start"),
        ),
    )


@router.callback_query(F.data == "funnel:why")
async def show_why(callback: CallbackQuery, db: Database) -> None:
    await db.set_step(callback.from_user.id, "why", event="why_view")
    await edit_message(
        callback,
        "<b>Почему канал закрытый</b>\n\n"
        "Материалы выходят для небольшой аудитории, поэтому их можно делать "
        "конкретнее и полезнее.\n\n"
        "Без рекламы, гонки за охватами и случайных публикаций — только системный архив "
        "и новые материалы по теме.",
        callback_keyboard(
            ("Посмотреть условия", "funnel:offer"),
            ("Назад", "funnel:inside"),
        ),
    )


@router.callback_query(F.data == "funnel:offer")
async def show_offer(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    await db.set_step(callback.from_user.id, "offer", event="offer_view")
    await edit_message(
        callback,
        "<b>Доступ к закрытому каналу</b>\n\n"
        f"Стоимость: <b>{settings.subscription_price_stars} ⭐ в месяц</b>.\n\n"
        "После оплаты Telegram сразу добавит тебя в канал. Подписка продлевается "
        "каждые 30 дней, отменить её можно в настройках Telegram.",
        callback_keyboard(
            (
                f"Оформить подписку — {settings.subscription_price_stars} ⭐",
                "subscription:create",
            ),
            ("Назад", "funnel:why"),
        ),
    )


@router.callback_query(F.data == "subscription:create")
async def create_subscription_link(
    callback: CallbackQuery,
    db: Database,
    subscriptions: SubscriptionLinkService,
    settings: Settings,
) -> None:
    await db.set_step(
        callback.from_user.id,
        "subscription_link",
        event="subscription_link_requested",
    )
    await callback.answer("Готовлю ссылку…")

    try:
        url = await subscriptions.get_or_create()
    except SubscriptionLinkError:
        logger.exception("Could not prepare a subscription link for %s", callback.from_user.id)
        if isinstance(callback.message, Message):
            await callback.message.answer(
                "Не получилось подготовить ссылку на подписку. Попробуй ещё раз или "
                f"обратись в поддержку.\n\n{support_text(settings)}"
            )
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "<b>Ссылка готова</b>\n\n"
            "Нажми кнопку ниже. Telegram покажет условия и добавит тебя в канал "
            "сразу после оплаты.",
            reply_markup=subscription_keyboard(url),
        )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>Команды</b>\n\n"
        "/start — начать сначала\n"
        "/help — помощь\n"
        "/paysupport — вопрос по оплате"
    )


@router.message(Command("paysupport"))
async def payment_support(message: Message, settings: Settings) -> None:
    await message.answer(support_text(settings))


@router.message(Command("stats"))
async def stats(message: Message, db: Database, settings: Settings) -> None:
    if not message.from_user or message.from_user.id not in settings.admin_ids:
        return

    data = await db.get_stats()
    await message.answer(
        "<b>Статистика воронки</b>\n\n"
        f"Запустили бота: <b>{data.total_users}</b>\n"
        f"Посмотрели содержимое: <b>{data.reached_inside}</b> "
        f"({data.percent(data.reached_inside, data.total_users):.1f}%)\n"
        f"Дошли до оффера: <b>{data.reached_offer}</b> "
        f"({data.percent(data.reached_offer, data.total_users):.1f}%)\n"
        f"Запросили ссылку: <b>{data.requested_subscription}</b> "
        f"({data.percent(data.requested_subscription, data.total_users):.1f}%)"
    )


@router.message(Command("refresh_link"))
async def refresh_link(
    message: Message,
    subscriptions: SubscriptionLinkService,
    settings: Settings,
) -> None:
    if not message.from_user or message.from_user.id not in settings.admin_ids:
        return
    try:
        await subscriptions.get_or_create(force=True)
    except SubscriptionLinkError as exc:
        await message.answer(f"Не удалось обновить ссылку: <code>{exc}</code>")
        return
    await message.answer("Новая платная ссылка создана и сохранена.")
