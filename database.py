import sqlite3
import json
import logging
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from config import Config

logger = logging.getLogger("codecomprehension.database")
CURRENT_SCHEMA_VERSION = 2
ANALYZER_VERSION = "2.1.0"


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    """
    Resolves the SQLite database path with preference:
    1. Explicit db_path parameter
    2. Active Flask application context current_app.config['DATABASE_PATH']
    3. Global Config.DATABASE_PATH
    Ensures parent directories exist.
    """
    target = db_path
    if target is None:
        try:
            from flask import current_app, has_app_context
            if has_app_context() and "DATABASE_PATH" in current_app.config:
                target = current_app.config["DATABASE_PATH"]
        except Exception:
            target = None

    if target is None:
        target = getattr(Config, "DATABASE_PATH", "codecomprehension.db")

    p = Path(target)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parent / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


@contextmanager
def get_db(db_path: Optional[str] = None):
    """
    Context manager for SQLite database connections.
    Guarantees:
      - sqlite3.Row factory
      - PRAGMA foreign_keys = ON
      - PRAGMA busy_timeout = 5000 (resilient concurrency)
      - Atomic transaction commit on success
      - Rollback on exception
      - Safe connection closure in finally block (prevents connection leaks)
    """
    conn = None
    target_path = _resolve_db_path(db_path)
    try:
        conn = sqlite3.connect(target_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        # Enable Write-Ahead Logging (WAL) mode for concurrent read/write support
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
        except Exception:
            pass  # WAL may be restricted on some network filesystems
        yield conn
        conn.commit()
    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Database error occurred during transaction: %s", exc)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def init_db(db_path: Optional[str] = None):
    """
    Initializes database schema and applies versioned migrations using PRAGMA user_version.
    Preserves existing user data while upgrading schema safely.
    Handles concurrency safely across Gunicorn workers.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA user_version;")
        row = cursor.fetchone()
        version = row[0] if row else 0

        if version < 1:
            # Base reviews table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    language TEXT NOT NULL,
                    title TEXT,
                    code TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    issue_count INTEGER DEFAULT 0,
                    time_complexity TEXT,
                    space_complexity TEXT,
                    review_json TEXT
                );
            """)
            cursor.execute("PRAGMA user_version = 1;")
            version = 1
            logger.info("Database schema initialized to version 1.")

        if version < 2:
            # Migration to Version 2:
            # Add cache hashes, provider tracking, and server-side progressive hints table
            try:
                cursor.execute("ALTER TABLE reviews ADD COLUMN code_hash TEXT;")
            except sqlite3.OperationalError:
                pass  # column may already exist
            try:
                cursor.execute("ALTER TABLE reviews ADD COLUMN ai_provider TEXT DEFAULT 'offline';")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE reviews ADD COLUMN prompt_version TEXT DEFAULT 'v1.0';")
            except sqlite3.OperationalError:
                pass

            # Table for server-side progressive hint state tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_hints_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER NOT NULL,
                    issue_id TEXT NOT NULL,
                    highest_hint_unlocked INTEGER DEFAULT 0,
                    solution_unlocked INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE,
                    UNIQUE (review_id, issue_id)
                );
            """)

            # Indexes for fast query and deduplication
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_code_hash ON reviews (code_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reviews_timestamp ON reviews (timestamp DESC);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hints_review ON review_hints_progress (review_id, issue_id);")

            cursor.execute("PRAGMA user_version = 2;")
            logger.info("Database migrated successfully to version 2.")


def compute_code_hash(code: str, language: str, analyzer_version: str = ANALYZER_VERSION) -> str:
    """Computes deterministic SHA-256 hash for code caching & deduplication including analyzer version."""
    clean = f"{language.lower().strip()}:{code.strip()}:{analyzer_version}"
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def save_review(
    language: str,
    code: str,
    score: int,
    issue_count: int,
    time_complexity: str,
    space_complexity: str,
    review_data: Any,
    title: Optional[str] = None,
    ai_provider: str = "offline",
    prompt_version: str = ANALYZER_VERSION,
    db_path: Optional[str] = None
) -> int:
    """
    Saves a review record with UTC ISO 8601 timestamp, content hash, and metadata.
    """
    if not title:
        first_line = code.strip().split("\n")[0][:45]
        title = first_line if first_line else "Code Review"

    now_utc = datetime.now(timezone.utc).isoformat()
    code_hash = compute_code_hash(code, language, prompt_version)
    json_str = json.dumps(review_data) if isinstance(review_data, (dict, list)) else review_data

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reviews (
                timestamp, language, title, code, score, issue_count,
                time_complexity, space_complexity, review_json,
                code_hash, ai_provider, prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_utc,
            language,
            title,
            code,
            score,
            issue_count,
            time_complexity,
            space_complexity,
            json_str,
            code_hash,
            ai_provider,
            prompt_version
        ))
        new_id = cursor.lastrowid
        return new_id


def get_cached_review(
    code: str,
    language: str,
    ai_provider: str = "offline",
    prompt_version: str = ANALYZER_VERSION,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Checks if a review for this exact code hash, language, provider, and prompt version exists.
    """
    code_hash = compute_code_hash(code, language, prompt_version)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, language, title, code, score, issue_count,
                   time_complexity, space_complexity, review_json, ai_provider, prompt_version
            FROM reviews
            WHERE code_hash = ? AND ai_provider = ? AND prompt_version = ?
            ORDER BY id DESC LIMIT 1
        """, (code_hash, ai_provider, prompt_version))
        row = cursor.fetchone()
        if not row:
            return None

        d = dict(row)
        try:
            d["review_data"] = json.loads(d["review_json"])
        except Exception as e:
            logger.warning("Corrupted cached review JSON for ID %s: %s", d.get("id"), e)
            return None
        return d


def get_recent_reviews(limit: int = 20, offset: int = 0, db_path: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
    """
    Returns paginated review history and the total record count.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reviews;")
        total_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT id, timestamp, language, title, score, issue_count, time_complexity, space_complexity, ai_provider
            FROM reviews
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()
        return [dict(r) for r in rows], total_count


