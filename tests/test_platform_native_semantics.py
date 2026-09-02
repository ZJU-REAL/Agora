import asyncio

from benchmarks import CandidateAction, WorldArtifact
from benchmarks.runners.exclusive import ExclusiveRunner
from oasis import AgoraOasis


def test_xiaohongshu_search_location_and_author_pinned_comment(tmp_path):
    sandbox = AgoraOasis.local("xhs-native", tmp_path / "worlds",
                               preset="xiaohongshu")
    creator = sandbox.create_user("creator", "博主")
    viewer = sandbox.create_user("viewer", "读者")
    post_id = sandbox.create_post(
        creator, title="上海旧街散步", body="梧桐树下慢慢走。",
        topics=["城市漫游"], location="上海·武康路")
    comment = asyncio.run(sandbox.create_comment(
        viewer, post_id, "请问几点去比较好？"))
    assert sandbox.pin_comment(creator, comment["comment_id"])
    result = sandbox.search_posts(viewer, "城市漫游")
    assert result[0]["location"] == "上海·武康路"
    assert sandbox.get_thread(post_id)[0]["is_pinned"] is True
    sandbox.close()


def test_reddit_community_filter_and_downvote(tmp_path):
    sandbox = AgoraOasis.local("reddit-native", tmp_path / "worlds",
                               preset="reddit")
    author = sandbox.create_user("author", "Author")
    viewer = sandbox.create_user("viewer", "Viewer")
    post_id = sandbox.create_post(
        author, title="Trail conditions", body="The north trail is muddy.",
        community="r/hiking")
    sandbox.create_post(author, title="Python tip", body="Use pathlib.",
                        community="r/python")
    assert sandbox.dislike_post(viewer, post_id)
    assert sandbox.search_posts(viewer, "trail", community="r/hiking")[0][
        "community"] == "r/hiking"
    assert sandbox.view_post(viewer, post_id)["num_dislikes"] == 1
    sandbox.close()


def test_x_quote_post_and_runner_native_actions(tmp_path):
    sandbox = AgoraOasis.local("x-native", tmp_path / "worlds", preset="x")
    author = sandbox.create_user("author", "Author")
    candidate = sandbox.create_user("candidate", "Candidate")
    post_id = sandbox.create_post(author, body="A public claim")
    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="x", version="1")
    sandbox.close()
    artifact.clone_episode(tmp_path / "episode", "episode")
    episode = AgoraOasis.local("world", tmp_path / "episode")
    runner = ExclusiveRunner(artifact, tmp_path / "outputs")
    outcome = asyncio.run(runner._apply_action(
        episode, candidate, CandidateAction("quote_post", {
            "post_id": post_id, "quote_body": "Here is the missing context."})))
    quoted = episode.view_post(candidate, outcome["post_id"])
    assert quoted["post_type"] == "quote"
    assert quoted["original_post_id"] == post_id
    assert quoted["quote_body"] == "Here is the missing context."
    episode.close()


def test_feed_enforces_private_and_followers_visibility(tmp_path):
    sandbox = AgoraOasis.local("visibility", tmp_path / "worlds",
                               preset="xiaohongshu")
    author = sandbox.create_user("author", "Author")
    follower = sandbox.create_user("follower", "Follower")
    stranger = sandbox.create_user("stranger", "Stranger")
    public = sandbox.create_post(author, body="public", visibility="public")
    followers = sandbox.create_post(
        author, body="followers", visibility="followers")
    private = sandbox.create_post(author, body="private", visibility="private")
    sandbox.follow_user(follower, author)

    assert {item["post_id"] for item in sandbox.get_feed(stranger)} == {public}
    assert {item["post_id"] for item in sandbox.get_feed(follower)} == {
        public, followers}
    assert {item["post_id"] for item in sandbox.get_feed(author)} == {
        public, followers, private}
    sandbox.close()
