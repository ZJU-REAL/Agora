# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from __future__ import annotations

import json
import random
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oasis.agora_types import (PLATFORM_PRESETS, AssetInput, Observation,
                               PersonaProfile, PlatformPreset, TickResult)
from oasis.social_platform.media_store import (ImportedMedia, LocalMediaStore,
                                                MediaLimits,
                                                media_record_values)
from oasis.social_platform.platform import Platform


@dataclass(frozen=True)
class AgoraOasisConfig:
    world_id: str
    data_root: Path = Path("data/worlds")
    preset: str = "generic"
    max_image_bytes: int = 20 * 1024 * 1024
    max_video_bytes: int = 500 * 1024 * 1024
    max_video_duration_ms: int = 10 * 60 * 1000

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
                            self.world_id):
            raise ValueError("world_id contains unsupported characters.")
        if self.preset not in PLATFORM_PRESETS:
            raise ValueError(f"Unknown platform preset: {self.preset}")
        object.__setattr__(self, "data_root", Path(self.data_root))

    @property
    def world_dir(self) -> Path:
        return self.data_root / self.world_id

    @property
    def database_path(self) -> Path:
        return self.world_dir / "sandbox.db"

    @property
    def media_path(self) -> Path:
        return self.world_dir / "media"


class AgoraOasis:
    """Single entry point for one enhanced OASIS social sandbox world."""

    def __init__(self, config: AgoraOasisConfig):
        self.config = config
        self.preset: PlatformPreset = PLATFORM_PRESETS[config.preset]
        config.world_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_world_manifest()
        # Agora uses simulated ticks for every preset; upstream's Reddit clock
        # derives timestamps from wall time and breaks episode reproduction.
        self.platform = Platform(db_path=str(config.database_path),
                                 recsys_type="twitter",
                                 platform_style=self.preset.name)
        self.media = LocalMediaStore(
            config.media_path,
            limits=MediaLimits(
                max_image_bytes=config.max_image_bytes,
                max_video_bytes=config.max_video_bytes,
                max_video_duration_ms=config.max_video_duration_ms,
            ),
        )

    def _ensure_world_manifest(self) -> None:
        path = self.config.world_dir / "world.json"
        if path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            if stored.get("preset") != self.config.preset:
                raise ValueError(
                    f"World uses preset {stored.get('preset')!r}, not "
                    f"{self.config.preset!r}.")
            return
        path.write_text(json.dumps({
            "world_id": self.config.world_id,
            "preset": self.config.preset,
            "format_version": 1,
        }, indent=2), encoding="utf-8")

    @classmethod
    def local(cls,
              world_id: str,
              data_root: str | Path = "data/worlds",
              preset: str | None = None) -> "AgoraOasis":
        data_root = Path(data_root)
        if preset is None:
            manifest_path = data_root / world_id / "world.json"
            if manifest_path.exists():
                preset = json.loads(manifest_path.read_text(
                    encoding="utf-8")).get("preset", "generic")
            else:
                preset = "generic"
        return cls(AgoraOasisConfig(world_id=world_id,
                                    data_root=data_root,
                                    preset=preset))

    def import_media(self, source: str | Path) -> ImportedMedia:
        media = self.media.import_file(source)
        self.platform.db.execute(
            "INSERT INTO media_asset "
            "(asset_id, media_type, object_key, original_filename, mime_type, "
            "byte_size, checksum_sha256, width, height, duration_ms, "
            "technical_metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            media_record_values(media),
        )
        self.platform.db.commit()
        return media

    @property
    def current_tick(self) -> int:
        return self.platform.db.execute(
            "SELECT current_tick FROM simulation_state WHERE singleton = 1"
        ).fetchone()[0]

    def set_seed(self, seed: int) -> None:
        self.platform.db.execute(
            "UPDATE simulation_state SET seed = ? WHERE singleton = 1",
            (seed, ))
        self.platform.db.commit()

    def create_user(self,
                    handle: str,
                    display_name: str,
                    bio: str = "",
                    user_id: int | None = None) -> int:
        if user_id is None:
            row = self.platform.db.execute(
                "SELECT COALESCE(MAX(user_id), 0) + 1 FROM user").fetchone()
            user_id = row[0]
        self.platform.db.execute(
            "INSERT INTO user (user_id, agent_id, user_name, name, bio, "
            "created_at, num_followings, num_followers) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
            (user_id, user_id, handle, display_name, bio, self.current_tick),
        )
        self._record_event("user_created", user_id, "user", user_id,
                           {"handle": handle})
        self.platform.db.commit()
        return user_id

    def add_persona(self, profile: PersonaProfile) -> int:
        user_id = self.create_user(profile.handle, profile.display_name,
                                   profile.bio)
        self.platform.db.execute(
            "INSERT INTO persona (profile_id, user_id, profile_version, "
            "persona_json, policy_type) VALUES (?, ?, ?, ?, ?)",
            (profile.profile_id, user_id, profile.profile_version,
             json.dumps(profile.__dict__, ensure_ascii=False),
             profile.policy_type),
        )
        self._record_event("persona_attached", user_id, "persona",
                           profile.profile_id,
                           {"profile_version": profile.profile_version})
        self.platform.db.commit()
        return user_id

    def create_post(self,
                    author_id: int,
                    body: str = "",
                    title: str | None = None,
                    post_type: str = "text",
                    assets: list[AssetInput] | None = None,
                    topics: list[str] | None = None,
                    language: str | None = None,
                    visibility: str = "public",
                    community: str | None = None,
                    location: str | None = None,
                    reply_to_post_id: int | None = None) -> int:
        assets = assets or []
        self._validate_post(post_type, body, assets)
        imported_assets = [(self.import_media(item.path), item)
                           for item in assets]
        self._validate_imported_assets(post_type, imported_assets)
        for media, asset_input in imported_assets:
            if asset_input.alt_text is not None or asset_input.transcript is not None:
                self.platform.db.execute(
                    "UPDATE media_asset SET alt_text = ?, transcript = ? "
                    "WHERE asset_id = ?",
                    (asset_input.alt_text, asset_input.transcript,
                     media.asset_id))
        cursor = self.platform.db.execute(
            "INSERT INTO post (user_id, content, created_at, num_likes, "
            "num_dislikes, num_shares, post_type, title, visibility, "
            "language, community, location, reply_to_post_id) "
            "VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?)",
            (author_id, body, self.current_tick, post_type, title, visibility,
             language, community, location, reply_to_post_id),
        )
        post_id = cursor.lastrowid
        for position, (media, asset_input) in enumerate(imported_assets):
            self.platform.db.execute(
                "INSERT INTO post_asset "
                "(post_id, asset_id, position, role, caption) "
                "VALUES (?, ?, ?, ?, ?)",
                (post_id, media.asset_id, position, asset_input.role,
                 asset_input.caption),
            )
        for topic_name in dict.fromkeys(topics or []):
            normalized = topic_name.strip().lstrip("#")
            if not normalized:
                continue
            self.platform.db.execute(
                "INSERT OR IGNORE INTO topic(name) VALUES (?)", (normalized, ))
            topic_id = self.platform.db.execute(
                "SELECT topic_id FROM topic WHERE name = ?", (normalized, )
            ).fetchone()[0]
            self.platform.db.execute(
                "INSERT OR IGNORE INTO post_topic(post_id, topic_id) "
                "VALUES (?, ?)", (post_id, topic_id))
        self._record_event("post_created", author_id, "post", post_id, {
            "post_type": post_type,
            "title": title,
            "body": body,
            "asset_count": len(assets),
            "topics": topics or [],
        })
        self.platform.db.commit()
        return post_id

    async def create_comment(self,
                             author_id: int,
                             post_id: int,
                             content: str,
                             parent_comment_id: int | None = None) -> dict:
        result = await self.platform.create_comment(
            author_id, (post_id, content, parent_comment_id))
        if result.get("success"):
            self._record_event("comment_created", author_id, "comment",
                               result["comment_id"], result)
            self.platform.db.commit()
        return result

    def like_post(self, user_id: int, post_id: int) -> bool:
        existing = self.platform.db.execute(
            'SELECT 1 FROM "like" WHERE user_id = ? AND post_id = ?',
            (user_id, post_id)).fetchone()
        if existing:
            return False
        self.platform.db.execute(
            'INSERT INTO "like" (user_id, post_id, created_at) '
            'VALUES (?, ?, ?)', (user_id, post_id, self.current_tick))
        self.platform.db.execute(
            "UPDATE post SET num_likes = num_likes + 1 WHERE post_id = ?",
            (post_id, ))
        self._record_event("post_liked", user_id, "post", post_id, {})
        self.platform.db.commit()
        return True

    def unlike_post(self, user_id: int, post_id: int) -> bool:
        cursor = self.platform.db.execute(
            'DELETE FROM "like" WHERE user_id = ? AND post_id = ?',
            (user_id, post_id))
        if not cursor.rowcount:
            return False
        self.platform.db.execute(
            "UPDATE post SET num_likes = MAX(0, num_likes - 1) "
            "WHERE post_id = ?", (post_id, ))
        self._record_event("post_unliked", user_id, "post", post_id, {})
        self.platform.db.commit()
        return True

    def collect_post(self, user_id: int, post_id: int) -> bool:
        if not self.preset.allow_collect:
            raise ValueError(f"Collections are disabled for {self.preset.name}.")
        cursor = self.platform.db.execute(
            "INSERT OR IGNORE INTO collection "
            "(user_id, post_id, created_at_tick) VALUES (?, ?, ?)",
            (user_id, post_id, self.current_tick))
        if not cursor.rowcount:
            return False
        self._record_event("post_collected", user_id, "post", post_id, {})
        self.platform.db.commit()
        return True

    def uncollect_post(self, user_id: int, post_id: int) -> bool:
        cursor = self.platform.db.execute(
            "DELETE FROM collection WHERE user_id = ? AND post_id = ?",
            (user_id, post_id))
        if not cursor.rowcount:
            return False
        self._record_event("post_uncollected", user_id, "post", post_id, {})
        self.platform.db.commit()
        return True

    def follow_user(self, follower_id: int, followee_id: int) -> bool:
        if follower_id == followee_id:
            raise ValueError("Users cannot follow themselves.")
        existing = self.platform.db.execute(
            "SELECT 1 FROM follow WHERE follower_id = ? AND followee_id = ?",
            (follower_id, followee_id)).fetchone()
        if existing:
            return False
        self.platform.db.execute(
            "INSERT INTO follow (follower_id, followee_id, created_at) "
            "VALUES (?, ?, ?)", (follower_id, followee_id, self.current_tick))
        self.platform.db.execute(
            "UPDATE user SET num_followings = num_followings + 1 "
            "WHERE user_id = ?", (follower_id, ))
        self.platform.db.execute(
            "UPDATE user SET num_followers = num_followers + 1 "
            "WHERE user_id = ?", (followee_id, ))
        self._record_event("user_followed", follower_id, "user", followee_id,
                           {})
        self.platform.db.commit()
        return True

    def unfollow_user(self, follower_id: int, followee_id: int) -> bool:
        cursor = self.platform.db.execute(
            "DELETE FROM follow WHERE follower_id = ? AND followee_id = ?",
            (follower_id, followee_id))
        if not cursor.rowcount:
            return False
        self.platform.db.execute(
            "UPDATE user SET num_followings = MAX(0, num_followings - 1) "
            "WHERE user_id = ?", (follower_id, ))
        self.platform.db.execute(
            "UPDATE user SET num_followers = MAX(0, num_followers - 1) "
            "WHERE user_id = ?", (followee_id, ))
        self._record_event("user_unfollowed", follower_id, "user", followee_id,
                           {})
        self.platform.db.commit()
        return True

    def view_post(self, user_id: int, post_id: int) -> dict[str, Any]:
        feed_item = next((item for item in self.get_feed(
            user_id, 200, record_impressions=False)
                          if item["post_id"] == post_id), None)
        if feed_item is None:
            raise KeyError(f"Unknown post_id: {post_id}")
        row = self.platform.db.execute(
            "SELECT impression_id FROM feed_impression WHERE user_id = ? "
            "AND post_id = ? AND tick = ? ORDER BY impression_id DESC LIMIT 1",
            (user_id, post_id, self.current_tick)).fetchone()
        if row:
            self.platform.db.execute(
                "UPDATE feed_impression SET viewed = 1 WHERE impression_id = ?",
                (row[0], ))
        self._record_event("post_viewed", user_id, "post", post_id, {})
        self.platform.db.commit()
        return feed_item

    def available_actions(self) -> tuple[str, ...]:
        actions = ["create_post", "create_comment", "reply_comment",
                   "like_post", "unlike_post", "follow_user",
                   "unfollow_user", "view_post"]
        if self.preset.allow_collect:
            actions.extend(("collect_post", "uncollect_post"))
        if self.preset.allow_dislike:
            actions.append("dislike_post")
        if self.preset.allow_repost:
            actions.extend(("repost", "quote_post"))
        actions.append("search_posts")
        if self.preset.name == "xiaohongshu":
            actions.append("pin_comment")
        return tuple(actions)

    def dislike_post(self, user_id: int, post_id: int) -> bool:
        if not self.preset.allow_dislike:
            raise ValueError(f"Dislikes are disabled for {self.preset.name}.")
        if self.platform.db.execute(
                "SELECT 1 FROM dislike WHERE user_id = ? AND post_id = ?",
                (user_id, post_id)).fetchone():
            return False
        self.platform.db.execute(
            "INSERT INTO dislike(user_id, post_id, created_at) VALUES (?, ?, ?)",
            (user_id, post_id, self.current_tick))
        self.platform.db.execute(
            "UPDATE post SET num_dislikes = num_dislikes + 1 WHERE post_id = ?",
            (post_id, ))
        self._record_event("post_disliked", user_id, "post", post_id, {})
        self.platform.db.commit()
        return True

    def repost(self, user_id: int, post_id: int, quote_body: str | None = None,
               community: str | None = None) -> int:
        if not self.preset.allow_repost:
            raise ValueError(f"Reposts are disabled for {self.preset.name}.")
        if not self.platform.db.execute(
                "SELECT 1 FROM post WHERE post_id = ?", (post_id, )).fetchone():
            raise KeyError(f"Unknown post_id: {post_id}")
        post_type = "quote" if quote_body else "repost"
        cursor = self.platform.db.execute(
            "INSERT INTO post(user_id, original_post_id, content, quote_content, "
            "created_at, post_type, community) VALUES (?, ?, '', ?, ?, ?, ?)",
            (user_id, post_id, quote_body, self.current_tick, post_type,
             community))
        self.platform.db.execute(
            "UPDATE post SET num_shares = num_shares + 1 WHERE post_id = ?",
            (post_id, ))
        repost_id = int(cursor.lastrowid)
        self._record_event("post_quoted" if quote_body else "post_reposted",
                           user_id, "post", post_id, {"new_post_id": repost_id})
        self.platform.db.commit()
        return repost_id

    def search_posts(self, user_id: int, query: str,
                     community: str | None = None, limit: int = 20) -> list[dict]:
        normalized = query.strip().lstrip("#")
        if not normalized:
            raise ValueError("Search query cannot be empty")
        feed = self.get_feed(user_id, 200, record_impressions=False)
        matches = []
        for post in feed:
            if community and post.get("community") != community:
                continue
            haystack = " ".join([post.get("title") or "", post.get("body") or "",
                                 *post.get("topics", [])]).casefold()
            if normalized.casefold() in haystack:
                matches.append(post)
        return matches[:limit]

    def pin_comment(self, author_id: int, comment_id: int) -> bool:
        row = self.platform.db.execute(
            "SELECT c.post_id, p.user_id FROM comment c JOIN post p "
            "ON p.post_id = c.post_id WHERE c.comment_id = ?",
            (comment_id, )).fetchone()
        if row is None:
            raise KeyError(f"Unknown comment_id: {comment_id}")
        if row[1] != author_id:
            raise PermissionError("Only the post author can pin comments")
        self.platform.db.execute(
            "UPDATE comment SET is_pinned = 0 WHERE post_id = ?", (row[0], ))
        self.platform.db.execute(
            "UPDATE comment SET is_pinned = 1 WHERE comment_id = ?", (comment_id, ))
        self._record_event("comment_pinned", author_id, "comment", comment_id, {})
        self.platform.db.commit()
        return True

    def get_thread(self, post_id: int) -> list[dict[str, Any]]:
        rows = self.platform.db.execute(
            "SELECT comment_id, user_id, content, created_at, num_likes, "
            "num_dislikes, parent_comment_id, root_comment_id, "
            "reply_to_user_id, is_pinned FROM comment WHERE post_id = ? "
            "ORDER BY is_pinned DESC, created_at, comment_id", (post_id, )).fetchall()
        flat = [{
            "comment_id": row[0],
            "author_id": row[1],
            "content": row[2],
            "created_at": row[3],
            "num_likes": row[4],
            "num_dislikes": row[5],
            "parent_comment_id": row[6],
            "root_comment_id": row[7],
            "reply_to_user_id": row[8],
            "is_pinned": bool(row[9]),
            "replies": [],
        } for row in rows]
        by_id = {item["comment_id"]: item for item in flat}
        roots = []
        for item in flat:
            parent_id = item["parent_comment_id"]
            if parent_id is None:
                roots.append(item)
            elif parent_id in by_id:
                by_id[parent_id]["replies"].append(item)
        return roots

    def get_post_topics(self, post_id: int) -> list[str]:
        return [row[0] for row in self.platform.db.execute(
            "SELECT t.name FROM post_topic pt JOIN topic t "
            "ON t.topic_id = pt.topic_id WHERE pt.post_id = ? "
            "ORDER BY t.name", (post_id, )).fetchall()]

    def get_feed(self,
                 user_id: int,
                 limit: int = 20,
                 feed_type: str = "discover",
                 record_impressions: bool = True,
                 eligible_post_ids: list[int] | tuple[int, ...] | None = None
                 ) -> list[dict[str, Any]]:
        if feed_type not in self.preset.feed_types:
            raise ValueError(f"Feed {feed_type!r} is unavailable for "
                             f"preset {self.preset.name!r}.")
        following_clause = ""
        params: tuple[Any, ...] = ()
        if feed_type == "following":
            following_clause = (
                "JOIN follow f ON f.followee_id = p.user_id "
                "AND f.follower_id = ? ")
            params = (user_id, )
        visibility_clause = (
            "WHERE (p.visibility = 'public' OR p.user_id = ? OR "
            "(p.visibility = 'followers' AND EXISTS (SELECT 1 FROM follow vf "
            "WHERE vf.follower_id = ? AND vf.followee_id = p.user_id))) ")
        params = (*params, user_id, user_id)
        rows = self.platform.db.execute(
            "SELECT p.post_id, p.user_id, u.user_name, u.name, p.post_type, "
            "p.title, p.content, p.created_at, p.num_likes, p.num_shares, "
            "(SELECT COUNT(*) FROM collection c WHERE c.post_id = p.post_id), "
            "(SELECT COUNT(*) FROM comment cm WHERE cm.post_id = p.post_id), "
            "p.community, p.location, p.original_post_id, p.quote_content, "
            "p.reply_to_post_id, p.num_dislikes "
            "FROM post p JOIN user u ON u.user_id = p.user_id "
            f"{following_clause}"
            f"{visibility_clause}"
            "ORDER BY p.post_id DESC", params
        ).fetchall()
        if eligible_post_ids is not None:
            eligible = set(eligible_post_ids)
            rows = [row for row in rows if row[0] in eligible]
        interests = {}
        persona_row = self.platform.db.execute(
            "SELECT persona_json FROM persona WHERE user_id = ?",
            (user_id, )).fetchone()
        if persona_row:
            interests = PersonaProfile.from_dict(
                json.loads(persona_row[0])).interests
        followed_authors = {int(row[0]) for row in self.platform.db.execute(
            "SELECT followee_id FROM follow WHERE follower_id = ?",
            (user_id, )).fetchall()}
        scored = []
        for row in rows:
            age = max(0, self.current_tick - int(row[7])) if str(
                row[7]).isdigit() else 0
            engagement = row[8] + 2.0 * row[10] + 1.5 * row[11]
            topics = self.get_post_topics(row[0])
            interest_score = sum(float(interests.get(topic, 0.0))
                                 for topic in topics)
            recency = 1.0 / (1.0 + age)
            following_bonus = 2.0 if row[1] in followed_authors else 0.0
            score = engagement + recency + following_bonus + interest_score
            reason = ("following" if following_bonus else
                      ("topic_interest" if interest_score else
                       ("engagement" if engagement else "fresh")))
            scored.append((score, row, reason))
        scored.sort(key=lambda item: (item[0], item[1][0]), reverse=True)
        selected = scored[:limit]
        feed = [{
            "post_id": row[0],
            "author_id": row[1],
            "author_handle": row[2],
            "author_name": row[3],
            "post_type": row[4],
            "title": row[5],
            "body": row[6],
            "created_at": row[7],
            "num_likes": row[8],
            "num_shares": row[9],
            "num_collections": row[10],
            "feed_score": score,
            "feed_reason": reason,
            "topics": self.get_post_topics(row[0]),
            "assets": self.get_post_assets(row[0]),
            "comments": self.get_thread(row[0]),
            "community": row[12],
            "location": row[13],
            "original_post_id": row[14],
            "quote_body": row[15],
            "reply_to_post_id": row[16],
            "num_dislikes": row[17],
        } for score, row, reason in selected]
        if record_impressions:
            for rank, item in enumerate(feed):
                self.platform.db.execute(
                    "INSERT INTO feed_impression "
                    "(user_id, post_id, feed_type, rank, score, reason, tick) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, item["post_id"], feed_type, rank,
                     item["feed_score"], item["feed_reason"], self.current_tick))
            self.platform.db.commit()
        return feed

    def observe(self, user_id: int, feed_limit: int = 20) -> Observation:
        row = self.platform.db.execute(
            "SELECT user_id, user_name, name, bio, num_followings, "
            "num_followers FROM user WHERE user_id = ?", (user_id, )
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown user_id: {user_id}")
        user = dict(zip(("user_id", "handle", "display_name", "bio",
                         "num_followings", "num_followers"), row))
        feed = self.get_feed(user_id, feed_limit)
        return Observation(user=user,
                           tick=self.current_tick,
                           feed=feed,
                           own_recent_posts=[
                               post for post in feed
                               if post["author_id"] == user_id
                           ])

    def observe_controlled(self, user_id: int,
                           visible_post_ids: list[int]) -> Observation:
        """Observe only an artifact-frozen post set in the requested order."""
        base = self.observe(user_id, feed_limit=max(200, len(visible_post_ids)))
        by_id = {post["post_id"]: post for post in base.feed}
        feed = [by_id[post_id] for post_id in visible_post_ids
                if post_id in by_id]
        return Observation(
            user=base.user, tick=base.tick, feed=feed,
            own_recent_posts=[post for post in feed
                              if post["author_id"] == user_id])

    def observe_ranked_pool(self, user_id: int,
                            visible_post_ids: list[int] | tuple[int, ...],
                            feed_limit: int = 20) -> Observation:
        """Rank one frozen content pool for a specific user's perspective."""
        row = self.platform.db.execute(
            "SELECT user_id, user_name, name, bio, num_followings, "
            "num_followers FROM user WHERE user_id = ?", (user_id, )
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown user_id: {user_id}")
        user = dict(zip(("user_id", "handle", "display_name", "bio",
                         "num_followings", "num_followers"), row))
        feed = self.get_feed(
            user_id, feed_limit, eligible_post_ids=visible_post_ids)
        return Observation(
            user=user, tick=self.current_tick, feed=feed,
            own_recent_posts=[post for post in feed
                              if post["author_id"] == user_id])

    async def advance(
            self,
            content_pool_post_ids: list[int] | tuple[int, ...] | None = None,
            actor_user_ids: list[int] | tuple[int, ...] | None = None,
            feed_limit: int = 10) -> TickResult:
        tick = self.current_tick
        seed = self.platform.db.execute(
            "SELECT seed FROM simulation_state WHERE singleton = 1").fetchone()[0]
        rng = random.Random(f"{seed}:{tick}")
        actions = []
        if content_pool_post_ids is None:
            content_pool_post_ids = tuple(int(row[0]) for row in
                                          self.platform.db.execute(
                "SELECT post_id FROM post ORDER BY post_id").fetchall())
        else:
            content_pool_post_ids = tuple(dict.fromkeys(
                int(post_id) for post_id in content_pool_post_ids))
        rows = self.platform.db.execute(
            "SELECT p.user_id, p.persona_json FROM persona p "
            "ORDER BY p.user_id").fetchall()
        if actor_user_ids is not None:
            allowed_actors = set(actor_user_ids)
            rows = [row for row in rows if row[0] in allowed_actors]
        rng.shuffle(rows)
        self._record_event("npc_order_frozen", None, "tick", tick, {
            "actor_user_ids": [row[0] for row in rows],
            "content_pool_post_ids": list(content_pool_post_ids),
        }, tick=tick)
        for user_id, persona_json in rows:
            profile = PersonaProfile.from_dict(json.loads(persona_json))
            # Every NPC receives the same frozen pool, but current engagement
            # and persona interests dynamically personalize its ordering.
            feed = self.get_feed(
                user_id, feed_limit, eligible_post_ids=content_pool_post_ids)
            candidates = [post for post in feed
                          if post["author_id"] != user_id]
            actions.append({
                "action": "observe_feed", "user_id": user_id,
                "post_ids": [post["post_id"] for post in feed],
                "content_pool_post_ids": list(content_pool_post_ids),
            })
            if candidates and rng.random() < profile.like_probability:
                target = candidates[0]
                if self.like_post(user_id, target["post_id"]):
                    actions.append({"action": "like_post",
                                    "user_id": user_id,
                                    "post_id": target["post_id"]})
            if candidates and rng.random() < profile.comment_probability:
                target = candidates[0]
                content = f"{profile.display_name} 看到了这条内容并留下了回应。"
                result = await self.create_comment(user_id,
                                                   target["post_id"],
                                                   content)
                actions.append({"action": "create_comment",
                                "user_id": user_id, **result})
            if rng.random() < profile.posting_probability:
                body = (profile.example_posts[tick % len(profile.example_posts)]
                        if profile.example_posts else
                        f"来自 {profile.display_name} 的第 {tick} 次分享")
                post_id = self.create_post(user_id,
                                           body=body,
                                           post_type="text",
                                           language=profile.locale)
                actions.append({"action": "create_post", "user_id": user_id,
                                "post_id": post_id})

        self.platform.db.execute(
            "UPDATE simulation_state SET current_tick = current_tick + 1 "
            "WHERE singleton = 1")
        self._record_event("tick_advanced", None, "tick", tick + 1,
                           {"action_count": len(actions)}, tick=tick)
        self.platform.db.commit()
        return TickResult(tick=tick,
                          actions=actions,
                          events=self.events(tick=tick))

    def events(self, tick: int | None = None) -> list[dict[str, Any]]:
        query = ("SELECT event_id, tick, event_sequence, event_type, "
                 "actor_user_id, target_type, target_id, payload "
                 "FROM sandbox_event")
        params = ()
        if tick is not None:
            query += " WHERE tick = ?"
            params = (tick, )
        query += " ORDER BY tick, event_sequence"
        return [{
            "event_id": row[0], "tick": row[1], "event_sequence": row[2],
            "event_type": row[3], "actor_user_id": row[4],
            "target_type": row[5], "target_id": row[6],
            "payload": json.loads(row[7]),
        } for row in self.platform.db.execute(query, params).fetchall()]

    def snapshot(self, snapshot_id: str | None = None) -> Path:
        snapshot_id = snapshot_id or f"tick-{self.current_tick}-{uuid.uuid4().hex[:8]}"
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", snapshot_id):
            raise ValueError("snapshot_id contains unsupported characters.")
        snapshot_dir = self.config.world_dir / "snapshots" / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        database_path = snapshot_dir / "sandbox.db"
        destination = sqlite3.connect(database_path)
        try:
            self.platform.db.backup(destination)
        finally:
            destination.close()
        media = [{
            "asset_id": row[0],
            "object_key": row[1],
            "checksum_sha256": row[2],
            "byte_size": row[3],
        } for row in self.platform.db.execute(
            "SELECT asset_id, object_key, checksum_sha256, byte_size "
            "FROM media_asset ORDER BY asset_id").fetchall()]
        manifest = {
            "snapshot_id": snapshot_id,
            "world_id": self.config.world_id,
            "tick": self.current_tick,
            "database": "sandbox.db",
            "media_root": str(self.config.media_path),
            "media": media,
        }
        (snapshot_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return snapshot_dir

    def _record_event(self,
                      event_type: str,
                      actor_user_id: int | None,
                      target_type: str,
                      target_id: Any,
                      payload: dict,
                      tick: int | None = None) -> None:
        tick = self.current_tick if tick is None else tick
        sequence = self.platform.db.execute(
            "SELECT COALESCE(MAX(event_sequence), -1) + 1 "
            "FROM sandbox_event WHERE tick = ?", (tick, )).fetchone()[0]
        self.platform.db.execute(
            "INSERT INTO sandbox_event (tick, event_sequence, event_type, "
            "actor_user_id, target_type, target_id, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tick, sequence, event_type, actor_user_id, target_type,
             str(target_id), json.dumps(payload, ensure_ascii=False)),
        )

    def _validate_post(self, post_type: str, body: str,
                       assets: list[AssetInput]) -> None:
        if post_type == "gallery" and not self.preset.allow_gallery:
            raise ValueError(f"Gallery posts are disabled for {self.preset.name}.")
        if post_type == "video" and not self.preset.allow_video:
            raise ValueError(f"Video posts are disabled for {self.preset.name}.")
        if post_type == "text" and not body.strip():
            raise ValueError("Text posts require a non-empty body.")
        if post_type == "text" and assets:
            raise ValueError("Text posts cannot contain media assets.")
        if post_type == "image" and len(assets) != 1:
            raise ValueError("Image posts require exactly one asset.")
        if post_type == "gallery" and not 2 <= len(assets) <= 20:
            raise ValueError("Gallery posts require between 2 and 20 assets.")
        if post_type == "video" and len(assets) not in {1, 2}:
            raise ValueError("Video posts require a video and optional cover.")

    @staticmethod
    def _validate_imported_assets(
            post_type: str,
            assets: list[tuple[ImportedMedia, AssetInput]]) -> None:
        media_types = [media.media_type for media, _ in assets]
        if post_type in {"image", "gallery"} and any(
                media_type != "image" for media_type in media_types):
            raise ValueError(f"{post_type} posts only accept image assets.")
        if post_type in {"image", "gallery"} and any(
                item.role != "content" for _, item in assets):
            raise ValueError(
                f"{post_type} assets must use the content role.")
        if post_type == "video":
            videos = [item for item in assets if item[0].media_type == "video"]
            images = [item for item in assets if item[0].media_type == "image"]
            if len(videos) != 1 or len(images) > 1:
                raise ValueError(
                    "Video posts require one video and at most one image cover.")
            if videos[0][1].role != "content":
                raise ValueError("The video asset must use the content role.")
            if images and images[0][1].role != "cover":
                raise ValueError("The video image must use the cover role.")

    def attach_media(self,
                     post_id: int,
                     asset_id: str,
                     position: int,
                     role: str = "content",
                     caption: str | None = None) -> None:
        self.platform.db.execute(
            "INSERT INTO post_asset "
            "(post_id, asset_id, position, role, caption) "
            "VALUES (?, ?, ?, ?, ?)",
            (post_id, asset_id, position, role, caption),
        )
        self.platform.db.commit()

    def get_post_assets(self, post_id: int) -> list[dict]:
        rows = self.platform.db.execute(
            "SELECT m.asset_id, m.media_type, m.object_key, m.mime_type, "
            "m.byte_size, m.width, m.height, m.duration_ms, p.position, "
            "p.role, p.caption, m.technical_metadata, m.alt_text, "
            "m.transcript "
            "FROM post_asset p JOIN media_asset m ON m.asset_id = p.asset_id "
            "WHERE p.post_id = ? ORDER BY p.position", (post_id, )).fetchall()
        return [{
            "asset_id": row[0],
            "media_type": row[1],
            "object_key": row[2],
            "mime_type": row[3],
            "byte_size": row[4],
            "width": row[5],
            "height": row[6],
            "duration_ms": row[7],
            "position": row[8],
            "role": row[9],
            "caption": row[10],
            "technical_metadata": json.loads(row[11]),
            "alt_text": row[12],
            "transcript": row[13],
        } for row in rows]

    def close(self) -> None:
        self.platform.db_cursor.close()
        self.platform.db.close()
