"""Persistent account sessions with explicit screens and actual exposure.

The agent sees public cards and tool results. Ranking diagnostics belong to the
researcher API and are never included in an agent observation.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict

from agora.recommendation import RecommendationConfig, RecommendationEngine

ACTION_SPECS = {
    "refresh": {"optional": ["feed_type"]},
    "scroll": {},
    "open_post": {"required": ["post_id"]},
    "back": {},
    "dwell": {"required": ["duration_ms"]},
    "not_interested": {"required": ["post_id"]},
    "search": {"required": ["query"], "optional": ["community"]},
    "like_post": {"required": ["post_id"]},
    "unlike_post": {"required": ["post_id"]},
    "collect_post": {"required": ["post_id"]},
    "uncollect_post": {"required": ["post_id"]},
    "follow_user": {"required": ["followee_id"]},
    "unfollow_user": {"required": ["followee_id"]},
    "create_comment": {
        "required": ["post_id", "content"],
        "optional": ["parent_comment_id"],
    },
    "create_post": {
        "required": ["body"],
        "optional": [
            "title",
            "topics",
            "language",
            "community",
            "location",
            "assets",
            "post_type",
        ],
    },
    "view_profile": {"optional": ["user_id"]},
    "open_notifications": {},
    "open_studio": {},
    "save_draft": {
        "required": ["body"],
        "optional": [
            "title",
            "topics",
            "assets",
            "post_type",
            "language",
            "community",
            "location",
        ],
    },
    "publish_draft": {},
    "end_session": {},
}
FEEDBACK_WEIGHTS = {
    "open_post": 0.15,
    "dwell": 0.4,
    "like_post": 0.7,
    "unlike_post": -0.7,
    "collect_post": 1.0,
    "uncollect_post": -1.0,
    "create_comment": 0.3,
    "not_interested": -1.5,
}


class SocialSession:
    """One continuous browser visit. The injected world supplies social CRUD.

    AgoraWorld owns storage and action transactions. This session supplies
    observable screens, account-owned media and continuous navigation.
    """

    def __init__(self, world, session_id: int):
        self.world = world
        self.db = world.db
        row = self.db.execute(
            "SELECT user_id, state_json, config_json FROM agora_session "
            "WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown session: {session_id}")
        self.session_id, self.user_id = session_id, row[0]
        self.state = json.loads(row[1])
        for key, value in {"draft": None, "profile": None, "notifications": []}.items():
            self.state.setdefault(key, value)
        self.config = RecommendationConfig(**json.loads(row[2]))
        self.engine = RecommendationEngine(self.db, self.config)

    @classmethod
    def start(cls, world, user_id: int, config: RecommendationConfig | None = None):
        RecommendationEngine(world.db, config)
        with world.atomic():
            return cls._start(world, user_id, config)

    @classmethod
    def _start(cls, world, user_id, config):
        config = config or RecommendationConfig()
        RecommendationEngine(world.db, config)
        if not world.db.execute(
            "SELECT 1 FROM user WHERE user_id = ?", (user_id,)
        ).fetchone():
            raise KeyError(f"Unknown user: {user_id}")
        state = {
            "screen": "feed",
            "feed_type": "discover",
            "cards": [],
            "page": 0,
            "request_id": None,
            "seen_ids": [],
            "current_post": None,
            "refresh": 0,
            "elapsed_ms": 0,
            "step": 0,
            "status": "active",
            "dwell_ms": 0,
        }
        cursor = world.db.execute(
            "INSERT INTO agora_session(user_id, started_tick, state_json, config_json) "
            "VALUES (?, ?, ?, ?)",
            (
                user_id,
                world.current_tick,
                json.dumps(state),
                json.dumps(asdict(config)),
            ),
        )
        world.db.commit()
        session = cls(world, cursor.lastrowid)
        session._request("discover")
        session._event(
            {"action_type": "start_session", "arguments": {}}, {"success": True}
        )
        return session

    def available_actions(self) -> dict:
        if self.state["status"] != "active":
            return {}
        names = {
            "refresh",
            "search",
            "create_post",
            "end_session",
            "view_profile",
            "open_notifications",
            "open_studio",
        }
        if self.state["screen"] in {"feed", "search", "profile", "notifications"}:
            names.update(
                {
                    "scroll",
                    "open_post",
                    "not_interested",
                    "follow_user",
                    "unfollow_user",
                }
            )
        if self.state["screen"] == "detail":
            names.update(
                {
                    "back",
                    "dwell",
                    "like_post",
                    "unlike_post",
                    "create_comment",
                    "follow_user",
                    "unfollow_user",
                    "not_interested",
                }
            )
            if self.world.preset.allow_collect:
                names.update({"collect_post", "uncollect_post"})
        if self.state["screen"] == "studio":
            names.update({"save_draft", "back"})
            if self.state.get("draft"):
                names.add("publish_draft")
        return {name: ACTION_SPECS[name] for name in sorted(names)}

    def observe(self) -> dict:
        user = self.db.execute(
            "SELECT user_name, name, bio FROM user WHERE user_id = ?", (self.user_id,)
        ).fetchone()
        return copy.deepcopy(
            {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "account": {"handle": user[0], "name": user[1], "bio": user[2]},
                "platform": self.world.preset.name,
                "tick": self.world.current_tick,
                "screen": self.state["screen"],
                "status": self.state["status"],
                "elapsed_ms": self.state["elapsed_ms"],
                "feed_type": self.state["feed_type"],
                "page": self.state["page"],
                "cards": self.state["cards"],
                "post": self.state["current_post"],
                "draft": self.state["draft"],
                "profile": self.state["profile"],
                "notifications": self.state["notifications"],
                "asset_library": self.world.asset_library(self.user_id)
                if self.state["screen"] == "studio"
                else [],
                "available_actions": self.available_actions(),
            }
        )

    def _public_post(self, post: dict, preview: bool = False) -> dict:
        result = {
            key: value
            for key, value in post.items()
            if key not in {"feed_score", "feed_reason", "comments", "assets"}
        }
        result["assets"] = [
            {
                key: value
                for key, value in asset.items()
                if key not in {"object_key", "technical_metadata"}
            }
            for asset in post.get("assets", [])
        ]
        if preview:
            result["body"] = result.get("body", "")[:120]
            # A card shows its cover; opening reveals the ordered gallery/video.
            assets = result["assets"]
            covers = [asset for asset in assets if asset["role"] == "cover"]
            result["assets"] = (covers or assets)[:1]
        else:
            result["comments"] = post.get("comments", [])
            result["liked"] = bool(
                self.db.execute(
                    'SELECT 1 FROM "like" WHERE user_id = ? AND post_id = ?',
                    (self.user_id, post["post_id"]),
                ).fetchone()
            )
            result["collected"] = bool(
                self.db.execute(
                    "SELECT 1 FROM collection WHERE user_id = ? AND post_id = ?",
                    (self.user_id, post["post_id"]),
                ).fetchone()
            )
        return result

    def _request(self, feed_type: str, query=None, community=None):
        seed = self.db.execute(
            "SELECT seed FROM simulation_state WHERE singleton = 1"
        ).fetchone()[0]
        ids, diagnostics = self.engine.rank(
            self.user_id,
            self.world.current_tick,
            seed,
            self.state["refresh"],
            feed_type,
            self.state["seen_ids"] if feed_type != "search" else (),
            query,
            community,
        )
        posts = self.world.get_feed(
            self.user_id, len(ids), record_impressions=False, eligible_post_ids=ids
        )
        by_id = {post["post_id"]: post for post in posts}
        cards = [
            self._public_post(by_id[post], preview=True)
            for post in ids
            if post in by_id
        ]
        self._store_cards(feed_type, cards, diagnostics)

    def _store_cards(self, feed_type, cards, diagnostics):
        cursor = self.db.execute(
            "INSERT INTO agora_request(session_id, user_id, tick, feed_type, policy_version, "
            "config_json, diagnostics_json, cards_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.session_id,
                self.user_id,
                self.world.current_tick,
                feed_type,
                self.config.policy_version,
                json.dumps(asdict(self.config)),
                json.dumps(diagnostics, ensure_ascii=False),
                json.dumps(cards, ensure_ascii=False),
            ),
        )
        self.state.update(
            screen="search" if feed_type == "search" else "feed",
            feed_type=feed_type,
            request_id=cursor.lastrowid,
            page=0,
            current_post=None,
            dwell_ms=0,
        )
        self.state["refresh"] += 1
        self._page(cards)

    def _page(self, all_cards):
        start = self.state["page"] * self.config.page_size
        # Recheck permissions if a follow relation changed after slate creation.
        current = self.world.get_feed(
            self.user_id,
            len(all_cards),
            record_impressions=False,
            eligible_post_ids=[
                post["post_id"]
                for post in all_cards[start : start + self.config.page_size]
            ],
        )
        allowed = {post["post_id"] for post in current}
        cards = [
            post
            for post in all_cards[start : start + self.config.page_size]
            if post["post_id"] in allowed
        ]
        self.state["cards"] = cards
        for rank, post in enumerate(cards, start):
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO agora_exposure(session_id, request_id, user_id, post_id, rank, tick) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    self.session_id,
                    self.state["request_id"],
                    self.user_id,
                    post["post_id"],
                    rank,
                    self.world.current_tick,
                ),
            )
            if cursor.rowcount:
                # Keep the old platform's view tracking meaningful too.
                self.db.execute(
                    "INSERT INTO feed_impression(user_id, post_id, feed_type, rank, score, reason, tick) "
                    "VALUES (?, ?, ?, ?, 0, 'agora-session', ?)",
                    (
                        self.user_id,
                        post["post_id"],
                        "following"
                        if self.state["feed_type"] == "following"
                        else "discover",
                        rank,
                        self.world.current_tick,
                    ),
                )
        self.state["seen_ids"] = sorted(
            set(self.state["seen_ids"]) | {post["post_id"] for post in cards}
        )

    def _feedback(self, post_id, kind, value=None):
        author = self.db.execute(
            "SELECT user_id FROM post WHERE post_id = ?", (post_id,)
        ).fetchone()
        if author and author[0] == self.user_id:
            return
        self.db.execute(
            "INSERT INTO agora_feedback(session_id, user_id, post_id, request_id, kind, value, tick) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self.session_id,
                self.user_id,
                post_id,
                self.state["request_id"],
                kind,
                FEEDBACK_WEIGHTS[kind] if value is None else value,
                self.world.current_tick,
            ),
        )

    def _event(self, action, result):
        self.state["step"] += 1
        self.db.execute(
            "UPDATE agora_session SET state_json = ?, status = ? WHERE session_id = ?",
            (
                json.dumps(self.state, ensure_ascii=False),
                self.state["status"],
                self.session_id,
            ),
        )
        self.db.execute(
            "INSERT INTO agora_session_event(session_id, step, tick, elapsed_ms, action_json, "
            "result_json, observation_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self.session_id,
                self.state["step"],
                self.world.current_tick,
                self.state["elapsed_ms"],
                json.dumps(action, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                json.dumps(self.observe(), ensure_ascii=False),
            ),
        )
        self.db.commit()

    async def act(
        self,
        action_type: str,
        arguments: dict | None = None,
        rationale: str | None = None,
    ) -> dict:
        if rationale is not None and (
            not isinstance(rationale, str) or len(rationale) > 2000
        ):
            raise ValueError("rationale must be a short public explanation")
        before = copy.deepcopy(self.state)
        try:
            with self.world.atomic():
                return await self._act(action_type, arguments, rationale)
        except BaseException:
            self.state = before
            raise

    async def _act(self, action_type, arguments, rationale):
        args = {} if arguments is None else arguments
        if not isinstance(args, dict):
            raise TypeError("arguments must be an object")
        if action_type not in self.available_actions():
            raise ValueError(f"Action {action_type!r} is unavailable on this screen")
        spec = ACTION_SPECS[action_type]
        if set(spec.get("required", [])) - args.keys():
            raise ValueError(f"Missing arguments for {action_type}")
        if args.keys() - set(spec.get("required", []) + spec.get("optional", [])):
            raise ValueError(f"Unexpected arguments for {action_type}")
        for key in ("post_id", "followee_id", "parent_comment_id", "user_id"):
            if key in args and (type(args[key]) is not int or args[key] < 1):
                raise ValueError(f"{key} must be a positive integer")
        visible = {post["post_id"] for post in self.state["cards"]}
        current = self.state["current_post"]
        if "post_id" in args:
            if self.state["screen"] == "detail":
                if args["post_id"] != current["post_id"]:
                    raise PermissionError("Open this post before interacting")
            elif args["post_id"] not in visible:
                raise PermissionError("Only visible cards can be opened or hidden")
            # Guard against stale cards revealing newly inaccessible content.
            self._check_visible(args["post_id"])
        if "followee_id" in args:
            authors = {post["author_id"] for post in self.state["cards"]}
            if current:
                authors.add(current["author_id"])
            if args["followee_id"] not in authors:
                raise PermissionError("Only a visible author can be followed")
        result = {"success": True}
        elapsed = 300
        if action_type == "view_profile":
            uid = args.get("user_id", self.user_id)
            known = {p["author_id"] for p in self.state["cards"]} | {self.user_id}
            if current:
                known.add(current["author_id"])
            if uid not in known:
                raise PermissionError("Only known profiles can be opened")
            profile = self.db.execute(
                "SELECT user_id, user_name, name, bio, num_followers, num_followings FROM user WHERE user_id = ?",
                (uid,),
            ).fetchone()
            if profile is None:
                raise KeyError("Unknown profile")
            self.state["profile"] = dict(
                zip(
                    ("user_id", "handle", "name", "bio", "followers", "following"),
                    profile,
                )
            )
            ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT post_id FROM post WHERE user_id = ? ORDER BY post_id DESC LIMIT 100",
                    (uid,),
                )
            ]
            posts = self.world.get_feed(
                self.user_id, 100, record_impressions=False, eligible_post_ids=ids
            )
            posts.sort(key=lambda post: post["post_id"], reverse=True)
            self._store_cards(
                "profile",
                [self._public_post(post, True) for post in posts],
                {
                    "candidate_count": len(posts),
                    "decisions": [],
                    "policy_version": "profile-chronological-v1",
                },
            )
            self.state["screen"] = "profile"
        elif action_type == "open_notifications":
            notifications = []
            ids = []
            for row in self.db.execute(
                "SELECT notification_id, actor_id, kind, post_id, comment_id, content, tick, read FROM notification WHERE recipient_id = ? ORDER BY notification_id DESC LIMIT 50",
                (self.user_id,),
            ):
                if row[3] is not None:
                    try:
                        self._check_visible(row[3])
                    except PermissionError:
                        continue
                    ids.append(row[3])
                notifications.append(
                    dict(
                        zip(
                            (
                                "notification_id",
                                "actor_id",
                                "kind",
                                "post_id",
                                "comment_id",
                                "content",
                                "tick",
                                "read",
                            ),
                            row,
                        )
                    )
                )
            self.state["notifications"] = notifications
            posts = self.world.get_feed(
                self.user_id, len(ids), record_impressions=False, eligible_post_ids=ids
            )
            self._store_cards(
                "notifications",
                [self._public_post(post, True) for post in posts],
                {
                    "candidate_count": len(posts),
                    "decisions": [],
                    "policy_version": "notifications-v1",
                },
            )
            self.state["screen"] = "notifications"
            self.db.execute(
                "UPDATE notification SET read = 1 WHERE recipient_id = ?",
                (self.user_id,),
            )
        elif action_type == "open_studio":
            self.state.update(screen="studio", current_post=None)
        elif action_type == "save_draft":
            self._validate_creation(args)
            self.state["draft"] = copy.deepcopy(args)
            result["draft_saved"] = True
            elapsed = 15000
        elif action_type == "publish_draft":
            result["post_id"] = self._publish(self.state["draft"])
            result["creation"] = copy.deepcopy(self.state["draft"])
            self.state["draft"] = None
            elapsed = 1000
        elif action_type == "refresh":
            feed_type = args.get("feed_type", "discover")
            if feed_type not in self.world.preset.feed_types:
                raise ValueError("Unavailable feed")
            self._request(feed_type)
            elapsed = 800
        elif action_type == "search":
            if not isinstance(args["query"], str) or len(args["query"]) > 200:
                raise ValueError("query must be a string of at most 200 characters")
            self._request("search", args["query"], args.get("community"))
            elapsed = 800
        elif action_type == "scroll":
            cards = json.loads(
                self.db.execute(
                    "SELECT cards_json FROM agora_request WHERE request_id = ?",
                    (self.state["request_id"],),
                ).fetchone()[0]
            )
            if (self.state["page"] + 1) * self.config.page_size >= len(cards):
                result = {"success": True, "end_of_feed": True}
            else:
                self.state["page"] += 1
                self._page(cards)
            elapsed = 700
        elif action_type == "open_post":
            self.state["current_post"] = self._public_post(
                self.world.view_post(self.user_id, args["post_id"])
            )
            self.state.update(screen="detail", dwell_ms=0)
            self._feedback(args["post_id"], "open_post")
            elapsed = 500
        elif action_type == "back":
            self.state.update(
                screen=self.state["feed_type"]
                if self.state["feed_type"] in {"search", "profile", "notifications"}
                else "feed",
                current_post=None,
                dwell_ms=0,
            )
        elif action_type == "dwell":
            duration = args["duration_ms"]
            if type(duration) is not int or not 1 <= duration <= 300000:
                raise ValueError("duration_ms must be between 1 and 300000")
            before = min(self.state["dwell_ms"], 30000)
            self.state["dwell_ms"] += duration
            delta = min(self.state["dwell_ms"], 30000) - before
            self._feedback(current["post_id"], "dwell", 0.4 * delta / 30000)
            elapsed = duration
        elif action_type == "not_interested":
            self._feedback(args["post_id"], action_type)
            self.state["cards"] = [
                post
                for post in self.state["cards"]
                if post["post_id"] != args["post_id"]
            ]
            self.state.update(
                current_post=None,
                screen=self.state["feed_type"]
                if self.state["feed_type"] in {"search", "profile", "notifications"}
                else "feed",
            )
        elif action_type == "create_post":
            result["post_id"] = self._publish(args)
            result["creation"] = copy.deepcopy(args)
            elapsed = 30000
        elif action_type == "create_comment":
            if (
                not isinstance(args["content"], str)
                or not args["content"].strip()
                or len(args["content"]) > 5000
            ):
                raise ValueError("content must be nonempty and at most 5000 characters")
            result = await self.world.create_comment(self.user_id, **args)
            if result.get("success"):
                self._feedback(args["post_id"], action_type)
            elapsed = 10000
        elif action_type == "end_session":
            self.state.update(status="ended")
        else:
            changed = getattr(self.world, action_type)(self.user_id, **args)
            result["changed"] = changed
            if changed and action_type in FEEDBACK_WEIGHTS:
                self._feedback(args["post_id"], action_type)
        if self.state["current_post"]:
            try:
                self.state["current_post"] = self._public_post(
                    self._check_visible(self.state["current_post"]["post_id"])
                )
            except PermissionError:
                self.state.update(current_post=None, screen="feed", cards=[])
        self.state["elapsed_ms"] += elapsed
        self._event(
            {
                "action_type": action_type,
                "arguments": args,
                **({"rationale": rationale} if rationale else {}),
            },
            result,
        )
        return result

    def _validate_creation(self, args):
        if (
            not isinstance(args["body"], str)
            or not args["body"].strip()
            or len(args["body"]) > 10000
        ):
            raise ValueError("body must be nonempty and at most 10000 characters")
        for key in ("title", "language", "community", "location"):
            if key in args and (not isinstance(args[key], str) or len(args[key]) > 200):
                raise ValueError(f"{key} must be a string of at most 200 characters")
        if "topics" in args and (
            not isinstance(args["topics"], list)
            or len(args["topics"]) > 20
            or any(
                not isinstance(topic, str) or len(topic) > 100
                for topic in args["topics"]
            )
        ):
            raise ValueError("topics must be a list of up to 20 short strings")
        assets = self.world.library_assets(self.user_id, args.get("assets", []))
        post_type = args.get(
            "post_type", "gallery" if len(assets) > 1 else "image" if assets else "text"
        )
        if post_type not in {"text", "image", "gallery", "video"}:
            raise ValueError("Unknown creation format")
        self.world._validate_post(post_type, args["body"], assets)

    def _publish(self, args):
        self._validate_creation(args)
        args = copy.deepcopy(args)
        assets = self.world.library_assets(self.user_id, args.pop("assets", []))
        post_type = args.pop(
            "post_type", "gallery" if len(assets) > 1 else "image" if assets else "text"
        )
        return self.world.create_post(
            self.user_id, **args, assets=assets, post_type=post_type
        )

    def _check_visible(self, post_id):
        posts = self.world.get_feed(
            self.user_id, 1, record_impressions=False, eligible_post_ids=[post_id]
        )
        if not posts:
            raise PermissionError("This post is no longer visible")
        return posts[0]

    def trajectory(self, limit=None, after_step=0) -> list[dict]:
        query = (
            "SELECT step, tick, elapsed_ms, action_json, result_json, observation_json "
            "FROM agora_session_event WHERE session_id = ? AND step > ? ORDER BY step"
        )
        params = (self.session_id, after_step)
        if limit is not None:
            query = query.removesuffix("ORDER BY step") + "ORDER BY step DESC LIMIT ?"
            params += (limit,)
        rows = self.db.execute(query, params).fetchall()
        if limit is not None:
            rows.reverse()
        return [
            {
                "step": row[0],
                "tick": row[1],
                "elapsed_ms": row[2],
                "action": json.loads(row[3]),
                "result": json.loads(row[4]),
                "observation": json.loads(row[5]),
            }
            for row in rows
        ]

    def diagnostics(self) -> list[dict]:
        return [
            {
                "request_id": row[0],
                "feed_type": row[1],
                "diagnostics": json.loads(row[2]),
            }
            for row in self.db.execute(
                "SELECT request_id, feed_type, diagnostics_json FROM agora_request "
                "WHERE session_id = ? ORDER BY request_id",
                (self.session_id,),
            )
        ]
