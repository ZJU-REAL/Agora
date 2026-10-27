from __future__ import annotations

import json
import math
import statistics
import secrets
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CalibrationJudgment:
    item_id: str
    judge_id: str
    judge_type: str
    score: float


@dataclass(frozen=True)
class CalibrationReport:
    item_count: int
    human_judges: int
    simulated_judges: int
    spearman_rank_correlation: float | None
    pairwise_direction_agreement: float
    mean_absolute_error: float
    correlation_status: str = "defined"


def load_calibration_judgments(
        path: str | Path, private_key: str | Path | None = None
        ) -> tuple[CalibrationJudgment, ...]:
    rows = [json.loads(line) for line in Path(path).read_text(
        encoding="utf-8").splitlines() if line.strip()]
    normalized = []
    keys = ({row["item_id"]: row for row in (
        json.loads(line) for line in Path(private_key).read_text().splitlines())}
            if private_key else {})
    simulated_seen = set()
    for row in rows:
        if private_key:
            if row["item_id"] not in keys:
                raise ValueError("Human label is absent from private calibration key")
            row = {**row, **keys[row["item_id"]]}
        if "judge_type" in row:
            normalized.append(CalibrationJudgment(**row))
            continue
        if row.get("human_score") is not None and row.get("human_judge_id"):
            normalized.append(CalibrationJudgment(
                row["item_id"], row["human_judge_id"], "human",
                float(row["human_score"])))
        if row.get("simulated_score") is not None and row["item_id"] not in simulated_seen:
            normalized.append(CalibrationJudgment(
                row["item_id"], row.get("simulated_judge_id", "observer"),
                "simulated", float(row["simulated_score"])))
            simulated_seen.add(row["item_id"])
    judgments = tuple(normalized)
    for item in judgments:
        if item.judge_type not in {"human", "simulated"}:
            raise ValueError(f"Invalid judge_type: {item.judge_type}")
        if not -1.0 <= item.score <= 1.0:
            raise ValueError("Calibration scores must be between -1 and 1")
    return judgments


def _average_by_item(judgments, judge_type):
    grouped = {}
    for item in judgments:
        if item.judge_type == judge_type:
            grouped.setdefault(item.item_id, []).append(item.score)
    return {key: statistics.fmean(values) for key, values in grouped.items()}


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end - 1) / 2 + 1
        for index in order[cursor:end]:
            ranks[index] = rank
        cursor = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum((a - left_mean) * (b - right_mean)
                    for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left)
                            * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else None


def calibration_report(
        judgments: tuple[CalibrationJudgment, ...]) -> CalibrationReport:
    human = _average_by_item(judgments, "human")
    simulated = _average_by_item(judgments, "simulated")
    item_ids = sorted(set(human) & set(simulated))
    if len(item_ids) < 2:
        raise ValueError("Calibration requires at least two jointly judged items")
    human_scores = [human[item] for item in item_ids]
    simulated_scores = [simulated[item] for item in item_ids]
    concordant = total = 0
    for left in range(len(item_ids)):
        for right in range(left + 1, len(item_ids)):
            human_direction = human_scores[left] - human_scores[right]
            simulated_direction = simulated_scores[left] - simulated_scores[right]
            concordant += int(human_direction * simulated_direction > 0
                              or human_direction == simulated_direction == 0)
            total += 1
    correlation = _pearson(_ranks(human_scores), _ranks(simulated_scores))
    return CalibrationReport(
        item_count=len(item_ids),
        human_judges=len({item.judge_id for item in judgments
                          if item.judge_type == "human"}),
        simulated_judges=len({item.judge_id for item in judgments
                              if item.judge_type == "simulated"}),
        spearman_rank_correlation=(round(correlation, 6)
                                   if correlation is not None else None),
        pairwise_direction_agreement=round(concordant / total, 6),
        mean_absolute_error=round(statistics.fmean(
            abs(a - b) for a, b in zip(human_scores, simulated_scores)), 6),
        correlation_status="defined" if correlation is not None else "zero_variance",
    )


def repeated_judgment_agreement(
        judgments: tuple[CalibrationJudgment, ...], judge_id: str) -> float:
    grouped = {}
    for item in judgments:
        if item.judge_id == judge_id:
            grouped.setdefault(item.item_id, []).append(item.score)
    repeated = [values for values in grouped.values() if len(values) > 1]
    if not repeated:
        raise ValueError("Judge has no repeated items")
    deviations = [statistics.pstdev(values) for values in repeated]
    return round(max(0.0, 1.0 - statistics.fmean(deviations) / 2.0), 6)


def export_human_calibration_sample(
        run_dirs: list[str | Path], output: str | Path,
        max_items_per_run: int = 10) -> Path:
    """Export blinded candidate actions and outcomes for platform-user labeling."""
    if max_items_per_run < 1:
        raise ValueError("max_items_per_run must be positive")
    rows: list[dict[str, Any]] = []
    private_rows = []
    for run_dir in map(Path, run_dirs):
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        candidate_ids = {actor.get("user_id") for actor in manifest.get("actors", [])
                         if actor.get("role") == "candidate"}
        def blind(value):
            if isinstance(value, list):
                return [blind(item) for item in value]
            if not isinstance(value, dict):
                return value
            value = {name: blind(item) for name, item in value.items()}
            if value.get("user_id") in candidate_ids and "handle" in value:
                value.update(handle="creator", display_name="Creator")
            if value.get("author_id") in candidate_ids:
                for name in ("author_handle", "author_name"):
                    if name in value:
                        value[name] = "Creator"
            return value
        records = [json.loads(line) for line in (run_dir / "trajectory.jsonl")
                   .read_text(encoding="utf-8").splitlines()]
        steps = [record for record in records
                 if record.get("record_type") == "step"]
        for record in steps[:max_items_per_run]:
            transitions = record.get("state_transitions", [])
            simulated_score = (statistics.fmean(
                item["after"]["attitude"] - item["before"]["attitude"]
                for item in transitions) if transitions else 0.0)
            observer_ids = sorted({
                item["judgment"]["observer_id"] for item in transitions})
            item_id = secrets.token_hex(12)
            rows.append({
                "item_id": item_id,
                "platform": manifest["platform"],
                "observation": blind(record["observation"]),
                "action": {name: record["action"][name]
                           for name in ("action_type", "arguments")},
                "outcome": blind(record["outcome"]),
                "human_score": None,
                "human_judge_id": None,
            })
            private_rows.append({
                "item_id": item_id, "run_id": run_dir.name,
                "step": record["step"],
                "simulated_score": round(simulated_score, 6) if transitions else None,
                "simulated_judge_id": "+".join(observer_ids) or "no-observer",
            })
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    random.SystemRandom().shuffle(rows)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                              for row in rows), encoding="utf-8")
    key_path = output.with_name(output.name + ".private-key.jsonl")
    key_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                for row in private_rows), encoding="utf-8")
    key_path.chmod(0o600)
    return output
