"""Platform-specific choices for offline accounts, based on visible evidence."""

import re

from agora.content_features import profile_text_interests, text_affinity
from agora.platforms import x_weighted_length


def visible_affinity(persona, post):
    topics = post.get("topics", [])
    weights = persona.get("interests", {})
    topic = sum(float(weights.get(t, 0)) for t in topics) / max(1, len(topics))
    text = " ".join(str(post.get(key) or "") for key in ["title", "body"])
    return topic + 0.3 * text_affinity(profile_text_interests(persona), text)


def relevant_communities(
    persona, communities, cards=(), posting=False, require_relevance=False
):
    scores = {}
    for community in communities:
        if posting and not community.get(
            "posting_allowed", community.get("visibility") == "public"
        ):
            continue
        text = " ".join(
            str(community.get(key) or "") for key in ["name", "title", "description"]
        )
        score = text_affinity(profile_text_interests(persona), text)
        evidence = [
            visible_affinity(persona, card)
            for card in cards
            if card.get("community") == community["name"]
        ]
        if evidence:
            score += max(-3, min(3, sum(evidence) / len(evidence)))
        if require_relevance and score <= 0:
            continue
        scores[community["name"]] = score + (0.2 if community.get("joined") else 0)
    return sorted(
        (c for c in communities if c["name"] in scores),
        key=lambda c: (-scores[c["name"]], c["name"]),
    )


def fit_body(platform, body, limit):
    body = body[: max(1, limit)]
    if platform == "x":
        while body and x_weighted_length(body) > limit:
            body = body[:-1]
    return body


class PlatformBehavior:
    def __init__(self, policy):
        self.policy = policy

    def preferred_feed(self, observation):
        return observation["contract"]["feeds"][0]

    def extra_reaction(self, observation, affinity):
        return None

    def relationship(self, observation, affinity):
        p, post = self.policy, observation["post"]
        if affinity <= 0 or post.get("following_author"):
            return None
        if p.rng.random() < p.setting("follow_probability", 0.08):
            return (
                "follow_user",
                {"followee_id": post["author_id"]},
                "这个作者的内容与账号兴趣相关，建立关注关系。",
            )
        return None

    def target_community(self, observation):
        return None

    def followup(self, observation):
        p, post = self.policy, observation["post"]
        label = str(post.get("title") or (post.get("topics") or ["this topic"])[0])[:60]
        if p.style == "brief":
            return (
                f"What changed for {label}?"
                if p.english
                else f"{label}，最明显的变化是什么？"
            )
        if p.style == "evidence":
            return (
                f"What measurements or comparisons support {label}?"
                if p.english
                else f"关于{label}，有没有对比或具体参数可以参考？"
            )
        if p.english:
            return f"What constraints mattered most for {label}? A concrete example would help."
        return f"关于{label}，实际尝试时有哪些限制？想听听具体经验。"

    def draft(self, observation):
        p = self.policy
        positive = [
            (name, value)
            for name, value in p.persona.get("interests", {}).items()
            if value > 0
        ]
        topic = (
            max(positive, key=lambda item: (item[1], item[0]))[0]
            if positive
            else ("everyday observations" if p.english else "日常记录")
        )
        examples = [
            text
            for text in p.persona.get("example_posts", [])
            if text not in p.used_examples
        ]
        if examples:
            body = p.rng.choice(examples)
            p.used_examples.add(body)
        else:
            body = (
                f"I'm comparing different approaches to {topic}. What has worked for you, and under what conditions?"
                if p.english
                else f"最近想了解{topic}的不同做法。你实际使用时最在意哪一点？希望听听具体场景。"
            )
            if p.style == "brief":
                body = (
                    f"What matters most for {topic}?"
                    if p.english
                    else f"关于{topic}，你最在意哪一点？"
                )
            elif p.style == "evidence":
                body = (
                    f"What evidence would you use to compare approaches to {topic}?"
                    if p.english
                    else f"想比较{topic}的不同做法。有哪些具体参数或依据值得记录？"
                )
        if not examples:
            suffixes = (
                [
                    " Which trade-offs matter most?",
                    " What would you compare first?",
                    " What would change your recommendation?",
                ]
                if p.english
                else [
                    "你最在意哪些取舍？",
                    "你会先比较什么？",
                    "什么情况会让你改变建议？",
                ]
            )
            body += suffixes[p.draft_count % len(suffixes)]
        p.draft_count += 1
        args = {
            "body": body,
            "title": f"A question about {topic}"
            if p.english
            else f"{topic}，想听听你的经验",
            "topics": [topic],
            "assets": p.choose_assets(observation),
        }
        if observation["platform"] == "x":
            args.pop("title")
            args.pop("topics")
            tag = re.sub(r"\W+", "", topic)
            if tag and "#" + tag not in body:
                args["body"] += " #" + tag
        if observation["platform"] == "xiaohongshu":
            location = p.persona.get("culture", {}).get("location") or observation.get(
                "location"
            )
            if isinstance(location, str) and location.strip():
                args["location"] = location.strip()
        contract = observation["contract"]
        if "title" in args:
            args["title"] = args["title"][: contract["title_limit"]]
        args["body"] = fit_body(
            observation["platform"], args["body"], contract["body_limit"]
        )
        return args


