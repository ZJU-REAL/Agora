"""Inspectable platform-specific organic distribution approximations."""

import math

# Inspectable simulation hypotheses, not fitted vendor parameters.
FEEDBACK_PROFILES = {
    "xiaohongshu": {
        "open_post": 0.15,
        "dwell": 0.5,
        "like_post": 0.6,
        "collect_post": 1.2,
        "create_comment": 0.3,
        "view_media": 0.2,
    },
    "x": {
        "open_post": 0.1,
        "dwell": 0.2,
        "like_post": 0.7,
        "collect_post": 0.35,
        "create_comment": 0.4,
        "reply_post": 0.4,
        "repost": 1.0,
        "quote_post": 0.6,
    },
    "reddit": {
        "open_post": 0.15,
        "dwell": 0.4,
        "like_post": 0.7,
        "collect_post": 0.5,
        "create_comment": 0.3,
    },
}


def feedback_weight(platform, kind, fallback):
    undo = {
        "unlike_post": "like_post",
        "uncollect_post": "collect_post",
        "undo_repost": "repost",
    }
    target = undo.get(kind, kind)
    weight = FEEDBACK_PROFILES.get(platform, {}).get(target, abs(fallback))
    return -weight if kind in undo else weight if fallback >= 0 else -weight


def platform_quality(
    platform, likes, dislikes, saves, comments, shares, ctr, reading_rate=0
):
    """Different bounded objectives for notes, conversations and communities."""
    if platform == "reddit":
        approval = (likes + 1) / (likes + dislikes + 2)
        return (
            wilson_lower(likes, dislikes)
            + min(1.0, math.log1p(max(0, likes - dislikes)) / 10)
            + 0.1 * approval * min(1.0, math.log1p(comments) / 5)
            + 0.1 * reading_rate
        )
    profile = PROFILES.get(platform, PROFILES["generic"])
    volume = max(
        0,
        likes * profile["likes"]
        + saves * profile["saves"]
        + comments * profile["comments"]
        + shares * profile["shares"]
        - dislikes,
    )
    return (
        ctr
        + min(1.0, math.log1p(volume) / 10)
        + ({"xiaohongshu": 0.6, "x": 0.4}.get(platform, 0) * reading_rate)
    )


PROFILES = {
    "xiaohongshu": {
        "likes": 1.0,
        "saves": 3.0,
        "comments": 2.0,
        "shares": 0.0,
        "freshness": 1.0,
        "trial": 0.35,
    },
    "x": {
        "likes": 1.0,
        "saves": 0.5,
        "comments": 2.5,
        "shares": 3.0,
        "freshness": 1.8,
        "trial": 0.15,
    },
    "reddit": {
        "likes": 1.0,
        "saves": 0.5,
        "comments": 1.5,
        "shares": 0.0,
        "freshness": 1.0,
        "trial": 0.2,
    },
    "generic": {
        "likes": 1.0,
        "saves": 2.0,
        "comments": 1.5,
        "shares": 2.0,
        "freshness": 1.0,
        "trial": 0.0,
    },
}


def reddit_hot(score, created_tick, tick_ms):
    """Historical public Reddit Hot shape, evaluated on the virtual clock."""
    sign = 1 if score > 0 else -1 if score < 0 else 0
    return (
        sign * math.log10(max(abs(score), 1)) + int(created_tick) * tick_ms / 45000000
    )


def wilson_lower(up, down):
    count = up + down
    if not count:
        return 0.0
    z, p = 1.281551565545, up / count
    return (
        p
        + z * z / (2 * count)
        - z * math.sqrt((p * (1 - p) + z * z / (4 * count)) / count)
    ) / (1 + z * z / count)
