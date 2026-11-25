"""Native storage, creation workflows and isolated observable experiments."""

import asyncio
import json
import sqlite3
import subprocess
import sys
import time

import pytest
from PIL import Image

from agora.core import AssetInput, PersonaProfile
from agora.experiments import ExperimentManager
from agora.models import ModelResponse
from agora.recommendation import RecommendationConfig, RecommendationEngine
from agora.runner import JsonSessionPolicy, run_sessions
from agora.session import SocialSession
from agora.world import open_world


@pytest.fixture
def source(tmp_path):
    world = open_world("source", tmp_path, "xiaohongshu")
    creator = world.add_persona(
        PersonaProfile("creator", "creator", "创作者", interests={"摄影": 1.0})
    )
    reader = world.add_persona(
        PersonaProfile("reader", "reader", "读者", interests={"摄影": 0.7})
    )
    for i, color in enumerate(("red", "blue")):
        path = tmp_path / f"{i}.png"
        Image.new("RGB", (20, 16), color).save(path)
        world.create_post(
            creator,
            title=f"照片 {i}",
            body="摄影记录",
            post_type="image",
            assets=[AssetInput(path)],
            topics=["摄影"],
        )
    world.set_seed(42)
    yield world, creator, reader
    world.close()


def action(session, kind, args=None, rationale=None):
    return asyncio.run(session.act(kind, args, rationale))


def test_native_world_does_not_import_old_runtime(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from agora.world import open_world; import sys; w=open_world('native', sys.argv[1]); assert type(w.store).__name__=='WorldStore'; assert not any(name == 'oasis' or name.startswith(('oasis.', 'third_party.', 'archive.', 'camel', 'torch')) for name in sys.modules); assert 'benchmarks' not in sys.modules; w.close()",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_gallery_draft_publish_profile_and_public_reason(source):
    world, creator, _ = source
    session = SocialSession.start(world, creator)
    action(session, "open_studio")
    library = session.observe()["asset_library"]
    args = {
        "title": "新的图集",
        "body": "按顺序讲述一次体验。",
        "topics": ["摄影"],
        "assets": [{"asset_id": asset["asset_id"]} for asset in reversed(library)],
    }
    action(session, "save_draft", args, "先展示第二张照片，再用第一张补充细节。")
    assert session.observe()["draft"] == args
    result = action(session, "publish_draft")
    assert [
        asset["asset_id"] for asset in world.get_post_assets(result["post_id"])
    ] == [asset["asset_id"] for asset in reversed(library)]
    assert world.view_post(creator, result["post_id"])["post_type"] == "gallery"
    action(session, "view_profile")
    assert session.observe()["cards"][0]["post_id"] == result["post_id"]
    assert session.trajectory()[2]["action"]["rationale"].startswith("先展示")


def test_account_library_isolation(source):
    world, creator, reader = source
    session = SocialSession.start(world, reader)
    action(session, "open_studio")
    with pytest.raises(PermissionError):
        action(
            session,
            "save_draft",
            {
                "body": "No access",
                "assets": [{"asset_id": world.asset_library(creator)[0]["asset_id"]}],
            },
        )
    assert session.observe()["draft"] is None
    assert len(session.trajectory()) == 2


def test_atomic_action_restores_state_and_preserves_shared_media(source, monkeypatch):
    world, creator, _ = source
    session = SocialSession.start(world, creator)
    action(session, "open_studio")
    action(
        session,
        "save_draft",
        {
            "body": "A draft",
            "assets": [{"asset_id": world.asset_library(creator)[0]["asset_id"]}],
        },
    )
    before = session.observe()
    posts = world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    files = {p for p in world.media.root.rglob("*") if p.is_file()}

    def fail(*args):
        raise RuntimeError("Injected persistence failure")

    monkeypatch.setattr(session, "_event", fail)
    with pytest.raises(RuntimeError):
        action(session, "publish_draft")
    assert session.observe() == before
    assert world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0] == posts
    assert files == {p for p in world.media.root.rglob("*") if p.is_file()}
    assert all(path.exists() for path in files)


