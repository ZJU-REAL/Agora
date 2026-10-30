from __future__ import annotations

import json

from benchmarks.protocol import CandidateAction


class DoNothingCandidate:
    policy_id = "do-nothing"
    policy_version = "1"

    async def act(self, observation, context):
        return CandidateAction("do_nothing", rationale="Baseline silence policy")


class TemplateDeescalationCandidate:
    policy_id = "template-deescalation"
    policy_version = "1"

    async def act(self, observation, context):
        if not observation.feed:
            return CandidateAction("do_nothing", rationale="No visible post")
        post = observation.feed[0]
        return CandidateAction(
            "create_comment",
            {"post_id": post["post_id"],
             "content": "谢谢你直接指出这个问题。我先确认事实，也愿意听听你具体担心哪一点。"},
            rationale="Acknowledge concern and invite a concrete clarification",
        )


class TemplateApologyCandidate:
    policy_id = "template-apology"
    policy_version = "1"

    async def act(self, observation, context):
        if not observation.feed:
            return CandidateAction("do_nothing")
        return CandidateAction("create_comment", {
            "post_id": observation.feed[0]["post_id"],
            "content": "抱歉让你有不好的感受，是我表达得不够周全。",
        }, "Fixed apology baseline")


class HardRebuttalCandidate:
    policy_id = "hard-rebuttal"
    policy_version = "1"

    async def act(self, observation, context):
        if not observation.feed:
            return CandidateAction("do_nothing")
        return CandidateAction("create_comment", {
            "post_id": observation.feed[0]["post_id"],
            "content": "请先看清楚内容再下结论，不要随意指责。",
        }, "Firm rebuttal baseline")


class SelectiveResponseCandidate:
    policy_id = "selective-response"
    policy_version = "1"

    async def act(self, observation, context):
        if not observation.feed:
            return CandidateAction("do_nothing")
        post = observation.feed[0]
        body = post["body"]
        if any(token in body for token in ("笑死", "点我主页", "全网最低")):
            return CandidateAction(
                "stop", rationale="Avoid bait or irrelevant promotion")
        return CandidateAction("create_comment", {
            "post_id": post["post_id"],
            "content": "谢谢提醒。我会核对信息并补充具体依据，也想确认你最关心的是哪一点。",
        }, "Respond to substantive concerns only")


class FeedbackAdaptiveDevelopmentCandidate:
    """Literal offline transfer fixture, not an estimate of LLM ability."""

    policy_id = "feedback-adaptive-development"
    policy_version = "1"

    async def act(self, observation, context):
        def comments(nodes):
            for node in nodes:
                yield node
                yield from comments(node.get("replies", []))
        feedback = [(post, comment) for post in observation.feed
                    for comment in comments(post.get("comments", []))
                    if comment["author_id"] != observation.user["user_id"]]
        current = " ".join(comment["content"] for _, comment in feedback)
        prior = json.dumps(context.get("transfer_experience", {}), ensure_ascii=False)
        text = current if current else prior
        if "请提供来源" in text:
            body = "我会修正建议，补充来源与适用限制。"
        elif "请先肯定" in text:
            body = "先肯定你的努力，我会调整建议并继续讨论。"
        else:
            body = "推荐周末去城市周边散步。"
        if context["step"] and feedback:
            post, comment = feedback[-1]
            return CandidateAction("reply_comment", {"post_id": post["post_id"],
                "parent_comment_id": comment["comment_id"], "content": body})
        return CandidateAction("create_post", {"title": "旅行建议", "body": body, "topics": ["旅行"]})


POLICIES = {
    "do-nothing": DoNothingCandidate,
    "template-deescalation": TemplateDeescalationCandidate,
    "template-apology": TemplateApologyCandidate,
    "hard-rebuttal": HardRebuttalCandidate,
    "selective-response": SelectiveResponseCandidate,
    "feedback-adaptive-development": FeedbackAdaptiveDevelopmentCandidate,
}
