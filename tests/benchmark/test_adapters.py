import json

import pytest

from benchmarks.adapters import JsonModelCandidate, ModelResponse
from oasis.agora_types import Observation


class FakeClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        text = ("not-json" if self.calls == 1 else json.dumps({
            "action_type": "do_nothing", "arguments": {},
            "rationale": "No relevant post"}))
        return ModelResponse(text, "fake-model", 10, 5, f"req-{self.calls}")


@pytest.mark.asyncio
async def test_json_model_candidate_retries_and_records_usage():
    candidate = JsonModelCandidate("fake", "1", FakeClient(), 2)
    action = await candidate.act(
        Observation({"user_id": 1}, 0, [], []), {
            "available_actions": (), "scenario_id": "test", "step": 0})
    assert action.action_type == "do_nothing"
    records = candidate.drain_call_records()
    assert [item["status"] for item in records] == ["failed", "completed"]
    assert records[1]["input_tokens"] == 10


def test_comment_body_is_normalized_to_content():
    arguments = JsonModelCandidate._normalize_arguments(
        "create_comment", {"post_id": 1, "body": "hello"})
    assert arguments == {"post_id": 1, "content": "hello"}


@pytest.mark.asyncio
async def test_candidate_prompt_includes_action_argument_schemas():
    class Client:
        messages = None

        async def complete(self, messages):
            self.messages = messages
            return ModelResponse(
                '{"action_type":"do_nothing","arguments":{}}', "model")

    client = Client()
    candidate = JsonModelCandidate("model", "1", client, 1)
    await candidate.act(Observation({"user_id": 1}, 0, [], []), {
        "available_actions": ["quote_post"], "scenario_id": "test", "step": 0})
    payload = json.loads(client.messages[1]["content"])
    assert payload["action_schemas"]["quote_post"]["required"] == [
        "post_id", "quote_body"]
