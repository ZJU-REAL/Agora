import asyncio
import json

from PIL import Image

from benchmarks.cli import main as benchmark_main
from oasis import AgoraOasis, DatasetImporter


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                            for row in rows), encoding="utf-8")


def test_imports_platform_fields_relations_interactions_and_media_metadata(
        tmp_path):
    dataset = tmp_path / "dataset"
    media = dataset / "media"
    media.mkdir(parents=True)
    Image.new("RGB", (12, 8), (20, 40, 60)).save(media / "photo.png")
    _write_jsonl(dataset / "users.jsonl", [
        {"external_id": "author", "handle": "author"},
        {"external_id": "viewer", "handle": "viewer"},
    ])
    _write_jsonl(dataset / "relations.jsonl", [{
        "external_id": "follow-1", "type": "follow",
        "actor_external_id": "viewer", "target_external_id": "author"}])
    _write_jsonl(dataset / "posts.jsonl", [{
        "external_id": "post-1", "author_external_id": "author",
        "post_type": "image", "body": "A photo", "location": "上海",
        "assets": [{"path": "photo.png", "alt_text": "蓝灰色图片"}]}])
    _write_jsonl(dataset / "interactions.jsonl", [
        {"external_id": "like-1", "type": "like",
         "actor_external_id": "viewer", "post_external_id": "post-1"},
        {"external_id": "collect-1", "type": "collect",
         "actor_external_id": "viewer", "post_external_id": "post-1"},
    ])
    manifest = {"dataset": {"name": "import"}, "files": {
        "users": "users.jsonl", "relations": "relations.jsonl",
        "posts": "posts.jsonl", "interactions": "interactions.jsonl",
        "media_root": "media"}, "import": {"id_namespace": "import-v1"}}
    (dataset / "manifest.json").write_text(json.dumps(manifest),
                                             encoding="utf-8")
    sandbox = AgoraOasis.local("import", tmp_path / "worlds",
                               preset="xiaohongshu")
    report = asyncio.run(DatasetImporter(sandbox).import_manifest(
        dataset / "manifest.json"))
    viewer = sandbox.platform.db.execute(
        "SELECT user_id FROM user WHERE user_name = 'viewer'").fetchone()[0]
    post = sandbox.get_feed(viewer)[0]
    assert (report.relations, report.interactions) == (1, 2)
    assert post["location"] == "上海"
    assert (post["num_likes"], post["num_collections"]) == (1, 1)
    assert post["assets"][0]["alt_text"] == "蓝灰色图片"
    sandbox.close()


def test_imported_world_can_run_complete_isolated_episode(tmp_path, capsys):
    worlds = tmp_path / "worlds"
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _write_jsonl(dataset / "users.jsonl", [
        {"external_id": "candidate", "handle": "candidate"},
        {"external_id": "npc", "handle": "npc"},
    ])
    _write_jsonl(dataset / "posts.jsonl", [{
        "external_id": "challenge", "author_external_id": "npc",
        "body": "这个说法有来源吗？",
    }])
    (dataset / "manifest.json").write_text(json.dumps({
        "dataset": {"name": "ready"},
        "files": {"users": "users.jsonl", "posts": "posts.jsonl"},
        "import": {"id_namespace": "ready-v1"},
    }), encoding="utf-8")
    sandbox = AgoraOasis.local("ready", worlds, preset="xiaohongshu")
    report = asyncio.run(DatasetImporter(sandbox).import_manifest(
        dataset / "manifest.json"))
    assert (report.users, report.posts) == (2, 1)
    candidate_id = sandbox.platform.db.execute(
        "SELECT user_id FROM user WHERE user_name = 'candidate'").fetchone()[0]
    sandbox.close()
    artifact = tmp_path / "artifact"
    config = tmp_path / "run.json"
    output_root = tmp_path / "outputs"

    assert benchmark_main([
        "artifact-create", "ready", str(artifact), "--data-root", str(worlds),
        "--artifact-id", "ready-v1", "--version", "1",
        "--candidate-user-id", str(candidate_id),
        "--scenario-id", "ready-check-1"]) == 0
    assert benchmark_main([
        "episode-init", str(artifact), str(config), "--run-id", "dry-run-1",
        "--output-root", str(output_root)]) == 0
    assert benchmark_main(["run", str(config)]) == 0
    output = capsys.readouterr().out
    assert '"status": "completed"' in output

    run_dir = output_root / "dry-run-1"
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    trajectory = [json.loads(line) for line in (
        run_dir / "trajectory.jsonl").read_text(
            encoding="utf-8").splitlines()]
    assert result["status"] == "completed"
    assert trajectory
    assert all(record.get("step") is not None for record in trajectory)
    assert (run_dir / "metrics.json").is_file()
    assert (run_dir / "attribution.json").is_file()

    source = AgoraOasis.local("ready", worlds)
    episode = AgoraOasis.local("world", run_dir)
    assert source.platform.db.execute(
        "SELECT COUNT(*) FROM comment").fetchone()[0] == 0
    assert episode.platform.db.execute(
        "SELECT COUNT(*) FROM comment").fetchone()[0] > 0
    source.close()
    episode.close()


def test_artifact_can_freeze_human_content_by_task_topic(tmp_path, capsys):
    worlds = tmp_path / "worlds"
    sandbox = AgoraOasis.local("topics", worlds, preset="xiaohongshu")
    candidate_id = sandbox.create_user("candidate", "Candidate")
    human_id = sandbox.create_user("human", "Human")
    selected = sandbox.create_post(human_id, body="Travel reference",
                                   topics=["旅行"])
    sandbox.create_post(human_id, body="Beauty reference", topics=["美妆"])
    sandbox.close()
    artifact_dir = tmp_path / "artifact"

    assert benchmark_main([
        "artifact-create", "topics", str(artifact_dir),
        "--data-root", str(worlds), "--artifact-id", "topics-v1",
        "--version", "1", "--candidate-user-id", str(candidate_id),
        "--content-topic", "旅行"]) == 0
    manifest = json.loads((artifact_dir / "manifest.json").read_text(
        encoding="utf-8"))
    assert manifest["metadata"]["content_topics"] == ["旅行"]
    assert manifest["metadata"]["controlled_post_ids"] == [selected]
    assert manifest["metadata"]["actor_user_ids"] == {
        "candidate": candidate_id}
    capsys.readouterr()