class XiaohongshuBehavior(PlatformBehavior):
    def preferred_feed(self, observation):
        location = self.policy.persona.get("culture", {}).get("location")
        if location and self.policy.rng.random() < 0.2:
            return "nearby"
        return "following" if self.policy.rng.random() < 0.15 else "discover"

    def extra_reaction(self, observation, affinity):
        post, p = observation["post"], self.policy
        if (
            affinity > 0
            and not post.get("saved")
            and p.rng.random() < p.setting("save_probability", 0.25)
        ):
            return (
                "collect_post",
                {"post_id": post["post_id"]},
                "这条笔记与当前需求相关，保存以便之后查看。",
            )
        return None


class XBehavior(PlatformBehavior):
    def preferred_feed(self, observation):
        return "following" if self.policy.rng.random() < 0.25 else "for_you"

    def extra_reaction(self, observation, affinity):
        post, p = observation["post"], self.policy
        if (
            affinity > 0
            and not post.get("reposted")
            and p.rng.random() < p.setting("repost_probability", 0.10)
        ):
            return (
                "repost",
                {"post_id": post.get("reaction_target_id", post["post_id"])},
                "这条原帖值得沿关注关系分享，保留原作者归属。",
            )
        if (
            affinity > 0
            and not post.get("saved")
            and p.rng.random() < p.setting("save_probability", 0.10)
        ):
            return (
                "bookmark_post",
                {"post_id": post.get("reaction_target_id", post["post_id"])},
                "保存这条原帖，之后再回看其中的讨论。",
            )
        return None

    def followup(self, observation):
        post, p = observation["post"], self.policy
        excerpt = " ".join(str(post.get("body") or "").split())[:60]
        if p.style == "brief":
            return (
                f'What shaped your view on "{excerpt}"?'
                if p.english
                else f"“{excerpt}”，你的依据是什么？"
            )
        return (
            f'On "{excerpt}": what led you to that view?'
            if p.english
            else f"关于“{excerpt}”，你是基于什么观察得出这个判断的？"
        )


class RedditBehavior(PlatformBehavior):
    def extra_reaction(self, observation, affinity):
        post, p = observation["post"], self.policy
        if (
            affinity > 0
            and not post.get("saved")
            and p.rng.random() < p.setting("save_probability", 0.10)
        ):
            return (
                "save_post",
                {"post_id": post["post_id"]},
                "保存这段相关讨论，之后继续比较其中的观点。",
            )
        return None

    def preferred_feed(self, observation):
        joined = any(c.get("joined") for c in observation.get("communities", []))
        return "following" if joined and self.policy.rng.random() < 0.35 else "for_you"

    def target_community(self, observation):
        if self.policy.planned_community is not None:
            return next(
                (
                    community
                    for community in observation.get("communities", [])
                    if community["name"] == self.policy.planned_community
                    and community.get(
                        "posting_allowed", community.get("visibility") == "public"
                    )
                ),
                None,
            )
        groups = relevant_communities(
            self.policy.persona,
            observation.get("communities", []),
            self.policy.community_cards,
            posting=True,
            require_relevance=True,
        )
        return groups[0] if groups else None

    def draft(self, observation):
        community = self.target_community(observation)
        if community is None:
            return None
        args = super().draft(observation)
        args["community"] = community["name"]
        if any(
            any(
                word in rule.casefold()
                for word in ["evidence", "source", "basis", "证据", "依据"]
            )
            for rule in community.get("rules", [])
        ):
            args["body"] += (
                " Please explain the evidence behind your suggestions."
                if self.policy.english
                else "也请说明建议背后的依据。"
            )
        args["body"] = fit_body(
            "reddit", args["body"], observation["contract"]["body_limit"]
        )
        return args

    def relationship(self, observation, affinity):
        community = observation.get("community")
        if (
            affinity > 0
            and community
            and not community.get("joined")
            and self.policy.rng.random() < self.policy.setting("join_probability", 0.15)
        ):
            return (
                "join_community",
                {"community": community["name"]},
                "这个社区的主题符合兴趣，加入后继续观察讨论。",
            )
        return None

    def followup(self, observation):
        post, p = observation["post"], self.policy
        title = str(post.get("title") or "the question")[:60]
        rules = (observation.get("community") or {}).get("rules", [])
        evidence = any(
            "evidence" in rule.casefold() or "依据" in rule for rule in rules
        )
        if p.english:
            return f'For "{title}", could you explain the context and {"evidence" if evidence else "trade-offs"}? That would make the discussion more useful.'
        return f"关于“{title}”，能补充背景与{'依据' if evidence else '取舍'}吗？这样更方便围绕问题讨论。"


BEHAVIORS = {
    "xiaohongshu": XiaohongshuBehavior,
    "x": XBehavior,
    "reddit": RedditBehavior,
}
