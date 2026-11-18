"""Provider-neutral client for AI accounts. Only public account operations exist."""

from __future__ import annotations

import asyncio
import base64
import io
import tempfile
import uuid
from pathlib import Path

import requests
from PIL import Image


class AgoraClient:
    def __init__(self, base_url="http://127.0.0.1:8766", token=None, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session_id = None

    def request(self, method, path, value=None):
        response = requests.request(
            method,
            self.base_url + path,
            json=value,
            headers={"Authorization": "Bearer " + self.token} if self.token else {},
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(response.json().get("error", "AI API request failed"))
        return response.json()

    def register(self, platform, handle, **profile):
        value = self.request(
            "POST", "/v1/accounts", {"platform": platform, "handle": handle, **profile}
        )
        self.token = value["token"]
        return {key: item for key, item in value.items() if key != "token"}

    def start(self):
        value = self.request("POST", "/v1/sessions", {})
        self.session_id = value["session_id"]
        return value["observation"]

    def observe(self, step=None):
        return self.request(
            "GET",
            f"/v1/sessions/{self.session_id}"
            + (f"?step={step}" if step is not None else ""),
        )

    def act(self, action_type, arguments=None, rationale=None, request_id=None):
        value = {
            "action_type": action_type,
            "arguments": arguments or {},
            "request_id": request_id or uuid.uuid4().hex,
        }
        if rationale:
            value["rationale"] = rationale
        return self.request("POST", f"/v1/sessions/{self.session_id}/actions", value)

    def upload(self, path, **metadata):
        path = Path(path)
        return self.request(
            "POST",
            "/v1/assets",
            {
                "filename": path.name,
                "data_base64": base64.b64encode(path.read_bytes()).decode(),
                **metadata,
            },
        )

    def tools(self):
        return self.request("GET", f"/v1/sessions/{self.session_id}/tools")["tools"]

    def memory(self, query=""):
        from urllib.parse import quote

        return self.request("GET", "/v1/memory?query=" + quote(query))["memory"]

    def trajectory(self):
        return self.request("GET", f"/v1/sessions/{self.session_id}/trajectory")[
            "trajectory"
        ]

    def vision_parts(self, observation):
        posts = (
            [observation["post"]]
            if observation["screen"] == "detail"
            else observation.get("cards", [])
        )
        posts += [
            post["original_post"]
            for post in posts
            if post
            and post.get("original_post")
            and not post["original_post"].get("unavailable")
        ]
        assets = (
            observation.get("asset_library", [])
            if observation["screen"] == "studio"
            else [
                asset
                for post in posts
                if post
                for asset in post.get("assets", [])
                if asset["asset_id"]
                in post.get(
                    "visible_asset_ids",
                    [item["asset_id"] for item in post.get("assets", [])],
                )
            ]
        )
        parts = []
        count = 0
        for asset in assets:
            if count >= 12:
                break
            response = requests.get(
                self.base_url + "/v1/assets/" + asset["asset_id"],
                stream=True,
                headers={"Authorization": "Bearer " + self.token},
                timeout=self.timeout,
            )
            response.raise_for_status()
            parts.append({"type": "text", "text": "Visible asset " + asset["asset_id"]})
            if asset["media_type"] == "image":
                with Image.open(io.BytesIO(response.content)) as image:
                    image.thumbnail((1024, 1024))
                    output = io.BytesIO()
                    image.convert("RGB").save(output, format="JPEG", quality=82)
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,"
                            + base64.b64encode(output.getvalue()).decode(),
                            "detail": "low",
                        },
                    }
                )
                count += 1
            elif asset["media_type"] == "video":
                from agora.media_context import video_frame_parts

                with tempfile.TemporaryDirectory(prefix="agora-client-video-") as root:
                    path = Path(root) / "visible.mp4"
                    with path.open("wb") as stream:
                        for chunk in response.iter_content(65536):
                            stream.write(chunk)
                    parts.extend(
                        video_frame_parts(
                            path, position_ms=observation.get("video_position_ms", 0)
                        )
                    )
                count += 1
            response.close()
        return parts

    async def run(self, model_client, goal, max_actions=20, supports_vision=False):
        from agora.runner import JsonSessionPolicy

        if type(max_actions) is not int or not 1 <= max_actions <= 1000:
            raise ValueError("max_actions must be from 1 to 1000")
        observation = await asyncio.to_thread(self.start)
        policy = JsonSessionPolicy(
            model_client,
            goal,
            visual_builder=self.vision_parts if supports_vision else None,
        )
        history, records = [], []
        for _ in range(max_actions):
            action = await policy.act(
                observation,
                {
                    "history": history[-8:],
                    "memory": await asyncio.to_thread(self.memory),
                    "remaining_total_actions": max_actions - len(history),
                },
            )
            receipt = await asyncio.to_thread(
                self.act,
                action["action_type"],
                action.get("arguments", {}),
                action.get("rationale"),
            )
            records.extend(policy.drain_call_records())
            history.append({"action": action, "result": receipt["result"]})
            observation = receipt["observation"]
            if observation["status"] != "active":
                break
        return {
            "session_id": self.session_id,
            "history": history,
            "model_calls": records,
        }
