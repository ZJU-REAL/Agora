"""Bounded, account-private memory derived from actual observations/actions."""

import json
import math


class AgentMemory:
    def __init__(self, world):
        self.world = world

    def remember(
        self, user, session_id, action, result, observation=None, after_observation=None
    ):
        content = json.dumps(
            {
                "action": action,
                "result": result,
                "observed": self.evidence(observation),
                "after": self.evidence(after_observation),
            },
            ensure_ascii=False,
        )
        importance = (
            0.9
            if action["action_type"]
            in {"publish_draft", "create_post", "create_comment"}
            else 0.4
        )
        self.world.db.execute(
            "INSERT INTO agent_memory(user_id, tick, kind, content, importance, source_session_id) VALUES (?, ?, 'experience', ?, ?, ?)",
            (user, self.world.current_tick, content, importance, session_id),
        )
        self.world.db.execute(
            "DELETE FROM agent_memory WHERE user_id = ? AND memory_id NOT IN (SELECT memory_id FROM agent_memory WHERE user_id = ? ORDER BY memory_id DESC LIMIT 500)",
            (user, user),
        )
        self.world.db.commit()

    @staticmethod
    def evidence(observation):
        if not observation:
            return None

        def post_evidence(post):
            if not post:
                return None
            comments = []
            stack = list(post.get("comments", []))
            while stack and len(comments) < 12:
                comment = stack.pop(0)
                comments.append(
                    {
                        "comment_id": comment["comment_id"],
                        "author_id": comment["author_id"],
                        "content": comment["content"][:400],
                    }
                )
                stack.extend(comment.get("replies", []))
            return {
                "post_id": post["post_id"],
                "author_id": post["author_id"],
                "title": post.get("title"),
                "body": post.get("body", "")[:1200],
                "comments": comments,
            }

        return {
            "screen": observation["screen"],
            "tick": observation["tick"],
            "post": post_evidence(observation.get("post")),
            "cards": [post_evidence(post) for post in observation.get("cards", [])[:6]],
            "notifications": [
                {"kind": item["kind"], "content": item["content"][:300]}
                for item in observation.get("notifications", [])[:6]
            ],
        }

    def retrieve(self, user, query="", limit=8):
        rows = self.world.db.execute(
            "SELECT memory_id, tick, kind, content, importance FROM agent_memory WHERE user_id = ? ORDER BY memory_id DESC LIMIT 200",
            (user,),
        ).fetchall()
        terms = query.split()[:20]
        scored = []
        for mid, tick, kind, content, importance in rows:
            relevance = sum(term.casefold() in content.casefold() for term in terms)
            score = (
                importance
                + 0.5 ** (max(0, self.world.current_tick - tick) / 24)
                + math.log1p(relevance)
            )
            scored.append(
                (score, mid, {"tick": tick, "kind": kind, "content": content})
            )
        return [
            item[2]
            for item in sorted(
                scored, key=lambda item: (item[0], item[1]), reverse=True
            )[:limit]
        ]
