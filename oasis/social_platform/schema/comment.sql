-- This is the schema definition for the comment table
CREATE TABLE comment (
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
