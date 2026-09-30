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
    plan TEXT NOT NULL DEFAULT 'trial',
    plan_started_at TEXT,
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
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT DEFAULT ''
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
CREATE TABLE IF NOT EXISTS sales_weekly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    week INTEGER NOT NULL,
    phase TEXT NOT NULL,
    search_sessions INTEGER NOT NULL,
    ai_sessions INTEGER NOT NULL,
    ai_orders INTEGER NOT NULL,
    ai_revenue REAL NOT NULL,
    expected_revenue REAL,
    lost_revenue REAL,
    inclusion INTEGER,
    accuracy INTEGER,
    misinfo_contacts INTEGER,
    source TEXT NOT NULL,
    UNIQUE(business_id, week)
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    request TEXT NOT NULL,
    result TEXT NOT NULL,
    business_id INTEGER REFERENCES businesses(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS page_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    text TEXT DEFAULT '',
    simulated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    fact_key TEXT NOT NULL,
    snapshot_id INTEGER REFERENCES page_snapshots(id),
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    value_found TEXT,
    agrees INTEGER,
    snippet TEXT DEFAULT '',
    checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS citation_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    snapshot_id INTEGER REFERENCES page_snapshots(id),
    domain TEXT NOT NULL,
    url TEXT NOT NULL,
    supports INTEGER,
    snippet TEXT DEFAULT '',
    checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    human_verdict TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referral_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    week_start TEXT NOT NULL,
    total_jobs INTEGER NOT NULL,
    ai_jobs INTEGER NOT NULL,
    ai_revenue REAL,
    created_at TEXT NOT NULL,
    UNIQUE(business_id, week_start)
);
CREATE TABLE IF NOT EXISTS proof_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    results TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT DEFAULT '',
    role TEXT DEFAULT '',
    business_name TEXT NOT NULL,
    website TEXT DEFAULT '',
    city TEXT DEFAULT '',
    segment TEXT DEFAULT '',
    reasons TEXT DEFAULT '[]',
    issues TEXT DEFAULT '[]',
    issue_text TEXT DEFAULT '',
    help_text TEXT DEFAULT '',
    lang TEXT DEFAULT 'en',
    consent INTEGER NOT NULL,
    check_id INTEGER REFERENCES checks(id),
    business_id INTEGER REFERENCES businesses(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'new',
    note TEXT DEFAULT ''
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


# Columns added after the first release, so older databases keep working.
MIGRATIONS = {
    "businesses": {"plan": "TEXT NOT NULL DEFAULT 'trial'", "plan_started_at": "TEXT"},
    "sales_weekly": {"expected_revenue": "REAL", "inclusion": "INTEGER", "accuracy": "INTEGER"},
    "incidents": {"approved_after_scan": "INTEGER", "origin": "TEXT", "origin_source": "TEXT"},
    "responses": {"description": "TEXT DEFAULT ''", "descriptors": "TEXT DEFAULT '[]'", "sentiment": "TEXT",
                  "model": "TEXT"},
}


def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
            for col, spec in cols.items():
                if col not in have:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {spec}")


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
