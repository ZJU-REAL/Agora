"""Bounded, public-only experience for in-context transfer between worlds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CONTEXT_FIELDS = {"platform", "culture", "domain", "language"}
PUBLIC_FIELDS = {
    "title",
    "body",
    "content",
    "quote_body",
    "query",
    "location",
    "community",
    "language",
    "topics",
    "success",
    "action_type",
    "post_type",
    "media_type",
    "caption",
    "alt_text",
    "transcript",
    "posts",
    "post",
    "feed",
    "comments",
    "replies",
    "assets",
    "num_likes",
    "num_dislikes",
    "num_collections",
    "num_shares",
    "num_followers",
    "speaker",
}


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def validate_context(context):
    if (
        not isinstance(context, dict)
        or set(context) != CONTEXT_FIELDS
        or any(
            not isinstance(value, str) or not value.strip()
            for value in context.values()
        )
    ):
        raise ValueError(
            "Context requires non-empty platform, culture, domain and language"
        )
    if context["platform"] not in {"xiaohongshu", "reddit", "x"}:
        raise ValueError("Unsupported context platform")


def _project(value, candidate_id, text_limit, hide_feedback=False):
    if isinstance(value, list):
        return [
            _project(item, candidate_id, text_limit, hide_feedback) for item in value
        ]
    if isinstance(value, str):
        return value[:text_limit]
    if isinstance(value, dict):
        public = {
            key: _project(
                [
                    comment
                    for comment in item
                    if comment.get("author_id") == candidate_id
                ]
                if hide_feedback
                and key in {"comments", "replies"}
                and isinstance(item, list)
                else item,
                candidate_id,
                text_limit,
                hide_feedback,
            )
            for key, item in value.items()
            if key in PUBLIC_FIELDS
        }
        if "author_id" in value:
            public["speaker"] = (
                "self" if value["author_id"] == candidate_id else "audience"
            )
        return public
    return value


def validate_experience(value, max_chars=64000):
    if not isinstance(value, dict) or set(value) != {
        "version",
        "origin_context",
        "memories",
    }:
        raise ValueError("Invalid transfer experience schema")
    if value["version"] != "public-experience-v1":
        raise ValueError("Unsupported transfer experience version")
    validate_context(value["origin_context"])
    if not isinstance(value["memories"], list) or not value["memories"]:
        raise ValueError("Transfer experience must contain observed memories")

    def check_public(item):
        if isinstance(item, dict):
            if set(item) - PUBLIC_FIELDS:
                raise ValueError(
                    "Transfer experience contains private fields or world IDs"
                )
            for child in item.values():
                check_public(child)
        elif isinstance(item, list):
            for child in item:
                check_public(child)

    for memory in value["memories"]:
        if not isinstance(memory, dict) or set(memory) != {
            "step",
            "observation",
            "action",
            "outcome",
        }:
            raise ValueError("Invalid transfer memory")
        if (
            not isinstance(memory["step"], int)
            or isinstance(memory["step"], bool)
            or memory["step"] < 0
        ):
            raise ValueError("Invalid experience step")
        for name in ("observation", "action", "outcome"):
            check_public(memory[name])
    if len(canonical_json(value)) > max_chars:
        raise ValueError("Transfer experience exceeds character budget")


def export_experience(run_dir: str | Path, context: dict, max_chars=12000):
    """Read only candidate observations/actions/results; never evaluator outputs."""
    validate_context(context)
    if (
        not isinstance(max_chars, int)
        or isinstance(max_chars, bool)
        or not 512 <= max_chars <= 64000
    ):
        raise ValueError("Experience max_chars must be between 512 and 64000")
    run_dir = Path(run_dir)
    result = json.loads((run_dir / "result.json").read_text())
    if result["status"] != "completed":
        raise ValueError("Cannot transfer experience from a failed run")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    candidate_id = next(
        actor["user_id"] for actor in manifest["actors"] if actor["role"] == "candidate"
    )
    steps = [
        record
        for record in (
            json.loads(line)
            for line in (run_dir / "trajectory.jsonl").read_text().splitlines()
        )
        if record.get("record_type") == "step"
    ]
    raw = [
        {
            "step": record["step"],
            "observation": record["observation"]["feed"],
            "action": {
                "action_type": record["action"]["action_type"],
                **record["action"]["arguments"],
            },
            # The final tool result was never supplied in a subsequent act().
            "outcome": record["outcome"] if index + 1 < len(steps) else {},
        }
        for index, record in enumerate(steps)
    ]
    text_limit = 512
    while True:
        memories = [
            {
                "step": memory["step"],
                **{
                    name: _project(
                        memory[name],
                        candidate_id,
                        text_limit,
                        manifest.get("metadata", {}).get("feedback_condition")
                        == "hidden",
                    )
                    for name in ("observation", "action", "outcome")
                },
            }
            for memory in raw
        ]
        capsule = {
            "version": "public-experience-v1",
            "origin_context": context,
            "memories": memories,
        }
        if len(canonical_json(capsule)) <= max_chars:
            break
        if len(raw) > 1:
            raw.pop(0)
        elif text_limit > 8:
            text_limit //= 2
        else:
            raise ValueError("Experience budget too small for the observed structure")
    validate_experience(capsule, max_chars)
    return capsule
