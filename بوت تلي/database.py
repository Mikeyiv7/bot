from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Any, Iterator


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    phone TEXT,
                    password TEXT,
                    is_blocked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    package_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    quota TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending', 'success', 'failed')),
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO settings(key, value)
                VALUES ('orders_paused', '0');
                """
            )
            try:
                connection.execute("ALTER TABLE users ADD COLUMN password TEXT")
            except sqlite3.OperationalError:
                pass

    def upsert_user(self, user_id: int, username: str | None) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO users(user_id, username) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
                """,
                (user_id, username),
            )

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT user_id, username, phone, password, is_blocked, created_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_credentials(self, user_id: int, phone: str, password: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE users SET phone = ?, password = ? WHERE user_id = ?",
                (phone, password, user_id)
            )

    def remove_credentials(self, user_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE users SET phone = NULL, password = NULL WHERE user_id = ?",
                (user_id,)
            )

    def list_users(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id, username, is_blocked FROM users
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def active_user_ids(self) -> list[int]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT user_id FROM users WHERE is_blocked = 0 ORDER BY user_id"
            ).fetchall()
            return [row["user_id"] for row in rows]

    def set_user_blocked(self, user_id: int, blocked: bool) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE users SET is_blocked = ? WHERE user_id = ?",
                (int(blocked), user_id),
            )
            return cursor.rowcount > 0

    def get_orders(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, package_name, price, quota, duration, status, created_at
                FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_recent_orders(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT orders.id, orders.user_id, users.username, orders.package_name,
                       orders.price, orders.quota, orders.duration, orders.status,
                       orders.created_at
                FROM orders JOIN users ON users.user_id = orders.user_id
                ORDER BY orders.id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def create_order(
        self,
        user_id: int,
        package_name: str,
        price: float,
        quota: str,
        duration: str,
        idempotency_key: str,
    ) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders(
                    user_id, package_name, price, quota, duration, status, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
                ON CONFLICT(idempotency_key) DO NOTHING
                """,
                (user_id, package_name, price, quota, duration, idempotency_key),
            )
            if cursor.lastrowid:
                return cursor.lastrowid
            row = connection.execute(
                "SELECT id FROM orders WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            return int(row["id"])

    def get_stats(self) -> dict[str, int]:
        with self._connection() as connection:
            users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            counts = connection.execute(
                "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
            ).fetchall()
            result = {"users": users, "orders": 0, "success": 0, "failed": 0, "pending": 0}
            for row in counts:
                result[row["status"]] = row["count"]
                result["orders"] += row["count"]
            return result

    def orders_paused(self) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = 'orders_paused'"
            ).fetchone()
            return bool(row and row["value"] == "1")

    def set_orders_paused(self, paused: bool) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value) VALUES ('orders_paused', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                ("1" if paused else "0",),
            )
