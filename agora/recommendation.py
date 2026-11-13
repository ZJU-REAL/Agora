"""Reproducible retrieval, ranking and slate construction with online feedback.

This is an inspectable approximation of common feed mechanisms, not a model of
any vendor's proprietary algorithm. The engine depends only on SQLite tables.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from agora.storage import ensure_schema


@dataclass(frozen=True)
class RecommendationConfig:
    policy_version: str = "agora-hybrid-v1"
    channel_limit: int = 100
    slate_size: int = 30
    page_size: int = 6
    feedback_half_life_ticks: float = 48.0
    freshness_half_life_ticks: float = 24.0
    exploration_fraction: float = 0.2
    topic_weight: float = 2.0
    following_weight: float = 0.8
    quality_weight: float = 0.7
    freshness_weight: float = 0.5
    fatigue_weight: float = 1.2
    author_diversity_penalty: float = 0.9
    topic_diversity_penalty: float = 0.3

    def __post_init__(self):
        if self.policy_version != "agora-hybrid-v1":
            raise ValueError("Unsupported recommendation policy version")
        for name in ("channel_limit", "slate_size", "page_size"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 1000:
                raise ValueError(f"{name} must be an integer between 1 and 1000")
        if self.page_size > self.slate_size:
            raise ValueError("page_size must not exceed slate_size")
        for name, value in asdict(self).items():
            if name in {"policy_version", "channel_limit", "slate_size", "page_size"}:
                continue
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be finite and nonnegative")
        if min(self.feedback_half_life_ticks, self.freshness_half_life_ticks) <= 0:
            raise ValueError("half lives must be positive")
        if not 0 <= self.exploration_fraction <= 0.5:
            raise ValueError("exploration_fraction must be between 0 and 0.5")


VISIBILITY = """(p.visibility = 'public' OR p.user_id = :viewer OR
    (p.visibility = 'followers' AND EXISTS
     (SELECT 1 FROM follow vf WHERE vf.follower_id = :viewer
      AND vf.followee_id = p.user_id)))"""


def _noise(seed: int, user: int, tick: int, refresh: int, post: int) -> float:
    digest = hashlib.sha256(f"{seed}:{user}:{tick}:{refresh}:{post}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / (2**64 - 1)


class RecommendationEngine:
    def __init__(
        self, db: sqlite3.Connection, config: RecommendationConfig | None = None
    ):
        self.db = db
        self.config = config or RecommendationConfig()
        ensure_schema(db)

    def interests(self, user_id: int, tick: int) -> dict[str, float]:
        row = self.db.execute(
            "SELECT persona_json FROM persona WHERE user_id = ?", (user_id,)
        ).fetchone()
        weights = defaultdict(float)
        if row:
            for topic, value in json.loads(row[0]).get("interests", {}).items():
                weights[topic] = max(-3.0, min(3.0, float(value)))
        # Bounded history, with decay and clipping so one enthusiastic session
        # cannot permanently lock a user into a single topic.
        rows = self.db.execute(
            "SELECT post_id, value, tick FROM agora_feedback WHERE user_id = ? "
            "ORDER BY feedback_id DESC LIMIT 1000",
            (user_id,),
        ).fetchall()
        post_ids = {row[0] for row in rows}
        topics = self._topics(post_ids)
        for post_id, value, at_tick in rows:
            decay = 0.5 ** (
                max(0, tick - at_tick) / self.config.feedback_half_life_ticks
            )
            for topic in topics.get(post_id, []):
                weights[topic] += value * decay
        return {
            topic: round(max(-3.0, min(3.0, value)), 6)
            for topic, value in sorted(weights.items())
        }

    def _topics(self, post_ids) -> dict[int, list[str]]:
        result = defaultdict(list)
        # Chunks also support SQLite builds with a 999-variable limit.
        ids = sorted(post_ids)
        for offset in range(0, len(ids), 400):
            chunk = ids[offset : offset + 400]
            rows = self.db.execute(
                "SELECT pt.post_id, t.name FROM post_topic pt JOIN topic t "
                "ON t.topic_id = pt.topic_id WHERE pt.post_id IN ("
                + ",".join("?" for _ in chunk)
                + ") ORDER BY pt.post_id, t.name",
                chunk,
            ).fetchall()
            for post, topic in rows:
                result[post].append(topic)
        return result

    def rank(
        self,
        user_id: int,
        tick: int,
        seed: int,
        refresh: int = 0,
        feed_type: str = "discover",
        seen_ids=(),
        query: str | None = None,
        community: str | None = None,
    ) -> tuple[list[int], dict]:
        if feed_type not in {"discover", "following", "search"}:
            raise ValueError("Unknown feed type")
        if feed_type == "search" and (not query or not query.strip()):
            raise ValueError("Search query cannot be empty")
        interests = self.interests(user_id, tick)
        params = {"viewer": user_id, "cap": self.config.channel_limit}
        gate = VISIBILITY + " AND p.user_id != :viewer"
        # Explicit post-level negative feedback is stronger than topic decay.
        gate += (
            " AND NOT EXISTS (SELECT 1 FROM agora_feedback nf WHERE "
            "nf.user_id = :viewer AND nf.post_id = p.post_id "
            "AND nf.kind = 'not_interested')"
        )
        if feed_type == "following":
            gate += (
                " AND EXISTS (SELECT 1 FROM follow f WHERE "
                "f.follower_id = :viewer AND f.followee_id = p.user_id)"
            )
        if community:
            gate += " AND p.community = :community"
            params["community"] = community
        if feed_type == "search":
            # instr treats %, _ and backslash as literal query characters.
            gate += (
                " AND (instr(lower(COALESCE(p.title, '') || ' ' || p.content), "
                ":query) > 0 OR EXISTS (SELECT 1 FROM post_topic pt JOIN "
                "topic t ON t.topic_id = pt.topic_id WHERE pt.post_id = "
                "p.post_id AND instr(lower(t.name), :query) > 0))"
            )
            params["query"] = query.strip().lstrip("#").lower()
            if not params["query"]:
                raise ValueError("Search query cannot be empty")
        channels = {}

        def retrieve(name, extra="", order="p.post_id DESC"):
            rows = self.db.execute(
                f"SELECT p.post_id FROM post p WHERE {gate} {extra} "
                f"ORDER BY {order} LIMIT :cap",
                params,
            ).fetchall()
            channels[name] = [row[0] for row in rows]

        retrieve("fresh")
        if feed_type == "discover":
            retrieve(
                "following",
                "AND EXISTS (SELECT 1 FROM follow f WHERE "
                "f.follower_id = :viewer AND f.followee_id = p.user_id)",
            )
            positive = [
                topic
                for topic, weight in sorted(
                    interests.items(), key=lambda item: (-item[1], item[0])
                )
                if weight > 0
            ][:20]
            if positive:
                for index, topic in enumerate(positive):
                    params[f"topic{index}"] = topic
                names = ",".join(f":topic{i}" for i in range(len(positive)))
                retrieve(
                    "interest",
                    "AND EXISTS (SELECT 1 FROM post_topic pt "
                    "JOIN topic t ON t.topic_id = pt.topic_id WHERE "
                    f"pt.post_id = p.post_id AND t.name IN ({names}))",
                )
            retrieve(
                "popular", order="(p.num_likes + 2 * p.num_shares) DESC, p.post_id DESC"
            )
            # Rotate a deterministic ID window over eligible posts for discovery;
            # no ORDER BY RANDOM() or unbounded hydration of the whole world.
            max_id = self.db.execute(
                "SELECT COALESCE(MAX(post_id), 0) FROM post"
            ).fetchone()[0]
            params["pivot"] = int(_noise(seed, user_id, tick, refresh, 0) * max_id)
            retrieve("explore", order="(p.post_id < :pivot), p.post_id")
        candidates = sorted({post for posts in channels.values() for post in posts})
        topics = self._topics(candidates)
        following = {
            row[0]
            for row in self.db.execute(
                "SELECT followee_id FROM follow WHERE follower_id = ?", (user_id,)
            )
        }
        exposure_counts = Counter()
        for post, count in self.db.execute(
            "SELECT post_id, COUNT(*) FROM agora_exposure WHERE user_id = ? "
            "AND tick >= ? GROUP BY post_id",
            (user_id, tick - 48),
        ):
            exposure_counts[post] = count
        seen = set(seen_ids)
        records = {}
        for offset in range(0, len(candidates), 400):
            chunk = candidates[offset : offset + 400]
            rows = self.db.execute(
                "SELECT p.post_id, p.user_id, p.created_at, p.num_likes, "
                "p.num_shares, p.num_dislikes, "
                "(SELECT COUNT(*) FROM collection c WHERE c.post_id = p.post_id), "
                "(SELECT COUNT(*) FROM comment c WHERE c.post_id = p.post_id), "
                "(SELECT COUNT(*) FROM agora_feedback fb WHERE fb.post_id = p.post_id "
                "AND fb.kind = 'open_post'), "
                "(SELECT COUNT(*) FROM agora_exposure e WHERE e.post_id = p.post_id) "
                "FROM post p WHERE p.post_id IN (" + ",".join("?" for _ in chunk) + ")",
                chunk,
            ).fetchall()
            for (
                post,
                author,
                created,
                likes,
                shares,
                dislikes,
                collections,
                comments,
                clicks,
                impressions,
            ) in rows:
                age = max(0, tick - int(created)) if str(created).isdigit() else 0
                affinity = sum(interests.get(t, 0) for t in topics[post]) / max(
                    1, len(topics[post])
                )
                # Smoothed observed CTR plus bounded engagement volume. This
                # prevents an old viral post overwhelming every personalized feed.
                ctr = (min(clicks, impressions) + 1) / (impressions + 10)
                volume = max(
                    0, likes + 2 * collections + 1.5 * comments + 2 * shares - dislikes
                )
                quality = ctr + min(1.0, math.log1p(volume) / 10)
                components = {
                    "topic": self.config.topic_weight * affinity,
                    "following": self.config.following_weight * (author in following),
                    "quality": self.config.quality_weight * quality,
                    "freshness": self.config.freshness_weight
                    * 0.5 ** (age / self.config.freshness_half_life_ticks),
                    "fatigue": -self.config.fatigue_weight
                    * math.log1p(exposure_counts[post]),
                }
                records[post] = {
                    "post_id": post,
                    "author_id": author,
                    "topics": topics[post],
                    "components": components,
                    "score": sum(components.values()),
                    "channels": [name for name, ids in channels.items() if post in ids],
                    "noise": _noise(seed, user_id, tick, refresh, post),
                }
        # Prefer unseen posts across refreshes; when the pool is exhausted,
        # permit repeats with fatigue rather than return a permanently empty feed.
        remaining = {post: value for post, value in records.items() if post not in seen}
        repeated = False
        if not remaining:
            remaining = dict(records)
            repeated = bool(records)
        authors, used_topics = Counter(), Counter()
        selected = []
        decisions = []
        interval = (
            max(2, round(1 / self.config.exploration_fraction))
            if self.config.exploration_fraction
            else 0
        )
        while remaining and len(selected) < self.config.slate_size:
            rank = len(selected)
            explore = (
                feed_type == "discover" and interval and rank % interval == interval - 1
            )

            def slate_score(post, explore=explore):
                record = remaining[post]
                penalty = self.config.author_diversity_penalty * authors[
                    record["author_id"]
                ] + self.config.topic_diversity_penalty * sum(
                    used_topics[t] for t in record["topics"]
                ) / max(1, len(record["topics"]))
                base = record["noise"] if explore else record["score"]
                return base - penalty

            post = max(remaining, key=lambda post: (slate_score(post), post))
            record = remaining.pop(post)
            decisions.append(
                {
                    **record,
                    "rank": rank,
                    "slate_score": slate_score_from_record(
                        record, authors, used_topics, self.config, bool(explore)
                    ),
                    "selection": "exploration" if explore else "ranked",
                }
            )
            selected.append(post)
            authors[record["author_id"]] += 1
            used_topics.update(record["topics"])
        diagnostics = {
            "policy_version": self.config.policy_version,
            "seed": seed,
            "tick": tick,
            "refresh": refresh,
            "interests": interests,
            "retrieval": channels,
            "candidate_count": len(candidates),
            "repeat_fallback": repeated,
            "decisions": decisions,
        }
        return selected, diagnostics


def slate_score_from_record(record, authors, topics, config, explore):
    penalty = config.author_diversity_penalty * authors[
        record["author_id"]
    ] + config.topic_diversity_penalty * sum(topics[t] for t in record["topics"]) / max(
        1, len(record["topics"])
    )
    return (record["noise"] if explore else record["score"]) - penalty
