from __future__ import annotations

import json
import math
import statistics
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
    spearman_rank_correlation: float
    pairwise_direction_agreement: float
    mean_absolute_error: float


def load_calibration_judgments(
        path: str | Path) -> tuple[CalibrationJudgment, ...]:
    rows = [json.loads(line) for line in Path(path).read_text(
        encoding="utf-8").splitlines() if line.strip()]
    normalized = []
    for row in rows:
        if "judge_type" in row:
            normalized.append(CalibrationJudgment(**row))
            continue
        if row.get("human_score") is not None and row.get("human_judge_id"):
            normalized.append(CalibrationJudgment(
                row["item_id"], row["human_judge_id"], "human",
                float(row["human_score"])))
        if row.get("simulated_score") is not None:
            normalized.append(CalibrationJudgment(
                row["item_id"], row.get("simulated_judge_id", "observer"),
                "simulated", float(row["simulated_score"])))
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


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = statistics.fmean(left)
    right_mean = statistics.fmean(right)
    numerator = sum((a - left_mean) * (b - right_mean)
                    for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left)
                            * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else 1.0


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
    return CalibrationReport(
        item_count=len(item_ids),
        human_judges=len({item.judge_id for item in judgments
                          if item.judge_type == "human"}),
        simulated_judges=len({item.judge_id for item in judgments
                              if item.judge_type == "simulated"}),
        spearman_rank_correlation=round(
            _pearson(_ranks(human_scores), _ranks(simulated_scores)), 6),
        pairwise_direction_agreement=round(concordant / total, 6),
        mean_absolute_error=round(statistics.fmean(
            abs(a - b) for a, b in zip(human_scores, simulated_scores)), 6),
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
    for run_dir in map(Path, run_dirs):
        records = [json.loads(line) for line in (run_dir / "trajectory.jsonl")
                   .read_text(encoding="utf-8").splitlines()]
        for record in records[:max_items_per_run]:
            if record.get("record_type") != "step":
                continue
            transitions = record.get("state_transitions", [])
            simulated_score = (statistics.fmean(
                item["after"]["attitude"] - item["before"]["attitude"]
                for item in transitions) if transitions else 0.0)
            observer_ids = sorted({
                item["judgment"]["observer_id"] for item in transitions})
            rows.append({
                "item_id": f"{run_dir.name}:step-{record['step']}",
                "platform": json.loads((run_dir / "manifest.json").read_text(
                    encoding="utf-8"))["platform"],
                "observation": record["observation"],
                "action": record["action"],
                "outcome": record["outcome"],
                "simulated_score": round(simulated_score, 6),
                "simulated_judge_id": "+".join(observer_ids) or "no-observer",
                "human_score": None,
                "human_judge_id": None,
            })
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                              for row in rows), encoding="utf-8")
    return output
