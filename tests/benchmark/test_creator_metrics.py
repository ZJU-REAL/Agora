from benchmarks.metrics import compute_creator_account_metrics
from oasis import AgoraOasis


def test_creator_account_metrics_cover_operation_dimensions(tmp_path):
    sandbox = AgoraOasis.local("world", tmp_path, preset="xiaohongshu")
    candidate = sandbox.create_user("creator", "Creator")
    post = sandbox.create_post(candidate, title="旅行日记", body="旅行的一天",
                               topics=["旅行"])
    fan = sandbox.create_user("fan", "Fan")
    sandbox.like_post(fan, post)
    sandbox.follow_user(fan, candidate)
    sandbox.close()
    metrics = compute_creator_account_metrics(
        tmp_path / "world" / "sandbox.db", candidate,
        persona_keywords=("旅行",))
    assert metrics.posts_created == 1
    assert metrics.title_completion_rate == 1.0
    assert metrics.topic_completion_rate == 1.0
    assert metrics.persona_consistency == 1.0
    assert metrics.follower_gain == 1
