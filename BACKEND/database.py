"""SQLite persistence for users and generated lessons."""

from pathlib import Path
import sqlite3
from typing import Any

DATABASE_PATH = Path(__file__).resolve().parent / "database.sqlite"


def _ensure_database_file() -> None:
    if not DATABASE_PATH.exists() or DATABASE_PATH.read_bytes()[:16] == b"SQLite format 3\x00":
        return
    legacy_path = DATABASE_PATH.with_name("database.sqlite.legacy")
    suffix = 1
    while legacy_path.exists():
        legacy_path = DATABASE_PATH.with_name(f"database.sqlite.legacy.{suffix}")
        suffix += 1
    DATABASE_PATH.replace(legacy_path)


def _connection() -> sqlite3.Connection:
    _ensure_database_file()
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('blind', 'deaf'))
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL REFERENCES users(username),
                topic TEXT NOT NULL,
                lesson TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def create_user(username: str, password_hash: str, salt: str, role: str) -> bool:
    init_db()
    try:
        with _connection() as connection:
            connection.execute(
                "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
                (username, password_hash, salt, role),
            )
    except sqlite3.IntegrityError:
        return False
    return True


def find_user(username: str) -> dict[str, Any] | None:
    init_db()
    with _connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def save_user_lesson(username: str, topic: str, lesson: str) -> None:
    init_db()
    if not topic.strip():
        raise ValueError("Lesson topic cannot be empty")
    if not lesson.strip():
        raise ValueError("Lesson content cannot be empty")
    with _connection() as connection:
        connection.execute("INSERT INTO lessons (username, topic, lesson) VALUES (?, ?, ?)", (username, topic.strip(), lesson))


def get_user_history(username: str) -> list[dict[str, Any]]:
    init_db()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT topic, lesson, created_at FROM lessons WHERE username = ? ORDER BY id DESC LIMIT 20",
            (username,),
        ).fetchall()
    return [dict(row) for row in rows]