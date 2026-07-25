from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class FunnelStats:
    total_users: int
    reached_inside: int
    reached_offer: int
    requested_subscription: int

    @staticmethod
    def percent(value: int, total: int) -> float:
        return 0.0 if total == 0 else value / total * 100


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    funnel_step TEXT NOT NULL DEFAULT 'start',
                    payment_status TEXT NOT NULL DEFAULT 'none',
                    subscription_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_events_name_user
                    ON events(name, telegram_id);

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def upsert_user(self, telegram_id: int, username: str | None, first_name: str) -> None:
        now = utc_now()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (telegram_id, username, first_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    updated_at = excluded.updated_at
                """,
                (telegram_id, username, first_name, now, now),
            )
            await db.commit()

    async def set_step(self, telegram_id: int, step: str, *, event: str | None = None) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET funnel_step = ?, updated_at = ? WHERE telegram_id = ?",
                (step, utc_now(), telegram_id),
            )
            if event:
                await db.execute(
                    "INSERT INTO events (telegram_id, name, created_at) VALUES (?, ?, ?)",
                    (telegram_id, event, utc_now()),
                )
            await db.commit()

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, utc_now()),
            )
            await db.commit()

    async def get_setting(self, key: str) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def get_stats(self) -> FunnelStats:
        async with aiosqlite.connect(self.path) as db:
            total_users = await self._scalar(db, "SELECT COUNT(*) FROM users")
            reached_inside = await self._scalar(
                db,
                "SELECT COUNT(DISTINCT telegram_id) FROM events WHERE name = 'inside_view'",
            )
            reached_offer = await self._scalar(
                db,
                "SELECT COUNT(DISTINCT telegram_id) FROM events WHERE name = 'offer_view'",
            )
            requested_subscription = await self._scalar(
                db,
                "SELECT COUNT(DISTINCT telegram_id) FROM events "
                "WHERE name = 'subscription_link_requested'",
            )
        return FunnelStats(
            total_users=total_users,
            reached_inside=reached_inside,
            reached_offer=reached_offer,
            requested_subscription=requested_subscription,
        )

    @staticmethod
    async def _scalar(db: aiosqlite.Connection, query: str) -> int:
        cursor = await db.execute(query)
        row = await cursor.fetchone()
        return int(row[0])
