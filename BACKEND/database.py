import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Stable database path anchored to the BACKEND directory
DB_PATH = os.getenv(
    "DATABASE_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "database.sqlite"))
)

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection configured with Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initializes tables and applies progressive migrations for gamification."""
    conn = get_connection()
    cursor = conn.cursor()

    # Core Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            password_hash TEXT,
            salt TEXT,
            role TEXT DEFAULT 'blind' CHECK (role IN ('blind', 'deaf', 'sign', 'non_speaking')),
            streak INTEGER DEFAULT 1,
            last_active TEXT,
            total_score INTEGER DEFAULT 0,
            quizzes_completed INTEGER DEFAULT 0
        )
    ''')

    # History of generated lessons
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            topic TEXT,
            lesson TEXT,
            mode TEXT DEFAULT 'deaf',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Gamification: Quiz results and milestone events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            topic TEXT,
            score INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 3,
            correct_answers INTEGER DEFAULT 0,
            badge_earned TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()

    # Dynamic migrations for existing databases
    migration_columns = [
        ("users", "password", "TEXT"),
        ("users", "password_hash", "TEXT"),
        ("users", "salt", "TEXT"),
        ("users", "streak", "INTEGER DEFAULT 1"),
        ("users", "last_active", "TEXT"),
        ("users", "total_score", "INTEGER DEFAULT 0"),
        ("users", "quizzes_completed", "INTEGER DEFAULT 0"),
        ("history", "mode", "TEXT DEFAULT 'blind'"),
    ]

    for table, col, col_type in migration_columns:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    cursor.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'")
    users_schema = (cursor.fetchone()[0] or "").lower()
    supported_roles = ("'blind'", "'deaf'", "'sign'", "'non_speaking'")
    if "check" in users_schema and any(role not in users_schema for role in supported_roles):
        cursor.execute("""
            CREATE TABLE users_migrated (
                username TEXT PRIMARY KEY,
                password TEXT,
                password_hash TEXT,
                salt TEXT,
                role TEXT DEFAULT 'blind' CHECK (role IN ('blind', 'deaf', 'sign', 'non_speaking')),
                streak INTEGER DEFAULT 1,
                last_active TEXT,
                total_score INTEGER DEFAULT 0,
                quizzes_completed INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            INSERT INTO users_migrated (
                username, password, password_hash, salt, role,
                streak, last_active, total_score, quizzes_completed
            )
            SELECT username, password, password_hash, salt, role,
                   streak, last_active, total_score, quizzes_completed
            FROM users
        """)
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_migrated RENAME TO users")
        conn.commit()

    # Migrate any legacy lessons into history table
    try:
        cursor.execute('''
            INSERT INTO history (username, topic, lesson, mode, timestamp)
            SELECT username, topic, lesson, 'blind', created_at 
            FROM lessons
            WHERE NOT EXISTS (
                SELECT 1 FROM history 
                WHERE history.username = lessons.username 
                  AND history.topic = lessons.topic 
                  AND history.timestamp = lessons.created_at
            )
        ''')
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.close()

# --- SESSIONLESS / ANONYMOUS PROFILE MANAGEMENT ---

DEFAULT_PROFILES = [
    {"username": "Guest Learner", "role": "deaf", "avatar": "🌟"},
    {"username": "Alex (Visual)", "role": "deaf", "avatar": "👁️"},
    {"username": "Jordan (Audio)", "role": "blind", "avatar": "🎧"},
    {"username": "Taylor (Sign)", "role": "sign", "avatar": "🤟"},
]

def get_or_create_profile(username: Optional[str] = None, role: str = "deaf") -> Dict[str, Any]:
    """Retrieves an existing profile or creates a sessionless profile automatically."""
    clean_username = (username or "").strip() or "Guest Learner"
    if role not in {"blind", "deaf", "sign", "non_speaking"}:
        role = "deaf"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (clean_username,))
    row = cursor.fetchone()

    today_str = str(date.today())
    if not row:
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, streak, last_active, total_score, quizzes_completed)
            VALUES (?, '', '', ?, 1, ?, 0, 0)
            """,
            (clean_username, role, today_str)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE username = ?", (clean_username,))
        row = cursor.fetchone()
    conn.close()

    return {
        "username": row["username"],
        "role": row["role"] if "role" in row.keys() and row["role"] else role,
        "streak": int(row["streak"] or 1) if "streak" in row.keys() else 1,
        "total_score": int(row["total_score"] or 0) if "total_score" in row.keys() else 0,
        "quizzes_completed": int(row["quizzes_completed"] or 0) if "quizzes_completed" in row.keys() else 0,
        "last_active": row["last_active"] if "last_active" in row.keys() else today_str
    }

def list_profiles() -> List[Dict[str, Any]]:
    """Returns all available profiles in SQLite, pre-populating defaults if empty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, role, streak, total_score, quizzes_completed, last_active FROM users ORDER BY last_active DESC, streak DESC")
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        for p in DEFAULT_PROFILES:
            get_or_create_profile(p["username"], p["role"])
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, role, streak, total_score, quizzes_completed, last_active FROM users")
        rows = cursor.fetchall()

    conn.close()
    return [
        {
            "username": r["username"],
            "role": r["role"] or "deaf",
            "streak": int(r["streak"] or 1),
            "total_score": int(r["total_score"] or 0),
            "quizzes_completed": int(r["quizzes_completed"] or 0),
            "last_active": r["last_active"] or ""
        }
        for r in rows
    ]

def update_profile_role(username: str, role: str) -> bool:
    """Updates learner pathway preference directly without needing authentication."""
    clean_username = (username or "").strip() or "Guest Learner"
    if role not in {"blind", "deaf", "sign", "non_speaking"}:
        return False
    # Ensure profile exists first
    get_or_create_profile(clean_username, role)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE username = ?", (role, clean_username))
    conn.commit()
    conn.close()
    return True

# --- USER MANAGEMENT & COMPATIBILITY AUTH ---

def register_user(username: str, password: str = "", role: str = "deaf") -> Tuple[bool, str]:
    """Registers or updates a profile with optional salted PBKDF2 hashing."""
    username = username.strip()
    if not username:
        return False, "Username cannot be empty."
    if role not in {"blind", "deaf", "sign", "non_speaking"}:
        role = "deaf"

    conn = get_connection()
    cursor = conn.cursor()
    today_str = str(date.today())

    import secrets
    from hashlib import pbkdf2_hmac
    salt_bytes = secrets.token_bytes(16)
    salt_hex = salt_bytes.hex()
    password_hash = pbkdf2_hmac("sha256", password.encode(), salt_bytes, 120_000).hex() if password else None

    try:
        cursor.execute(
            """
            INSERT INTO users (username, password, password_hash, salt, role, streak, last_active, total_score, quizzes_completed)
            VALUES (?, ?, ?, ?, ?, 1, ?, 0, 0)
            """,
            (username, password, password_hash, salt_hex, role, today_str)
        )
        conn.commit()
        return True, "Profile created successfully!"
    except sqlite3.IntegrityError:
        cursor.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        conn.commit()
        return True, "Profile updated."
    except sqlite3.OperationalError:
        try:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, salt, role, streak, last_active, total_score, quizzes_completed)
                VALUES (?, ?, ?, ?, 1, ?, 0, 0)
                """,
                (username, password_hash, salt_hex, role, today_str)
            )
            conn.commit()
            return True, "Profile created successfully!"
        except sqlite3.IntegrityError:
            cursor.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
            conn.commit()
            return True, "Profile updated."
    finally:
        conn.close()

