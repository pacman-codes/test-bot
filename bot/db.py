from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite


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
                """
            )
            await db.commit()

    async def upsert_user(self, telegram_id: int, username: str | None, first_name: str) -> None:
        now = datetime.now(UTC).isoformat()
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

    async def set_step(self, telegram_id: int, step: str) -> None:
        await self._update(telegram_id, "funnel_step", step)

    async def set_payment_status(self, telegram_id: int, status: str) -> None:
        await self._update(telegram_id, "payment_status", status)

    async def activate_subscription(self, telegram_id: int, days: int) -> str:
        until = datetime.now(UTC) + timedelta(days=days)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                UPDATE users
                SET payment_status = 'approved', subscription_until = ?, updated_at = ?
                WHERE telegram_id = ?
                """,
                (until.isoformat(), datetime.now(UTC).isoformat(), telegram_id),
            )
            await db.commit()
        return until.isoformat()

    async def get_user(self, telegram_id: int) -> dict[str, object] | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def _update(self, telegram_id: int, field: str, value: str) -> None:
        allowed = {"funnel_step", "payment_status"}
        if field not in allowed:
            raise ValueError(f"Unsupported field: {field}")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                f"UPDATE users SET {field} = ?, updated_at = ? WHERE telegram_id = ?",
                (value, datetime.now(UTC).isoformat(), telegram_id),
            )
            await db.commit()
