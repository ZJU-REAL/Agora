"""Native community, voting, editing and collection operations."""

import json
import re


class PlatformActions:
    def require_post(self, user, post_id):
        posts = self.get_feed(
            user,
            1,
            record_impressions=False,
            eligible_post_ids=[post_id],
            include_comments=False,
        )
        if not posts:
            raise PermissionError("Post is unavailable to this account")
        return posts[0]

    def require_comment(self, user, comment_id):
        row = self.db.execute(
            "SELECT post_id, user_id FROM comment WHERE comment_id = ?", (comment_id,)
        ).fetchone()
        if row is None:
            raise KeyError("Unknown comment")
        self.require_post(user, row[0])
        return row

    def vote_post(self, user_id, post_id, value):
        if self.preset.name != "reddit" or value not in {-1, 0, 1}:
            raise ValueError("Post voting is a Reddit action")
        self.require_post(user_id, post_id)
        with self.atomic():
            up = bool(
                self.db.execute(
                    'SELECT 1 FROM "like" WHERE user_id = ? AND post_id = ?',
                    (user_id, post_id),
                ).fetchone()
            )
            down = bool(
                self.db.execute(
                    "SELECT 1 FROM dislike WHERE user_id = ? AND post_id = ?",
                    (user_id, post_id),
                ).fetchone()
            )
            before = int(up) - int(down)
            if before == value:
                return False
            self.db.execute(
                'DELETE FROM "like" WHERE user_id = ? AND post_id = ?',
                (user_id, post_id),
            )
            self.db.execute(
                "DELETE FROM dislike WHERE user_id = ? AND post_id = ?",
                (user_id, post_id),
            )
            if value:
                table = '"like"' if value > 0 else "dislike"
                self.db.execute(
                    f"INSERT INTO {table}(user_id, post_id, created_at) VALUES (?, ?, ?)",
                    (user_id, post_id, self.current_tick),
                )
            self.db.execute(
                "UPDATE post SET num_likes = MAX(0, num_likes + ?), num_dislikes = MAX(0, num_dislikes + ?) WHERE post_id = ?",
                (int(value == 1) - int(up), int(value == -1) - int(down), post_id),
            )
            self._record_event(
                "post_vote_changed",
                user_id,
                "post",
                post_id,
                {"before": before, "value": value},
            )
        return True

    def vote_comment(self, user_id, comment_id, value):
        if value not in {-1, 0, 1} or value < 0 and self.preset.name != "reddit":
            raise ValueError("Unavailable comment vote")
        self.require_comment(user_id, comment_id)
        with self.atomic():
            up = bool(
                self.db.execute(
                    "SELECT 1 FROM comment_like WHERE user_id = ? AND comment_id = ?",
                    (user_id, comment_id),
                ).fetchone()
            )
            down = bool(
                self.db.execute(
                    "SELECT 1 FROM comment_dislike WHERE user_id = ? AND comment_id = ?",
                    (user_id, comment_id),
                ).fetchone()
            )
            if int(up) - int(down) == value:
                return False
            for table in ("comment_like", "comment_dislike"):
                self.db.execute(
                    f"DELETE FROM {table} WHERE user_id = ? AND comment_id = ?",
                    (user_id, comment_id),
                )
            if value:
                table = "comment_like" if value > 0 else "comment_dislike"
                self.db.execute(
                    f"INSERT INTO {table}(user_id, comment_id, created_at) VALUES (?, ?, ?)",
                    (user_id, comment_id, self.current_tick),
                )
            self.db.execute(
                "UPDATE comment SET num_likes = MAX(0, num_likes + ?), num_dislikes = MAX(0, num_dislikes + ?) WHERE comment_id = ?",
                (int(value == 1) - int(up), int(value == -1) - int(down), comment_id),
            )
            self._record_event(
                "comment_vote_changed", user_id, "comment", comment_id, {"value": value}
            )
        return True

    def save_post(self, user_id, post_id, saved=True):
        self.require_post(user_id, post_id)
        with self.atomic():
            if saved:
                cursor = self.db.execute(
                    "INSERT OR IGNORE INTO collection(user_id, post_id, created_at_tick) VALUES (?, ?, ?)",
                    (user_id, post_id, self.current_tick),
                )
            else:
                cursor = self.db.execute(
                    "DELETE FROM collection WHERE user_id = ? AND post_id = ?",
                    (user_id, post_id),
                )
                self.db.execute(
                    "DELETE FROM folder_post WHERE post_id = ? AND folder_id IN (SELECT folder_id FROM collection_folder WHERE user_id = ?)",
                    (post_id, user_id),
                )
            changed = bool(cursor.rowcount)
            if changed:
                self._record_event(
                    "post_saved" if saved else "post_unsaved",
                    user_id,
                    "post",
                    post_id,
                    {},
                )
        return changed

    def edit_post(self, user_id, post_id, body=None, title=None):
        post = self.require_post(user_id, post_id)
        if post["author_id"] != user_id:
            raise PermissionError("Only the author may edit a post")
        if self.preset.name == "x":
            raise ValueError(
                "Editing requires an X subscription; this contract models standard accounts"
            )
        if self.preset.name == "reddit" and title is not None:
            raise ValueError("Reddit post titles cannot be edited")
        with self.atomic():
            self.db.execute(
                "UPDATE post SET content = ?, title = ?, edited_at_tick = ? WHERE post_id = ?",
                (
                    post["body"] if body is None else body,
                    post["title"] if title is None else title,
                    self.current_tick,
                    post_id,
                ),
            )
            self._record_event(
                "post_edited", user_id, "post", post_id, {"body": body, "title": title}
            )
        return True

    def delete_post(self, user_id, post_id):
        post = self.require_post(user_id, post_id)
        if post["author_id"] != user_id:
            raise PermissionError("Only the author may delete this post")
        with self.atomic():
            self.db.execute("UPDATE post SET deleted = 1 WHERE post_id = ?", (post_id,))
            if post.get("original_post_id") is not None and post["post_type"] in {
                "repost",
                "quote",
            }:
                self.db.execute(
                    "UPDATE post SET num_shares = MAX(0, num_shares - 1) WHERE post_id = ?",
                    (post["original_post_id"],),
                )
            self._record_event("post_deleted", user_id, "post", post_id, {})
        return True

    def edit_comment(self, user_id, comment_id, content):
        _, author = self.require_comment(user_id, comment_id)
        if author != user_id:
            raise PermissionError("Only the author may edit this comment")
        if self.preset.name == "x":
            raise ValueError("Standard X replies cannot be edited")
        with self.atomic():
            self.db.execute(
                "UPDATE comment SET content = ?, edited_at_tick = ? WHERE comment_id = ? AND deleted = 0",
                (content, self.current_tick, comment_id),
            )
            self._record_event(
                "comment_edited", user_id, "comment", comment_id, {"content": content}
            )
        return True

    def delete_comment(self, user_id, comment_id):
        _, author = self.require_comment(user_id, comment_id)
        if author != user_id:
            raise PermissionError("Only the author may delete this comment")
        with self.atomic():
            self.db.execute(
                "UPDATE comment SET deleted = 1, content = '[deleted]' WHERE comment_id = ?",
                (comment_id,),
            )
            self._record_event("comment_deleted", user_id, "comment", comment_id, {})
        return True

    def create_community(
        self, user_id, name, title, description="", rules=None, visibility="public"
    ):
        if self.preset.name != "reddit":
            raise ValueError("Communities are a Reddit feature")
        name = name if name.startswith("r/") else "r/" + name
        if not re.fullmatch(r"r/[A-Za-z0-9_]{3,21}", name) or visibility not in {
            "public",
            "restricted",
            "private",
        }:
            raise ValueError("Invalid community name or visibility")
        if self.db.execute(
            "SELECT 1 FROM community WHERE name = ?", (name,)
        ).fetchone():
            raise ValueError("Community already exists")
        if not isinstance(rules or [], list) or any(
            not isinstance(rule, str) or len(rule) > 1000 for rule in rules or []
        ):
            raise ValueError("rules must be a list of short text rules")
        with self.atomic():
            self.db.execute(
                "INSERT INTO community(name, title, description, rules_json, creator_id, visibility) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    name,
                    title,
                    description,
                    json.dumps(rules or [], ensure_ascii=False),
                    user_id,
                    visibility,
                ),
            )
            self.db.execute(
                "INSERT INTO community_member(community, user_id, role) VALUES (?, ?, 'moderator')",
                (name, user_id),
            )
            self._record_event(
                "community_created",
                user_id,
                "community",
                name,
                {"visibility": visibility},
            )
        return name

    def list_communities(self, user_id):
        rows = self.db.execute(
            "SELECT c.name, c.title, c.description, c.rules_json, c.visibility, (SELECT role FROM community_member m WHERE m.community = c.name AND m.user_id = ?), (SELECT COUNT(*) FROM community_member m WHERE m.community = c.name), COALESCE((SELECT approved FROM community_member m WHERE m.community=c.name AND m.user_id=?),0) FROM community c WHERE c.visibility != 'private' OR EXISTS (SELECT 1 FROM community_member m WHERE m.community = c.name AND m.user_id = ?) ORDER BY c.name",
            (user_id, user_id, user_id),
        ).fetchall()
        return [
            {
                "name": r[0],
                "title": r[1],
                "description": r[2],
                "rules": json.loads(r[3]),
                "visibility": r[4],
                "role": r[5],
                "joined": r[5] is not None,
                "members": r[6],
                "posting_allowed": r[4] == "public"
                or bool(r[5] and (r[4] == "private" or r[5] == "moderator" or r[7])),
            }
            for r in rows
        ]

    def join_community(self, user_id, community, joining=True):
        row = self.db.execute(
            "SELECT visibility FROM community WHERE name = ?", (community,)
        ).fetchone()
        if row is None:
            raise KeyError("Unknown community")
        if joining and row[0] == "private":
            raise PermissionError("Private communities require moderator approval")
        with self.atomic():
            if joining:
                cursor = self.db.execute(
                    "INSERT OR IGNORE INTO community_member(community,user_id) VALUES (?, ?)",
                    (community, user_id),
                )
            else:
                if self.is_moderator(user_id, community):
                    raise ValueError(
                        "A moderator must transfer their role before leaving"
                    )
                cursor = self.db.execute(
                    "DELETE FROM community_member WHERE community = ? AND user_id = ?",
                    (community, user_id),
                )
            self._record_event(
                "community_joined" if joining else "community_left",
                user_id,
                "community",
                community,
                {},
            )
        return bool(cursor.rowcount)

    def is_moderator(self, user_id, community):
        return bool(
            self.db.execute(
                "SELECT 1 FROM community_member WHERE community = ? AND user_id = ? AND role = 'moderator'",
                (community, user_id),
            ).fetchone()
        )

    def can_post_to(self, user_id, community):
        row = self.db.execute(
            "SELECT visibility FROM community WHERE name = ?", (community,)
        ).fetchone()
        if row is None:
            raise KeyError("Unknown community")
        member = self.db.execute(
            "SELECT role,approved FROM community_member WHERE community = ? AND user_id = ?",
            (community, user_id),
        ).fetchone()
        if (
            row[0] == "public"
            or member
            and (row[0] == "private" or member[0] == "moderator" or member[1])
        ):
            return True
        raise PermissionError("Posting in this community requires approval")

    def approve_member(self, user_id, community, member_id):
        if not self.is_moderator(user_id, community):
            raise PermissionError("Only the community moderator may approve a member")
        with self.atomic():
            self.db.execute(
                "INSERT INTO community_member(community,user_id,approved) VALUES (?, ?, 1) ON CONFLICT(community,user_id) DO UPDATE SET approved=1",
                (community, member_id),
            )
            self._record_event(
                "member_approved",
                user_id,
                "community",
                community,
                {"user_id": member_id},
            )
        return True

    def moderate_post(self, user_id, post_id, removed=True, reason=""):
        row = self.db.execute(
            "SELECT community, deleted FROM post WHERE post_id = ?", (post_id,)
        ).fetchone()
        if (
            row is None
            or self.preset.name != "reddit"
            or not self.is_moderator(user_id, row[0])
        ):
            raise PermissionError(
                "Only this community's moderator may moderate the post"
            )
        if row[1]:
            raise ValueError("Author-deleted posts cannot be restored")
        with self.atomic():
            self.db.execute(
                "UPDATE post SET removed_by = ? WHERE post_id = ?",
                (user_id if removed else None, post_id),
            )
            self._record_event(
                "post_removed" if removed else "post_approved",
                user_id,
                "post",
                post_id,
                {"reason": reason},
            )
        return True

    def create_collection(self, user_id, name):
        if self.preset.name != "xiaohongshu":
            raise ValueError("Collection albums are a Xiaohongshu feature")
        with self.atomic():
            cursor = self.db.execute(
                "INSERT INTO collection_folder(user_id, name) VALUES (?, ?)",
                (user_id, name),
            )
            self._record_event(
                "collection_created",
                user_id,
                "collection",
                cursor.lastrowid,
                {"name": name},
            )
        return cursor.lastrowid

    def add_to_collection(self, user_id, folder_id, post_id):
        if not self.db.execute(
            "SELECT 1 FROM collection_folder WHERE folder_id = ? AND user_id = ?",
            (folder_id, user_id),
        ).fetchone():
            raise PermissionError("Collection belongs to another account")
        with self.atomic():
            self.save_post(user_id, post_id)
            self.db.execute(
                "INSERT OR IGNORE INTO folder_post(folder_id,post_id) VALUES (?, ?)",
                (folder_id, post_id),
            )
            self._record_event(
                "collection_updated",
                user_id,
                "collection",
                folder_id,
                {"post_id": post_id},
            )
        return True

    def set_time(self, time_ms):
        if type(time_ms) is not int or time_ms < self.current_time_ms:
            raise ValueError("Simulation time cannot move backwards")
        self.db.execute(
            "UPDATE simulation_state SET current_time_ms = ?, current_tick = ? / tick_duration_ms WHERE singleton = 1",
            (time_ms, time_ms),
        )
        self.db.commit()

    @property
    def current_time_ms(self):
        return self.db.execute(
            "SELECT MAX(current_time_ms,current_tick*tick_duration_ms) FROM simulation_state WHERE singleton=1"
        ).fetchone()[0]
