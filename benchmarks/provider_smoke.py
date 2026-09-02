from __future__ import annotations

from dataclasses import asdict
from typing import Any

from benchmarks.observers import JsonModelObserver
from benchmarks.protocol import CandidateAction
from benchmarks.providers import build_model_client


async def smoke_test_observer(provider: dict[str, Any], *,
                              observer_id: str = "smoke-observer",
                              observer_version: str = "development") -> dict[str, Any]:
    """Spend exactly one provider request on the observer JSON contract."""
    client = build_model_client(provider)
    observer = JsonModelObserver(
        observer_id, observer_version, client, parse_failure_mode="raise")
    action = CandidateAction("create_comment", {
        "post_id": 1,
        "content": "谢谢提醒。我先核对原始记录；如果确实有误，我会更正并补充来源。",
    })
    try:
        judgments = await observer.judge(action, {"success": True}, {
            "target_actor_id": "concerned-user",
            "is_direct_target": True,
        })
    except Exception as error:
        calls = observer.drain_call_records()
        return {
            "passed": False,
            "configured_model_id": provider["model_id"],
            "returned_model_id": calls[0]["model_id"] if calls else None,
            "request_count": client.request_count,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "call": calls[0] if calls else None,
        }
    calls = observer.drain_call_records()
    return {
        "passed": True,
        "configured_model_id": provider["model_id"],
        "returned_model_id": calls[0]["model_id"],
        "request_count": client.request_count,
        "input_tokens": calls[0]["input_tokens"],
        "output_tokens": calls[0]["output_tokens"],
        "judgment": asdict(judgments[0]),
    }
