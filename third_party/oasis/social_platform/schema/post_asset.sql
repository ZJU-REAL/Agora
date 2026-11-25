CREATE TABLE IF NOT EXISTS post_asset (
    post_id INTEGER NOT NULL,
    asset_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    role TEXT NOT NULL DEFAULT 'content'
        CHECK(role IN ('content', 'cover', 'thumbnail', 'attachment')),
    caption TEXT,
    PRIMARY KEY(post_id, position),
    UNIQUE(post_id, asset_id, role),
    FOREIGN KEY(post_id) REFERENCES post(post_id),
    FOREIGN KEY(asset_id) REFERENCES media_asset(asset_id)
);

CREATE INDEX IF NOT EXISTS idx_post_asset_asset ON post_asset(asset_id);
