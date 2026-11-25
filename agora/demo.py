"""Small replaceable fixtures for checking native platforms, not evaluation tasks."""

from __future__ import annotations

import json
from pathlib import Path


def populate(world):
    if world.db.execute("SELECT COUNT(*) FROM user").fetchone()[0]:
        raise ValueError("Demo requires an empty world; use a new world_id")
    from agora.core import AssetInput, PersonaProfile

    root = Path(__file__).parent / "fixtures"
    fixture = json.loads((root / "sample_worlds.json").read_text())
    name = world.preset.name
    spec = fixture.get(name, fixture["xiaohongshu"])
    users = [
        world.add_persona(
            PersonaProfile(
                profile_id=f"sample-{name}-{index}",
                handle=row["handle"],
                display_name=row["name"],
                bio=row["bio"],
                interests=row["interests"],
                tone=tuple(row["tone"]),
                example_posts=tuple(row["examples"]),
                locale="zh-CN" if name == "xiaohongshu" else "en-US",
                posting_probability=row.get(
                    "posting_probability", 0.12 if index < 3 else 0
                ),
                like_probability=row.get("like_probability", 0.3),
                comment_probability=row.get("comment_probability", 0.2),
                content_formats=row.get(
                    "content_formats", {"text": 0.2, "image": 0.6, "gallery": 0.2}
                ),
                culture=row.get("culture", {}),
            )
        )
        for index, row in enumerate(spec["users"])
    ]
    if name == "reddit":
        for row in spec["communities"]:
            world.create_community(
                users[0], row["name"], row["title"], row["description"], row["rules"]
            )
        for user in users[:3]:
            for community in spec["communities"]:
                world.join_community(user, community["name"])
        world.join_community(users[-1], "r/photography")
    tick_ms = world.db.execute(
        "SELECT tick_duration_ms FROM simulation_state WHERE singleton=1"
    ).fetchone()[0]
    world.set_time(60 * tick_ms)
    posts = []
    for row in spec["posts"]:
        files = row.get("assets", [])
        post = world.create_post(
            users[row["author"]],
            body=row["body"],
            title=row.get("title"),
            post_type="gallery" if len(files) > 1 else "image" if files else "text",
            assets=[
                AssetInput(
                    root / "media" / file, alt_text="Public illustration photo: " + file
                )
                for file in files
            ],
            topics=row.get("topics", []),
            community=row.get("community"),
            location=row.get("location", "示例城市") if name == "xiaohongshu" else None,
            language="zh-CN" if name == "xiaohongshu" else "en",
        )
        world.db.execute(
            "UPDATE post SET created_at=? WHERE post_id=?", (60 - row["age"], post)
        )
        world.db.commit()
        posts.append(post)
        if name == "reddit":
            world.vote_post(users[row["author"]], post, 1)
    comments = []
    for row in spec["comments"]:
        if name == "x":
            reply = world.create_post(
                users[row["author"]],
                body=row["content"],
                reply_to_post_id=comments[row["parent"]]
                if "parent" in row
                else posts[row["post"]],
            )
            comments.append(reply)
        else:
            result = world.add_comment(
                users[row["author"]],
                posts[row["post"]],
                row["content"],
                comments[row["parent"]] if "parent" in row else None,
            )
            comments.append(result["comment_id"])
            if name == "reddit":
                world.vote_comment(users[row["author"]], result["comment_id"], 1)
    reader = users[-1]
    world.follow_user(reader, users[0])
    world.db.execute(
        "INSERT OR IGNORE INTO creator_asset(user_id,asset_id,alt_text,transcript) SELECT ?,asset_id,alt_text,transcript FROM creator_asset WHERE user_id=?",
        (reader, users[0]),
    )
    world.db.commit()
    world.set_seed(42)
    return {
        "reader_id": reader,
        "creator_ids": users[:3],
        "world_id": world.config.world_id,
        "posts": len(posts),
        "users": len(users),
        "fixture_version": fixture["format_version"],
    }
