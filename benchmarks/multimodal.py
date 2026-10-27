from __future__ import annotations

import base64
import io
import mimetypes
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image


def _image_data_url(path: Path) -> str:
    with Image.open(path) as image:
        image.thumbnail((1024, 1024))
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        stream = io.BytesIO()
        image.save(stream, format="JPEG", quality=82, optimize=True)
    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def image_part(path: Path, *, detail: str = "low") -> dict[str, Any]:
    return {"type": "image_url", "image_url": {
        "url": _image_data_url(path), "detail": detail}}


def video_frame_parts(path: Path, *, frame_count: int = 3) -> list[dict[str, Any]]:
    """Extract deterministic representative JPEG frames without persistent files."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True)
    duration = max(0.0, float(probe.stdout.strip() or 0))
    times = ([0.0] if frame_count == 1 or duration <= 0 else
             [duration * 0.95 * index / (frame_count - 1)
              for index in range(frame_count)])
    parts: list[dict[str, Any]] = []
    for index, timestamp in enumerate(times):
        frame = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{timestamp:.3f}", "-i",
             str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec",
             "mjpeg", "-vf", "scale='min(768,iw)':-2", "pipe:1"],
            check=True, capture_output=True).stdout
        parts.append({"type": "text",
                      "text": f"Video frame {index + 1}/{len(times)}"})
        parts.append({"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64,"
                   + base64.b64encode(frame).decode("ascii"),
            "detail": "low"}})
    return parts


def sandbox_observation_parts(sandbox, observation) -> list[dict[str, Any]]:
    """Create model-only visual context; data URIs never enter trajectories."""
    parts: list[dict[str, Any]] = []
    visual_count = 0
    for post in observation.feed:
        for asset in post.get("assets", []):
            if visual_count >= 12:
                return parts
            path = sandbox.media.path_for(asset["object_key"])
            parts.append({"type": "text", "text": (
                f"Post {post['post_id']} asset {asset['position']} "
                f"role={asset['role']} type={asset['media_type']}")})
            if asset["media_type"] == "image":
                parts.append(image_part(path))
                visual_count += 1
            elif asset["media_type"] == "video":
                parts.extend(video_frame_parts(path))
                visual_count += 3
            if asset.get("transcript"):
                parts.append({"type": "text",
                              "text": f"Transcript: {asset['transcript']}"})
    return parts


def post_media_parts(sandbox, post_id: int) -> list[dict[str, Any]]:
    post = {"post_id": post_id, "assets": sandbox.get_post_assets(post_id)}
    observation = type("MediaObservation", (), {"feed": [post]})()
    return sandbox_observation_parts(sandbox, observation)


def artifact_asset_parts(artifact, asset_keys: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    metadata = artifact.manifest.metadata.get("candidate_asset_metadata", {})
    visual_count = 0
    for key in asset_keys:
        if visual_count >= 12:
            break
        path = artifact.root / "resources" / key
        mime = mimetypes.guess_type(path.name)[0] or ""
        parts.append({"type": "text", "text": f"Available asset: {key}"})
        if mime.startswith("image/"):
            parts.append(image_part(path))
            visual_count += 1
        elif mime.startswith("video/"):
            parts.extend(video_frame_parts(path))
            visual_count += 3
        if metadata.get(key, {}).get("transcript"):
            parts.append({"type": "text", "text": (
                f"Transcript for {key}: {metadata[key]['transcript']}")})
    return parts
