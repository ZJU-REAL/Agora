"""Exercise publishing, reading and evaluating real media on every platform."""
import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image

from benchmarks import (ActorRole, ActorSpec, CandidateAction, EpisodeManifest,
                        WorldArtifact)
from benchmarks.observers import ScriptedDevelopmentObserver
from benchmarks.runners.exclusive import ExclusiveRunner
from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile
from oasis.cli import main


def test_view_post_beyond_feed_limit_preserves_visibility(tmp_path):
    sandbox = AgoraOasis.local("large", tmp_path, preset="xiaohongshu")
    try:
        author = sandbox.create_user("author", "Author")
        viewer = sandbox.create_user("viewer", "Viewer")
        oldest = sandbox.create_post(author, body="Old public note")
        private = sandbox.create_post(
            author, body="Private", visibility="private")
        sandbox.platform.db.executemany(
            "INSERT INTO post(user_id, content, created_at) VALUES (?, ?, 0)",
            [(author, f"Newer note {index}") for index in range(201)])
        sandbox.platform.db.commit()
        assert sandbox.view_post(viewer, oldest)["body"] == "Old public note"
        with pytest.raises(KeyError):
            sandbox.view_post(viewer, private)
    finally:
        sandbox.close()


@pytest.mark.parametrize("preset", ["xiaohongshu", "reddit", "x"])
def test_cli_publishes_single_image_and_ordered_gallery(tmp_path, capsys, preset):
    images = []
    for index, color in enumerate(("red", "blue")):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (12, 8), color).save(path)
        images.append(str(path))
    cli = ["--data-root", str(tmp_path / "worlds")]
    assert main(cli + ["world-create", preset, "--preset", preset]) == 0
    capsys.readouterr()
    assert main(cli + ["user-create", preset, "creator",
                       "--display-name", "旅行博主"]) == 0
    user_id = json.loads(capsys.readouterr().out)["user_id"]
    for selected in (images[:1], images[::-1]):
        command = cli + ["post-create", preset, "--author-id", str(user_id),
                         "--title", "旧街散步", "--body", "图文正文",
                         "--topic", "城市漫游", "--location", "上海",
                         "--language", "zh-CN"]
        for path in selected:
            command.extend(["--image", path])
        assert main(command) == 0
        published = json.loads(capsys.readouterr().out)
        assert main(cli + ["post-view", preset, str(published["post_id"]),
                           "--user-id", str(user_id)]) == 0
        post = json.loads(capsys.readouterr().out)
        assert post["post_type"] == (
            "image" if len(selected) == 1 else "gallery")
        assert (post["title"], post["body"], post["location"]) == (
            "旧街散步", "图文正文", "上海")
        assert post["topics"] == ["城市漫游"]
        assert post["language"] == "zh-CN"
        sandbox = AgoraOasis.local(preset, tmp_path / "worlds")
        try:
            for asset, original in zip(post["assets"], selected):
                stored = sandbox.media.path_for(asset["object_key"])
                assert stored.read_bytes() == Path(original).read_bytes()
            assert [asset["position"] for asset in post["assets"]] == list(
                range(len(selected)))
        finally:
            sandbox.close()


@pytest.mark.parametrize("preset", ["xiaohongshu", "reddit", "x"])
def test_full_episode_publishes_gallery_and_npc_can_interact(tmp_path, preset):
    resources = {}
    for index, color in enumerate(("red", "blue")):
        image = tmp_path / f"{index}.png"
        Image.new("RGB", (12, 8), color).save(image)
        resources[image.name] = image
    source = AgoraOasis.local("source", tmp_path / "worlds", preset=preset)
    candidate_id = source.create_user("candidate", "博主")
    npc_id = source.add_persona(PersonaProfile(
        "reader", "reader", "读者", posting_probability=0,
        comment_probability=0, like_probability=1))
    source.create_post(npc_id, body="人类参考内容")
    artifact = WorldArtifact.create(
        source, tmp_path / "artifact", artifact_id="media-world", version="1",
        observer_pool_version="scripted-dev-1", resources=resources,
        metadata={"candidate_asset_keys": list(resources)})
    source.close()

    class Candidate:
        policy_id = "gallery"
        policy_version = "1"

        async def act(self, observation, context):
            if context["step"] == 0:
                return CandidateAction("create_post", {
                    "post_type": "gallery", "title": "图文笔记",
                    "body": "正文与有序图片", "topics": ["旅行"],
                    "assets": [{"asset_key": key}
                               for key in reversed(resources)]})
            gallery = next(post for post in observation.feed
                           if post["post_type"] == "gallery")
            return CandidateAction("create_comment", {
                "post_id": gallery["post_id"], "content": "补充说明"})

    manifest = EpisodeManifest(
        protocol_version="agora-dev-1", world_artifact_version="1",
        world_artifact_id="media-world", candidate_id="candidate",
        platform=preset, scenario_id="gallery-readiness", seed=42,
        run_id="gallery-run", observer_pool_version="scripted-dev-1",
        actors=(ActorSpec("candidate", ActorRole.CANDIDATE,
                          "gallery", "1", candidate_id),
                ActorSpec("reader", ActorRole.NPC, "scripted", "1", npc_id)),
        max_ticks=2)
    result = asyncio.run(ExclusiveRunner(artifact, tmp_path / "outputs").run(
        manifest, Candidate(), ScriptedDevelopmentObserver()))
    assert result.status == "completed"
    assert result.ticks_completed == 2
    episode = AgoraOasis.local("world", result.output_dir)
    try:
        post = next(post for post in episode.get_feed(npc_id)
                    if post["post_type"] == "gallery")
        assert post["body"] == "正文与有序图片"
        assert post["num_likes"] == 1
        assert post["comments"][0]["content"] == "补充说明"
        assert len(post["assets"]) == 2
        assert (result.output_dir / "metrics.json").is_file()
        assert (result.output_dir / "attribution.json").is_file()
    finally:
        episode.close()
    source = AgoraOasis.local("source", tmp_path / "worlds")
    try:
        assert source.platform.db.execute(
            "SELECT COUNT(*) FROM post").fetchone()[0] == 1
        assert source.platform.db.execute(
            "SELECT COUNT(*) FROM media_asset").fetchone()[0] == 0
        artifact.validate()
    finally:
        source.close()
