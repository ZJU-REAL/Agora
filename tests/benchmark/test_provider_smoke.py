import pytest

from benchmarks.adapters import ModelResponse
from benchmarks.provider_smoke import smoke_test_observer


@pytest.mark.asyncio
async def test_observer_smoke_spends_one_request_and_reports_identity(monkeypatch):
    class Client:
        request_count = 0

        async def complete(self, _messages):
            self.request_count += 1
            return ModelResponse(
                '{"attitude":0.3,"arousal":-0.2,"trust":0.2,'
                '"engagement_intent":0.1,"confidence":0.8,'
                '"evidence":"The reply acknowledges the concern."}',
                "returned-cheap-model", 80, 35, "request-1")

    monkeypatch.setattr(
        "benchmarks.provider_smoke.build_model_client", lambda _config: Client())
    result = await smoke_test_observer({"model_id": "configured-cheap-model"})
    assert result["passed"] is True
    assert result["request_count"] == 1
    assert result["returned_model_id"] == "returned-cheap-model"
    assert result["judgment"]["confidence"] == 0.8


@pytest.mark.asyncio
async def test_observer_smoke_returns_auditable_parse_failure(monkeypatch):
    class Client:
        request_count = 0

        async def complete(self, _messages):
            self.request_count += 1
            return ModelResponse('{"attitude":', "broken-model", 20, 3)

    monkeypatch.setattr(
        "benchmarks.provider_smoke.build_model_client", lambda _config: Client())
    result = await smoke_test_observer({"model_id": "broken-model"})
    assert result["passed"] is False
    assert result["request_count"] == 1
    assert result["call"]["status"] == "parse_failed"
    assert result["call"]["raw_output"] == '{"attitude":'
