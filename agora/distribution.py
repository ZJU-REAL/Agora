"""Inspectable platform-specific organic distribution approximations."""

import math

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
