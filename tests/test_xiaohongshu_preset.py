from oasis import AgoraOasis


def test_xiaohongshu_actions_and_feeds(tmp_path):
    sandbox = AgoraOasis.local("xhs", tmp_path / "worlds",
                               preset="xiaohongshu")
    creator = sandbox.create_user("creator", "旅行博主")
    viewer = sandbox.create_user("viewer", "读者")
    other = sandbox.create_user("other", "其他博主")
    creator_post = sandbox.create_post(
        creator, title="旧街散步", body="傍晚适合慢慢走。", post_type="text",
        language="zh-CN", topics=["城市漫游", "摄影"])
    sandbox.create_post(other, title="咖啡记录", body="今天的手冲。",
                        post_type="text", language="zh-CN")

    assert sandbox.preset.name == "xiaohongshu"
    assert "collect_post" in sandbox.available_actions()
    assert "dislike_post" not in sandbox.available_actions()
    assert "repost" not in sandbox.available_actions()

    assert sandbox.follow_user(viewer, creator) is True
    assert sandbox.follow_user(viewer, creator) is False
    assert sandbox.like_post(viewer, creator_post) is True
    assert sandbox.like_post(viewer, creator_post) is False
    assert sandbox.collect_post(viewer, creator_post) is True
    assert sandbox.collect_post(viewer, creator_post) is False

    following = sandbox.get_feed(viewer, feed_type="following")
    assert [post["post_id"] for post in following] == [creator_post]
    assert following[0]["feed_reason"] == "following"
    assert following[0]["num_collections"] == 1
    assert following[0]["topics"] == ["城市漫游", "摄影"]

    discover = sandbox.get_feed(viewer, feed_type="discover")
    assert discover[0]["post_id"] == creator_post
    assert discover[0]["feed_reason"] == "following"
    viewed = sandbox.view_post(viewer, creator_post)
    assert viewed["title"] == "旧街散步"

    assert sandbox.platform.db.execute(
        "SELECT COUNT(*) FROM feed_impression WHERE user_id = ?",
        (viewer, )).fetchone()[0] == 3
    assert sandbox.platform.db.execute(
        "SELECT COUNT(*) FROM feed_impression WHERE user_id = ? AND viewed = 1",
        (viewer, )).fetchone()[0] == 1
    sandbox.close()


def test_world_reopens_with_its_stored_preset(tmp_path):
    first = AgoraOasis.local("xhs", tmp_path / "worlds",
                             preset="xiaohongshu")
    first.close()
    reopened = AgoraOasis.local("xhs", tmp_path / "worlds")
    assert reopened.preset.name == "xiaohongshu"
    reopened.close()
