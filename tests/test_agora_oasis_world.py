import asyncio
import json

from PIL import Image

from oasis import AgoraOasis, DatasetImporter


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                            for row in rows),
                    encoding="utf-8")


def test_import_observe_and_advance_world(tmp_path):
    dataset = tmp_path / "dataset"
    media_dir = dataset / "media"
    media_dir.mkdir(parents=True)
    Image.new("RGB", (40, 30), (80, 120, 200)).save(media_dir / "city.jpg")

    _write_jsonl(dataset / "users.jsonl", [{
        "external_id": "seed-user",
        "handle": "city_seed",
        "display_name": "城市样本",
    }])
    _write_jsonl(dataset / "personas.jsonl", [{
        "profile_id": "creator-travel",
        "identity": {
            "handle": "slow_trip",
            "display_name": "阿南慢旅行",
            "bio": "城市漫游和摄影",
        },
        "creator": {
            "niche": ["旅行", "摄影"],
            "content_formats": {"text": 1.0},
        },
        "activity": {"posting_probability": 1.0},
        "style": {"example_posts": ["今天沿着旧街慢慢走了一圈。"]},
    }])
    _write_jsonl(dataset / "posts.jsonl", [{
        "external_id": "post-city",
        "author_external_id": "seed-user",
        "post_type": "image",
        "title": "傍晚的街道",
        "body": "这里适合慢慢走。",
        "assets": [{"path": "city.jpg"}],
    }])
    _write_jsonl(dataset / "comments.jsonl", [{
        "external_id": "comment-reply",
        "post_external_id": "post-city",
        "author_external_id": "seed-user",
        "parent_external_id": "comment-root",
        "content": "晚上会更安静。",
    }, {
        "external_id": "comment-root",
        "post_external_id": "post-city",
        "author_external_id": "seed-user",
        "content": "你也喜欢这里吗？",
    }])
    manifest = {
        "dataset": {"name": "world-demo"},
        "files": {
            "users": "users.jsonl",
            "personas": "personas.jsonl",
            "posts": "posts.jsonl",
            "comments": "comments.jsonl",
            "media_root": "media",
        },
        "import": {"id_namespace": "demo-v1"},
    }
    (dataset / "manifest.json").write_text(json.dumps(manifest),
                                             encoding="utf-8")

    sandbox = AgoraOasis.local("demo", tmp_path / "worlds")
    report = asyncio.run(
        DatasetImporter(sandbox).import_manifest(dataset / "manifest.json"))
    assert report.users == 1
    assert report.personas == 1
    assert report.posts == 1
    assert report.comments == 2

    creator_id = sandbox.platform.db.execute(
        "SELECT user_id FROM persona WHERE profile_id = 'creator-travel'"
    ).fetchone()[0]
    observation = sandbox.observe(creator_id)
    assert observation.tick == 0
    assert observation.feed[0]["post_type"] == "image"
    assert observation.feed[0]["assets"][0]["width"] == 40
    assert observation.feed[0]["comments"][0]["replies"][0][
        "content"] == "晚上会更安静。"

    result = asyncio.run(sandbox.advance())
    assert result.tick == 0
    assert result.actions[0]["action"] == "observe_feed"
    assert any(action["action"] == "create_post"
               for action in result.actions)
    assert sandbox.current_tick == 1
    assert any(event["event_type"] == "tick_advanced"
               for event in result.events)

    snapshot = sandbox.snapshot("after-first-tick")
    assert (snapshot / "sandbox.db").is_file()
    snapshot_manifest = json.loads(
        (snapshot / "manifest.json").read_text(encoding="utf-8"))
    assert snapshot_manifest["tick"] == 1
    assert len(snapshot_manifest["media"]) == 1

    second_import = asyncio.run(
        DatasetImporter(sandbox).import_manifest(dataset / "manifest.json"))
    assert second_import.skipped == 5
    sandbox.close()