def test_world_atomic_rolls_back_new_media_and_nested_commits(source, tmp_path):
    world, creator, _ = source
    before = world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    files = {p for p in world.media.root.rglob("*") if p.is_file()}
    image = tmp_path / "green.png"
    Image.new("RGB", (12, 9), "green").save(image)
    with pytest.raises(RuntimeError), world.atomic():
        world.create_post(
            creator, body="Rolled back", post_type="image", assets=[AssetInput(image)]
        )
        world.db.commit()
        raise RuntimeError("After media import")
    assert world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0] == before
    assert files == {p for p in world.media.root.rglob("*") if p.is_file()}


def test_notification_thread_uses_simulated_time_and_correct_recipient(source):
    world, creator, reader = source
    world.db.execute("UPDATE simulation_state SET current_tick = 7")
    world.db.commit()
    comment = asyncio.run(world.create_comment(reader, 1, "怎么拍摄的？"))
    assert (
        world.db.execute(
            "SELECT created_at FROM comment WHERE comment_id = ?",
            (comment["comment_id"],),
        ).fetchone()[0]
        == 7
    )
    creator_session = SocialSession.start(world, creator)
    action(creator_session, "open_notifications")
    assert creator_session.observe()["notifications"][0]["content"] == "怎么拍摄的？"
    stranger_session = SocialSession.start(world, reader)
    action(stranger_session, "open_notifications")
    assert stranger_session.observe()["notifications"] == []


def test_content_addressed_imports_are_stable_and_deduplicate(source, tmp_path):
    world, creator, _ = source
    asset = world.asset_library(creator)[0]
    post = world.create_post(
        creator,
        body="reuse",
        post_type="image",
        assets=world.library_assets(creator, [{"asset_id": asset["asset_id"]}]),
    )
    assert world.get_post_assets(post)[0]["asset_id"] == asset["asset_id"]
    assert world.db.execute("SELECT COUNT(*) FROM media_asset").fetchone()[0] == 2


def test_experiment_clones_source_and_replays_same_semantic_trace(source):
    world, creator, reader = source
    # Make creation explicit now that the rule policy respects activity values.
    world.db.execute(
        "UPDATE persona SET persona_json=json_set(persona_json,'$.posting_probability',1.0) WHERE user_id=?",
        (creator,),
    )
    world.db.execute(
        "UPDATE persona SET persona_json=json_set(persona_json,'$.posting_probability',0.0) WHERE user_id=?",
        (reader,),
    )
    world.db.commit()
    before = (
        world.current_tick,
        world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0],
    )
    manager = ExperimentManager(world)
    results = []
    try:
        for _ in range(2):
            job = manager.start(
                {
                    "user_ids": [creator, reader],
                    "ticks": 4,
                    "steps_per_tick": 8,
                    "seed": 42,
                }
            )
            manager.threads[job["run_id"]].join(10)
            run = manager.inspect(job["run_id"])
            assert run["status"] == "completed"
            assert run["metrics"]["created_posts"] == 2
            assert run["metrics"]["drafts"] == 2
            assert run["report"]["failures"] == []
            with manager.snapshot(job["run_id"]) as cloned:
                with pytest.raises(sqlite3.OperationalError):
                    cloned.db.execute("DELETE FROM post")
                results.append(
                    [
                        SocialSession(cloned, sid).trajectory()
                        for sid in run["session_ids"]
                    ]
                )
        assert results[0] == results[1]
        assert before == (
            world.current_tick,
            world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0],
        )
    finally:
        manager.shutdown()


