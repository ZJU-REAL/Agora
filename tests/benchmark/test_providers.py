import json

import pytest

from benchmarks.providers import (OpenAICompatibleClient, ProviderLimits,
                                  RednoteGeminiGatewayClient,
                                  load_provider_config)
from benchmarks.providers import build_model_client


def test_provider_limits_enforce_small_request_budget():
    limits = ProviderLimits(max_requests=1, max_output_tokens=128)
    client = OpenAICompatibleClient("https://example.test/v1", "cheap", limits=limits)
    client._consume_request()
    with pytest.raises(RuntimeError, match="budget exhausted"):
        client._consume_request()


def test_provider_config_rejects_embedded_secret(tmp_path):
    path = tmp_path / "provider.json"
    path.write_text('{"api_key": "forbidden"}', encoding="utf-8")
    with pytest.raises(ValueError, match="must not contain API keys"):
        load_provider_config(str(path))


def test_rednote_gateway_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        RednoteGeminiGatewayClient(url="http://example.test")


def test_openai_gateway_supports_dual_auth_and_disabled_thinking(
        monkeypatch):
    captured = {}

    class Response:
        headers = {"x-request-id": "request-1"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "request-1", "model": "cheap-model",
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1}}

    def fake_post(self, url, **kwargs):
        captured.update(url=url, trust_env=self.trust_env, **kwargs)
        return Response()

    monkeypatch.setenv("TEST_MAAS_KEY", "test-only-secret")
    monkeypatch.setattr("requests.Session.post", fake_post)
    client = build_model_client({
        "provider": "openai-compatible",
        "base_url": "https://maas.example.test/v1",
        "model_id": "cheap-model", "api_key_env": "TEST_MAAS_KEY",
        "auth_style": "both", "trust_env": False,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "limits": {"max_requests": 1, "max_output_tokens": 64},
    })
    response = client._complete_sync([{"role": "user", "content": "judge"}])
    assert captured["headers"]["api-key"] == "test-only-secret"
    assert captured["headers"]["Authorization"] == "Bearer test-only-secret"
    assert captured["json"]["chat_template_kwargs"]["enable_thinking"] is False
    assert captured["trust_env"] is False
    assert response.model_id == "cheap-model"


def test_provider_config_rejects_nested_secret(tmp_path):
    path = tmp_path / "provider.json"
    path.write_text(json.dumps({
        "provider": "openai-compatible",
        "extra_body": {"token": "forbidden"},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="must not contain API keys"):
        load_provider_config(str(path))


def test_builds_lazy_local_transformers_client():
    client = build_model_client({
        "provider": "local-transformers", "model_path": "/model/not-loaded",
        "model_id": "local-cheap", "limits": {"max_requests": 1},
    })
    assert client.model_id == "local-cheap"
    assert client._model is None
