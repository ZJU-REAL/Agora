"""Temporary media adapter shared with the benchmark's bounded VLM encoder."""


def session_visual_parts(world, observation):
    from agora.media_context import sandbox_observation_parts

    # Read precisely the assets visible on the current screen. Feed cards have
    # covers only; a detail page has the full gallery and video keyframes.
    if observation["screen"] == "studio":
        assets = []
        for asset in observation["asset_library"]:
            row = world.db.execute(
                "SELECT m.object_key FROM creator_asset ca JOIN media_asset m ON m.asset_id = ca.asset_id WHERE ca.user_id = ? AND m.asset_id = ?",
                (observation["user_id"], asset["asset_id"]),
            ).fetchone()
            if row:
                assets.append(
                    {
                        **asset,
                        "object_key": row[0],
                        "role": "content",
                        "position": len(assets),
                    }
                )
        posts = [{"post_id": "素材库", "assets": assets}]
    else:
        posts = (
            [observation["post"]]
            if observation["screen"] == "detail"
            else observation["cards"]
        )
    references = [
        post["original_post"]
        for post in posts
        if post.get("original_post") and not post["original_post"].get("unavailable")
    ]
    posts += references
    visible = []
    for post in posts:
        asset_ids = set(
            post.get(
                "visible_asset_ids", [asset["asset_id"] for asset in post["assets"]]
            )
        )
        assets = (
            post["assets"]
            if post["post_id"] == "素材库"
            else [
                asset
                for asset in world.get_post_assets(post["post_id"])
                if asset["asset_id"] in asset_ids
            ]
        )
        visible.append(
            {
                "post_id": post["post_id"],
                "assets": assets,
                "video_position_ms": post.get("video_position_ms"),
            }
        )
    proxy = type("MediaObservation", (), {"feed": visible})()
    parts = []
    count = 0
    for part in sandbox_observation_parts(world, proxy):
        if part["type"] == "image_url":
            if count == 12:
                break
            count += 1
        parts.append(part)
    return parts
