"""Versioned, additive storage owned by Agora, independent of OASIS runtime."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS agora_session (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(user_id),
    started_tick INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    state_json TEXT NOT NULL,
    config_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agora_request (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES agora_session(session_id),
    user_id INTEGER NOT NULL REFERENCES user(user_id),
    tick INTEGER NOT NULL,
    feed_type TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    config_json TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    cards_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agora_exposure (
    exposure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES agora_session(session_id),
    request_id INTEGER NOT NULL REFERENCES agora_request(request_id),
    user_id INTEGER NOT NULL REFERENCES user(user_id),
    post_id INTEGER NOT NULL REFERENCES post(post_id),
    rank INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    UNIQUE(request_id, post_id)
);
CREATE TABLE IF NOT EXISTS agora_feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES agora_session(session_id),
    user_id INTEGER NOT NULL REFERENCES user(user_id),
    post_id INTEGER NOT NULL REFERENCES post(post_id),
    request_id INTEGER REFERENCES agora_request(request_id),
    kind TEXT NOT NULL,
    value REAL NOT NULL,
    tick INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS agora_session_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES agora_session(session_id),
    step INTEGER NOT NULL,
    tick INTEGER NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    action_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    observation_json TEXT NOT NULL,
    UNIQUE(session_id, step)
);
CREATE INDEX IF NOT EXISTS idx_agora_feedback_user
    ON agora_feedback(user_id, tick, feedback_id);
CREATE INDEX IF NOT EXISTS idx_agora_exposure_user
    ON agora_exposure(user_id, post_id, tick);
CREATE INDEX IF NOT EXISTS idx_agora_exposure_post
    ON agora_exposure(post_id);
CREATE INDEX IF NOT EXISTS idx_agora_feedback_post_kind
    ON agora_feedback(post_id, kind);
CREATE INDEX IF NOT EXISTS idx_agora_event_session
    ON agora_session_event(session_id, step);
CREATE INDEX IF NOT EXISTS idx_agora_post_author
    ON post(user_id, post_id);
CREATE INDEX IF NOT EXISTS idx_agora_post_visibility
    ON post(visibility, post_id);
"""


def ensure_schema(db: sqlite3.Connection) -> None:
    existing = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    required = {
        "agora_session",
        "agora_request",
        "agora_exposure",
        "agora_feedback",
        "agora_session_event",
    }
    if required <= existing:
        return
    if db.in_transaction:
        raise RuntimeError("Apply Agora schema migrations before starting an action")
    db.executescript(SCHEMA)
    db.commit()