def authenticate_user(username: str, password: str = "") -> Tuple[bool, Any]:
    """Authenticates credentials or provides instant login for sessionless profiles."""
    username = (username or "").strip()
    if not username:
        username = "Guest Learner"

    profile = get_or_create_profile(username)
    current_streak = update_user_streak(username)
    return True, {
        "username": profile["username"],
        "role": profile["role"],
        "streak": current_streak
    }

# Compatibility helpers for auth.py
def find_user(username: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(username: str, password_hash: str, salt: str, role: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    today_str = str(date.today())
    if role not in {"blind", "deaf", "sign", "non_speaking"}:
        role = "deaf"
    try:
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, salt, role, streak, last_active, total_score, quizzes_completed)
            VALUES (?, ?, ?, ?, 1, ?, 0, 0)
            """,
            (username.strip(), password_hash, salt, role, today_str)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# --- STREAK & PROGRESS MANAGEMENT ---

def get_user_streak(username: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT streak FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return int(row["streak"]) if row and row["streak"] is not None else 1

def update_user_streak(username: str) -> int:
    """Dynamically calculates streaks based on consecutive active days."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT streak, last_active FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return 1

    current_streak = int(row["streak"] or 1)
    last_active = row["last_active"]
    today = date.today()
    today_str = str(today)

    if last_active == today_str:
        conn.close()
        return current_streak

    if last_active:
        try:
            last_date = datetime.strptime(last_active, "%Y-%m-%d").date()
            diff = (today - last_date).days
            if diff == 1:
                new_streak = current_streak + 1
            elif diff > 1:
                new_streak = 1
            else:
                new_streak = current_streak
        except Exception:
            new_streak = 1
    else:
        new_streak = 1

    cursor.execute(
        "UPDATE users SET streak = ?, last_active = ? WHERE username = ?",
        (new_streak, today_str, username)
    )
    conn.commit()
    conn.close()
    return new_streak

class HistoryItem(dict):
    """Dictionary that supports both key and integer index access for backwards compatibility."""
    def __getitem__(self, key):
        if isinstance(key, int):
            mapping = {0: "topic", 1: "lesson", 2: "timestamp"}
            if key in mapping and mapping[key] in self:
                return self[mapping[key]]
        return super().__getitem__(key)

def save_user_lesson(username: Optional[str], topic: str, lesson: str, mode: str = "deaf") -> None:
    clean_username = (username or "").strip() or "Guest Learner"
    get_or_create_profile(clean_username, role=mode)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (username, topic, lesson, mode) VALUES (?, ?, ?, ?)",
        (clean_username, topic, lesson, mode)
    )
    # Also sync legacy lessons table if it exists
    try:
        cursor.execute(
            "INSERT INTO lessons (username, topic, lesson) VALUES (?, ?, ?)",
            (clean_username, topic, lesson)
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()
    update_user_streak(clean_username)

def get_user_history(username: Optional[str], limit: int = 20) -> List[Dict[str, Any]]:
    clean_username = (username or "").strip() or "Guest Learner"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, topic, lesson, mode, timestamp 
        FROM history 
        WHERE username = ? 
        ORDER BY id DESC 
        LIMIT ?
        """,
        (clean_username, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        HistoryItem({
            "id": r["id"],
            "topic": r["topic"],
            "lesson": r["lesson"],
            "mode": r["mode"] if "mode" in r.keys() else "deaf",
            "timestamp": str(r["timestamp"]),
            "created_at": str(r["timestamp"])  # Backwards compatibility for React client
        })
        for r in rows
    ]

def record_quiz_result(username: Optional[str], topic: str, score: int, total_questions: int, correct_answers: int) -> Dict[str, Any]:
    """Records a completed quiz and evaluates milestone badges."""
    clean_username = (username or "").strip() or "Guest Learner"
    get_or_create_profile(clean_username)

    badge = None
    if total_questions > 0 and correct_answers == total_questions:
        badge = "🎯 Perfect Score Ace"
    elif score >= 100:
        badge = "🌟 High Achiever"
    elif correct_answers > 0:
        badge = "🧠 Knowledge Seeker"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO quiz_results (username, topic, score, total_questions, correct_answers, badge_earned)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (clean_username, topic, score, total_questions, correct_answers, badge)
    )

    cursor.execute(
        """
        UPDATE users 
        SET total_score = COALESCE(total_score, 0) + ?,
            quizzes_completed = COALESCE(quizzes_completed, 0) + 1
        WHERE username = ?
        """,
        (score, clean_username)
    )
    conn.commit()
    conn.close()

    streak = update_user_streak(clean_username)
    return {
        "score": score,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "badge_earned": badge,
        "streak": streak
    }

def get_user_stats(username: Optional[str]) -> Dict[str, Any]:
    """Aggregates all gamification stats, streaks, and milestone badges."""
    clean_username = (username or "").strip() or "Guest Learner"
    get_or_create_profile(clean_username)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT streak, last_active, total_score, quizzes_completed, role FROM users WHERE username = ?",
        (clean_username,)
    )
    user_row = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as count FROM history WHERE username = ?", (clean_username,))
    lessons_count = cursor.fetchone()["count"]

    cursor.execute(
        """
        SELECT topic, score, total_questions, correct_answers, badge_earned, timestamp 
        FROM quiz_results 
        WHERE username = ? 
        ORDER BY id DESC 
        LIMIT 5
        """,
        (clean_username,)
    )
    quiz_rows = cursor.fetchall()
    conn.close()

    streak = int(user_row["streak"] or 1) if user_row else 1
    total_score = int(user_row["total_score"] or 0) if user_row else 0
    quizzes_completed = int(user_row["quizzes_completed"] or 0) if user_row else 0
    role = user_row["role"] if user_row else "deaf"

    # Compute Milestone Badges dynamically
    badges = []
    if lessons_count >= 1:
        badges.append({"id": "first_lesson", "name": "🌱 First Step", "desc": "Completed your first AI lesson"})
    if streak >= 3:
        badges.append({"id": "streak_3", "name": "🔥 3-Day Flame", "desc": "Maintained learning streak for 3 consecutive days"})
    if streak >= 7:
        badges.append({"id": "streak_7", "name": "⚡ Week Champion", "desc": "7 days of dedicated learning"})
    if quizzes_completed >= 1:
        badges.append({"id": "quiz_1", "name": "🧠 Quiz Challenger", "desc": "Completed your first interactive quiz"})
    if quizzes_completed >= 5:
        badges.append({"id": "quiz_5", "name": "🏆 Scholar Master", "desc": "Completed 5 or more knowledge quizzes"})
    if any(q["total_questions"] > 0 and q["correct_answers"] == q["total_questions"] for q in quiz_rows):
        badges.append({"id": "perfect_quiz", "name": "🎯 Accuracy Ace", "desc": "Scored 100% on a knowledge quiz"})

    return {
        "username": username,
        "role": role,
        "streak": streak,
        "total_score": total_score,
        "quizzes_completed": quizzes_completed,
        "lessons_generated": lessons_count,
        "badges": badges,
        "recent_quizzes": [
            {
                "topic": q["topic"],
                "score": q["score"],
                "total_questions": q["total_questions"],
                "correct_answers": q["correct_answers"],
                "badge_earned": q["badge_earned"],
                "timestamp": str(q["timestamp"])
            }
            for q in quiz_rows
        ]
    }