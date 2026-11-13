"""Temporary media adapter shared with the benchmark's bounded VLM encoder."""


def session_visual_parts(world, observation):
    from benchmarks.multimodal import sandbox_observation_parts

    # Read precisely the assets visible on the current screen. Feed cards have
    # covers only; a detail page has the full gallery and video keyframes.
    posts = (
        [observation["post"]]
        if observation["screen"] == "detail"
        else observation["cards"]
    )
    visible = []
    for post in posts:
        asset_ids = {asset["asset_id"] for asset in post["assets"]}
        assets = [
            asset
            for asset in world.get_post_assets(post["post_id"])
            if asset["asset_id"] in asset_ids
        ]
        visible.append({"post_id": post["post_id"], "assets": assets})
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
