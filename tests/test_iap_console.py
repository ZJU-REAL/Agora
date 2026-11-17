"""Exercise mounted pages, private model settings and isolated actor populations."""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

import pytest
import requests

from agora.experiments import ExperimentManager
from agora.models import ModelResponse
from agora.provider_registry import ProviderRegistry
from agora.world import open_world
from oasis import PersonaProfile

PUBLIC_ORIGIN = "https://lidingm.iap.platform.shaipower.com"


@pytest.fixture(scope="module")
def mounted_server(tmp_path_factory):
    root = tmp_path_factory.mktemp("iap-http")
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
            "mounted",
            "--bootstrap",
            "--port",
            str(ports[0]),
            "--api-port",
            str(ports[1]),
            "--base-path",
            "/agora",
            "--public-origin",
            PUBLIC_ORIGIN,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    console, native = [f"http://127.0.0.1:{port}" for port in ports]
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                if requests.get(console + "/agora/api/platforms", timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None:
                pytest.fail(process.stderr.read())
            time.sleep(0.1)
        else:
            pytest.fail("Mounted server failed to start")
        yield console + "/agora", native, root
    finally:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_developer_viewer_and_embedded_account_are_mounted(mounted_server):
    console, native, _ = mounted_server
    for route, view in [("/developer", "developer"), ("/viewer", "viewer")]:
        response = requests.get(console + route)
        assert response.ok
        assert f'data-view="{view}"' in response.text
        assert 'href="/agora/static/studio.css"' in response.text
        assert 'src="/agora/static/studio.js"' in response.text
        assert 'window.AGORA_BASE_PATH="/agora"' in response.text
    for asset in ("studio.css", "studio.js", "native.css", "native.js", "embed.css"):
        assert requests.get(console + "/static/" + asset).ok
    account = requests.get(console + "/account?embed=1").text
    assert 'href="/agora/static/embed.css"' in account
    assert "agora:frame" in account
    assert requests.get(native + "/api/providers").status_code == 403
    assert requests.get(native + "/viewer").status_code == 403


def test_https_iap_origin_is_accepted_but_other_origins_are_rejected(mounted_server):
    console, native, _ = mounted_server
    value = {"user_id": 1}
    accepted = requests.post(
        console + "/api/session", json=value, headers={"Origin": PUBLIC_ORIGIN}
    )
    assert accepted.status_code == 201
    rejected = requests.post(
        console + "/api/session",
        json=value,
        headers={"Origin": "https://another.example"},
    )
    assert rejected.status_code == 403
    account = requests.post(
        native + "/v1/accounts",
        json={"platform": "x", "handle": "iap_origin"},
        headers={"Origin": PUBLIC_ORIGIN},
    )
    assert account.status_code == 201
    revoked = requests.delete(
        native + "/v1/token",
        headers={
            "Origin": PUBLIC_ORIGIN,
            "Authorization": "Bearer " + account.json()["token"],
        },
    )
    assert revoked.ok


def test_saved_model_credentials_never_reach_pages_or_exports(mounted_server):
    console, _, root = mounted_server
    secret = "unit-test-model-credential"
    value = {
        "display_name": "Test endpoint",
        "provider": "openai-compatible",
        "model_id": "test-model",
        "base_url": "https://model.example/v1",
        "api_key": secret,
    }
    response = requests.post(
        console + "/api/providers", json=value, headers={"Origin": PUBLIC_ORIGIN}
    )
    assert response.status_code == 201, response.text
    assert secret not in response.text
    options = requests.get(console + "/api/providers").json()["providers"]
    assert options[0]["credential_available"]
    assert "api_key_env" not in options[0]
    assert secret not in json.dumps(options)
    private = root / "mounted" / ".private" / "providers.json"
    assert private.stat().st_mode & 0o777 == 0o600
    assert private.parent.stat().st_mode & 0o777 == 0o700
    # Model settings must be shared by all three managers, even if initially empty.
    for platform in ("xiaohongshu", "x", "reddit"):
        available = requests.get(
            console + "/api/runs", params={"platform": platform}
        ).json()["providers"]
        assert available[0]["model_id"] == "test-model"
        assert secret not in json.dumps(available)


def test_provider_registry_reloads_and_preserves_credentials(tmp_path):
    registry = ProviderRegistry(tmp_path / ".private")
    value = {
        "display_name": "Test",
        "model_id": "test-model",
        "base_url": "https://model.example/v1",
        "api_key": "test-only-key",
    }
    saved = registry.save(value)
    reloaded = ProviderRegistry(tmp_path / ".private")
    assert reloaded.options()[0]["provider_id"] == saved["provider_id"]
    before = registry.providers[saved["provider_id"]].copy()
    value.update(
        provider_id=saved["provider_id"], api_key=None, model_id="updated-model"
    )
    updated = reloaded.save(value)
    assert updated["model_id"] == "updated-model"
    assert updated["credential_available"]
    assert os.environ[before["api_key_env"]] == "test-only-key"
    assert (
        reloaded.providers[saved["provider_id"]]["api_key_env"] != before["api_key_env"]
    )


def test_provider_connection_test_redacts_errors(tmp_path, monkeypatch):
    registry = ProviderRegistry(tmp_path / ".private")
    saved = registry.save(
        {
            "display_name": "Test",
            "model_id": "test-model",
            "base_url": "https://model.example/v1",
            "api_key": "test-only-key",
        }
    )

    class BadClient:
        async def complete(self, messages):
            raise RuntimeError("upstream echoed test-only-key")

    monkeypatch.setattr(
        "agora.provider_registry.build_model_client", lambda spec: BadClient()
    )
    result = registry.test(saved["provider_id"])
    assert not result["success"]
    assert "test-only-key" not in json.dumps(result)


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_agent_count_expands_only_the_experiment(platform, tmp_path):
    world = open_world("source", tmp_path, platform)
    focal = world.add_persona(
        PersonaProfile("tested", "tested", "受测账号", interests={"摄影": 1})
    )
    other = world.add_persona(PersonaProfile("background", "background", "背景账号"))
    if platform == "reddit":
        world.create_community(focal, "r/photography", "Photography")
    manager = ExperimentManager(world)
    try:
        job = manager.start(
            {
                "agent_count": 10,
                "focal_user_id": focal,
                "ticks": 1,
                "steps_per_tick": 4,
                "seed": 42,
            }
        )
        manager.threads[job["run_id"]].join(timeout=12)
        result = manager.inspect(job["run_id"])
        assert result["status"] == "completed", result
        assert result["report"]["failures"] == []
        assert len(result["config"]["user_ids"]) == 10
        assert len(result["session_ids"]) == 10
        assert result["config"]["focal_user_id"] == focal
        assert world.db.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 2
        assert result["config"]["user_ids"][:2] == [focal, other]
    finally:
        manager.shutdown()
        world.close()


def test_focal_model_is_isolated_from_background_and_configuration_updates(
    tmp_path, monkeypatch
):
    world = open_world("roles", tmp_path, "xiaohongshu")
    focal = world.add_persona(PersonaProfile("focal", "focal", "受测模型"))
    world.add_persona(PersonaProfile("other", "other", "背景策略"))
    monkeypatch.setenv("AGORA_TEST_ROLE_KEY", "test-key")
    providers = {
        "model": {
            "provider": "openai-compatible",
            "model_id": "original-model",
            "base_url": "https://model.example/v1",
            "api_key_env": "AGORA_TEST_ROLE_KEY",
        }
    }
    captured = []
    called = []
    entered, proceed = threading.Event(), threading.Event()

    class Model:
        async def complete(self, messages):
            value = json.loads(messages[1]["content"])
            called.append(value["observation"]["user_id"])
            return ModelResponse(
                json.dumps({"action_type": "end_session", "arguments": {}}),
                "original-model",
                1,
                1,
            )

    def build(spec):
        entered.set()
        assert proceed.wait(5)
        captured.append(spec["model_id"])
        return Model()

    monkeypatch.setattr("agora.models.build_model_client", build)
    manager = ExperimentManager(world, providers)
    try:
        job = manager.start(
            {
                "agent_count": 3,
                "focal_user_id": focal,
                "provider_id": "model",
                "ticks": 1,
                "steps_per_tick": 4,
            }
        )
        assert entered.wait(5)
        providers["model"]["model_id"] = "new-model"
        proceed.set()
        manager.threads[job["run_id"]].join(timeout=10)
        result = manager.inspect(job["run_id"])
        assert result["status"] == "completed", result
        assert not result["report"]["failures"], result
        assert captured == ["original-model"]
        assert called == [focal]
        assert len(result["model_calls"]) == 1
        assert result["background_model"] == "persona-development"
        assert len(result["session_ids"]) == 3
    finally:
        proceed.set()
        manager.shutdown()
        world.close()


def test_invalid_population_and_embedded_credentials_are_rejected(tmp_path):
    registry = ProviderRegistry(tmp_path / ".private")
    with pytest.raises(TypeError, match="URL string"):
        registry.save({"model_id": "test", "base_url": None, "api_key": "test-key"})
    with pytest.raises(ValueError, match="HTTPS"):
        registry.save(
            {
                "model_id": "test",
                "base_url": "https://key:secret@model.example/v1",
                "api_key": "test-key",
            }
        )
    world = open_world("invalid", tmp_path, "x")
    user = world.add_persona(PersonaProfile("user", "user", "User"))
    manager = ExperimentManager(world)
    try:
        with pytest.raises(ValueError, match="agent_count"):
            manager.start({"agent_count": 101, "focal_user_id": user})
    finally:
        manager.shutdown()
        world.close()
