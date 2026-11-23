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

from agora.content_features import (
    LocalityMatcher,
    profile_text_interests,
    text_affinity,
    text_terms,
)
from agora.distribution import PROFILES, feedback_weight, platform_quality
from agora.storage import ensure_schema


@dataclass(frozen=True)
class RecommendationConfig:
    policy_version: str = "agora-hybrid-v4"
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
    collaborative_weight: float = 0.6
    graph_weight: float = 0.8
    community_weight: float = 0.8
    community_diversity_penalty: float = 0.75
    text_weight: float = 0.45
    relationship_half_life_ticks: float = 48.0

    def __post_init__(self):
        if self.policy_version not in {
            "agora-hybrid-v1",
            "agora-hybrid-v2",
            "agora-hybrid-v3",
            "agora-hybrid-v4",
        }:
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
        if (
            min(
                self.feedback_half_life_ticks,
                self.freshness_half_life_ticks,
                self.relationship_half_life_ticks,
            )
            <= 0
        ):
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
        self,
        db: sqlite3.Connection,
        config: RecommendationConfig | None = None,
        platform="generic",
        location_aliases=None,
    ):
        self.db = db
        self.config = config or RecommendationConfig()
        self.platform = platform
        self.localities = LocalityMatcher(location_aliases)
        self.db.create_function(
            "agora_locality_matches", 2, self.localities.matches, deterministic=True
        )
        ensure_schema(db)

    @property
    def native(self):
        return self.config.policy_version == "agora-hybrid-v4"

    def text_interests(self, user_id, tick):
        row = self.db.execute(
            "SELECT persona_json FROM persona WHERE user_id=?", (user_id,)
        ).fetchone()
        weights = defaultdict(
            float, profile_text_interests(json.loads(row[0]) if row else {})
        )
        for value, at_tick, title, body in self.db.execute(
            "SELECT f.value,f.tick,substr(p.title,1,160),substr(COALESCE(NULLIF(p.quote_content,''),p.content),1,512) "
            "FROM agora_feedback f JOIN post p ON p.post_id=f.post_id "
            "WHERE f.user_id=? ORDER BY f.feedback_id DESC LIMIT 96",
            (user_id,),
        ):
            decay = 0.5 ** (
                max(0, tick - at_tick) / self.config.feedback_half_life_ticks
            )
            tokens = text_terms((title or "") + " " + (body or ""), limit=24)
            for term in tokens:
                weights[term] += value * decay / math.sqrt(max(1, len(tokens)))
        return {term: max(-3.0, min(3.0, weight)) for term, weight in weights.items()}

    def author_interests(self, user_id, tick):
        weights = defaultdict(float)
        for author, value, at_tick in self.db.execute(
            "SELECT p.user_id,f.value,f.tick FROM agora_feedback f JOIN post p ON p.post_id=f.post_id "
            "WHERE f.user_id=? ORDER BY f.feedback_id DESC LIMIT 256",
            (user_id,),
        ):
            weights[author] += value * 0.5 ** (
                max(0, tick - at_tick) / self.config.relationship_half_life_ticks
            )
        return {author: max(-1.0, min(1.0, value)) for author, value in weights.items()}

    def community_interests(self, user_id, tick):
        """Learn community affinity even when communities have the same topics."""
        weights = defaultdict(float)
        for community, value, at_tick in self.db.execute(
            "SELECT p.community, f.value, f.tick FROM agora_feedback f "
            "JOIN post p ON p.post_id=f.post_id WHERE f.user_id=? "
            "AND p.community IS NOT NULL ORDER BY f.feedback_id DESC LIMIT 1000",
            (user_id,),
        ):
            weights[community] += value * 0.5 ** (
                max(0, tick - at_tick) / self.config.feedback_half_life_ticks
            )
        return {key: max(-3.0, min(3.0, value)) for key, value in weights.items()}

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
        eligible_post_ids=None,
        location: str | None = None,
        subscribed_only: bool = False,
        min_created_tick=None,
    ) -> tuple[list[int], dict]:
        if feed_type not in {"discover", "following", "search"}:
            raise ValueError("Unknown feed type")
        if feed_type == "search" and (not query or not query.strip()):
            raise ValueError("Search query cannot be empty")
        interests = self.interests(user_id, tick)
        words = (
            self.text_interests(user_id, tick)
            if self.native and self.config.text_weight
            else {}
        )
        author_affinity = (
            self.author_interests(user_id, tick)
            if self.native and self.platform == "x"
            else {}
        )
        params = {"viewer": user_id, "cap": self.config.channel_limit}
        gate = (
            VISIBILITY
            + " AND p.user_id != :viewer AND p.deleted = 0 AND p.removed_by IS NULL"
        )
        gate += " AND NOT EXISTS (SELECT 1 FROM community nc WHERE nc.name = p.community AND nc.visibility = 'private' AND NOT EXISTS (SELECT 1 FROM community_member nm WHERE nm.community = nc.name AND nm.user_id = :viewer))"
        if self.native:
            params["tick"] = tick
            gate += " AND CAST(p.created_at AS INTEGER) <= :tick"
            if self.platform == "x":
                gate += " AND (p.post_type != 'repost' OR EXISTS (SELECT 1 FROM post original WHERE original.post_id=p.original_post_id AND original.deleted=0 AND original.removed_by IS NULL AND (original.visibility='public' OR original.user_id=:viewer OR (original.visibility='followers' AND EXISTS (SELECT 1 FROM follow vf WHERE vf.follower_id=:viewer AND vf.followee_id=original.user_id)))))"
                gate += " AND NOT EXISTS (SELECT 1 FROM agora_feedback nf WHERE nf.user_id=:viewer AND nf.post_id=p.original_post_id AND p.post_type='repost' AND nf.kind='not_interested')"
        if location is not None:
            gate += (
                " AND agora_locality_matches(p.location,:location)"
                if self.native
                else " AND instr(lower(COALESCE(p.location,'')), :location)>0"
            )
            params["location"] = location.strip().lower()
        if subscribed_only:
            gate += " AND EXISTS (SELECT 1 FROM community_member m WHERE m.community=p.community AND m.user_id=:viewer)"
        if min_created_tick is not None:
            gate += " AND CAST(p.created_at AS INTEGER)>=:min_created"
            params["min_created"] = min_created_tick
        if eligible_post_ids is not None:
            gate += " AND p.post_id IN (SELECT value FROM json_each(:eligible))"
            params["eligible"] = json.dumps(list(eligible_post_ids))
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
        neighbors = {}
        community_affinity = (
            self.community_interests(user_id, tick)
            if self.native and self.platform == "reddit"
            else {}
        )

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
            if self.platform == "reddit":
                retrieve(
                    "subscriptions",
                    "AND EXISTS (SELECT 1 FROM community_member cm WHERE cm.community=p.community AND cm.user_id=:viewer)",
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
            lexical = [
                term
                for term, weight in sorted(
                    words.items(), key=lambda item: (-item[1], item[0])
                )
                if weight > 0
            ][:8]
            if lexical:
                for index, term in enumerate(lexical):
                    params[f"text{index}"] = term
                text = "lower(COALESCE(p.title,'') || ' ' || COALESCE(NULLIF(p.quote_content,''),p.content,''))"
                retrieve(
                    "text_interest",
                    "AND ("
                    + " OR ".join(
                        f"instr({text},:text{i})>0" for i in range(len(lexical))
                    )
                    + ")",
                )
            popular_order = "(p.num_likes + 2 * p.num_shares) DESC, p.post_id DESC"
            if self.native:
                if self.platform == "reddit":
                    popular_order = "(p.num_likes-p.num_dislikes) DESC, p.post_id DESC"
                elif self.platform == "xiaohongshu":
                    popular_order = "(p.num_likes+3*(SELECT COUNT(*) FROM collection c WHERE c.post_id=p.post_id)) DESC, p.post_id DESC"
            retrieve("popular", order=popular_order)
            if self.native and self.platform == "x":
                retrieve(
                    "social_graph",
                    "AND (EXISTS (SELECT 1 FROM follow first JOIN follow second ON second.follower_id=first.followee_id WHERE first.follower_id=:viewer AND second.followee_id=p.user_id) OR EXISTS (SELECT 1 FROM follow f JOIN \"like\" l ON l.user_id=f.followee_id WHERE f.follower_id=:viewer AND l.post_id=COALESCE(CASE WHEN p.post_type='repost' THEN p.original_post_id END,p.post_id)))",
                )
            if self.native and self.platform == "x":
                retrieve(
                    "conversations",
                    "AND EXISTS (SELECT 1 FROM post parent WHERE parent.post_id=p.reply_to_post_id AND parent.user_id=:viewer AND parent.deleted=0)",
                )
                if author_affinity:
                    params["familiar_authors"] = json.dumps(
                        sorted(
                            author
                            for author, value in author_affinity.items()
                            if value > 0
                        )
                    )
                    retrieve(
                        "familiar_authors",
                        "AND p.user_id IN (SELECT value FROM json_each(:familiar_authors))",
                    )
            if community_affinity:
                params["liked_communities"] = json.dumps(
                    sorted(
                        key for key, value in community_affinity.items() if value > 0
                    )
                )
                retrieve(
                    "community_interest",
                    "AND p.community IN (SELECT value FROM json_each(:liked_communities))",
                )
            # Rotate a deterministic ID window over eligible posts for discovery;
            # no ORDER BY RANDOM() or unbounded hydration of the whole world.
            max_id = self.db.execute(
                "SELECT COALESCE(MAX(post_id), 0) FROM post"
            ).fetchone()[0]
            params["pivot"] = int(_noise(seed, user_id, tick, refresh, 0) * max_id)
            retrieve("explore", order="(p.post_id < :pivot), p.post_id")
            if self.config.policy_version != "agora-hybrid-v1":
                neighbors = {
                    row[0]: row[1]
                    for row in self.db.execute(
                        'SELECT peer.user_id, COUNT(*) FROM "like" me JOIN "like" peer '
                        "ON peer.post_id = me.post_id WHERE me.user_id = ? AND peer.user_id != ? "
                        "GROUP BY peer.user_id ORDER BY COUNT(*) DESC, peer.user_id LIMIT 20",
                        (user_id, user_id),
                    )
                }
                if neighbors:
                    for index, peer in enumerate(neighbors):
                        params[f"peer{index}"] = peer
                    names = ",".join(f":peer{i}" for i in range(len(neighbors)))
                    retrieve(
                        "collaborative",
                        f'AND EXISTS (SELECT 1 FROM "like" cl WHERE cl.post_id = p.post_id AND cl.user_id IN ({names}))',
                    )
        candidates = sorted({post for posts in channels.values() for post in posts})
        topics = self._topics(candidates)
        following = {
            row[0]
            for row in self.db.execute(
                "SELECT followee_id FROM follow WHERE follower_id = ?", (user_id,)
            )
        }
        subscriptions = {
            row[0]
            for row in self.db.execute(
                "SELECT community FROM community_member WHERE user_id=?", (user_id,)
            )
        }
        graph = defaultdict(float)
        if self.native and self.platform == "x" and following:
            actor_likes = {}
            for post, actor, created in self.db.execute(
                'SELECT l.post_id,l.user_id,l.created_at FROM "like" l '
                "JOIN follow f ON f.followee_id=l.user_id WHERE f.follower_id=? "
                "AND l.post_id IN (SELECT value FROM json_each(?))",
                (user_id, json.dumps(candidates)),
            ):
                at_tick = int(created) if str(created).lstrip("-").isdigit() else 0
                strength = 0.5 ** (
                    max(0, tick - at_tick) / self.config.relationship_half_life_ticks
                )
                actor_likes[(post, actor)] = max(
                    actor_likes.get((post, actor), 0), strength
                )
            for (post, _), strength in actor_likes.items():
                graph[post] += strength / len(following)
            for (author,) in self.db.execute(
                "SELECT DISTINCT second.followee_id FROM follow first JOIN follow second "
                "ON second.follower_id=first.followee_id WHERE first.follower_id=? "
                "AND second.followee_id != ? AND second.followee_id IN "
                "(SELECT user_id FROM post WHERE post_id IN (SELECT value FROM json_each(?)))",
                (user_id, user_id, json.dumps(candidates)),
            ):
                graph[("author", author)] = 0.25
        exposure_counts = Counter()
        for post, count in self.db.execute(
            "SELECT post_id, COUNT(*) FROM agora_exposure WHERE user_id = ? "
            "AND tick >= ? GROUP BY post_id",
            (user_id, tick - 48),
        ):
            exposure_counts[post] = count
        seen = set(seen_ids)
        if self.native and self.platform == "x":
            seen.update(
                row[0]
                for row in self.db.execute(
                    "SELECT original_post_id FROM post WHERE post_type='repost' "
                    "AND post_id IN (SELECT value FROM json_each(?))",
                    (json.dumps(list(seen)),),
                )
            )
        records = {}
        evidence = {}
        if self.native:
            metrics_ids = [
                row[0]
                for row in self.db.execute(
                    "SELECT DISTINCT CASE WHEN post_type='repost' AND ?='x' "
                    "THEN original_post_id ELSE post_id END FROM post "
                    "WHERE post_id IN (SELECT value FROM json_each(?))",
                    (self.platform, json.dumps(candidates)),
                )
            ]
            target = (
                "CASE WHEN shown.post_type='repost' THEN shown.original_post_id ELSE shown.post_id END"
                if self.platform == "x"
                else "shown.post_id"
            )
            for post, impressions, clicks, readers in self.db.execute(
                f"SELECT {target}, COUNT(DISTINCT printf('%d:%d',e.user_id,e.request_id)), "
                "COUNT(DISTINCT CASE WHEN EXISTS (SELECT 1 FROM agora_feedback f "
                "WHERE f.user_id=e.user_id AND f.request_id=e.request_id "
                f"AND (f.post_id={target} OR f.post_id=e.post_id) AND f.kind='open_post') "
                "THEN printf('%d:%d',e.user_id,e.request_id) END), "
                "COUNT(DISTINCT CASE WHEN (SELECT COALESCE(SUM(f.value),0) "
                "FROM agora_feedback f WHERE f.user_id=e.user_id AND f.request_id=e.request_id "
                f"AND (f.post_id={target} OR f.post_id=e.post_id) AND f.kind='dwell') >= ? "
                "THEN printf('%d:%d',e.user_id,e.request_id) END) "
                "FROM agora_exposure e JOIN post shown ON shown.post_id=e.post_id "
                f"JOIN post source ON source.post_id={target} WHERE e.tick>=? "
                f"AND {target} IN (SELECT value FROM json_each(?)) "
                f"AND e.user_id!=source.user_id GROUP BY {target}",
                (
                    feedback_weight(self.platform, "dwell", 0.4) / 2,
                    tick - 2 * self.config.feedback_half_life_ticks,
                    json.dumps(metrics_ids),
                ),
            ):
                evidence[post] = (impressions, clicks, readers)
        collaborative = defaultdict(float)
        if neighbors:
            total = sum(neighbors.values())
            peers = list(neighbors)
            for offset in range(0, len(candidates), 400):
                chunk = candidates[offset : offset + 400]
                query = (
                    'SELECT user_id, post_id FROM "like" WHERE user_id IN ('
                    + ",".join("?" for _ in peers)
                    + ") AND post_id IN ("
                    + ",".join("?" for _ in chunk)
                    + ")"
                )
                for peer, post in self.db.execute(query, peers + chunk):
                    collaborative[post] += neighbors[peer] / total
        for offset in range(0, len(candidates), 400):
            chunk = candidates[offset : offset + 400]
            metric = "m" if self.native and self.platform == "x" else "p"
            rows = self.db.execute(
                f"SELECT p.post_id, p.user_id, p.created_at, {metric}.num_likes, "
                f"{metric}.num_shares, {metric}.num_dislikes, "
                f"(SELECT COUNT(*) FROM collection c WHERE c.post_id = {metric}.post_id), "
                f"(SELECT COUNT(*) FROM comment c WHERE c.post_id = {metric}.post_id AND c.deleted=0) + (SELECT COUNT(*) FROM post reply WHERE reply.reply_to_post_id={metric}.post_id AND reply.deleted=0), "
                "(SELECT COUNT(*) FROM agora_feedback fb WHERE fb.post_id = p.post_id "
                "AND fb.kind = 'open_post' AND fb.user_id != p.user_id), "
                "(SELECT COUNT(*) FROM agora_exposure e WHERE e.post_id = p.post_id AND e.user_id != p.user_id), p.community, p.original_post_id, p.post_type, "
                f"substr({metric}.title,1,160),substr(COALESCE(NULLIF({metric}.quote_content,''),{metric}.content),1,1024), "
                "EXISTS (SELECT 1 FROM post parent WHERE parent.post_id=p.reply_to_post_id AND parent.user_id=? AND parent.deleted=0) "
                "FROM post p LEFT JOIN post m ON m.post_id=CASE WHEN p.post_type='repost' THEN p.original_post_id ELSE p.post_id END "
                "WHERE p.post_id IN (" + ",".join("?" for _ in chunk) + ")",
                [user_id, *chunk],
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
                post_community,
                original_id,
                post_type,
                title,
                body,
                related_conversation,
            ) in rows:
                age = (
                    max(0, tick - int(created))
                    if str(created).lstrip("-").isdigit()
                    else 0
                )
                affinity = sum(interests.get(t, 0) for t in topics[post]) / max(
                    1, len(topics[post])
                )
                # Smoothed observed CTR plus bounded engagement volume. This
                # prevents an old viral post overwhelming every personalized feed.
                ctr = (min(clicks, impressions) + 1) / (impressions + 10)
                readers = 0
                if self.native:
                    target_id = (
                        original_id
                        if self.platform == "x" and post_type == "repost"
                        else post
                    )
                    impressions, clicks, readers = evidence.get(target_id, (0, 0, 0))
                    ctr = (clicks + 1) / (impressions + 10)
                volume = max(
                    0, likes + 2 * collections + 1.5 * comments + 2 * shares - dislikes
                )
                profile = PROFILES.get(self.platform, PROFILES["generic"])
                if self.config.policy_version in {"agora-hybrid-v3", "agora-hybrid-v4"}:
                    volume = max(
                        0,
                        likes * profile["likes"]
                        + collections * profile["saves"]
                        + comments * profile["comments"]
                        + shares * profile["shares"]
                        - dislikes,
                    )
                quality = ctr + min(1.0, math.log1p(volume) / 10)
                if self.native:
                    quality = platform_quality(
                        self.platform,
                        likes,
                        dislikes,
                        collections,
                        comments,
                        shares,
                        ctr,
                        (readers + 1) / (impressions + 10),
                    )
                components = {
                    "topic": self.config.topic_weight * affinity,
                    "following": self.config.following_weight
                    * (
                        (post_community in subscriptions)
                        if self.platform == "reddit"
                        else (author in following)
                    ),
                    "quality": self.config.quality_weight * quality,
                    "freshness": self.config.freshness_weight
                    * (
                        profile["freshness"]
                        if self.config.policy_version
                        in {"agora-hybrid-v3", "agora-hybrid-v4"}
                        else 1
                    )
                    * 0.5
                    ** (
                        age
                        / (
                            self.config.freshness_half_life_ticks
                            * (
                                {"xiaohongshu": 2.0, "x": 0.5}.get(self.platform, 1.0)
                                if self.native
                                else 1.0
                            )
                        )
                    ),
                    "fatigue": -self.config.fatigue_weight
                    * math.log1p(exposure_counts[post]),
                    "collaborative": self.config.collaborative_weight
                    * collaborative[post],
                }
                if self.config.policy_version in {"agora-hybrid-v3", "agora-hybrid-v4"}:
                    components["cold_start"] = (
                        profile["trial"]
                        * 10
                        / (impressions + 10)
                        * 0.5 ** (age / self.config.freshness_half_life_ticks)
                    )
                if self.native and self.platform == "x":
                    target = original_id if post_type == "repost" else post
                    components["social_graph"] = self.config.graph_weight * (
                        graph[target]
                        + graph[("author", author)]
                        + 0.2 * author_affinity.get(author, 0)
                        + 0.3 * related_conversation
                    )
                if self.native and words:
                    components["text"] = self.config.text_weight * text_affinity(
                        words, (title or "") + " " + (body or "")
                    )
                if self.native and self.platform == "reddit":
                    components["community"] = (
                        self.config.community_weight
                        * community_affinity.get(post_community, 0)
                    )
                records[post] = {
                    "post_id": post,
                    "author_id": author,
                    "topics": topics[post],
                    "community": post_community,
                    "content_id": original_id
                    if self.platform == "x" and post_type == "repost"
                    else post,
                    "components": components,
                    "evidence": {
                        "impressions": impressions,
                        "clicks": clicks,
                        "readers": readers,
                    },
                    "score": sum(components.values()),
                    "channels": [name for name, ids in channels.items() if post in ids],
                    "noise": _noise(seed, user_id, tick, refresh, post),
                }
        # Prefer unseen posts across refreshes; when the pool is exhausted,
        # permit repeats with fatigue rather than return a permanently empty feed.
        remaining = {
            post: value
            for post, value in records.items()
            if post not in seen and (not self.native or value["content_id"] not in seen)
        }
        repeated = False
        if not remaining:
            remaining = dict(records)
            repeated = bool(records)
        authors, used_topics, used_communities = Counter(), Counter(), Counter()
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

            def slate_score(post, explore=explore, remaining=remaining):
                record = remaining[post]
                penalty = self.config.author_diversity_penalty * authors[
                    record["author_id"]
                ] + self.config.topic_diversity_penalty * sum(
                    used_topics[t] for t in record["topics"]
                ) / max(1, len(record["topics"]))
                if self.native and self.platform == "reddit" and record["community"]:
                    penalty += (
                        self.config.community_diversity_penalty
                        * used_communities[record["community"]]
                    )
                base = record["noise"] if explore else record["score"]
                return base - penalty

            post = max(remaining, key=lambda post: (slate_score(post), post))
            record = remaining.pop(post)
            community_penalty = (
                self.config.community_diversity_penalty
                * used_communities[record["community"]]
                if self.native and self.platform == "reddit" and record["community"]
                else 0
            )
            decisions.append(
                {
                    **record,
                    "rank": rank,
                    "slate_score": slate_score_from_record(
                        record, authors, used_topics, self.config, bool(explore)
                    )
                    - community_penalty,
                    "selection": "exploration" if explore else "ranked",
                }
            )
            selected.append(post)
            authors[record["author_id"]] += 1
            used_topics.update(record["topics"])
            used_communities[record["community"]] += 1
            if self.native and self.platform == "x":
                remaining = {
                    pid: item
                    for pid, item in remaining.items()
                    if item["content_id"] != record["content_id"]
                }
        diagnostics = {
            "policy_version": self.config.policy_version,
            "platform": self.platform,
            "community_interests": community_affinity,
            "text_interests": words,
            "author_interests": author_affinity,
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
