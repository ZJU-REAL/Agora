import asyncio

import pytest

from oasis import ActionType, DefaultPlatformType
from oasis.social_platform.platform import Platform


def test_xiaohongshu_is_a_native_platform_type():
    assert DefaultPlatformType.XIAOHONGSHU.value == "xiaohongshu"
    actions = ActionType.get_default_xiaohongshu_actions()
    assert ActionType.COLLECT_POST in actions
    assert ActionType.DISCOVER_FEED in actions
    assert ActionType.FOLLOWING_FEED in actions
    assert ActionType.VIEW_POST in actions
    assert ActionType.DISLIKE_POST not in actions
    assert ActionType.REPOST not in actions


def test_native_xiaohongshu_platform_actions(tmp_path):
    platform = Platform(str(tmp_path / "native-xhs.db"),
                        platform_style="xiaohongshu",
                        recsys_type="reddit",
                        show_score=False,
                        refresh_rec_post_count=10)
    platform.db.executemany(
        "INSERT INTO user "
        "(user_id, agent_id, user_name, name, num_followings, num_followers) "
        "VALUES (?, ?, ?, ?, 0, 0)",
        [(1, 1, "creator", "博主"), (2, 2, "viewer", "读者")])
    platform.db.execute(
        "INSERT INTO post (post_id, user_id, content, created_at, post_type, "
        "title) VALUES (1, 1, '散步记录', '0', 'text', '旧街散步')")
    platform.db.execute(
        "INSERT INTO follow (follower_id, followee_id, created_at) "
        "VALUES (2, 1, '0')")
    platform.db.execute(
        "INSERT INTO media_asset "
        "(asset_id, media_type, object_key, mime_type, byte_size, "
        "checksum_sha256) VALUES "
        "('image-1', 'image', 'images/1.jpg', 'image/jpeg', 10, 'abc')")
    platform.db.commit()

    image_note = asyncio.run(platform.create_post(1, {
        "content": "一张照片",
        "title": "雨后的街道",
        "post_type": "image",
        "asset_ids": ["image-1"],
        "topics": ["城市漫游"],
        "language": "zh-CN",
    }))
    collected = asyncio.run(platform.collect_post(2, 1))
    discover = asyncio.run(platform.discover_feed(2))
    following = asyncio.run(platform.following_feed(2))
    viewed = asyncio.run(platform.view_post(2, 1))

    assert collected == {"success": True, "post_id": 1}
    assert image_note["success"] is True
    assert platform.db.execute(
        "SELECT post_type, title FROM post WHERE post_id = ?",
        (image_note["post_id"], )).fetchone() == ("image", "雨后的街道")
    assert platform.db.execute(
        "SELECT asset_id FROM post_asset WHERE post_id = ?",
        (image_note["post_id"], )).fetchone()[0] == "image-1"
    assert discover["success"] is True
    assert discover["feed_type"] == "discover"
    assert discover["posts"][0]["content"] == "散步记录"
    assert following["success"] is True
    assert following["posts"][0]["post_id"] == 1
    image_feed_item = next(post for post in discover["posts"]
                           if post["post_id"] == image_note["post_id"])
    assert image_feed_item["title"] == "雨后的街道"
    assert image_feed_item["post_type"] == "image"
    assert image_feed_item["language"] == "zh-CN"
    assert image_feed_item["topics"] == ["城市漫游"]
    assert image_feed_item["assets"][0]["asset_id"] == "image-1"
    assert viewed["success"] is True
    assert viewed["post"]["post_id"] == 1
    assert platform.db.execute(
        "SELECT viewed FROM feed_impression WHERE user_id = 2 AND post_id = 1 "
        "ORDER BY impression_id DESC LIMIT 1").fetchone()[0] == 1

    platform.db_cursor.close()
    platform.db.close()


@pytest.mark.parametrize("post_type,asset_ids", [
    ("image", ["video"]),
    ("gallery", ["image", "video"]),
    ("video", ["image"]),
    ("video", ["video", "video"]),
    ("text", ["image"]),
])
def test_native_notes_reject_wrong_media_types(tmp_path, post_type, asset_ids):
    platform = Platform(str(tmp_path / "invalid-media.db"),
                        platform_style="xiaohongshu")
    try:
        asyncio.run(platform.sign_up(1, ("creator", "博主", "")))
        platform.db.executemany(
            "INSERT INTO media_asset "
            "(asset_id, media_type, object_key, mime_type, byte_size, "
            "checksum_sha256) VALUES (?, ?, ?, ?, 10, 'abc')",
            [("image", "image", "image.png", "image/png"),
             ("video", "video", "video.mp4", "video/mp4")])
        platform.db.commit()
        outcome = asyncio.run(platform.create_post(1, {
            "content": "图文正文", "post_type": post_type,
            "asset_ids": asset_ids}))
        assert outcome["success"] is False
        assert platform.db.execute(
            "SELECT COUNT(*) FROM post").fetchone()[0] == 0
        assert platform.db.execute(
            "SELECT COUNT(*) FROM post_asset").fetchone()[0] == 0
    finally:
        platform.db_cursor.close()
        platform.db.close()
