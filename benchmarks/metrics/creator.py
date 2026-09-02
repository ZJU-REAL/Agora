from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CreatorAccountMetrics:
    posts_created: int
    format_diversity: int
    title_completion_rate: float
    body_completion_rate: float
    topic_completion_rate: float
    media_completion_rate: float
    cover_completion_rate: float
    timing_adherence: float
    mean_engagement: float
    feedback_adaptation: float
    low_response_rate: float
    follower_gain: int
    persona_consistency: float


def compute_creator_account_metrics(
        database_path: str | Path,
        candidate_user_id: int,
        *,
        initial_followers: int = 0,
        persona_keywords: tuple[str, ...] = (),
        expected_publish_ticks: tuple[int, ...] = ()) -> CreatorAccountMetrics:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(
            "SELECT post_id, post_type, title, content, num_likes, num_shares, "
            "created_at "
            "FROM post WHERE user_id = ? ORDER BY created_at, post_id",
            (candidate_user_id, )).fetchall()
        followers = connection.execute(
            "SELECT num_followers FROM user WHERE user_id = ?",
            (candidate_user_id, )).fetchone()
        engagements = []
        title_complete = body_complete = topic_complete = 0
        media_complete = cover_complete = consistent = 0
        publish_ticks = []
        for post_id, post_type, title, body, likes, shares, created_at in rows:
            comments = connection.execute(
                "SELECT COUNT(*) FROM comment WHERE post_id = ?",
                (post_id, )).fetchone()[0]
            topics = connection.execute(
                "SELECT COUNT(*) FROM post_topic WHERE post_id = ?",
                (post_id, )).fetchone()[0]
            assets = connection.execute(
                "SELECT COUNT(*) FROM post_asset WHERE post_id = ?",
                (post_id, )).fetchone()[0]
            covers = connection.execute(
                "SELECT COUNT(*) FROM post_asset WHERE post_id = ? "
                "AND role = 'cover'", (post_id, )).fetchone()[0]
            engagements.append(float(likes + shares + comments))
            title_complete += int(bool(title and title.strip()))
            body_complete += int(bool(body and body.strip()))
            topic_complete += int(topics > 0)
            expected_assets = {"text": 0, "image": 1, "gallery": 2,
                               "video": 1}.get(post_type, 0)
            media_complete += int(assets >= expected_assets)
            cover_complete += int(post_type != "video" or covers > 0)
            try:
                publish_ticks.append(int(created_at))
            except (TypeError, ValueError):
                pass
            content = f"{title or ''} {body or ''}".lower()
            consistent += int(not persona_keywords or any(
                keyword.lower() in content for keyword in persona_keywords))
        count = len(rows)
        adaptation = (engagements[-1] - engagements[0]
                      if len(engagements) >= 2 else 0.0)
        return CreatorAccountMetrics(
            posts_created=count,
            format_diversity=len({row[1] for row in rows}),
            title_completion_rate=round(title_complete / count, 6) if count else 0.0,
            body_completion_rate=round(body_complete / count, 6) if count else 0.0,
            topic_completion_rate=round(topic_complete / count, 6) if count else 0.0,
            media_completion_rate=round(media_complete / count, 6) if count else 0.0,
            cover_completion_rate=round(cover_complete / count, 6)
            if count else 0.0,
            timing_adherence=(round(len(set(publish_ticks)
                                        & set(expected_publish_ticks))
                                    / len(expected_publish_ticks), 6)
                              if expected_publish_ticks else 1.0),
            mean_engagement=round(statistics.fmean(engagements), 6)
            if engagements else 0.0,
            feedback_adaptation=round(adaptation, 6),
            low_response_rate=round(sum(value == 0 for value in engagements)
                                    / count, 6) if count else 0.0,
            follower_gain=(int(followers[0]) - initial_followers
                           if followers else 0),
            persona_consistency=round(consistent / count, 6) if count else 0.0,
        )
    finally:
        connection.close()
