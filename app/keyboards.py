from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def one_button(text: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]]
    )


def welcome_keyboard() -> InlineKeyboardMarkup:
    return one_button("Посмотреть, что внутри", "funnel:details")


def details_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Почему канал закрытый", callback_data="funnel:proof")],
            [InlineKeyboardButton(text="Назад", callback_data="funnel:start")],
        ]
    )


def proof_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Узнать условия", callback_data="funnel:offer")],
            [InlineKeyboardButton(text="Назад", callback_data="funnel:details")],
        ]
    )


def offer_keyboard(price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оформить подписку — {price} ⭐",
                    callback_data="funnel:subscribe",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="funnel:proof")],
        ]
    )


def subscription_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Перейти к оплате", url=url)],
            [InlineKeyboardButton(text="Вернуться к условиям", callback_data="funnel:offer")],
        ]
    )
