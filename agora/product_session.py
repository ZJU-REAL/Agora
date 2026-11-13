"""Platform-native tools used by both AI clients and the visible account UI."""

from __future__ import annotations

from agora.platforms import (
    contract_for,
    validate_creation,
    x_weighted_length,
)

NATIVE_SPECS = {
    "load_comments": {"optional": ["sort", "offset", "limit"]},
    "delete_post": {"required": ["post_id"]},
    "edit_post": {"required": ["post_id", "body"], "optional": ["title"]},
    "edit_comment": {"required": ["comment_id", "content"]},
    "delete_comment": {"required": ["comment_id"]},
    "like_comment": {"required": ["comment_id"]},
    "unlike_comment": {"required": ["comment_id"]},
    "view_saved": {},
    "edit_profile": {"optional": ["display_name", "bio"]},
    "open_notification": {"required": ["notification_id"]},
    "view_media": {"required": ["index"]},
    "play_video": {"required": ["duration_ms"]},
    "seek_video": {"required": ["position_ms"]},
    "undo_repost": {"required": ["post_id"]},
    "repost": {"required": ["post_id"]},
    "quote_post": {"required": ["post_id", "quote_body"], "optional": ["assets"]},
    "reply_post": {
        "required": ["post_id", "body"],
        "optional": ["assets", "post_type"],
    },
    "bookmark_post": {"required": ["post_id"]},
    "unbookmark_post": {"required": ["post_id"]},
    "save_post": {"required": ["post_id"]},
    "unsave_post": {"required": ["post_id"]},
    "upvote_post": {"required": ["post_id"]},
    "downvote_post": {"required": ["post_id"]},
    "clear_post_vote": {"required": ["post_id"]},
    "upvote_comment": {"required": ["comment_id"]},
    "downvote_comment": {"required": ["comment_id"]},
    "clear_comment_vote": {"required": ["comment_id"]},
    "list_communities": {},
    "view_community": {"required": ["community"], "optional": ["sort", "time_range"]},
    "join_community": {"required": ["community"]},
    "leave_community": {"required": ["community"]},
    "create_community": {
        "required": ["name", "title"],
        "optional": ["description", "rules", "visibility"],
    },
    "approve_member": {"required": ["community", "user_id"]},
    "crosspost": {"required": ["post_id", "community"], "optional": ["title"]},
    "remove_post": {"required": ["post_id"], "optional": ["reason"]},
    "approve_post": {"required": ["post_id"]},
    "create_collection": {"required": ["name"]},
    "view_collection": {"required": ["folder_id"]},
    "add_to_collection": {"required": ["folder_id", "post_id"]},
    "pin_comment": {"required": ["comment_id"]},
    "unpin_comment": {"required": ["comment_id"]},
}


