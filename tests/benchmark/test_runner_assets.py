import asyncio

import pytest
from PIL import Image

from benchmarks import CandidateAction, WorldArtifact
from benchmarks.runners.exclusive import ExclusiveRunner
from oasis import AgoraOasis
from oasis.social_platform.media_store import LocalMediaStore


def test_runner_only_accepts_frozen_candidate_assets(tmp_path):
    image = tmp_path / "photo.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(image)
    source = AgoraOasis.local("source", tmp_path / "worlds",
                              preset="xiaohongshu")
    user_id = source.create_user("candidate", "Candidate")
    artifact = WorldArtifact.create(
        source, tmp_path / "artifact", artifact_id="media", version="1",
        resources={"photo.png": image},
        metadata={"candidate_asset_keys": ["photo.png"]})
    source.close()
    artifact.clone_episode(tmp_path / "episode", "episode")
    episode = AgoraOasis.local("world", tmp_path / "episode")
    runner = ExclusiveRunner(artifact, tmp_path / "outputs")
    outcome = asyncio.run(runner._apply_action(
        episode, user_id, CandidateAction("create_post", {
            "post_type": "image", "body": "A frozen photo",
            "assets": [{"asset_key": "photo.png"}]})))
    assert outcome["success"]
    with pytest.raises(ValueError, match="must use artifact asset_key"):
        asyncio.run(runner._apply_action(
            episode, user_id, CandidateAction("create_post", {
                "post_type": "image", "assets": [{"path": str(image)}]})))
    episode.close()


def test_artifact_rejects_unfrozen_candidate_asset_key(tmp_path):
    source = AgoraOasis.local("missing-source", tmp_path / "worlds",
                              preset="xiaohongshu")
    with pytest.raises(ValueError, match="missing from resources"):
        WorldArtifact.create(
            source, tmp_path / "missing-artifact", artifact_id="missing",
            version="1", metadata={"candidate_asset_keys": ["absent.png"]})
    source.close()


def test_runner_creates_ordered_gallery_from_frozen_assets(tmp_path):
    resources = {}
    for index, color in enumerate(((200, 20, 30), (30, 180, 60),
                                   (40, 70, 210)), start=1):
        path = tmp_path / f"photo-{index}.png"
        Image.new("RGB", (8, 8), color).save(path)
        resources[path.name] = path
    source = AgoraOasis.local("gallery-source", tmp_path / "worlds",
                              preset="xiaohongshu")
    user_id = source.create_user("candidate", "Candidate")
    artifact = WorldArtifact.create(
        source, tmp_path / "gallery-artifact", artifact_id="gallery",
        version="1", resources=resources,
        metadata={"candidate_asset_keys": list(resources)})
    source.close()
    artifact.clone_episode(tmp_path / "gallery-episode", "episode")
    episode = AgoraOasis.local("world", tmp_path / "gallery-episode")
    runner = ExclusiveRunner(artifact, tmp_path / "outputs")

    outcome = asyncio.run(runner._apply_action(
        episode, user_id, CandidateAction("create_post", {
            "post_type": "gallery", "title": "Three views",
            "assets": [
                {"asset_key": "photo-2.png", "caption": "second"},
                {"asset_key": "photo-1.png", "caption": "first"},
                {"asset_key": "photo-3.png", "caption": "third"},
            ]})))

    assets = episode.get_post_assets(outcome["post_id"])
    assert [item["caption"] for item in assets] == ["second", "first", "third"]
    assert [item["position"] for item in assets] == [0, 1, 2]
    assert {item["role"] for item in assets} == {"content"}
    episode.close()


def test_runner_creates_video_with_explicit_cover(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"frozen test video")
    cover = tmp_path / "cover.png"
    Image.new("RGB", (16, 9), (12, 34, 56)).save(cover)
    monkeypatch.setattr(LocalMediaStore, "_inspect_video", staticmethod(
        lambda _path: {"format": "mp4", "mime_type": "video/mp4",
                       "width": 16, "height": 9, "duration_ms": 1000,
                       "video_codec": "test"}))
    source = AgoraOasis.local("video-source", tmp_path / "worlds",
                              preset="xiaohongshu")
    user_id = source.create_user("candidate", "Candidate")
    artifact = WorldArtifact.create(
        source, tmp_path / "video-artifact", artifact_id="video", version="1",
        resources={"clip.mp4": video, "cover.png": cover},
        metadata={"candidate_asset_keys": ["clip.mp4", "cover.png"]})
    source.close()
    artifact.clone_episode(tmp_path / "video-episode", "episode")
    episode = AgoraOasis.local("world", tmp_path / "video-episode")
    runner = ExclusiveRunner(artifact, tmp_path / "outputs")

    outcome = asyncio.run(runner._apply_action(
        episode, user_id, CandidateAction("create_post", {
            "post_type": "video", "title": "A short clip",
            "assets": [{"asset_key": "clip.mp4"},
                       {"asset_key": "cover.png", "role": "cover"}]})))

    assets = episode.get_post_assets(outcome["post_id"])
    assert [(item["media_type"], item["role"]) for item in assets] == [
        ("video", "content"), ("image", "cover")]
    episode.close()


def test_video_cover_role_is_not_inferred_from_position(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"frozen test video")
    cover = tmp_path / "cover.png"
    Image.new("RGB", (16, 9), (12, 34, 56)).save(cover)
    monkeypatch.setattr(LocalMediaStore, "_inspect_video", staticmethod(
        lambda _path: {"mime_type": "video/mp4", "duration_ms": 1000}))
    source = AgoraOasis.local("role-source", tmp_path / "worlds",
                              preset="xiaohongshu")
    user_id = source.create_user("candidate", "Candidate")
    artifact = WorldArtifact.create(
        source, tmp_path / "role-artifact", artifact_id="roles", version="1",
        resources={"clip.mp4": video, "cover.png": cover},
        metadata={"candidate_asset_keys": ["clip.mp4", "cover.png"]})
    source.close()
    artifact.clone_episode(tmp_path / "role-episode", "episode")
    episode = AgoraOasis.local("world", tmp_path / "role-episode")
    runner = ExclusiveRunner(artifact, tmp_path / "outputs")

    with pytest.raises(ValueError, match="cover role"):
        asyncio.run(runner._apply_action(
            episode, user_id, CandidateAction("create_post", {
                "post_type": "video",
                "assets": [{"asset_key": "clip.mp4"},
                           {"asset_key": "cover.png"}]})))
    episode.close()
