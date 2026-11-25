"""World initialization must separate experimental starting conditions from actions."""

import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image

from agora.api import PlatformHub
from agora.core import AssetInput, PersonaProfile
from agora.experiments import ExperimentManager
from agora.initialization import resolve_accounts
from agora.population import extend_population
from agora.session import SocialSession
from agora.world import open_world


@pytest.fixture(params=["xiaohongshu", "x", "reddit"])
def seeded(tmp_path, request):
    source = open_world("source", tmp_path, request.param)
    owner = source.add_persona(
        PersonaProfile(
            "owner", "owner", "Existing operator", interests={"photography": 1}
        )
    )
    reader = source.add_persona(PersonaProfile("reader", "reader", "Reader"))
    source.db.execute(
        "INSERT INTO community(name,title,creator_id) VALUES ('r/photography','Photography',?)",
        (owner,),
    )
    source.db.execute(
        "INSERT INTO community(name,title,creator_id,visibility) VALUES ('r/private','Private',?,'private')",
        (owner,),
    )
    source.db.commit()
    images = []
    for i in range(2):
        path = tmp_path / f"photo-{i}.png"
        Image.new("RGB", (18, 16), ("red", "blue")[i]).save(path)
        images.append(AssetInput(path, alt_text=f"Image {i}"))
    original = source.create_post(
        owner,
        body="Original public post",
        title="Existing gallery",
        post_type="gallery",
        assets=images,
        topics=["photography"],
        community="r/photography",
        location="Hong Kong",
    )
    source.db.execute(
        "UPDATE post SET link_url=? WHERE post_id=?",
        ("https://example.org/photo", original),
    )
    source.db.commit()
    source.set_time(10000)
    latest = source.create_post(
        owner, body="Another public original", title="Latest", topics=["photography"]
    )
    source.like_post(reader, original)
    source.follow_user(owner, reader)
    asyncio.run(source.create_comment(reader, original, "Historical comment"))
    for field, value in [
        ("visibility", "private"),
        ("deleted", 1),
        ("removed_by", reader),
        ("original_post_id", original),
        ("reply_to_post_id", original),
        ("community", "r/private"),
    ]:
        pid = source.create_post(
            owner, body="Excluded historical content", title="Excluded"
        )
        source.db.execute(f"UPDATE post SET {field}=? WHERE post_id=?", (value, pid))
    source.db.execute(
        "INSERT INTO agent_api_token(token_hash,user_id) VALUES ('source-token',?)",
        (owner,),
    )
    source.db.commit()
    session = SocialSession.start(source, owner)
    yield source, owner, reader, original, latest, session.session_id
    source.close()


def initial_run(source, monkeypatch, config):
    manager = ExperimentManager(source)

    # Freeze before policies act, so the initial snapshot itself is asserted.
    def stop_before_actions(run_id):
        with manager.lock:
            manager.jobs[run_id]["status"] = "completed"
            manager._write(run_id)

    monkeypatch.setattr(manager, "_worker", stop_before_actions)
    job = manager.start(
        {"ticks": 1, "steps_per_tick": 1, "goal": "Focal task", **config}
    )
    manager.threads[job["run_id"]].join(5)
    return manager, manager.inspect(job["run_id"])


def fingerprint(source):
    source.db.commit()
    return (
        tuple(source.db.iterdump()),
        {
            str(p.relative_to(source.config.world_dir)): p.read_bytes()
            for p in source.config.world_dir.rglob("*")
            if p.is_file()
            and "experiments" not in p.relative_to(source.config.world_dir).parts
            and p.suffix not in {".db", ".db-wal", ".db-shm"}
        },
    )


def test_background_takeover_preserves_history_and_source(seeded, monkeypatch):
    source, owner, reader, original, _, sid = seeded
    before = fingerprint(source)
    manager, run = initial_run(
        source,
        monkeypatch,
        {"agent_count": 2, "focal_user_id": owner, "world_mode": "background"},
    )
    try:
        config = run["config"]
        assert config["focal_start"] == "existing"
        assert config["user_ids"] == [owner, reader]
        assert config["agent_goals"] == {str(owner): "Focal task", str(reader): ""}
        assert config["initial_state"]["focal_posts"] > 0
        with manager.snapshot(run["run_id"]) as target:
            assert target.db.execute(
                "SELECT 1 FROM follow WHERE follower_id=? AND followee_id=?",
                (owner, reader),
            ).fetchone()
            assert (
                target.db.execute(
                    "SELECT num_likes FROM post WHERE post_id=?", (original,)
                ).fetchone()[0]
                == 1
            )
            assert target.db.execute(
                "SELECT 1 FROM agora_session WHERE session_id=?", (sid,)
            ).fetchone()
            assert (
                target.db.execute("SELECT COUNT(*) FROM agent_api_token").fetchone()[0]
                == 0
            )
        assert run["metrics"]["created_posts"] == run["events_total"] == 0
        assert fingerprint(source) == before
    finally:
        manager.shutdown()


