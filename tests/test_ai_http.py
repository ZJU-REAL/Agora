"""Exercise the published AI client against the real two-port platform server."""

import asyncio
import json
import signal
import socket
import subprocess
import sys
import time

import pytest
import requests

from agora.client import AgoraClient
from agora.models import ModelResponse


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    root = tmp_path_factory.mktemp("ai-http")
    ports = []
    for _ in range(2):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agora",
            "--data-root",
            str(root),
            "serve",
            "web",
            "--bootstrap",
            "--port",
            str(ports[0]),
            "--api-port",
            str(ports[1]),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    console, native = [f"http://127.0.0.1:{port}" for port in ports]
    deadline = time.monotonic() + 12
    try:
        while time.monotonic() < deadline:
            try:
                if requests.get(native + "/v1/platforms", timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None:
                pytest.fail(process.stderr.read())
            time.sleep(0.1)
        else:
            pytest.fail("AI server did not start")
        yield console, native
    finally:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_native_listener_excludes_research_information(server):
    console, native = server
    assert requests.get(native + "/api/world").status_code == 403
    assert requests.get(native + "/account").status_code == 403
    data = requests.get(native + "/v1/platforms").json()
    assert {platform["platform"] for platform in data["platforms"]} == {
        "xiaohongshu",
        "x",
        "reddit",
    }
    assert requests.get(console + "/static/native.js").ok


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_ai_client_can_publish_and_read_its_native_platform(server, platform):
    _, native = server
    client = AgoraClient(native)
    client.register(platform, "http_" + platform[:7])
    observation = client.start()
    assert observation["platform"] == platform
    args = {"body": "A real client publishing to a virtual platform"}
    if platform != "x":
        args["title"] = "HTTP publication"
    if platform == "reddit":
        args["community"] = "r/photography"
    receipt = client.act("create_post", args, request_id="first")
    assert receipt["status"] == "succeeded", receipt
    again = client.act("create_post", args, request_id="first")
    assert again == receipt
    opened = client.act("open_post", {"post_id": receipt["result"]["post_id"]})
    assert opened["observation"]["post"]["body"] == args["body"]
    assert client.trajectory()
    tools = client.tools()
    assert any(tool["function"]["name"] == "delete_post" for tool in tools)


def test_model_adapter_can_operate_an_ai_account(server):
    client = AgoraClient(server[1])
    client.register("x", "model_bridge")

    class Model:
        def __init__(self):
            self.calls = 0

        async def complete(self, messages):
            value = json.loads(messages[1]["content"])
            assert "memory" in value
            assert "feed_score" not in messages[1]["content"]
            self.calls += 1
            action = (
                {
                    "action_type": "create_post",
                    "arguments": {"body": "Model bridge #agora"},
                }
                if self.calls == 1
                else {"action_type": "end_session", "arguments": {}}
            )
            return ModelResponse(json.dumps(action), "mock-model", 10, 5)

    result = asyncio.run(client.run(Model(), "Publish one post", max_actions=2))
    assert len(result["history"]) == 2
    assert result["history"][0]["result"]["post_id"]
    assert len(result["model_calls"]) == 2
