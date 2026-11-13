"""Observable persona-driven development agents with creation and response plans."""

import random


class PersonaPolicy:
    def __init__(self, seed, persona=None, creator=True):
        self.rng = random.Random(seed)
        self.persona = persona or {}
        self.creator = creator
        self.created_ticks = set()
        self.commented = set()
        self.last_profile = -1
        self.just_published = False
        self.followed = set()

    async def act(self, observation, context):
        screen, tick = observation["screen"], observation["tick"]

        def choice(kind, args=None, reason=""):
            return {"action_type": kind, "arguments": args or {}, "rationale": reason}

        if screen == "studio":
            if self.just_published:
                self.just_published = False
                return choice(
                    "view_profile", reason="发布完成，回到个人主页检查内容和反馈。"
                )
            if observation["draft"]:
                self.created_ticks.add(tick)
                self.just_published = True
                return choice(
                    "publish_draft",
                    reason="草稿和素材已经准备好，发布后再观察受众反馈。",
                )
            interests = self.persona.get("interests", {})
            topic = max(interests, key=interests.get) if interests else "日常记录"
            assets = [
                asset
                for asset in observation["asset_library"]
                if asset["media_type"] == "image"
            ]
            selected = self.rng.sample(assets, min(2, len(assets)))
            args = {
                "title": f"关于{topic}的一次新尝试 · {tick + 1}",
                "body": f"这次继续记录{topic}。先尝试一个小改变，再看看大家的反馈。"
                "你遇到过类似的情况吗？欢迎分享具体经验。",
                "topics": [topic],
                "assets": [{"asset_id": asset["asset_id"]} for asset in selected],
            }
            if observation["platform"] == "x":
                args.pop("title", None)
                args.pop("topics", None)
                args["body"] += " #" + topic
            elif observation["platform"] == "reddit":
                args.pop("topics", None)
                communities = observation.get("communities", [])
                if not communities:
                    return choice(
                        "create_community",
                        {
                            "name": f"demo_{observation['user_id']}",
                            "title": "Community discussions",
                        },
                        "先创建一个可供发布和讨论的社区。",
                    )
                args["community"] = next(
                    (item["name"] for item in communities if item["joined"]),
                    communities[0]["name"],
                )
            else:
                args["title"] = args["title"][:20]
            return choice(
                "save_draft",
                args,
                "根据账号兴趣拟定主题，从自己的素材库选择配图并保存草稿。",
            )
        if self.creator and tick % 3 == 0 and tick not in self.created_ticks:
            if self.last_profile != tick:
                self.last_profile = tick
                return choice(
                    "view_profile",
                    reason="先查看自己的内容和账号反馈，再决定本轮创作。",
                )
            return choice(
                "open_studio", reason="进入创作工作台，准备新内容和图片顺序。"
            )
        if screen == "detail":
            post = observation["post"]
            if not post["liked"] and post["author_id"] != observation["user_id"]:
                return choice(
                    "upvote_post"
                    if observation["platform"] == "reddit"
                    else "like_post",
                    {"post_id": post["post_id"]},
                    "这条内容与当前浏览兴趣相关，表达一次认可。",
                )
            if (
                post["author_id"] != observation["user_id"]
                and post["author_id"] not in self.followed
                and self.rng.random() < 0.15
            ):
                self.followed.add(post["author_id"])
                return choice(
                    "follow_user",
                    {"followee_id": post["author_id"]},
                    "这个作者的内容值得持续关注，后续也查看关注流。",
                )
            if post["post_id"] not in self.commented and self.rng.random() < 0.35:
                self.commented.add(post["post_id"])
                args = {
                    "post_id": post["post_id"],
                    "content": "这个经验很具体。你会建议第一次尝试的人从哪一步开始？",
                }
                return choice(
                    "reply_post"
                    if observation["platform"] == "x"
                    else "create_comment",
                    {"post_id": post["post_id"], "body": args["content"]}
                    if observation["platform"] == "x"
                    else args,
                    "阅读后提出一个具体问题，尝试继续交流。",
                )
            if self.rng.random() < 0.3:
                return choice(
                    "dwell",
                    {"duration_ms": self.rng.randint(4000, 18000)},
                    "多停留一会儿，阅读内容和评论。",
                )
            return choice("back", reason="返回列表，继续了解其他人的内容。")
        if screen in {"profile", "notifications"}:
            return choice("refresh", reason="回到发现页，看看社区中的新内容。")
        cards = observation["cards"]
        if cards and self.rng.random() < 0.75:
            post = self.rng.choices(
                cards, weights=[1 / (index + 1) for index in range(len(cards))]
            )[0]
            return choice(
                "open_post",
                {"post_id": post["post_id"]},
                "根据当前卡片和位置选择一条内容，打开后再决定如何互动。",
            )
        if self.rng.random() < 0.2:
            return choice("open_notifications", reason="检查是否有人回应了自己的内容。")
        return choice("refresh", reason="刷新发现页，获取当前兴趣下的新推荐。")
