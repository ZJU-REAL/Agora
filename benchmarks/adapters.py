from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from benchmarks.protocol import CandidateAction


ACTION_SCHEMAS = {
    "create_post": {"required": [], "optional": [
        "body", "title", "post_type", "assets", "topics", "language",
        "visibility", "community", "location", "reply_to_post_id"]},
    "create_comment": {"required": ["post_id", "content"],
                       "optional": ["parent_comment_id"]},
    "reply_comment": {"required": ["post_id", "content", "parent_comment_id"],
                      "optional": []},
    "like_post": {"required": ["post_id"], "optional": []},
    "unlike_post": {"required": ["post_id"], "optional": []},
    "dislike_post": {"required": ["post_id"], "optional": []},
    "collect_post": {"required": ["post_id"], "optional": []},
    "uncollect_post": {"required": ["post_id"], "optional": []},
    "follow_user": {"required": ["followee_id"], "optional": []},
    "unfollow_user": {"required": ["followee_id"], "optional": []},
    "view_post": {"required": ["post_id"], "optional": []},
    "repost": {"required": ["post_id"], "optional": ["community"]},
    "quote_post": {"required": ["post_id", "quote_body"],
                   "optional": ["community"]},
    "search_posts": {"required": ["query"],
                     "optional": ["community", "limit"]},
    "pin_comment": {"required": ["comment_id"], "optional": []},
    "do_nothing": {"required": [], "optional": []},
    "stop": {"required": [], "optional": []},
}


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_request_id: str | None = None


class ModelClient(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        ...


@dataclass(frozen=True)
class ModelCallRecord:
    attempt: int
    status: str
    elapsed_ms: float
    model_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    provider_request_id: str | None
    error_type: str | None = None
    error_message: str | None = None


class JsonModelCandidate:
    """Provider-neutral candidate using a strict JSON action contract."""

    def __init__(self, policy_id: str, policy_version: str,
                 client: ModelClient, max_attempts: int = 2,
                 expected_model_id: str | None = None,
                 supports_vision: bool = False):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.policy_id = policy_id
        self.policy_version = policy_version
        self.client = client
        self.max_attempts = max_attempts
        self.expected_model_id = expected_model_id
        self.supports_multimodal_context = supports_vision
        self._records: list[ModelCallRecord] = []

    async def act(self, observation, context):
        allowed = set(context["available_actions"]) | {"do_nothing", "stop"}
        user_payload = json.dumps({
            "scenario_id": context["scenario_id"],
            "step": context["step"],
            "available_actions": sorted(allowed),
            "action_schemas": {
                name: ACTION_SCHEMAS[name] for name in sorted(allowed)
                if name in ACTION_SCHEMAS},
            "available_asset_keys": context.get("available_asset_keys", []),
            "asset_rule": (
                "For media posts, arguments.assets entries must use asset_key "
                "from available_asset_keys; never use file paths."),
            "observation": asdict(observation),
        }, ensure_ascii=False)
        multimodal_parts = context.get("multimodal_parts", [])
        user_content = ([{"type": "text", "text": user_payload},
                         *multimodal_parts]
                        if multimodal_parts else user_payload)
        messages = [{
            "role": "system",
            "content": (
                "Operate the social account. Return one JSON object with "
                "action_type, arguments, and optional rationale. Do not include "
                "markdown or hidden-state assumptions."),
        }, {
            "role": "user",
            "content": user_content,
        }]
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            started = time.monotonic()
            try:
                response = await self.client.complete(messages)
                if (self.expected_model_id is not None
                        and response.model_id != self.expected_model_id):
                    raise ValueError(
                        f"Provider returned model {response.model_id!r}; expected "
                        f"{self.expected_model_id!r}")
                value = self._parse_json_object(response.text)
                action = CandidateAction(
                    action_type=value["action_type"],
                    arguments=self._normalize_arguments(
                        value["action_type"],
                        dict(value.get("arguments", {}))),
                    rationale=value.get("rationale"))
                if action.action_type not in allowed:
                    raise ValueError(
                        f"Model selected unavailable action: {action.action_type}")
                self._records.append(ModelCallRecord(
                    attempt, "completed",
                    round((time.monotonic() - started) * 1000, 3),
                    response.model_id, response.input_tokens,
                    response.output_tokens, response.provider_request_id))
                return action
            except Exception as error:
                last_error = error
                self._records.append(ModelCallRecord(
                    attempt, "failed",
                    round((time.monotonic() - started) * 1000, 3),
                    None, None, None, None, type(error).__name__, str(error)))
                messages.append({
                    "role": "user",
                    "content": "Previous output was invalid. Return only a valid "
                               "JSON action using an available action_type.",
                })
        assert last_error is not None
        raise RuntimeError("Candidate exhausted model-call attempts") from last_error

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped,
                              flags=re.IGNORECASE)
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            start, end = stripped.find("{"), stripped.rfind("}")
            if start < 0 or end <= start:
                raise
            value = json.loads(stripped[start:end + 1])
        if not isinstance(value, dict):
            raise ValueError("Model action must be a JSON object")
        return value

    @staticmethod
    def _normalize_arguments(action_type: str,
                             arguments: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(arguments)
        if action_type in {"create_comment", "reply_comment"}:
            if "content" not in normalized and "body" in normalized:
                normalized["content"] = normalized.pop("body")
            required = {"post_id", "content"}
        elif action_type in {"like_post", "unlike_post", "dislike_post",
                             "collect_post", "uncollect_post", "view_post",
                             "repost"}:
            required = {"post_id"}
        elif action_type == "quote_post":
            required = {"post_id", "quote_body"}
        elif action_type in {"follow_user", "unfollow_user"}:
            required = {"followee_id"}
        elif action_type == "search_posts":
            required = {"query"}
        elif action_type == "pin_comment":
            required = {"comment_id"}
        else:
            required = set()
        missing = sorted(required - normalized.keys())
        if missing:
            raise ValueError(
                f"Action {action_type} is missing arguments: {missing}")
        return normalized

    def drain_call_records(self) -> list[dict[str, Any]]:
        records = [asdict(item) for item in self._records]
        self._records.clear()
        return records