@pytest.mark.parametrize("mode", ["background", "ai_only"])
@pytest.mark.parametrize("preload", [0, 20])
def test_new_and_prepared_accounts_have_explicit_history(
    seeded, monkeypatch, mode, preload
):
    source, owner, _, original, latest, _ = seeded
    before = fingerprint(source)
    manager, run = initial_run(
        source,
        monkeypatch,
        {
            "world_mode": mode,
            "focal_start": "new",
            "focal_template_user_id": owner,
            "focal_starter_posts": preload,
            "background_start": "new",
            "agent_count": 3,
            "background_tasks": ["Background task"],
            "include_starter_assets": False,
            "new_account_name": "New operator",
            "focal_profile": {"bio": "A new identity"},
        },
    )
    try:
        cfg, state = run["config"], run["config"]["initial_state"]
        focal = cfg["focal_user_id"]
        assert state["focal_posts"] == (2 if preload else 0)
        assert state["world_users"] == (3 if mode == "ai_only" else 5)
        assert cfg["agent_goals"] == {
            str(focal): "Focal task",
            str(cfg["user_ids"][1]): "Background task",
            str(cfg["user_ids"][2]): "",
        }
        assert [p["source_post_id"] for p in state["preloaded_posts"]] == (
            [latest, original] if preload else []
        )
        with manager.snapshot(run["run_id"]) as target:
            assert target.db.execute(
                "SELECT name,bio,num_followers,num_followings FROM user WHERE user_id=?",
                (focal,),
            ).fetchone() == ("New operator", "A new identity", 0, 0)
            assert (
                target.db.execute(
                    "SELECT COUNT(*) FROM follow WHERE follower_id=? OR followee_id=?",
                    (focal, focal),
                ).fetchone()[0]
                == 0
            )
            assert target.db.execute(
                "SELECT COUNT(*) FROM creator_asset WHERE user_id=?", (focal,)
            ).fetchone()[0] == (2 if preload else 0)
            assert (
                target.db.execute(
                    "SELECT COUNT(*) FROM post WHERE user_id=? AND (num_likes!=0 OR num_shares!=0 OR num_dislikes!=0)",
                    (focal,),
                ).fetchone()[0]
                == 0
            )
            if preload:
                copied = state["preloaded_posts"][1]["post_id"]
                assert target.get_post_assets(copied) == source.get_post_assets(
                    original
                )
                fields = "content,title,post_type,language,community,location,created_at,link_url"
                assert (
                    target.db.execute(
                        f"SELECT {fields} FROM post WHERE post_id=?", (copied,)
                    ).fetchone()
                    == source.db.execute(
                        f"SELECT {fields} FROM post WHERE post_id=?", (original,)
                    ).fetchone()
                )
                assert target.get_post_topics(copied) == source.get_post_topics(
                    original
                )
            if mode == "ai_only":
                assert (
                    target.db.execute("SELECT COUNT(*) FROM post").fetchone()[0]
                    == state["focal_posts"]
                )
                for table in (
                    "comment",
                    "like",
                    "follow",
                    "agent_api_token",
                    "agora_session",
                ):
                    assert (
                        target.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                        == 0
                    )
                assert target.db.execute(
                    "SELECT creator_id FROM community WHERE name='r/photography'"
                ).fetchone() == (None,)
                assert not target.db.execute(
                    "SELECT 1 FROM community WHERE name='r/private'"
                ).fetchone()
                assert (
                    target.db.execute(
                        "SELECT COUNT(*) FROM user WHERE user_name IN ('owner','reader')"
                    ).fetchone()[0]
                    == 0
                )
        exported = manager.export_file(run["run_id"])
        try:
            assert json.loads(exported.read_text())["config"]["initial_state"] == state
        finally:
            exported.unlink()
        assert fingerprint(source) == before
    finally:
        manager.shutdown()