def test_pause_resume_stop_preserves_observable_job(source, monkeypatch):
    from agora.policies import PersonaPolicy

    original = PersonaPolicy.act

    async def slow(self, observation, context):
        await asyncio.sleep(0.015)
        return await original(self, observation, context)

    monkeypatch.setattr(PersonaPolicy, "act", slow)
    world, creator, _ = source
    manager = ExperimentManager(world)
    try:
        job = manager.start({"user_ids": [creator], "ticks": 20, "steps_per_tick": 10})
        rid = job["run_id"]
        manager.control(rid, "pause")
        deadline = time.monotonic() + 3
        while manager.jobs[rid]["status"] != "paused" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert manager.jobs[rid]["status"] == "paused"
        before = manager.jobs[rid]["attempted_actions"]
        time.sleep(0.05)
        assert manager.jobs[rid]["attempted_actions"] == before
        manager.control(rid, "resume")
        deadline = time.monotonic() + 3
        while (
            manager.jobs[rid]["attempted_actions"] == before
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert manager.jobs[rid]["attempted_actions"] > before
        manager.control(rid, "stop")
        manager.threads[rid].join(5)
        assert manager.inspect(rid)["status"] == "canceled"
    finally:
        manager.shutdown()


def test_model_calls_and_public_rationale_are_recorded(source):
    world, _, reader = source

    class Client:
        async def complete(self, messages):
            payload = json.loads(messages[1]["content"])
            assert "memory" in payload
            assert "feed_score" not in messages[1]["content"]
            return ModelResponse(
                json.dumps(
                    {
                        "action_type": "refresh",
                        "arguments": {},
                        "rationale": "查看新内容。",
                    }
                ),
                "fake-model",
                10,
                5,
            )

    report = asyncio.run(
        run_sessions(
            world,
            [reader],
            1,
            2,
            lambda user: JsonSessionPolicy(Client(), expected_model_id="fake-model"),
        )
    )
    records = world.db.execute(
        "SELECT status, model_id, input_tokens, output_tokens FROM agent_model_call"
    ).fetchall()
    assert records == [("completed", "fake-model", 10, 5)] * 2
    session = SocialSession(world, report["session_ids"][0])
    assert session.trajectory()[1]["action"]["rationale"] == "查看新内容。"


def test_collaborative_recall_and_versioned_ranking(source):
    world, creator, _ = source
    viewer = world.create_user("viewer", "Viewer")
    peer = world.create_user("peer", "Peer")
    world.like_post(viewer, 1)
    world.like_post(peer, 1)
    world.like_post(peer, 2)
    for index in range(8):
        world.create_post(creator, body=f"New {index}")
    options = {
        "channel_limit": 2,
        "slate_size": 2,
        "page_size": 2,
        "exploration_fraction": 0,
        "topic_weight": 0,
        "quality_weight": 0,
        "freshness_weight": 0,
        "following_weight": 0,
        "fatigue_weight": 0,
        "collaborative_weight": 1,
    }
    v2 = RecommendationEngine(world.db, RecommendationConfig(**options))
    ids, diagnostic = v2.rank(viewer, 0, 42)
    assert 2 in diagnostic["retrieval"]["collaborative"]
    assert ids[0] == 2
    v1 = RecommendationEngine(
        world.db, RecommendationConfig(policy_version="agora-hybrid-v1", **options)
    )
    ids, diagnostic = v1.rank(viewer, 0, 42)
    assert "collaborative" not in diagnostic["retrieval"]
    assert ids[0] != 2


def test_media_integrity_failure_leaves_no_partial_experiment(source):
    world, _, reader = source
    asset = world.db.execute("SELECT object_key FROM media_asset LIMIT 1").fetchone()[0]
    world.media.path_for(asset).write_bytes(b"tampered")
    manager = ExperimentManager(world)
    with pytest.raises(ValueError, match="checksum"):
        manager.start({"user_ids": [reader]})
    assert manager.list() == []
    assert list(manager.root.iterdir()) == []


def test_experiment_export_contains_actual_observations(source):
    world, _, reader = source
    manager = ExperimentManager(world)
    try:
        job = manager.start({"user_ids": [reader], "ticks": 1, "steps_per_tick": 2})
        manager.threads[job["run_id"]].join(5)
        export = manager.export(job["run_id"])
        assert export["format_version"] == "agora-experiment-v1"
        assert export["media_manifest"]
        assert export["trajectories"][0]["trajectory"][0]["observation"]["cards"]
        assert export["world_events"]
    finally:
        manager.shutdown()


@pytest.mark.parametrize(
    "config",
    [
        {"user_ids": []},
        {"user_ids": [999]},
        {"user_ids": [1], "ticks": 0},
        {"user_ids": [1], "steps_per_tick": 31},
        {"user_ids": [1], "seed": True},
        {"user_ids": [1], "provider_id": "unknown"},
    ],
)
def test_invalid_experiment_does_not_create_world(source, config):
    world, _, _ = source
    manager = ExperimentManager(world)
    with pytest.raises(ValueError):
        manager.start(config)
    assert manager.list() == []
