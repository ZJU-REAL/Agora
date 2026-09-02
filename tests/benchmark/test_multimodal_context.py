import asyncio
import base64
import subprocess

from PIL import Image

from benchmarks.adapters import JsonModelCandidate, ModelResponse
from benchmarks.observers import JsonModelObserver
from benchmarks.protocol import CandidateAction
from benchmarks.multimodal import (artifact_asset_parts,
                                   sandbox_observation_parts,
                                   video_frame_parts)
from benchmarks.providers import _gemini_parts, _text_content
from benchmarks import WorldArtifact
from oasis import AgoraOasis
from oasis.agora_types import AssetInput, Observation


def test_provider_converts_openai_image_part_to_gemini_inline_data():
    encoded = base64.b64encode(b"image-bytes").decode("ascii")
    content = [{"type": "text", "text": "look"}, {
        "type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{encoded}", "detail": "low"}}]
    assert _gemini_parts(content) == [
        {"text": "look"},
        {"inlineData": {"mimeType": "image/jpeg", "data": encoded}},
    ]
    assert _text_content(content) == "look\n[visual input]"


def test_observation_and_candidate_assets_become_visual_parts(tmp_path):
    image = tmp_path / "large.png"
    Image.new("RGB", (1400, 700), (30, 60, 90)).save(image)
    sandbox = AgoraOasis.local("visual", tmp_path / "worlds",
                               preset="xiaohongshu")
    creator = sandbox.create_user("creator", "Creator")
    viewer = sandbox.create_user("viewer", "Viewer")
    sandbox.create_post(creator, post_type="image", body="Photo",
                        assets=[AssetInput(image)])
    observation = sandbox.observe(viewer)
    parts = sandbox_observation_parts(sandbox, observation)
    assert parts[0]["text"].startswith("Post 1 asset 0")
    assert parts[1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,")

    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="visual", version="1",
        resources={"candidate.png": image},
        metadata={"candidate_asset_keys": ["candidate.png"]})
    candidate_parts = artifact_asset_parts(artifact, ["candidate.png"])
    assert candidate_parts[0]["text"] == "Available asset: candidate.png"
    assert candidate_parts[1]["type"] == "image_url"
    sandbox.close()


def test_candidate_sends_visual_parts_without_serializing_them():
    class Client:
        messages = None

        async def complete(self, messages):
            self.messages = messages
            return ModelResponse(
                '{"action_type":"do_nothing","arguments":{}}', "vision")

    client = Client()
    candidate = JsonModelCandidate("vision", "1", client, 1)
    visual = {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64,aW1hZ2U=", "detail": "low"}}
    asyncio.run(candidate.act(Observation({"user_id": 1}, 0, [], []), {
        "available_actions": [], "scenario_id": "visual", "step": 0,
        "multimodal_parts": [visual]}))
    assert isinstance(client.messages[1]["content"], list)
    assert client.messages[1]["content"][-1] == visual


def test_observer_receives_candidate_media_parts():
    class Client:
        messages = None

        async def complete(self, messages):
            self.messages = messages
            return ModelResponse(
                '{"attitude":0,"arousal":0,"trust":0,'
                '"engagement_intent":0,"confidence":0.5,'
                '"evidence":"Visual and text are consistent."}', "vision")

    client = Client()
    observer = JsonModelObserver("vision", "1", client)
    visual = {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64,aW1hZ2U=", "detail": "low"}}
    asyncio.run(observer.judge(
        CandidateAction("create_post", {"post_type": "image"}),
        {"success": True, "post_id": 1},
        {"target_actor_id": "npc", "multimodal_parts": [visual]}))
    assert client.messages[1]["content"][-1] == visual


def test_video_produces_three_ordered_frames_and_transcript(tmp_path):
    video = tmp_path / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=64x48:d=1", "-pix_fmt", "yuv420p", str(video),
    ], check=True)
    frames = video_frame_parts(video)
    assert [part["text"] for part in frames if part["type"] == "text"] == [
        "Video frame 1/3", "Video frame 2/3", "Video frame 3/3"]
    assert all(part["image_url"]["url"].startswith(
        "data:image/jpeg;base64,") for part in frames
               if part["type"] == "image_url")

    sandbox = AgoraOasis.local("video-context", tmp_path / "worlds",
                               preset="xiaohongshu")
    creator = sandbox.create_user("creator", "Creator")
    viewer = sandbox.create_user("viewer", "Viewer")
    sandbox.create_post(
        creator, post_type="video", body="A short clip",
        assets=[AssetInput(video, transcript="A blue screen is shown.")])
    parts = sandbox_observation_parts(sandbox, sandbox.observe(viewer))
    assert parts[-1] == {"type": "text",
                         "text": "Transcript: A blue screen is shown."}
    sandbox.close()
