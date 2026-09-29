"""SQLite storage. Swap for PostgreSQL in production; the schema carries over."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "aparece.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    category_es TEXT DEFAULT '',
    segment TEXT NOT NULL DEFAULT 'services',
    city TEXT NOT NULL,
    website TEXT DEFAULT '',
    competitors TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    product TEXT DEFAULT '',
    product_es TEXT DEFAULT '',
    label TEXT NOT NULL,
    label_es TEXT DEFAULT '',
    value TEXT NOT NULL,
    category TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT 'owner',
    source TEXT DEFAULT '',
    verified_by TEXT DEFAULT '',
    verified_at TEXT NOT NULL,
    UNIQUE(business_id, key)
);
CREATE TABLE IF NOT EXISTS journeys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    language TEXT NOT NULL,
    category TEXT NOT NULL,
    related_facts TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    text TEXT NOT NULL,
    mentioned INTEGER NOT NULL,
    position INTEGER,
    competitors TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
    fact_key TEXT NOT NULL,
    value TEXT NOT NULL,
    verdict TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    scan_id INTEGER REFERENCES scans(id),
    type TEXT NOT NULL,
    fact_key TEXT,
    provider TEXT,
    category TEXT,
    language TEXT,
    ai_value TEXT,
    verified_value TEXT,
    detail TEXT,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    suggested_fix TEXT,
    approved_by TEXT,
    approved_at TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    detail TEXT,
    at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)


def rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def row(cursor) -> dict | None:
    r = cursor.fetchone()
    return dict(r) if r else None


def log(db, business_id, action, actor, detail=None):
    """Every automatic action and every human approval lands here (governance trail)."""
    db.execute(
        "INSERT INTO audit_log (business_id, action, actor, detail, at) VALUES (?,?,?,?,?)",
        (business_id, action, actor, json.dumps(detail) if detail is not None else None, now()),
    )
