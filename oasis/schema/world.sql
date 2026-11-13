-- Agora world schema. Compatible entity layout; lifecycle owned by WorldStore.
-- Derived entity definitions retain Apache-2.0 attribution in docs/upstream.md.

-- This is the schema definition for the user table
CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER,
    user_name TEXT,
    name TEXT,
    bio TEXT,
    created_at DATETIME,
    num_followings INTEGER DEFAULT 0,
    num_followers INTEGER DEFAULT 0
);

-- This is the schema definition for the post table
-- Add Images, location etc.?
CREATE TABLE IF NOT EXISTS post (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    original_post_id INTEGER,  -- NULL if this is an original post
    content TEXT DEFAULT '',  -- DEFAULT '' for initial posts
    quote_content TEXT,  -- NULL if this is an original post or a repost
    created_at DATETIME,
    num_likes INTEGER DEFAULT 0,
    num_dislikes INTEGER DEFAULT 0,
    num_shares INTEGER DEFAULT 0,  -- num_shares = num_reposts + num_quotes
    num_reports INTEGER DEFAULT 0,
    post_type TEXT NOT NULL DEFAULT 'text'
        CHECK(post_type IN ('text', 'image', 'gallery', 'video', 'article',
                            'repost', 'quote')),
    title TEXT,
    visibility TEXT NOT NULL DEFAULT 'public'
        CHECK(visibility IN ('public', 'followers', 'private', 'group')),
    language TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    edited_at_tick INTEGER,
    removed_by INTEGER REFERENCES user(user_id),
    link_url TEXT,
    community TEXT,
    location TEXT,
    reply_to_post_id INTEGER REFERENCES post(post_id),
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(original_post_id) REFERENCES post(post_id)
);

-- This is the schema definition for the comment table
CREATE TABLE IF NOT EXISTS comment (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    user_id INTEGER,
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    num_likes INTEGER DEFAULT 0,
    num_dislikes INTEGER DEFAULT 0,
    parent_comment_id INTEGER,
    root_comment_id INTEGER,
    reply_to_user_id INTEGER,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    edited_at_tick INTEGER,
    FOREIGN KEY(post_id) REFERENCES post(post_id),
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(parent_comment_id) REFERENCES comment(comment_id),
    FOREIGN KEY(root_comment_id) REFERENCES comment(comment_id),
    FOREIGN KEY(reply_to_user_id) REFERENCES user(user_id)
);

CREATE INDEX IF NOT EXISTS idx_comment_post_parent
    ON comment(post_id, parent_comment_id, created_at, comment_id);
CREATE INDEX IF NOT EXISTS idx_comment_root
    ON comment(root_comment_id, created_at, comment_id);

