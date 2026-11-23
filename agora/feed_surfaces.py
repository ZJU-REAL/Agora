"""Bounded native timelines: filter and sort in SQL before reading posts."""

from agora.distribution import reddit_hot
from agora.recommendation import VISIBILITY

WINDOWS = {
    "hour": 3600000,
    "day": 86400000,
    "week": 604800000,
    "month": 2592000000,
    "year": 31536000000,
    "all": None,
}


def surface_ids(
    db,
    user,
    platform,
    surface,
    tick,
    limit,
    sort="new",
    community=None,
    time_range="all",
):
    if time_range not in WINDOWS:
        raise ValueError("Unknown top-post time range")
    params = {"viewer": user, "tick": tick, "limit": limit}
    gate = VISIBILITY + " AND p.deleted=0 AND p.removed_by IS NULL"
    gate += " AND CAST(p.created_at AS INTEGER)<=:tick"
    gate += " AND NOT EXISTS (SELECT 1 FROM community c WHERE c.name=p.community AND c.visibility='private' AND NOT EXISTS (SELECT 1 FROM community_member m WHERE m.community=c.name AND m.user_id=:viewer))"
    gate += " AND NOT EXISTS (SELECT 1 FROM agora_feedback f WHERE f.user_id=:viewer AND f.post_id=p.post_id AND f.kind='not_interested')"
    if community:
        params["community"] = community
        gate += " AND p.community=:community"
    if surface == "following":
        if platform == "reddit":
            gate += " AND EXISTS (SELECT 1 FROM community_member m WHERE m.community=p.community AND m.user_id=:viewer)"
        else:
            gate += " AND (p.user_id=:viewer OR EXISTS (SELECT 1 FROM follow f WHERE f.follower_id=:viewer AND f.followee_id=p.user_id))"
    if platform == "x":
        parent_visibility = VISIBILITY.replace("p.", "parent.")
        if surface == "following":
            gate += (
                " AND (p.reply_to_post_id IS NULL OR p.user_id=:viewer OR EXISTS (SELECT 1 FROM post parent WHERE parent.post_id=p.reply_to_post_id AND parent.deleted=0 AND (parent.user_id=:viewer OR EXISTS (SELECT 1 FROM follow f WHERE f.follower_id=:viewer AND f.followee_id=parent.user_id)) AND "
                + parent_visibility
                + "))"
            )
        gate += (
            " AND (p.post_type!='repost' OR EXISTS (SELECT 1 FROM post parent WHERE parent.post_id=p.original_post_id AND parent.deleted=0 AND parent.removed_by IS NULL AND "
            + parent_visibility
            + "))"
        )
        gate += " AND NOT EXISTS (SELECT 1 FROM agora_feedback f WHERE f.user_id=:viewer AND p.post_type='repost' AND f.post_id=p.original_post_id AND f.kind='not_interested')"
    tick_ms = db.execute(
        "SELECT tick_duration_ms FROM simulation_state WHERE singleton=1"
    ).fetchone()[0]
    if WINDOWS[time_range] is not None:
        params["cutoff"] = tick * tick_ms - WINDOWS[time_range]
        params["tick_ms"] = tick_ms
        gate += " AND CAST(p.created_at AS INTEGER)*:tick_ms>=:cutoff"
    order = "CAST(p.created_at AS INTEGER) DESC,p.post_id DESC"
    if sort == "top":
        order = "(p.num_likes-p.num_dislikes) DESC," + order
    elif sort == "hot":
        db.create_function("agora_reddit_hot", 3, reddit_hot, deterministic=True)
        params["tick_ms"] = tick_ms
        order = "agora_reddit_hot(p.num_likes-p.num_dislikes,p.created_at,:tick_ms) DESC,p.post_id DESC"
    return [
        row[0]
        for row in db.execute(
            f"SELECT p.post_id FROM post p WHERE {gate} ORDER BY {order} LIMIT :limit",
            params,
        )
    ]
