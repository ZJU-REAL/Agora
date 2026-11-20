"""Full managed-agent and SDK journeys through a local, controlled HTTPS model.

The model server is a deterministic transport fixture, not an actual LLM. TLS
verification remains enabled. Worlds, model credentials and publications stay
under pytest's temporary directory; no production account or API is touched.
"""

import asyncio
import base64
import json
import os
import shutil
import signal
import socket
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
import test_native_ui

from agora.client import AgoraClient
from agora.models import build_model_client

MODEL = "agora-controlled-http-fixture"
KEY = "local-transport-fixture-not-a-real-key"


@pytest.fixture
def browser():
    yield from test_native_ui.browser.__wrapped__()


@pytest.fixture(scope="module")
def chain(tmp_path_factory):
    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("OpenSSL is required for the verified local HTTPS fixture")
    root = tmp_path_factory.mktemp("model-http-chain")
    cert, key = root / "cert.pem", root / "key.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    requests_seen = []

    class ModelHandler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            assert self.path == "/v1/chat/completions"
            assert self.headers["Authorization"] == "Bearer " + KEY
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert value["response_format"] == {"type": "json_object"}
            content = value["messages"][1]["content"]
            model = value["model"]
            if model == "invalid-json-fixture":
                response_text = "Unstructured response " + KEY
            elif isinstance(content, str) and content == "Check the model connection.":
                response_text = json.dumps({"ok": True})
            else:
                text = content if isinstance(content, str) else content[0]["text"]
                assert "feed_score" not in text and "diagnostics_json" not in text
                payload = json.loads(text)
                observation = payload["observation"]
                platform = observation["platform"]
                images = (
                    []
                    if isinstance(content, str)
                    else [p for p in content if p["type"] == "image_url"]
                )
                assert images, (
                    "Visual observations must reach the configured vision model"
                )
                assert all(
                    base64.b64decode(p["image_url"]["url"].split(",", 1)[1]).startswith(
                        b"\xff\xd8"
                    )
                    for p in images
                )
                history = payload["history"]
                if any(
                    item["action"]["action_type"] == "publish_draft" for item in history
                ):
                    action = {"action_type": "end_session", "arguments": {}}
                elif observation["screen"] == "studio" and observation["draft"]:
                    action = {"action_type": "publish_draft", "arguments": {}}
                elif observation["screen"] == "studio":
                    args = {
                        "body": "Controlled HTTP fixture publication; not LLM-generated.",
                        "assets": [
                            {"asset_id": observation["asset_library"][0]["asset_id"]}
                        ],
                    }
                    if platform != "x":
                        args["title"] = "接口联调"
                    if platform == "reddit":
                        args["community"] = "r/photography"
                    action = {"action_type": "save_draft", "arguments": args}
                else:
                    action = {"action_type": "open_studio", "arguments": {}}
                assert action["action_type"] in observation["available_actions"]
                assert (
                    set(
                        observation["available_actions"][action["action_type"]].get(
                            "required", []
                        )
                    )
                    <= action["arguments"].keys()
                )
                action["rationale"] = "受控接口联调：验证实际画面、素材、动作和回执。"
                response_text = json.dumps(action, ensure_ascii=False)
                requests_seen.append(
                    {
                        "platform": platform,
                        "action": action["action_type"],
                        "images": len(images),
                    }
                )
            body = json.dumps(
                {
                    "id": "controlled-http-request",
                    "model": model,
                    "choices": [{"message": {"content": response_text}}],
                    "usage": {"prompt_tokens": 17, "completion_tokens": 9},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    model_server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    model_server.socket = tls.wrap_socket(model_server.socket, server_side=True)
    model_thread = threading.Thread(target=model_server.serve_forever, daemon=True)
    model_thread.start()
    model_url = f"https://127.0.0.1:{model_server.server_port}/v1"
    patch = pytest.MonkeyPatch()
    patch.setenv("REQUESTS_CA_BUNDLE", str(cert))
    patch.setenv("AGORA_CHAIN_FIXTURE_KEY", KEY)
    for name in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]:
        patch.delenv(name, raising=False)
    ports = []
    for _ in range(2):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    worlds = root / "worlds"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agora",
            "--data-root",
            str(worlds),
            "serve",
            "chain",
            "--bootstrap",
            "--port",
            str(ports[0]),
            "--api-port",
            str(ports[1]),
            "--base-path",
            "/agora",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )
    console, native = (
        f"http://127.0.0.1:{ports[0]}/agora",
        f"http://127.0.0.1:{ports[1]}",
    )
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                if requests.get(console + "/api/platforms", timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None:
                pytest.fail(process.stderr.read())
            time.sleep(0.1)
        else:
            pytest.fail("Isolated console did not become ready")
        saved = requests.post(
            console + "/api/providers",
            json={
                "provider_id": "controlled",
                "display_name": "受控接口联调（非真实 LLM）",
                "provider": "openai-compatible",
                "model_id": MODEL,
                "base_url": model_url,
                "api_key": KEY,
                "supports_vision": True,
                "trust_env": True,
                "limits": {
                    "max_requests": 8,
                    "max_output_tokens": 512,
                    "timeout_seconds": 5,
                },
            },
        )
        assert saved.status_code == 201, saved.text
        assert KEY not in saved.text
        probe = requests.post(
            console + "/api/providers/test",
            json={"provider_id": "controlled"},
            timeout=12,
        )
        assert probe.ok and probe.json()["success"], probe.text
        yield {
            "console": console,
            "native": native,
            "model_url": model_url,
            "root": root,
            "worlds": worlds,
            "requests": requests_seen,
            "pid": process.pid,
        }
    finally:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        model_server.shutdown()
        model_server.server_close()
        model_thread.join(3)
        patch.undo()


def source_counts(chain, platform):
    slug = "chain" + ("" if platform == "xiaohongshu" else "-" + platform)
    with sqlite3.connect(chain["worlds"] / slug / "sandbox.db") as db:
        return tuple(
            db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in ["user", "post", "creator_asset"]
        )


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_model_http_to_native_viewer_and_export(browser, chain, platform):
    root = chain["console"]
    before = source_counts(chain, platform)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(root + "/developer?platform=" + platform)
        page.wait_for_function(
            "world?.users?.length > 0 && !developerLoading", polling=100
        )
        page.locator("#focalUser").select_option("1")
        page.locator("#focalModel").select_option("controlled")
        page.locator("#backgroundModel").select_option("controlled")
        page.locator("#agentCount").fill("2")
        page.locator("#ticks").fill("1")
        page.locator("#steps").fill("4")
        page.locator(".advanced-settings summary").evaluate("el => el.click()")
        page.locator("#pace").select_option("0")
        page.locator("#launchButton").evaluate("el => el.click()")
        page.wait_for_url("**/viewer?**")
        page.wait_for_function(
            "run?.status === 'completed' && actorData?.trajectory?.length > 0",
            polling=100,
        )
        run_id = page.evaluate("run.run_id")
        result = requests.get(root + "/api/runs/" + run_id).json()
        assert result["model"] == MODEL and result["background_model"] == MODEL
        assert result["metrics"]["model_calls"] == 8
        assert result["metrics"]["created_posts"] == 2
        assert result["failure_count"] == 0 and result["report"]["failures"] == []
        assert len(result["model_calls"]) == 8
        assert all(call["status"] == "completed" for call in result["model_calls"])
        assert source_counts(chain, platform) == before
        page.evaluate("chooseFrame(3)")
        page.wait_for_function(
            "currentEvent()?.action.action_type === 'publish_draft'", polling=100
        )
        child = next(frame for frame in page.frames if "/account?" in frame.url)
        step = page.evaluate("currentEvent().step")
        child.wait_for_function(
            "step => typeof current === 'function' && current()?.screen && data?.trajectory?.[frame]?.step === step",
            arg=step,
            polling=100,
        )
        assert child.evaluate("!editable()")
        assert "受控接口联调" in page.locator("#decisionDetail").inner_text()
        response = requests.get(root + "/api/runs/" + run_id + "/export")
        assert response.ok and KEY not in response.text
        export = response.json()
        assert len(export["model_calls"]) == 8
        assert all(call["model_id"] == MODEL for call in export["model_calls"])
        assert len(export["trajectories"]) == 2
        assert any(
            step["action"]["action_type"] == "publish_draft"
            and step["observation"]["platform"] == platform
            for actor in export["trajectories"]
            for step in actor["trajectory"]
        )
        options = requests.get(root + "/api/providers").text
        assert KEY not in options
        assert any(r["platform"] == platform and r["images"] for r in chain["requests"])
    finally:
        page.close()


def test_external_sdk_can_use_the_same_https_model(chain, tmp_path):
    from PIL import Image

    client = AgoraClient(chain["native"])
    client.register("x", "sdk_fixture")
    image = tmp_path / "sdk-fixture.png"
    Image.new("RGB", (20, 16), "#5264b6").save(image)
    client.upload(image, alt_text="Synthetic SDK upload")
    model = build_model_client(
        {
            "provider": "openai-compatible",
            "model_id": MODEL,
            "base_url": chain["model_url"],
            "api_key_env": "AGORA_CHAIN_FIXTURE_KEY",
            "trust_env": True,
            "limits": {
                "timeout_seconds": 5,
                "max_requests": 4,
                "max_output_tokens": 512,
            },
        }
    )
    result = asyncio.run(
        client.run(
            model, "Controlled transport check", max_actions=4, supports_vision=True
        )
    )
    assert len(result["model_calls"]) == 4
    assert all(call["status"] == "completed" for call in result["model_calls"])
    assert all(item["result"]["success"] for item in result["history"])
    assert [item["action"]["action_type"] for item in result["history"]] == [
        "open_studio",
        "save_draft",
        "publish_draft",
        "end_session",
    ]
    assert len(client.trajectory()) == 5
    # SDK sessions are source-world operations, not managed Viewer experiments.
    runs = requests.get(chain["console"] + "/api/runs?platform=x").json()["runs"]
    assert len(runs) == 1
    assert "session_id" in result and "run_id" not in result
    assert requests.get(chain["native"] + "/api/providers").status_code == 403
    assert KEY not in json.dumps(client.trajectory())


def test_http_probe_rejects_a_connected_non_json_model(chain):
    response = requests.post(
        chain["console"] + "/api/providers",
        json={
            "provider_id": "invalid-json",
            "model_id": "invalid-json-fixture",
            "base_url": chain["model_url"],
            "api_key": KEY,
            "trust_env": True,
        },
    )
    assert response.status_code == 201
    tested = requests.post(
        chain["console"] + "/api/providers/test",
        json={"provider_id": "invalid-json"},
        timeout=12,
    )
    assert tested.ok and tested.json()["success"] is False
    assert tested.json()["error_type"] == "ModelContractError"
    assert KEY not in tested.text
