from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class FunnelStats:
    total_users: int
    reached_details: int
    reached_offer: int
    requested_link: int

    @property
    def offer_conversion(self) -> float:
        return 0.0 if self.total_users == 0 else self.reached_offer / self.total_users * 100

    @property
    def link_conversion(self) -> float:
        return 0.0 if self.total_users == 0 else self.requested_link / self.total_users * 100


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @asynccontextmanager
    async def connect(self):
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA journal_mode=WAL")
        await connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            await connection.close()

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    last_step TEXT NOT NULL DEFAULT 'start'
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_events_name_user
                    ON events(event_name, user_id);

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def touch_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        step: str,
    ) -> None:
        now = utc_now_iso()
        async with self.connect() as db:
            await db.execute(
                """
                INSERT INTO users(user_id, username, first_name, started_at, last_seen_at, last_step)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_seen_at = excluded.last_seen_at,
                    last_step = excluded.last_step
                """,
                (user_id, username, first_name, now, now, step),
            )
            await db.commit()

    async def log_event(self, user_id: int, event_name: str) -> None:
        async with self.connect() as db:
            await db.execute(
                "INSERT INTO events(user_id, event_name, created_at) VALUES (?, ?, ?)",
                (user_id, event_name, utc_now_iso()),
            )
            await db.commit()

    async def set_value(self, key: str, value: str) -> None:
        async with self.connect() as db:
            await db.execute(
                """
                INSERT INTO app_settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, utc_now_iso()),
            )
            await db.commit()

    async def get_value(self, key: str) -> str | None:
        async with self.connect() as db:
            cursor = await db.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return None if row is None else str(row["value"])

    async def get_stats(self) -> FunnelStats:
        async with self.connect() as db:
            total = await self._scalar(db, "SELECT COUNT(*) FROM users")
            details = await self._scalar(
                db,
                "SELECT COUNT(DISTINCT user_id) FROM events WHERE event_name = 'details_view'",
            )
            offer = await self._scalar(
                db,
                "SELECT COUNT(DISTINCT user_id) FROM events WHERE event_name = 'offer_view'",
            )
            link = await self._scalar(
                db,
                "SELECT COUNT(DISTINCT user_id) FROM events WHERE event_name = 'subscription_link_requested'",
            )
        return FunnelStats(total, details, offer, link)

    @staticmethod
    async def _scalar(db: aiosqlite.Connection, query: str) -> int:
        cursor = await db.execute(query)
        row = await cursor.fetchone()
        return int(row[0])
