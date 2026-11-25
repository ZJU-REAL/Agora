"""Offline accounts with explicit activity and platform-specific behavior."""

import math
import random

from agora.platform_behavior import (
    BEHAVIORS,
    PlatformBehavior,
    fit_body,
    visible_affinity,
)


class PersonaPolicy:
    def __init__(self, seed, persona=None, creator=True):
        self.rng = random.Random(seed)
        self.persona = persona or {}
        self.creator = creator
        self.behavior = None
        self.plan_tick = None
        self.posting = False
        self.next_post_tick = 0
        self.just_published = False
        self.used_examples = set()
        self.draft_count = 0
        self.post_actions = {}
        self.community_cards = []
        self.community_reads = set()
        self.planned_community = None
        self.posting_probability = self._probability(
            self.persona.get("activity", {}).get(
                "posting_probability",
                self.persona.get("posting_probability", 0.05 if creator else 0),
            ),
            "posting_probability",
        )
        social = self.persona.get("social_behavior", {})
        self.like_probability = self._probability(
            social.get("like_probability", self.persona.get("like_probability", 0.3)),
            "like_probability",
        )
        self.comment_probability = self._probability(
            social.get(
                "reply_probability", self.persona.get("comment_probability", 0.2)
            ),
            "comment_probability",
        )
        self.cooldown = self.persona.get("culture", {}).get("posting_cooldown_ticks", 3)
        if type(self.cooldown) is not int or not 1 <= self.cooldown <= 1000:
            raise ValueError("posting_cooldown_ticks must be between 1 and 1000")

    @staticmethod
    def _probability(value, name):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError(f"{name} must be a finite probability between 0 and 1")
        return float(value)

    @property
    def english(self):
        return self.persona.get(
            "locale", self.persona.get("identity", {}).get("locale", "zh-CN")
        ).startswith("en")

    @property
    def style(self):
        tones = " ".join(
            self.persona.get("tone", self.persona.get("style", {}).get("tone", []))
        ).casefold()
        if any(word in tones for word in ["evidence", "specific", "谨慎", "具体"]):
            return "evidence"
        if any(
            word in tones for word in ["direct", "brief", "concise", "简短", "直接"]
        ):
            return "brief"
        return "curious"

    def setting(self, name, default):
        return self._probability(
            self.persona.get("culture", {}).get(name, default), name
        )

    def choose_assets(self, observation):
        library = observation.get("asset_library", [])
        images = [asset for asset in library if asset["media_type"] == "image"]
        videos = [asset for asset in library if asset["media_type"] == "video"]
        formats = self.persona.get(
            "content_formats",
            self.persona.get("creator", {}).get("content_formats", {"text": 1}),
        )
        feasible = {
            "text": True,
            "image": bool(images),
            "gallery": len(images) >= 2,
            "video": bool(videos)
            and (observation["platform"] != "xiaohongshu" or bool(images)),
        }
        weights = {
            name: float(value) for name, value in formats.items() if feasible.get(name)
        }
        if any(not math.isfinite(value) or value < 0 for value in weights.values()):
            raise ValueError("Content format weights must be finite and nonnegative")
        weights = {name: value for name, value in weights.items() if value > 0}
        if not weights:
            return []
        chosen = self.rng.choices(list(weights), weights=list(weights.values()))[0]
        if chosen == "text":
            return []
        if chosen == "video":
            result = [{"asset_id": self.rng.choice(videos)["asset_id"]}]
            if observation["platform"] == "xiaohongshu":
                result.append(
                    {"asset_id": self.rng.choice(images)["asset_id"], "role": "cover"}
                )
            return result
        count = min(
            2 if chosen == "gallery" else 1,
            len(images),
            observation["contract"]["max_images"],
        )
        return [
            {"asset_id": asset["asset_id"]} for asset in self.rng.sample(images, count)
        ]

    @staticmethod
    def choice(kind, args=None, reason=""):
        return {"action_type": kind, "arguments": args or {}, "rationale": reason}

    def _refresh(self, observation):
        feed = self.behavior.preferred_feed(observation)
        arguments = {"feed_type": feed}
        if feed == "nearby":
            arguments["location"] = self.persona["culture"]["location"]
        return self.choice(
            "refresh", arguments, "按当前平台的关系、兴趣或社区入口继续浏览。"
        )

    def _detail(self, observation):
        post = observation["post"]
        if not post or post["author_id"] == observation["user_id"]:
            return self.choice("back", reason="查看完自己的内容，返回浏览。")
        target = post.get("reaction_target_id", post["post_id"])
        done = self.post_actions.setdefault(target, set())
        affinity = visible_affinity(self.persona, post)
        available = observation["available_actions"]
        if affinity < -0.15:
            if "not_interested" in available:
                return self.choice(
                    "not_interested",
                    {"post_id": post["post_id"]},
                    "这条内容与账号明确不感兴趣的主题相关，减少后续推荐。",
                )
            return self.choice("back", reason="这个主题不符合当前兴趣，继续浏览。")
        if "read" not in done:
            done.add("read")
            video = next(
                (
                    asset
                    for asset in post.get("assets", [])
                    if asset["media_type"] == "video"
                ),
                None,
            )
            if video and video.get("duration_ms") and "play_video" in available:
                return self.choice(
                    "play_video",
                    {"duration_ms": min(15000, video["duration_ms"])},
                    "先播放实际视频，再决定是否互动。",
                )
            return self.choice(
                "dwell",
                {"duration_ms": self.rng.randint(4000, 15000)},
                "先阅读当前内容，再决定是否互动。",
            )
        if "extra" not in done:
            done.add("extra")
            action = self.behavior.extra_reaction(observation, affinity)
            if action and action[0] in available:
                return self.choice(*action)
        if "like" not in done:
            done.add("like")
            if not post.get("liked") and self.rng.random() < self.like_probability * (
                1 if affinity > 0 else 0.5
            ):
                action = (
                    "upvote_post"
                    if observation["platform"] == "reddit"
                    else "like_post"
                )
                return self.choice(
                    action, {"post_id": target}, "阅读后按账号的互动倾向表达认可。"
                )
        if "relationship" not in done:
            done.add("relationship")
            action = self.behavior.relationship(observation, affinity)
            if action and action[0] in available:
                return self.choice(*action)
        if "comment" not in done:
            done.add("comment")
            if self.rng.random() < self.comment_probability:
                body = fit_body(
                    observation["platform"],
                    self.behavior.followup(observation),
                    observation["contract"]["body_limit"],
                )
                action, field = (
                    ("reply_post", "body")
                    if observation["platform"] == "x"
                    else ("create_comment", "content")
                )
                if action in available:
                    return self.choice(
                        action,
                        {"post_id": target, field: body},
                        "围绕当前内容和平台语境提出具体问题。",
                    )
        if "gallery" not in done and observation["platform"] == "xiaohongshu":
            done.add("gallery")
            if (
                len(post.get("assets", [])) > 1
                and "view_media" in available
                and self.rng.random() < self.setting("gallery_probability", 0.5)
            ):
                return self.choice(
                    "view_media", {"index": 1}, "继续查看这条笔记的下一张图片。"
                )
        return self.choice("back", reason="本次阅读和互动结束，继续看其他内容。")

    async def act(self, observation, context):
        screen, tick = observation["screen"], observation["tick"]
        if self.behavior is None:
            self.behavior = BEHAVIORS.get(observation["platform"], PlatformBehavior)(
                self
            )
        if observation.get("cards"):
            known = {card["post_id"]: card for card in self.community_cards}
            known.update({card["post_id"]: card for card in observation["cards"]})
            self.community_cards = list(known.values())[-30:]
        if self.plan_tick != tick:
            self.plan_tick = tick
            self.posting = (
                tick >= self.next_post_tick
                and self.rng.random() < self.posting_probability
            )
        if self.just_published:
            self.just_published = False
            return self.choice(
                "view_profile", reason="发布完成，查看自己的内容与反馈。"
            )
        if screen == "studio":
            if observation.get("draft"):
                self.posting = False
                self.next_post_tick = tick + self.cooldown
                self.just_published = True
                self.planned_community = None
                return self.choice(
                    "publish_draft", reason="草稿已准备好，发布后再观察反馈。"
                )
            draft = self.behavior.draft(observation)
            if draft is None:
                self.posting = False
                return self._refresh(observation)
            return self.choice(
                "save_draft", draft, "根据账号兴趣、素材类型和平台规则组织草稿。"
            )
        if self.posting:
            community = self.behavior.target_community(observation)
            if observation["platform"] == "reddit":
                if community is None:
                    self.posting = False
                    self.planned_community = None
                    return self._refresh(observation)
                self.planned_community = community["name"]
                if community["name"] not in self.community_reads:
                    self.community_reads.add(community["name"])
                    return self.choice(
                        "view_community",
                        {"community": community["name"]},
                        "先查看相关社区的规则，再准备发帖。",
                    )
            return self.choice(
                "open_studio", reason="本轮选择创作，进入平台发布工作台。"
            )
        if screen == "detail":
            return self._detail(observation)
        if screen in {"profile", "notifications", "communities"}:
            return self._refresh(observation)
        cards = observation.get("cards", [])
        if cards and self.rng.random() < 0.75:
            weights = [
                max(0.05, 1 + visible_affinity(self.persona, card)) / (i + 1) ** 0.5
                for i, card in enumerate(cards)
            ]
            post = self.rng.choices(cards, weights=weights)[0]
            return self.choice(
                "open_post",
                {"post_id": post["post_id"]},
                "结合可见内容与账号兴趣选择阅读，不读取隐藏排序分数。",
            )
        return self._refresh(observation)
