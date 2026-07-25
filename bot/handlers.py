from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import Settings
from bot.db import Database

router = Router()


def keyboard(*rows: tuple[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)] for text, data in rows]
    )


@router.message(CommandStart())
async def start(message: Message, db: Database) -> None:
    user = message.from_user
    if not user:
        return
    await db.upsert_user(user.id, user.username, user.first_name)
    await db.set_step(user.id, "welcome")
    await message.answer(
        f"Привет, {user.first_name}! 👋\n\n"
        "Здесь находится закрытое сообщество с материалами и обновлениями, "
        "которых нет в открытом доступе.",
        reply_markup=keyboard(("Что внутри?", "funnel:inside")),
    )


@router.callback_query(F.data == "funnel:inside")
async def show_inside(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    if not callback.from_user:
        return
    await db.set_step(callback.from_user.id, "inside")
    await callback.message.edit_text(
        "Внутри канала:\n\n"
        "• практические материалы без воды;\n"
        "• регулярные обновления;\n"
        "• разборы и дополнительные публикации;\n"
        "• доступ ко всему архиву сразу.",
        reply_markup=keyboard(("Посмотреть условия", "funnel:offer")),
    )


@router.callback_query(F.data == "funnel:offer")
async def show_offer(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    await callback.answer()
    await db.set_step(callback.from_user.id, "offer")
    await callback.message.edit_text(
        "Доступ к закрытому каналу\n\n"
        f"Стоимость: {settings.subscription_price_rub} ₽\n"
        f"Срок доступа: {settings.subscription_days} дней\n\n"
        "После оплаты бот отправит персональную ссылку для входа.",
        reply_markup=keyboard(("Оформить подписку", "payment:create"), ("Назад", "funnel:inside")),
    )


@router.callback_query(F.data == "payment:create")
async def create_payment_request(
    callback: CallbackQuery, db: Database, settings: Settings, bot: Bot
) -> None:
    await callback.answer()
    user = callback.from_user
    await db.set_step(user.id, "payment_pending")
    await db.set_payment_status(user.id, "pending")
    await callback.message.edit_text(
        "Заявка создана ✅\n\n"
        "На этапе MVP оплата подтверждается администратором вручную. "
        "После подтверждения ссылка придёт сюда автоматически."
    )
    username = f"@{user.username}" if user.username else "без username"
    for admin_id in settings.admin_ids:
        await bot.send_message(
            admin_id,
            "Новая заявка на подписку\n\n"
            f"Пользователь: {user.full_name} ({username})\n"
            f"Telegram ID: <code>{user.id}</code>\n\n"
            f"Подтвердить: <code>/approve {user.id}</code>\n"
            f"Отклонить: <code>/reject {user.id}</code>",
        )


@router.message(Command("approve"))
async def approve(
    message: Message, command: CommandObject, db: Database, settings: Settings, bot: Bot
) -> None:
    if not message.from_user or message.from_user.id not in settings.admin_ids:
        return
    args = (command.args or "").split()
    if not args or not args[0].isdigit():
        await message.answer("Формат: /approve <telegram_id> [days]")
        return
    telegram_id = int(args[0])
    days = int(args[1]) if len(args) > 1 and args[1].isdigit() else settings.subscription_days
    user = await db.get_user(telegram_id)
    if not user:
        await message.answer("Пользователь не найден.")
        return
    until = await db.activate_subscription(telegram_id, days)
    invite = await bot.create_chat_invite_link(
        chat_id=settings.private_channel_id,
        member_limit=1,
        name=f"subscription-{telegram_id}",
    )
    await bot.send_message(
        telegram_id,
        "Оплата подтверждена ✅\n\n"
        f"Подписка активирована на {days} дней.\n"
        f"Персональная ссылка для входа:\n{invite.invite_link}\n\n"
        "Ссылка одноразовая — не пересылай её другим.",
    )
    await message.answer(f"Готово. Подписка активна до {until}.")


@router.message(Command("reject"))
async def reject(message: Message, command: CommandObject, db: Database, settings: Settings, bot: Bot) -> None:
    if not message.from_user or message.from_user.id not in settings.admin_ids:
        return
    value = (command.args or "").strip()
    if not value.isdigit():
        await message.answer("Формат: /reject <telegram_id>")
        return
    telegram_id = int(value)
    await db.set_payment_status(telegram_id, "rejected")
    await bot.send_message(telegram_id, "Заявка отклонена. Напиши администратору, если это ошибка.")
    await message.answer("Заявка отклонена.")


@router.message(Command("status"))
async def status(message: Message, command: CommandObject, db: Database, settings: Settings) -> None:
    if not message.from_user or message.from_user.id not in settings.admin_ids:
        return
    value = (command.args or "").strip()
    if not value.isdigit():
        await message.answer("Формат: /status <telegram_id>")
        return
    user = await db.get_user(int(value))
    await message.answer(f"<pre>{user}</pre>" if user else "Пользователь не найден.")
