"""Behavioral checks for actual exposure, online feedback and account replay."""

import asyncio
import json

import pytest

from agora import RecommendationConfig, RecommendationEngine, SocialSession
from agora.runner import JsonSessionPolicy, run_sessions
from oasis import AgoraOasis, PersonaProfile


@pytest.fixture
def world(tmp_path):
    sandbox = AgoraOasis.local("sessions", tmp_path, preset="xiaohongshu")
    sandbox.set_seed(42)
    yield sandbox
    sandbox.close()


def seed(world, count=36):
    viewer = world.add_persona(
        PersonaProfile("reader", "reader", "Reader", interests={"旅行": 1.0})
    )
    authors = [world.create_user(f"author-{i}", f"Author {i}") for i in range(6)]
    posts = [
        world.create_post(
            authors[i % 6], body=f"Note {i}", topics=["旅行" if i % 2 else "咖啡"]
        )
        for i in range(count)
    ]
    return viewer, authors, posts


def act(session, name, args=None):
    return asyncio.run(session.act(name, args))


def test_only_visible_page_counts_as_exposure_and_refresh_avoids_seen(world):
    viewer, _, _ = seed(world)
    session = SocialSession.start(world, viewer)
    first = {post["post_id"] for post in session.observe()["cards"]}
    assert len(first) == 6
    assert (
        world.platform.db.execute("SELECT COUNT(*) FROM agora_exposure").fetchone()[0]
        == 6
    )
    assert (
        world.platform.db.execute("SELECT COUNT(*) FROM feed_impression").fetchone()[0]
        == 6
    )
    act(session, "refresh")
    second = {post["post_id"] for post in session.observe()["cards"]}
    assert first.isdisjoint(second)
    act(session, "scroll")
    assert (
        world.platform.db.execute("SELECT COUNT(*) FROM agora_exposure").fetchone()[0]
        == 18
    )


def test_detail_is_required_and_observation_hides_ranking_and_full_body(world):
    viewer, _, _ = seed(world)
    session = SocialSession.start(world, viewer)
    card = session.observe()["cards"][0]
    assert (
        "comments" not in card
        and "feed_score" not in card
        and "feed_reason" not in card
    )
    with pytest.raises(ValueError):
        act(
            session,
            "create_comment",
            {"post_id": card["post_id"], "content": "Read first"},
        )
    with pytest.raises(PermissionError):
        act(session, "open_post", {"post_id": 999})
    act(session, "open_post", {"post_id": card["post_id"]})
    assert session.observe()["screen"] == "detail"
    assert "comments" in session.observe()["post"]
    assert "diagnostics" not in json.dumps(session.observe())
    assert session.diagnostics()[0]["diagnostics"]["candidate_count"] > 6


def test_feedback_learns_decays_and_idempotent_likes_do_not_amplify(world):
    viewer, _, _ = seed(world)
    session = SocialSession.start(world, viewer)
    card = next(post for post in session.observe()["cards"] if "旅行" in post["topics"])
    before = session.engine.interests(viewer, 0)["旅行"]
    act(session, "open_post", {"post_id": card["post_id"]})
    act(session, "like_post", {"post_id": card["post_id"]})
    learned = session.engine.interests(viewer, 0)["旅行"]
    assert learned > before
    act(session, "like_post", {"post_id": card["post_id"]})
    assert session.engine.interests(viewer, 0)["旅行"] == learned
    act(session, "dwell", {"duration_ms": 30000})
    after_dwell = session.engine.interests(viewer, 0)["旅行"]
    act(session, "dwell", {"duration_ms": 30000})
    assert session.engine.interests(viewer, 0)["旅行"] == after_dwell
    assert before < session.engine.interests(viewer, 240)["旅行"] < learned
    act(session, "not_interested", {"post_id": card["post_id"]})
    ids, _ = session.engine.rank(viewer, 0, 42)
    assert card["post_id"] not in ids


