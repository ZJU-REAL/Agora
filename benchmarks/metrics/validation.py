from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_IDENTITY_FIELDS = (
    "protocol_version", "world_artifact_version", "world_artifact_id",
    "candidate_id", "platform", "scenario_id", "seed", "run_id",
    "observer_pool_version", "exposure_mode", "exposure_policy_version",
)


def validate_main_run(manifest: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_IDENTITY_FIELDS
               if field not in manifest]
    if missing:
        raise ValueError(f"Run manifest is missing fields: {missing}")
    candidates = [actor for actor in manifest.get("actors", [])
                  if actor.get("role") == "candidate"]
    if len(candidates) != 1:
        raise ValueError("Main-score runs require exactly one candidate")
    if candidates[0].get("actor_id") != manifest["candidate_id"]:
        raise ValueError("Candidate actor does not match candidate_id")
    if manifest["exposure_mode"] == "learned_recommender":
        raise ValueError("Learned recommenders are forbidden in main-score runs")


def load_validated_main_run(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_main_run(value)
    return value
