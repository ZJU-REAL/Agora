"""Agora-owned SQLite lifecycle, migrations and nested action transactions."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class ActionConnection(sqlite3.Connection):
    action_depth = 0

    def commit(self):
        # Domain methods may commit for standalone callers. During a compound
        # action the outer savepoint owns durability and prevents partial writes.
        if not self.action_depth:
            super().commit()


class WorldStore:
    SCHEMA_VERSION = 1

    def __init__(self, path):
        self.db = sqlite3.connect(str(path), factory=ActionConnection)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = NORMAL")
        self.db.execute("PRAGMA busy_timeout = 5000")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > self.SCHEMA_VERSION:
            self.db.close()
            raise ValueError("World schema is newer than this Agora installation")
        # Add missing columns before indexes are created on an older world.
        self._columns(
            "post",
            {
                "community": "TEXT",
                "location": "TEXT",
                "reply_to_post_id": "INTEGER REFERENCES post(post_id)",
                "post_type": "TEXT NOT NULL DEFAULT 'text'",
                "title": "TEXT",
                "visibility": "TEXT NOT NULL DEFAULT 'public'",
                "language": "TEXT",
            },
        )
        self._columns(
            "comment",
            {
                "parent_comment_id": "INTEGER REFERENCES comment(comment_id)",
                "root_comment_id": "INTEGER REFERENCES comment(comment_id)",
                "reply_to_user_id": "INTEGER REFERENCES user(user_id)",
                "is_pinned": "INTEGER NOT NULL DEFAULT 0",
            },
        )
        self.db.executescript(
            (Path(__file__).parent / "schema" / "world.sql").read_text()
        )
        self.db.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        self.db.commit()
        self.db_cursor = self.db.cursor()
        self.closed = False

    def _columns(self, table, definitions):
        present = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
        if not present:
            return
        for name, definition in definitions.items():
            if name not in present:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    @property
    def depth(self):
        return self.db.action_depth

    @contextmanager
    def atomic(self):
        name = f"agora_action_{self.depth}"
        self.db.execute(f"SAVEPOINT {name}")
        self.db.action_depth += 1
        try:
            yield
        except BaseException:
            self.db.execute(f"ROLLBACK TO {name}")
            self.db.execute(f"RELEASE {name}")
            raise
        else:
            self.db.execute(f"RELEASE {name}")
        finally:
            self.db.action_depth -= 1

    def close(self):
        if not self.closed:
            self.db_cursor.close()
            self.db.close()
            self.closed = True