def test_ranking_changes_with_feedback_and_viral_volume_is_bounded(world):
    viewer = world.create_user("reader", "Reader")
    author = world.create_user("author", "Author")
    travel = world.create_post(author, body="Travel", topics=["旅行"])
    coffee = world.create_post(author, body="Coffee", topics=["咖啡"])
    world.platform.db.execute(
        "UPDATE post SET num_likes = 1000000 WHERE post_id = ?", (coffee,)
    )
    world.platform.db.commit()
    session = SocialSession.start(world, viewer)
    act(session, "open_post", {"post_id": travel})
    act(session, "collect_post", {"post_id": travel})
    ids, _ = session.engine.rank(viewer, 0, 42)
    assert ids[0] == travel


def test_private_content_and_following_semantics(world):
    viewer, authors, _ = seed(world)
    private = world.create_post(authors[0], body="secret", visibility="private")
    followers = world.create_post(
        authors[0], body="followers only", visibility="followers"
    )
    engine = RecommendationEngine(world.platform.db)
    ids, _ = engine.rank(viewer, 0, 42)
    assert private not in ids and followers not in ids
    ids, _ = engine.rank(viewer, 0, 42, feed_type="following")
    assert ids == []
    world.follow_user(viewer, authors[0])
    ids, _ = engine.rank(viewer, 0, 42, feed_type="following")
    assert followers in ids and private not in ids
    assert all(world.view_post(viewer, post)["author_id"] == authors[0] for post in ids)


def test_search_finds_old_posts_and_literal_wildcards(world):
    viewer, authors, _ = seed(world, 220)
    oldest = world.create_post(
        authors[0], body="literal 50%_offer", topics=["稀有主题"]
    )
    world.platform.db.execute(
        "UPDATE post SET num_likes = 1000 WHERE post_id != ?", (oldest,)
    )
    world.platform.db.commit()
    assert [post["post_id"] for post in world.search_posts(viewer, "50%_offer")] == [
        oldest
    ]
    session = SocialSession.start(world, viewer)
    act(session, "search", {"query": "稀有主题"})
    assert [post["post_id"] for post in session.observe()["cards"]] == [oldest]


def test_small_pools_repeat_and_snapshots_reopen_session(tmp_path, world):
    viewer, _, _ = seed(world, 2)
    session = SocialSession.start(world, viewer)
    act(session, "refresh")
    assert len(session.observe()["cards"]) == 2
    assert session.diagnostics()[-1]["diagnostics"]["repeat_fallback"]
    snapshot = world.snapshot("session-state")
    assert (snapshot / "sandbox.db").exists()
    reopened = SocialSession(world, session.session_id)
    assert reopened.observe() == session.observe()
    assert reopened.trajectory() == session.trajectory()
    act(reopened, "end_session")
    with pytest.raises(ValueError):
        act(reopened, "refresh")


def test_same_seed_has_same_slate_and_multi_user_semantic_trajectory(tmp_path):
    outputs = []
    for name in ("one", "two"):
        world = AgoraOasis.local(name, tmp_path, preset="xiaohongshu")
        try:
            world.set_seed(42)
            viewer, authors, _ = seed(world)
            engine = RecommendationEngine(world.platform.db)
            assert engine.rank(viewer, 0, 42) == engine.rank(viewer, 0, 42)
            report = asyncio.run(
                run_sessions(world, [viewer, authors[0]], ticks=2, steps_per_tick=5)
            )
            assert report["failures"] == []
            outputs.append(
                [
                    SocialSession(world, sid).trajectory()
                    for sid in report["session_ids"]
                ]
            )
        finally:
            world.close()
    assert outputs[0] == outputs[1]