def test_ai_only_starter_library_is_owned_without_posts(seeded, monkeypatch):
    source, *_ = seeded
    manager, run = initial_run(
        source, monkeypatch, {"world_mode": "ai_only", "agent_count": 2}
    )
    try:
        assert run["config"]["initial_state"]["posts"] == 0
        assert run["config"]["initial_state"]["focal_assets"] == 2
        with manager.snapshot(run["run_id"]) as target:
            for user in run["config"]["user_ids"]:
                assert len(target.asset_library(user)) == 2
    finally:
        manager.shutdown()


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
@pytest.mark.parametrize("mode", ["background", "ai_only"])
def test_empty_world_can_create_agents(tmp_path, monkeypatch, platform, mode):
    source = open_world("empty", tmp_path, platform)
    try:
        manager, run = initial_run(
            source,
            monkeypatch,
            {
                "world_mode": mode,
                "focal_start": "new",
                "agent_count": 2,
                "user_ids": [],
                "include_starter_assets": False,
            },
        )
        try:
            assert run["config"]["initial_state"]["posts"] == 0
            assert run["config"]["initial_state"]["world_users"] == 2
            assert run["config"]["focal_user_id"] in run["config"]["user_ids"]
            assert source.db.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 0
        finally:
            manager.shutdown()
    finally:
        source.close()


@pytest.mark.parametrize(
    "invalid",
    [
        {"world_mode": "unknown"},
        {"world_mode": "ai_only", "focal_start": "existing"},
        {"world_mode": "ai_only", "background_start": "existing"},
        {"focal_start": "new", "focal_starter_posts": 21},
        {
            "focal_start": "new",
            "focal_starter_posts": 1,
            "focal_template_user_id": None,
        },
        {"focal_start": "new", "focal_template_user_id": 999},
        {"background_tasks": ["Too many", "tasks"]},
        {"include_starter_assets": 1},
        {"focal_start": "new", "new_account_name": " "},
    ],
)
def test_invalid_modes_leave_no_partial_run(seeded, invalid):
    source, owner, *_ = seeded
    manager = ExperimentManager(source)
    before = set(manager.root.iterdir())
    try:
        with pytest.raises((ValueError, TypeError)):
            manager.start({"agent_count": 2, "focal_user_id": owner, **invalid})
        assert set(manager.root.iterdir()) == before
        assert not manager.jobs
    finally:
        manager.shutdown()


def test_initialization_failure_cleans_up_run(seeded):
    source, *_ = seeded
    manager = ExperimentManager(source)
    before = set(manager.root.iterdir())
    try:
        with pytest.raises(ValueError):
            manager.start(
                {
                    "agent_count": 1,
                    "focal_start": "new",
                    "focal_profile": {"posting_probability": 9},
                }
            )
        assert set(manager.root.iterdir()) == before
        assert not manager.jobs
    finally:
        manager.shutdown()


def test_legacy_selection_and_task_semantics(seeded, monkeypatch):
    source, owner, reader, *_ = seeded
    users, focal, count, options = resolve_accounts(
        source, {"user_ids": [reader, owner]}
    )
    assert (users, focal, count) == ([reader, owner], reader, 2)
    assert options["separate_tasks"] is False
    manager, run = initial_run(source, monkeypatch, {"user_ids": [reader, owner]})
    try:
        assert set(run["config"]["agent_goals"].values()) == {"Focal task"}
        with pytest.raises(ValueError):
            resolve_accounts(source, {"user_ids": []})
    finally:
        manager.shutdown()


def test_new_focal_counts_toward_admission(seeded):
    source, owner, reader, *_ = seeded
    hub = PlatformHub(source, max_active_agents=2)
    try:
        with pytest.raises(ValueError, match="最多同时运行"):
            hub.admit({"user_ids": [owner, reader], "focal_start": "new"})
    finally:
        hub.shutdown()


def test_generated_identity_does_not_collide(seeded):
    source, owner, *_ = seeded
    first = extend_population(source, [owner], 2, 42, provide_assets=False)[1]
    second = extend_population(source, [owner], 2, 42, provide_assets=False)[1]
    assert first != second
    assert (
        source.db.execute(
            "SELECT COUNT(DISTINCT user_name) FROM user WHERE user_id IN (?,?)",
            (first, second),
        ).fetchone()[0]
        == 2
    )


def test_large_media_manifest_streams_and_exports_all_assets(
    seeded, monkeypatch, tmp_path
):
    source, owner, *_ = seeded
    for i in range(130):
        image = tmp_path / f"extra-{i}.png"
        Image.new("RGB", (2, 2), (i, 20, 50)).save(image)
        source.import_media(image)
    original_read = Path.read_bytes

    def guarded_read(path):
        assert path.name != "sandbox.db", (
            "The initial database must be hashed in chunks"
        )
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    manager, run = initial_run(
        source, monkeypatch, {"agent_count": 1, "focal_user_id": owner}
    )
    try:
        assert run["media_manifest_count"] == 132
        assert len(run["media_manifest"]) == 128
        assert run["media_manifest_truncated"] is True
        exported = manager.export_file(run["run_id"])
        try:
            data = json.loads(exported.read_text())
            assert len(data["initial_media_manifest"]) == 132
        finally:
            exported.unlink()
    finally:
        manager.shutdown()
