CREATE TABLE IF NOT EXISTS external_id_map (
    namespace TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    internal_id TEXT NOT NULL,
    PRIMARY KEY(namespace, entity_type, external_id)
);

CREATE TABLE IF NOT EXISTS persona (
    profile_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    profile_version TEXT NOT NULL,
    persona_json TEXT NOT NULL,
    policy_type TEXT NOT NULL DEFAULT 'scripted',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES user(user_id)
);

CREATE TABLE IF NOT EXISTS simulation_state (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    current_tick INTEGER NOT NULL DEFAULT 0,
    seed INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO simulation_state(singleton, current_tick, seed)
VALUES (1, 0, 0);

CREATE TABLE IF NOT EXISTS sandbox_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tick INTEGER NOT NULL,
    event_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor_user_id INTEGER,
    target_type TEXT,
    target_id TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tick, event_sequence),
    FOREIGN KEY(actor_user_id) REFERENCES user(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sandbox_event_tick
    ON sandbox_event(tick, event_sequence);

CREATE TABLE IF NOT EXISTS collection (
    collection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    created_at_tick INTEGER NOT NULL,
    UNIQUE(user_id, post_id),
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(post_id) REFERENCES post(post_id)
);

CREATE TABLE IF NOT EXISTS feed_impression (
    impression_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    feed_type TEXT NOT NULL CHECK(feed_type IN ('discover', 'following')),
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    reason TEXT NOT NULL,
    tick INTEGER NOT NULL,
    viewed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(post_id) REFERENCES post(post_id)
);

CREATE INDEX IF NOT EXISTS idx_feed_impression_user_tick
    ON feed_impression(user_id, tick, feed_type, rank);

CREATE TABLE IF NOT EXISTS topic (
    topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS audience_relationship (
    audience_user_id INTEGER NOT NULL,
    author_user_id INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    history_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY(audience_user_id, author_user_id),
    FOREIGN KEY(audience_user_id) REFERENCES user(user_id),
    FOREIGN KEY(author_user_id) REFERENCES user(user_id)
);

CREATE TABLE IF NOT EXISTS post_topic (
    post_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    PRIMARY KEY(post_id, topic_id),
    FOREIGN KEY(post_id) REFERENCES post(post_id),
    FOREIGN KEY(topic_id) REFERENCES topic(topic_id)
);