def test_model_session_contract_receives_public_history_and_uses_same_tools(world):
    viewer, _, _ = seed(world)

    class Client:
        async def complete(self, messages):
            self.payload = json.loads(messages[1]["content"])
            return type(
                "Response",
                (),
                {
                    "text": json.dumps(
                        {
                            "action_type": "open_post",
                            "arguments": {
                                "post_id": self.payload["observation"]["cards"][0][
                                    "post_id"
                                ]
                            },
                        }
                    )
                },
            )()

    client = Client()
    session = SocialSession.start(world, viewer)
    action = asyncio.run(
        JsonSessionPolicy(client).act(session.observe(), {"history": []})
    )
    act(session, action["action_type"], action["arguments"])
    assert session.observe()["screen"] == "detail"
    assert "feed_score" not in json.dumps(client.payload)


def test_model_vision_receives_visible_cover_bytes_without_leaking_into_replay(
    world, tmp_path
):
    from PIL import Image

    from agora.backends.visual import session_visual_parts
    from oasis import AssetInput

    viewer = world.create_user("viewer", "Viewer")
    author = world.create_user("author", "Author")
    images = []
    for index, color in enumerate(("red", "blue")):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (20, 20), color).save(path)
        images.append(AssetInput(path))
    post = world.create_post(author, body="Gallery", post_type="gallery", assets=images)
    session = SocialSession.start(world, viewer)
    parts = session_visual_parts(world, session.observe())
    assert len([part for part in parts if part["type"] == "image_url"]) == 1
    assert any(
        part.get("image_url", {}).get("url", "").startswith("data:image/jpeg;base64,")
        for part in parts
    )
    act(session, "open_post", {"post_id": post})
    parts = session_visual_parts(world, session.observe())
    assert len([part for part in parts if part["type"] == "image_url"]) == 1
    first = parts[-1]
    act(session, "view_media", {"index": 1})
    assert session_visual_parts(world, session.observe())[-1] != first
    assert "base64" not in json.dumps(session.trajectory())
    assert "object_key" not in json.dumps(session.observe())


def test_failed_account_policy_is_audited_and_other_accounts_continue(world):
    viewer, authors, _ = seed(world)

    class Policy:
        def __init__(self, user):
            self.user = user

        async def act(self, observation, context):
            if self.user == viewer:
                raise RuntimeError("Simulated provider failure")
            return {"action_type": "refresh", "arguments": {}}

    result = asyncio.run(
        run_sessions(
            world,
            [viewer, authors[0]],
            ticks=2,
            steps_per_tick=2,
            policy_factory=Policy,
        )
    )
    assert len(result["failures"]) == 2
    failed, healthy = [SocialSession(world, sid) for sid in result["session_ids"]]
    assert (
        sum(
            item["action"]["action_type"] == "policy_failure"
            for item in failed.trajectory()
        )
        == 2
    )
    assert (
        sum(item["action"]["action_type"] == "refresh" for item in healthy.trajectory())
        == 4
    )


def test_session_persists_after_world_connection_is_closed(tmp_path):
    first = AgoraOasis.local("persist", tmp_path, preset="xiaohongshu")
    viewer, _, _ = seed(first)
    session = SocialSession.start(first, viewer)
    act(session, "open_post", {"post_id": session.observe()["cards"][0]["post_id"]})
    expected = session.observe()
    sid = session.session_id
    first.close()
    reopened = AgoraOasis.local("persist", tmp_path)
    try:
        restored = SocialSession(reopened, sid)
        assert restored.observe() == expected
        act(restored, "back")
        assert len(restored.trajectory()) == 3
    finally:
        reopened.close()


def test_controlled_exposure_records_only_requested_order(world):
    viewer, _, posts = seed(world)
    world.observe_controlled(viewer, [posts[0], posts[-1]])
    assert world.platform.db.execute(
        "SELECT post_id, rank FROM feed_impression ORDER BY impression_id"
    ).fetchall() == [(posts[0], 0), (posts[-1], 1)]


@pytest.mark.parametrize(
    "bad",
    [
        {"page_size": 0},
        {"exploration_fraction": 0.7},
        {"topic_weight": float("nan")},
        {"page_size": 31},
        {"policy_version": "unknown"},
    ],
)
def test_recommendation_config_rejects_invalid_experiment_settings(bad):
    with pytest.raises(ValueError):
        RecommendationConfig(**bad)