def get_review_by_id(review_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves full review record by ID.
    Raises or logs clean diagnostics if stored review_json is corrupted.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
        row = cursor.fetchone()
        if not row:
            return None

        d = dict(row)
        try:
            d["review_data"] = json.loads(d["review_json"])
        except Exception as e:
            logger.error("Failed to decode review_json for record %s: %s", review_id, e)
            d["review_data"] = None
            d["json_corruption_error"] = "Stored review data contains corrupted JSON format."
        return d


def delete_review(review_id: int, db_path: Optional[str] = None) -> bool:
    """
    Deletes a specific review record by ID.
    Returns True only if a record was actually deleted, False if record did not exist.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        return cursor.rowcount > 0


def delete_all_reviews(db_path: Optional[str] = None) -> int:
    """
    Permanently deletes all stored review records and associated hint histories.
    Returns the total number of deleted records.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM review_hints_progress;")
        cursor.execute("DELETE FROM reviews;")
        return cursor.rowcount


# ==============================================================================
# Server-Side Progressive Hint Progression State Management
# ==============================================================================

def record_hint_unlock(review_id: int, issue_id: str, requested_level: int, db_path: Optional[str] = None) -> int:
    """
    Records and verifies server-side hint level progression.
    Enforces strict sequence: Level 1 -> Level 2 -> Level 3.
    Returns the current highest unlocked hint level for this issue.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT highest_hint_unlocked, solution_unlocked
            FROM review_hints_progress
            WHERE review_id = ? AND issue_id = ?
        """, (review_id, issue_id))
        row = cursor.fetchone()

        current_level = row["highest_hint_unlocked"] if row else 0

        # Allow unlocking the next sequential hint level
        if requested_level <= current_level + 1:
            new_level = max(current_level, requested_level)
            cursor.execute("""
                INSERT INTO review_hints_progress (review_id, issue_id, highest_hint_unlocked, solution_unlocked, updated_at)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(review_id, issue_id) DO UPDATE SET
                    highest_hint_unlocked = MAX(highest_hint_unlocked, excluded.highest_hint_unlocked),
                    updated_at = excluded.updated_at
            """, (review_id, issue_id, new_level, now_utc))
            return new_level

        return current_level


def check_solution_authorized(review_id: int, issue_id: str, db_path: Optional[str] = None) -> bool:
    """
    Verifies on the server whether the user has unlocked all 3 progressive hints
    before permitting access to the final solution.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT highest_hint_unlocked FROM review_hints_progress
            WHERE review_id = ? AND issue_id = ?
        """, (review_id, issue_id))
        row = cursor.fetchone()
        if not row:
            return False
        # User must have reached hint level 3
        return row["highest_hint_unlocked"] >= 3


def record_solution_unlocked(review_id: int, issue_id: str, db_path: Optional[str] = None) -> bool:
    """Marks solution as officially unlocked in server state."""
    now_utc = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE review_hints_progress
            SET solution_unlocked = 1, updated_at = ?
            WHERE review_id = ? AND issue_id = ? AND highest_hint_unlocked >= 3
        """, (now_utc, review_id, issue_id))
        return cursor.rowcount > 0


def backup_database(destination_path: str, db_path: Optional[str] = None) -> bool:
    """
    Performs an online, zero-downtime backup of the active SQLite database
    using the official SQLite Backup API.
    """
    dest = Path(destination_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with get_db(db_path) as src_conn:
        dest_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dest_conn)
            return True
        finally:
            dest_conn.close()
