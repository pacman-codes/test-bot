from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    private_channel_id: int
    admin_ids: Annotated[frozenset[int], NoDecode] = frozenset()
    database_path: Path = Path("data/bot.sqlite3")
    subscription_price_stars: int = 150
    subscription_link_name: str = "Закрытый канал"
    support_username: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> frozenset[int]:
        if value in (None, ""):
            return frozenset()
        if isinstance(value, str):
            return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
        return frozenset(value)  # type: ignore[arg-type]

    @field_validator("subscription_price_stars")
    @classmethod
    def validate_price(cls, value: int) -> int:
        if not 1 <= value <= 10_000:
            raise ValueError("subscription_price_stars must be between 1 and 10000")
        return value

    @field_validator("subscription_link_name")
    @classmethod
    def validate_link_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("subscription_link_name must not be empty")
        if len(value) > 32:
            raise ValueError("subscription_link_name must be at most 32 characters")
        return value

    @field_validator("support_username", mode="before")
    @classmethod
    def normalize_support_username(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lstrip("@")
        return normalized or None


settings = Settings()
