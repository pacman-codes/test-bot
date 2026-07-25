from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when required environment configuration is invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Environment variable {name} is required")
    return value


def _parse_int(name: str, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        if default is None:
            raise ConfigError(f"Environment variable {name} is required")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc


def _parse_admin_ids(raw: str) -> frozenset[int]:
    if not raw.strip():
        return frozenset()
    try:
        return frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise ConfigError("ADMIN_IDS must be a comma-separated list of Telegram user IDs") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    channel_id: int
    subscription_price: int
    database_path: Path
    admin_ids: frozenset[int]
    support_username: str | None
    subscription_link_name: str

    @classmethod
    def from_env(cls) -> "Settings":
        price = _parse_int("SUBSCRIPTION_PRICE", 150)
        if not 1 <= price <= 10_000:
            raise ConfigError("SUBSCRIPTION_PRICE must be between 1 and 10000 Stars")

        support_username = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@") or None
        link_name = os.getenv("SUBSCRIPTION_LINK_NAME", "Bot subscription").strip()
        if len(link_name) > 32:
            raise ConfigError("SUBSCRIPTION_LINK_NAME must be at most 32 characters")

        return cls(
            bot_token=_required("BOT_TOKEN"),
            channel_id=_parse_int("CHANNEL_ID"),
            subscription_price=price,
            database_path=Path(os.getenv("DATABASE_PATH", "data/bot.sqlite3")),
            admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
            support_username=support_username,
            subscription_link_name=link_name,
        )
