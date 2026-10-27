from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from benchmarks.metrics import compute_run_metrics
from benchmarks.metrics.validation import load_validated_main_run


def semantic_run_fingerprint(run_dir: str | Path) -> str:
    run_dir = Path(run_dir)
    manifest = load_validated_main_run(run_dir / "manifest.json")
    records = []
    for line in (run_dir / "trajectory.jsonl").read_text(
            encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "step":
            records.append({
            "step": record["step"],
            "tick_before": record["tick_before"],
            "observation": record["observation"],
            "action": record["action"],
            "outcome": record["outcome"],
            "environment_actions": record["environment_actions"],
            "state_transitions": [{
                key: value for key, value in transition.items()
                if key != "action_id"
            } for transition in record["state_transitions"]],
            "pending_judgments": [{
                **item, "action_id": "semantic-action-reference",
            } for item in record.get("pending_judgments", [])],
            })
        elif record.get("record_type") == "terminal_effects":
            records.append({
                "record_type": "terminal_effects",
                "tick": record["tick"],
                "state_transitions": [{
                    key: value for key, value in transition.items()
                    if key != "action_id"
                } for transition in record.get("state_transitions", [])],
            })
    value = {
        "protocol_version": manifest["protocol_version"],
        "world_artifact_version": manifest["world_artifact_version"],
        "platform": manifest["platform"],
        "scenario_id": manifest["scenario_id"],
        "seed": manifest["seed"],
        "candidate_id": manifest["candidate_id"],
        "records": records,
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare_reproductions(first: str | Path, second: str | Path) -> dict:
    first_metrics = compute_run_metrics(first)
    second_metrics = compute_run_metrics(second)
    first_metric_values = asdict(first_metrics)
    second_metric_values = asdict(second_metrics)
    first_metric_values.pop("run_id")
    second_metric_values.pop("run_id")
    first_fingerprint = semantic_run_fingerprint(first)
    second_fingerprint = semantic_run_fingerprint(second)
    return {
        "reproducible": (first_fingerprint == second_fingerprint
                         and first_metric_values == second_metric_values),
        "first_fingerprint": first_fingerprint,
        "second_fingerprint": second_fingerprint,
        "metrics_equal": first_metric_values == second_metric_values,
    }