class ProductSession:
    @property
    def contract(self):
        return contract_for(self.world)

    def product_actions(self):
        platform = self.world.preset.name
        names = {"view_saved", "edit_profile", "open_notification"}
        detail = self.state["screen"] == "detail"
        visible_feed = self.state["screen"] in {
            "feed",
            "search",
            "profile",
            "community",
            "saved",
            "collection",
            "notifications",
        }
        if visible_feed and platform == "reddit":
            names.update(
                {
                    "upvote_post",
                    "downvote_post",
                    "clear_post_vote",
                    "save_post",
                    "unsave_post",
                }
            )
        if visible_feed and platform == "x":
            names.update({"repost", "undo_repost", "bookmark_post", "unbookmark_post"})
        if detail:
            names.update(
                {
                    "delete_post",
                    "delete_comment",
                    "view_media",
                    "play_video",
                    "seek_video",
                    "load_comments",
                }
            )
            if platform != "x":
                names.update({"edit_post", "edit_comment"})
            if platform == "x":
                names.update(
                    {
                        "repost",
                        "undo_repost",
                        "quote_post",
                        "reply_post",
                        "bookmark_post",
                        "unbookmark_post",
                    }
                )
            elif platform == "reddit":
                names.update(
                    {
                        "upvote_post",
                        "downvote_post",
                        "clear_post_vote",
                        "upvote_comment",
                        "downvote_comment",
                        "clear_comment_vote",
                        "save_post",
                        "unsave_post",
                        "crosspost",
                        "remove_post",
                        "approve_post",
                    }
                )
            else:
                names.update({"like_comment", "unlike_comment"})
        if platform == "reddit":
            names.update(
                {
                    "approve_member",
                    "list_communities",
                    "view_community",
                    "join_community",
                    "leave_community",
                    "create_community",
                }
            )
        if platform == "xiaohongshu":
            names.update({"create_collection", "view_collection"})
            if detail:
                names.add("add_to_collection")
                if self.state["current_post"]["author_id"] == self.user_id:
                    names.update({"pin_comment", "unpin_comment"})
        if detail:
            current = self.state["current_post"]
            if current.get("owner_id", current["author_id"]) != self.user_id:
                names.difference_update({"delete_post", "edit_post"})
            if platform == "reddit" and not self.world.is_moderator(
                self.user_id, current.get("community")
            ):
                names.difference_update({"remove_post", "approve_post"})
        if platform == "reddit" and not any(
            item["role"] == "moderator"
            for item in self.world.list_communities(self.user_id)
        ):
            names.discard("approve_member")
        return {name: NATIVE_SPECS[name] for name in names}

    def native_observation(self):
        value = {
            "contract": self.contract.to_dict(),
            "time_ms": self.world.current_time_ms,
            "media_index": self.state.get("media_index", 0),
            "video_position_ms": self.state.get("video_position_ms", 0),
        }
        if self.world.preset.name == "reddit":
            value["communities"] = self.world.list_communities(self.user_id)
            value["community"] = self.state.get("community")
        if self.world.preset.name == "xiaohongshu":
            value["collections"] = [
                {"folder_id": row[0], "name": row[1]}
                for row in self.db.execute(
                    "SELECT folder_id,name FROM collection_folder WHERE user_id=? ORDER BY folder_id",
                    (self.user_id,),
                )
            ]
        return value

    def normalize_post(self, post, preview=False, include_refs=True):
        post["liked"] = bool(
            self.db.execute(
                'SELECT 1 FROM "like" WHERE user_id=? AND post_id=?',
                (self.user_id, post["post_id"]),
            ).fetchone()
        )
        post["saved"] = bool(
            self.db.execute(
                "SELECT 1 FROM collection WHERE user_id=? AND post_id=?",
                (self.user_id, post["post_id"]),
            ).fetchone()
        )
        platform = self.world.preset.name
        post["owner_id"] = post["author_id"]
        if platform == "reddit":
            if post.get("url"):
                post["post_type"] = "link"
            post["score"] = post["num_likes"] - post["num_dislikes"]
            up = self.db.execute(
                'SELECT 1 FROM "like" WHERE user_id=? AND post_id=?',
                (self.user_id, post["post_id"]),
            ).fetchone()
            down = self.db.execute(
                "SELECT 1 FROM dislike WHERE user_id=? AND post_id=?",
                (self.user_id, post["post_id"]),
            ).fetchone()
            post["vote"] = 1 if up else -1 if down else 0
            post.pop("num_collections", None)
        elif platform == "x":
            post.pop("title", None)
            post.pop("num_collections", None)
            post["num_replies"] = self.db.execute(
                "SELECT COUNT(*) FROM post WHERE reply_to_post_id=? AND deleted=0",
                (post["post_id"],),
            ).fetchone()[0]
            post["num_comments"] = post["num_replies"]
            target = (
                post.get("original_post_id")
                if post["post_type"] == "repost"
                else post["post_id"]
            )
            post["reposted"] = bool(
                self.db.execute(
                    "SELECT 1 FROM post WHERE user_id=? AND original_post_id=? AND post_type='repost' AND deleted=0",
                    (self.user_id, target),
                ).fetchone()
            )
        if not preview:
            if platform == "x":
                ids = [
                    row[0]
                    for row in self.db.execute(
                        "SELECT post_id FROM post WHERE reply_to_post_id=? ORDER BY post_id LIMIT 50",
                        (post["post_id"],),
                    )
                ]
                post["replies"] = [
                    self._public_post(item, True, False)
                    for item in self.world.get_feed(
                        self.user_id,
                        len(ids),
                        record_impressions=False,
                        eligible_post_ids=ids,
                    )
                ]
            else:
                post["comments"] = self.comment_page(post["post_id"])
            post["media_index"] = self.state.get("media_index", 0)
            post["video_position_ms"] = self.state.get("video_position_ms", 0)
            assets = post.get("assets", [])
            if platform != "x" and post.get("post_type") == "gallery":
                index = min(self.state.get("media_index", 0), max(0, len(assets) - 1))
                post["visible_asset_ids"] = (
                    [assets[index]["asset_id"]] if assets else []
                )
            else:
                post["visible_asset_ids"] = [asset["asset_id"] for asset in assets]
        reference = post.get("original_post_id") or post.get("reply_to_post_id")
        if include_refs and reference is not None:
            original = self.world.get_feed(
                self.user_id, 1, record_impressions=False, eligible_post_ids=[reference]
            )
            post["original_post"] = (
                self._public_post(original[0], True, False)
                if original
                else {"post_id": reference, "unavailable": True}
            )
        if (
            platform == "x"
            and post["post_type"] == "repost"
            and post.get("original_post")
            and not post["original_post"].get("unavailable")
        ):
            original = post["original_post"]
            if not preview:
                root = self.world.get_feed(
                    self.user_id,
                    1,
                    record_impressions=False,
                    eligible_post_ids=[original["post_id"]],
                )
                original = self._public_post(root[0], False, False)
                post["original_post"] = original
            post["reaction_target_id"] = original["post_id"]
            post["reposted_by"] = post["author_name"]
            for key in (
                "author_id",
                "author_name",
                "author_handle",
                "body",
                "assets",
                "num_likes",
                "num_shares",
                "num_comments",
                "saved",
            ):
                post[key] = original.get(key, post.get(key))
            post["visible_asset_ids"] = original.get(
                "visible_asset_ids",
                [asset["asset_id"] for asset in original.get("assets", [])],
            )
            post["liked"] = bool(
                self.db.execute(
                    'SELECT 1 FROM "like" WHERE user_id=? AND post_id=?',
                    (self.user_id, original["post_id"]),
                ).fetchone()
            )
        return post

    def comment_page(self, post_id):
        comments = self.world.get_thread(post_id)
        upvotes = {
            row[0]
            for row in self.db.execute(
                "SELECT comment_id FROM comment_like WHERE user_id=?", (self.user_id,)
            )
        }
        downvotes = {
            row[0]
            for row in self.db.execute(
                "SELECT comment_id FROM comment_dislike WHERE user_id=?",
                (self.user_id,),
            )
        }
        queue = list(comments)
        while queue:
            comment = queue.pop()
            comment["liked"] = comment["comment_id"] in upvotes
            comment["vote"] = int(comment["liked"]) - int(
                comment["comment_id"] in downvotes
            )
            comment["score"] = comment["num_likes"] - comment["num_dislikes"]
            queue.extend(comment.get("replies", []))
        sort = self.state.get("comment_sort", "best")
        if sort == "new":
            comments.sort(
                key=lambda item: (item["created_at"], item["comment_id"]), reverse=True
            )
        else:
            comments.sort(
                key=lambda item: (
                    item["is_pinned"],
                    item["num_likes"] - item["num_dislikes"],
                    item["comment_id"],
                ),
                reverse=True,
            )
        offset, limit = (
            self.state.get("comment_offset", 0),
            self.state.get("comment_limit", 20),
        )
        return comments[offset : offset + limit]

    def _native_cards(self, surface, ids, sort="new"):
        posts = self.world.get_feed(
            self.user_id, len(ids), record_impressions=False, eligible_post_ids=ids
        )
        if sort == "saved":
            order = {pid: index for index, pid in enumerate(ids)}
            posts.sort(key=lambda item: order[item["post_id"]])
        elif sort in {"new", "latest", "following"}:
            posts.sort(
                key=lambda item: (item["created_at"], item["post_id"]), reverse=True
            )
        elif sort == "top":
            posts.sort(
                key=lambda item: (
                    item["num_likes"] - item["num_dislikes"],
                    item["post_id"],
                ),
                reverse=True,
            )
        else:
            posts.sort(
                key=lambda item: (
                    (item["num_likes"] - item["num_dislikes"])
                    / (max(0, self.world.current_tick - int(item["created_at"])) + 2)
                    ** 1.5,
                    item["post_id"],
                ),
                reverse=True,
            )
        self._store_cards(
            surface,
            [self._public_post(post, True) for post in posts[: self.config.slate_size]],
            {
                "candidate_count": len(posts),
                "decisions": [],
                "policy_version": f"{self.world.preset.name}-{sort}-v1",
            },
        )

    def product_feed(self, feed_type, community=None, location=None):
        platform = self.world.preset.name
        if platform == "x" and feed_type == "following":
            ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT p.post_id FROM post p WHERE p.user_id=? OR EXISTS (SELECT 1 FROM follow f WHERE f.followee_id=p.user_id AND f.follower_id=?) ORDER BY p.post_id DESC LIMIT 500",
                    (self.user_id, self.user_id),
                )
            ]
            self._native_cards("following", ids, "following")
            return True
        if platform == "xiaohongshu" and feed_type == "nearby":
            if not isinstance(location, str) or not location.strip():
                raise ValueError("Nearby discovery requires a location")
            ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT post_id FROM post WHERE instr(COALESCE(location,''),?)>0 ORDER BY post_id DESC LIMIT 500",
                    (location,),
                )
            ]
            self._native_cards("nearby", ids)
            return True
        if platform == "reddit" and feed_type in {"home", "popular", "latest"}:
            if feed_type == "home":
                ids = [
                    row[0]
                    for row in self.db.execute(
                        "SELECT p.post_id FROM post p JOIN community_member m ON m.community=p.community WHERE m.user_id=? ORDER BY p.post_id DESC LIMIT 500",
                        (self.user_id,),
                    )
                ]
            else:
                ids = [
                    row[0]
                    for row in self.db.execute(
                        "SELECT post_id FROM post ORDER BY post_id DESC LIMIT 500"
                    )
                ]
            self._native_cards(
                feed_type, ids, "hot" if feed_type != "latest" else "new"
            )
            return True
        return False

    def dispatch_product(self, action, args):
        result, elapsed = {"success": True}, 300
        user, current = self.user_id, self.state.get("current_post")
        if action == "undo_repost":
            row = self.db.execute(
                "SELECT post_id FROM post WHERE user_id=? AND original_post_id=? AND post_type='repost' AND deleted=0",
                (user, args["post_id"]),
            ).fetchone()
            result["changed"] = self.world.delete_post(user, row[0]) if row else False
            return result, 300
        if action in {"repost", "crosspost", "quote_post"}:
            community = args.get("community")
            if action == "crosspost":
                self.world.can_post_to(user, community)
            quote = args.get("quote_body")
            if action == "quote_post" and (
                not isinstance(quote, str)
                or not quote.strip()
                or x_weighted_length(quote) > 280
            ):
                raise ValueError(
                    "Quote text must be nonempty and within 280 weighted characters"
                )
            result["post_id"] = self.world.repost(
                user, args["post_id"], quote_body=quote, community=community
            )
            if action == "quote_post" and args.get("assets"):
                creation = {"body": quote, "assets": args["assets"]}
                self._validate_creation(creation)
                for index, spec in enumerate(args["assets"]):
                    self.world.attach_media(
                        result["post_id"],
                        spec["asset_id"],
                        index,
                        spec.get("role", "content"),
                        spec.get("caption"),
                    )
            if action == "crosspost":
                title = (
                    args.get("title")
                    or self.world.require_post(user, args["post_id"]).get("title")
                    or "Crosspost"
                )
                if not isinstance(title, str) or len(title) > 300:
                    raise ValueError("Crosspost title exceeds 300 characters")
                self.db.execute(
                    "UPDATE post SET title=? WHERE post_id=?",
                    (title, result["post_id"]),
                )
            if action == "crosspost" and args.get("title"):
                self.db.execute(
                    "UPDATE post SET title=? WHERE post_id=?",
                    (args["title"], result["post_id"]),
                )
            return result, 1000
        if action == "reply_post":
            creation = {key: value for key, value in args.items() if key != "post_id"}
            self._validate_creation(creation)
            post_type = validate_creation(
                "x", creation, self.world.asset_library(user), self.contract
            )
            assets = self.world.library_assets(user, creation.pop("assets", []))
            creation.pop("post_type", None)
            result["post_id"] = self.world.create_post(
                user,
                **creation,
                assets=assets,
                post_type=post_type,
                reply_to_post_id=args["post_id"],
            )
            self.world.notify(
                self.world.require_post(user, args["post_id"])["author_id"],
                user,
                "reply",
                result["post_id"],
                content=args["body"],
            )
            return result, 10000
        if action in {"upvote_post", "downvote_post", "clear_post_vote"}:
            before_vote = int(
                bool(
                    self.db.execute(
                        'SELECT 1 FROM "like" WHERE user_id=? AND post_id=?',
                        (user, args["post_id"]),
                    ).fetchone()
                )
            ) - int(
                bool(
                    self.db.execute(
                        "SELECT 1 FROM dislike WHERE user_id=? AND post_id=?",
                        (user, args["post_id"]),
                    ).fetchone()
                )
            )
            result["changed"] = self.world.vote_post(
                user,
                args["post_id"],
                {"upvote_post": 1, "downvote_post": -1, "clear_post_vote": 0}[action],
            )
            if result["changed"]:
                value = {"upvote_post": 1, "downvote_post": -1, "clear_post_vote": 0}[
                    action
                ]
                self._feedback(
                    args["post_id"], "like_post", 0.7 * (value - before_vote)
                )
        elif action in {"bookmark_post", "unbookmark_post", "save_post", "unsave_post"}:
            saved = action in {"bookmark_post", "save_post"}
            result["changed"] = self.world.save_post(user, args["post_id"], saved)
            if result["changed"]:
                self._feedback(
                    args["post_id"], "collect_post" if saved else "uncollect_post"
                )
        elif action in {
            "like_comment",
            "unlike_comment",
            "upvote_comment",
            "downvote_comment",
            "clear_comment_vote",
        }:
            result["changed"] = self.world.vote_comment(
                user,
                args["comment_id"],
                {
                    "like_comment": 1,
                    "unlike_comment": 0,
                    "upvote_comment": 1,
                    "downvote_comment": -1,
                    "clear_comment_vote": 0,
                }[action],
            )
        elif action == "view_saved":
            ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT post_id FROM collection WHERE user_id=? ORDER BY collection_id DESC LIMIT 500",
                    (user,),
                )
            ]
            self._native_cards("saved", ids, "saved")
            self.state["screen"] = "saved"
        elif action == "edit_profile":
            if not args or any(
                not isinstance(value, str)
                or len(value) > (80 if key == "display_name" else 300)
                for key, value in args.items()
            ):
                raise ValueError("Provide a short display_name or bio")
            for key, value in args.items():
                column = "name" if key == "display_name" else "bio"
                self.db.execute(
                    f"UPDATE user SET {column}=? WHERE user_id=?", (value, user)
                )
            self.world._record_event("profile_edited", user, "user", user, args)
        elif action == "delete_post":
            self.world.delete_post(user, args["post_id"])
            self.state.update(current_post=None, screen="feed", cards=[])
        elif action == "edit_post":
            validate_creation(
                self.world.preset.name,
                {
                    "body": args["body"],
                    "title": args.get("title", current.get("title", "")),
                    "community": current.get("community"),
                    "assets": [],
                },
                self.world.asset_library(user),
            )
            self.world.edit_post(user, **args)
        elif action in {"edit_comment", "delete_comment"}:
            getattr(self.world, action)(user, **args)
        elif action == "load_comments":
            sort, offset, limit = (
                args.get("sort", "best"),
                args.get("offset", 0),
                args.get("limit", 20),
            )
            if (
                sort not in {"best", "new"}
                or type(offset) is not int
                or offset < 0
                or type(limit) is not int
                or not 1 <= limit <= 100
            ):
                raise ValueError("Invalid comment page")
            self.state.update(
                comment_sort=sort, comment_offset=offset, comment_limit=limit
            )
        elif action == "view_media":
            index = args["index"]
            if type(index) is not int or not 0 <= index < len(current["assets"]):
                raise ValueError("Media index out of range")
            self.state["media_index"] = index
        elif action in {"play_video", "seek_video"}:
            video = next(
                (
                    asset
                    for asset in current["assets"]
                    if asset["media_type"] == "video"
                ),
                None,
            )
            if not video:
                raise ValueError("This post has no video")
            value = (
                args["duration_ms"] if action == "play_video" else args["position_ms"]
            )
            if type(value) is not int or value < 0:
                raise ValueError("Video time must be a nonnegative integer")
            duration = video.get("duration_ms") or 0
            if action == "seek_video" and value > duration:
                raise ValueError("Seek exceeds video duration")
            previous = self.state.get("video_position_ms", 0)
            self.state["video_position_ms"] = (
                min(duration, previous + value) if action == "play_video" else value
            )
            elapsed = (
                self.state["video_position_ms"] - previous
                if action == "play_video"
                else 300
            )
            if elapsed:
                self._feedback(
                    current["post_id"], "dwell", 0.4 * min(30000, elapsed) / 30000
                )
        elif action == "list_communities":
            self.state.update(screen="communities", current_post=None)
        elif action == "view_community":
            community, sort = args["community"], args.get("sort", "hot")
            available = {
                item["name"]: item for item in self.world.list_communities(user)
            }
            if community not in available or sort not in {"hot", "new", "top"}:
                raise ValueError("Unknown community or sort")
            ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT post_id FROM post WHERE community=? ORDER BY post_id DESC LIMIT 500",
                    (community,),
                )
            ]
            time_range = args.get("time_range", "all")
            windows = {
                "hour": 3600000,
                "day": 86400000,
                "week": 604800000,
                "month": 2592000000,
                "year": 31536000000,
                "all": None,
            }
            if time_range not in windows:
                raise ValueError("Unknown top-post time range")
            if windows[time_range] is not None:
                tick_ms = self.db.execute(
                    "SELECT tick_duration_ms FROM simulation_state WHERE singleton=1"
                ).fetchone()[0]
                cutoff = self.world.current_tick - windows[time_range] // tick_ms
                ids = [
                    pid
                    for pid in ids
                    if self.db.execute(
                        "SELECT created_at FROM post WHERE post_id=?", (pid,)
                    ).fetchone()[0]
                    >= cutoff
                ]
            self.state["community"] = available[community]
            self._native_cards("community", ids, sort)
            self.state["screen"] = "community"
        elif action in {"join_community", "leave_community"}:
            result["changed"] = self.world.join_community(
                user, args["community"], action == "join_community"
            )
        elif action == "approve_member":
            result["changed"] = self.world.approve_member(
                user, args["community"], args["user_id"]
            )
        elif action == "create_community":
            result["community"] = self.world.create_community(user, **args)
        elif action in {"remove_post", "approve_post"}:
            self.world.moderate_post(
                user, args["post_id"], action == "remove_post", args.get("reason", "")
            )
            self.state.update(screen="feed", current_post=None, cards=[])
        elif action == "create_collection":
            name = args["name"]
            if not isinstance(name, str) or not name.strip() or len(name) > 60:
                raise ValueError("Collection name must be 1–60 characters")
            result["folder_id"] = self.world.create_collection(user, name)
        elif action == "add_to_collection":
            self.world.add_to_collection(user, **args)
        elif action == "view_collection":
            if not self.db.execute(
                "SELECT 1 FROM collection_folder WHERE folder_id=? AND user_id=?",
                (args["folder_id"], user),
            ).fetchone():
                raise PermissionError("Collection belongs to another account")
            ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT post_id FROM folder_post WHERE folder_id=?",
                    (args["folder_id"],),
                )
            ]
            self._native_cards("collection", ids)
            self.state["screen"] = "collection"
        elif action in {"pin_comment", "unpin_comment"}:
            if action == "pin_comment":
                self.world.pin_comment(user, args["comment_id"])
            else:
                post, _author = self.world.require_comment(user, args["comment_id"])
                if self.world.require_post(user, post)["author_id"] != user:
                    raise PermissionError("Only the note author may unpin comments")
                self.db.execute(
                    "UPDATE comment SET is_pinned=0 WHERE comment_id=?",
                    (args["comment_id"],),
                )
        elif action == "open_notification":
            row = self.db.execute(
                "SELECT actor_id,post_id,comment_id FROM notification WHERE notification_id=? AND recipient_id=?",
                (args["notification_id"], user),
            ).fetchone()
            if not row:
                raise PermissionError("Notification belongs to another account")
            self.db.execute(
                "UPDATE notification SET read=1 WHERE notification_id=?",
                (args["notification_id"],),
            )
            if row[1]:
                self.state.update(
                    current_post=self._public_post(
                        self.world.require_post(user, row[1])
                    ),
                    screen="detail",
                    highlighted_comment_id=row[2],
                    media_index=0,
                )
            else:
                result["actor_id"] = row[0]
        else:
            raise ValueError("Unsupported product action")
        return result, elapsed
