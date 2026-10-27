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
