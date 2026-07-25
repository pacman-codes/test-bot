from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    admin_ids: frozenset[int]
    private_channel_id: int
    database_path: Path = Path("data/bot.sqlite3")
    subscription_price_rub: int = 499
    subscription_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> frozenset[int]:
        if isinstance(value, int):
            return frozenset({value})
        if isinstance(value, str):
            return frozenset(
                int(item.strip())
                for item in value.split(",")
                if item.strip()
            )
        return frozenset(value)  # type: ignore[arg-type]


settings = Settings()