CREATE TABLE IF NOT EXISTS media_asset (
    asset_id TEXT PRIMARY KEY,
    media_type TEXT NOT NULL CHECK(media_type IN ('image', 'video', 'audio')),
    object_key TEXT NOT NULL UNIQUE,
    original_filename TEXT,
    mime_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
    checksum_sha256 TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    duration_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'ready'
        CHECK(status IN ('pending', 'ready', 'failed', 'deleted')),
    alt_text TEXT,
    caption TEXT,
    transcript TEXT,
    technical_metadata TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_media_asset_checksum
    ON media_asset(checksum_sha256);

CREATE TABLE IF NOT EXISTS post_asset (
    post_id INTEGER NOT NULL,
    asset_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    role TEXT NOT NULL DEFAULT 'content'
        CHECK(role IN ('content', 'cover', 'thumbnail', 'attachment')),
    caption TEXT,
    alt_text TEXT,
    transcript TEXT,
    PRIMARY KEY(post_id, position),
    UNIQUE(post_id, asset_id, role),
    FOREIGN KEY(post_id) REFERENCES post(post_id),
    FOREIGN KEY(asset_id) REFERENCES media_asset(asset_id)
);

CREATE INDEX IF NOT EXISTS idx_post_asset_asset ON post_asset(asset_id);

-- This is the schema definition for the follow table
CREATE TABLE IF NOT EXISTS follow (
    follow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id INTEGER,
    followee_id INTEGER,
    created_at DATETIME,
    FOREIGN KEY(follower_id) REFERENCES user(user_id),
    FOREIGN KEY(followee_id) REFERENCES user(user_id)
);

-- This is the schema definition for the like table
CREATE TABLE IF NOT EXISTS like (
    like_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    post_id INTEGER,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(post_id) REFERENCES post(post_id)
);

-- This is the schema definition for the dislike table
CREATE TABLE IF NOT EXISTS dislike (
    dislike_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    post_id INTEGER,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(post_id) REFERENCES post(post_id)
);

-- This is the schema definition for the comment_like table
CREATE TABLE IF NOT EXISTS comment_like (
    comment_like_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    comment_id INTEGER,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(comment_id) REFERENCES comment(comment_id)
);

-- This is the schema definition for the comment_dislike table
CREATE TABLE IF NOT EXISTS comment_dislike (
    comment_dislike_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    comment_id INTEGER,
    created_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user(user_id),
    FOREIGN KEY(comment_id) REFERENCES comment(comment_id)
);

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
    seed INTEGER NOT NULL DEFAULT 0,
    current_time_ms INTEGER NOT NULL DEFAULT 0,
    tick_duration_ms INTEGER NOT NULL DEFAULT 60000
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

-- This is the schema definition for the trace table
CREATE TABLE IF NOT EXISTS trace (
    user_id INTEGER,
    created_at DATETIME,
    action TEXT,
    info TEXT,
    PRIMARY KEY(user_id, created_at, action, info),
    FOREIGN KEY(user_id) REFERENCES user(user_id)
);

CREATE TABLE IF NOT EXISTS notification (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL REFERENCES user(user_id),
    actor_id INTEGER NOT NULL REFERENCES user(user_id),
    kind TEXT NOT NULL,
    post_id INTEGER REFERENCES post(post_id),
    comment_id INTEGER REFERENCES comment(comment_id),
    content TEXT NOT NULL DEFAULT '',
    tick INTEGER NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notification_recipient ON notification(recipient_id, notification_id);
CREATE TABLE IF NOT EXISTS creator_asset (
    user_id INTEGER NOT NULL REFERENCES user(user_id),
    asset_id TEXT NOT NULL REFERENCES media_asset(asset_id),
    alt_text TEXT,
    transcript TEXT,
    PRIMARY KEY(user_id, asset_id)
);
CREATE TABLE IF NOT EXISTS agent_memory (
    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(user_id),
    tick INTEGER NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0.5,
    source_session_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_user ON agent_memory(user_id, memory_id);


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

CREATE TABLE IF NOT EXISTS agent_model_call (
 call_id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id INTEGER NOT NULL REFERENCES agora_session(session_id),
 step INTEGER NOT NULL, tick INTEGER NOT NULL,
 status TEXT NOT NULL, model_id TEXT, input_tokens INTEGER, output_tokens INTEGER,
 elapsed_ms REAL, error_type TEXT, request_id TEXT, decision_id TEXT, ordinal INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO creator_asset(user_id, asset_id)
 SELECT p.user_id, pa.asset_id FROM post_asset pa JOIN post p ON p.post_id = pa.post_id;

CREATE INDEX IF NOT EXISTS idx_agora_like_user_post ON "like"(user_id, post_id);
CREATE INDEX IF NOT EXISTS idx_agora_like_post_user ON "like"(post_id, user_id);

CREATE TABLE IF NOT EXISTS community (
 name TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 rules_json TEXT NOT NULL DEFAULT '[]', creator_id INTEGER REFERENCES user(user_id),
 visibility TEXT NOT NULL DEFAULT 'public' CHECK(visibility IN ('public','restricted','private'))
);
CREATE TABLE IF NOT EXISTS community_member (
 community TEXT NOT NULL REFERENCES community(name), user_id INTEGER NOT NULL REFERENCES user(user_id),
 role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('member','moderator')), approved INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(community,user_id)
);
CREATE TABLE IF NOT EXISTS collection_folder (
 folder_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES user(user_id),
 name TEXT NOT NULL, UNIQUE(user_id,name)
);
CREATE TABLE IF NOT EXISTS folder_post (
 folder_id INTEGER NOT NULL REFERENCES collection_folder(folder_id), post_id INTEGER NOT NULL REFERENCES post(post_id), PRIMARY KEY(folder_id,post_id)
);
CREATE TABLE IF NOT EXISTS agent_decision (
 decision_id TEXT PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES agora_session(session_id),
 user_id INTEGER NOT NULL REFERENCES user(user_id), tick INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','ready','succeeded','failed')),
 action_json TEXT, result_json TEXT, request_hash TEXT, step INTEGER,
 before_json TEXT NOT NULL, after_json TEXT, model_records_json TEXT NOT NULL DEFAULT '[]', failure_type TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_call_decision ON agent_model_call(decision_id,ordinal);
CREATE TABLE IF NOT EXISTS agent_api_token (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user(user_id), revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS client_asset (
 user_id INTEGER NOT NULL REFERENCES user(user_id), asset_id TEXT NOT NULL REFERENCES media_asset(asset_id), PRIMARY KEY(user_id,asset_id)
);
