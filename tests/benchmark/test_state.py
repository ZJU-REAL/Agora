import pytest

from benchmarks.observers import (JsonModelObserver, ObserverPool,
                                  ScriptedDevelopmentObserver)
from benchmarks.protocol import CandidateAction
from benchmarks.adapters import ModelResponse
from benchmarks.state import SocialState, StateDelta


def test_state_update_is_bounded_and_confidence_weighted():
    state = SocialState(attitude=0.9, arousal=0.5)
    updated = state.apply(StateDelta(attitude=0.5, arousal=-0.4), 0.5)
    assert updated.attitude == 1.0
    assert updated.arousal == 0.3


def test_state_rejects_unbounded_delta():
    with pytest.raises(ValueError, match="between -1 and 1"):
        StateDelta(trust=1.1)


@pytest.mark.asyncio
async def test_observer_pool_aggregates_versioned_judgments():
    first = ScriptedDevelopmentObserver()
    second = ScriptedDevelopmentObserver()
    second.observer_id = "scripted-development-variant"
    pool = ObserverPool("dev-1", (first, second))
    judgments = await pool.judge(
        CandidateAction("do_nothing"), {},
        {"target_actor_id": "npc", "is_direct_target": True})
    assert judgments[0].observer_version == "dev-1"
    assert "scripted-development-variant" in judgments[0].evidence


@pytest.mark.asyncio
async def test_json_model_observer_parses_bounded_judgment():
    class Client:
        async def complete(self, messages):
            return ModelResponse(
                '{"attitude":0.2,"arousal":-0.1,"trust":0.1,'
                '"engagement_intent":0.2,"confidence":0.8,'
                '"evidence":"Acknowledges concern"}', "fake", 10, 12)

    observer = JsonModelObserver("observer", "1", Client())
    judgments = await observer.judge(
        CandidateAction("do_nothing"), {},
        {"target_actor_id": "npc", "is_direct_target": True})
    assert judgments[0].delta.attitude == 0.2
    assert observer.drain_call_records()[0]["input_tokens"] == 10


@pytest.mark.asyncio
async def test_json_model_observer_can_record_neutral_parse_fallback():
    class Client:
        async def complete(self, messages):
            return ModelResponse("not-json", "fake", 3, 2)

    observer = JsonModelObserver(
        "observer", "1", Client(), parse_failure_mode="neutral")
    judgment = (await observer.judge(
        CandidateAction("do_nothing"), {},
        {"target_actor_id": "npc"}))[0]
    assert judgment.confidence == 0
    assert observer.drain_call_records()[0]["status"] == "parse_failed"
