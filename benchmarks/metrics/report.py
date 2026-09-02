from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from benchmarks.metrics.validation import load_validated_main_run


@dataclass(frozen=True)
class RunMetrics:
    run_id: str
    candidate_id: str
    ticks: int
    candidate_actions: int
    attitude_delta: float
    arousal_delta: float
    trust_delta: float
    engagement_intent_delta: float
    reaction_quality: float
    dialogue_progress: float
    conflict_handling: float
    timing_judgment: float
    model_calls: int
    observer_calls: int
    input_tokens: int
    output_tokens: int
    observer_input_tokens: int
    observer_output_tokens: int
    actions_per_positive_attitude: float | None


@dataclass(frozen=True)
class AggregateValue:
    mean: float
    standard_deviation: float
    confidence_interval_95: tuple[float, float]


@dataclass(frozen=True)
class AggregateReport:
    protocol_version: str
    candidate_id: str
    platform: str
    scenario_id: str
    successful_runs: int
    failed_runs: int
    metrics: dict[str, AggregateValue]


@dataclass(frozen=True)
class ActionAttribution:
    action_id: str
    step: int
    action_type: str
    attitude_delta: float
    trust_delta: float
    affected_actors: tuple[str, ...]


def compute_run_metrics(run_dir: str | Path) -> RunMetrics:
    run_dir = Path(run_dir)
    manifest = load_validated_main_run(run_dir / "manifest.json")
    totals = {name: 0.0 for name in (
        "attitude", "arousal", "trust", "engagement_intent")}
    ticks = 0
    actions = 0
    model_calls = 0
    input_tokens = 0
    output_tokens = 0
    observer_calls = observer_input_tokens = observer_output_tokens = 0
    action_types = []
    for line in (run_dir / "trajectory.jsonl").read_text(
            encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "step":
            ticks += 1
            actions += 1
            action_types.append(record["action"]["action_type"])
            for call in record.get("model_calls", []):
                model_calls += 1
                input_tokens += int(call.get("input_tokens") or 0)
                output_tokens += int(call.get("output_tokens") or 0)
            for call in record.get("observer_calls", []):
                observer_calls += 1
                observer_input_tokens += int(call.get("input_tokens") or 0)
                observer_output_tokens += int(call.get("output_tokens") or 0)
        for transition in record.get("state_transitions", []):
            for name in totals:
                totals[name] += (transition["after"][name]
                                 - transition["before"][name])
    attitude = round(totals["attitude"], 6)
    arousal = round(totals["arousal"], 6)
    trust = round(totals["trust"], 6)
    engagement = round(totals["engagement_intent"], 6)
    should_ignore = any(token in manifest["scenario_id"]
                        for token in ("bait", "spam"))
    did_ignore = bool(action_types) and all(
        item == "do_nothing" for item in action_types)
    timing = 1.0 if should_ignore == did_ignore else 0.0
    return RunMetrics(
        run_id=manifest["run_id"], candidate_id=manifest["candidate_id"],
        ticks=ticks, candidate_actions=actions,
        attitude_delta=attitude, arousal_delta=arousal, trust_delta=trust,
        engagement_intent_delta=engagement,
        reaction_quality=round((attitude + trust + engagement) / 3, 6),
        dialogue_progress=attitude,
        conflict_handling=round((attitude - arousal) / 2, 6),
        timing_judgment=timing, model_calls=model_calls,
        observer_calls=observer_calls,
        input_tokens=input_tokens, output_tokens=output_tokens,
        observer_input_tokens=observer_input_tokens,
        observer_output_tokens=observer_output_tokens,
        actions_per_positive_attitude=(
            round(actions / attitude, 6) if attitude > 0 else None),
    )


def write_run_report(run_dir: str | Path) -> Path:
    run_dir = Path(run_dir)
    path = run_dir / "metrics.json"
    path.write_text(json.dumps(asdict(compute_run_metrics(run_dir)), indent=2)
                    + "\n", encoding="utf-8")
    attributions = compute_action_attributions(run_dir)
    (run_dir / "attribution.json").write_text(json.dumps({
        "most_positive": [asdict(item) for item in sorted(
            attributions, key=lambda item: item.attitude_delta,
            reverse=True)[:5]],
        "most_negative": [asdict(item) for item in sorted(
            attributions, key=lambda item: item.attitude_delta)[:5]],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def compute_action_attributions(run_dir: str | Path) -> tuple[ActionAttribution, ...]:
    records = [json.loads(line) for line in (Path(run_dir) / "trajectory.jsonl")
               .read_text(encoding="utf-8").splitlines()]
    actions = {record["action_id"]: record for record in records
               if record.get("record_type") == "step"}
    totals = {action_id: {"attitude": 0.0, "trust": 0.0, "actors": set()}
              for action_id in actions}
    for record in records:
        for transition in record.get("state_transitions", []):
            action_id = transition["action_id"]
            if action_id not in totals:
                continue
            totals[action_id]["attitude"] += (
                transition["after"]["attitude"]
                - transition["before"]["attitude"])
            totals[action_id]["trust"] += (
                transition["after"]["trust"]
                - transition["before"]["trust"])
            totals[action_id]["actors"].add(transition["target_actor_id"])
    return tuple(ActionAttribution(
        action_id, actions[action_id]["step"],
        actions[action_id]["action"]["action_type"],
        round(value["attitude"], 6), round(value["trust"], 6),
        tuple(sorted(value["actors"]))) for action_id, value in totals.items())


def aggregate_runs(run_dirs: list[str | Path]) -> AggregateReport:
    if not run_dirs:
        raise ValueError("At least one run directory is required")
    manifests = []
    metrics = []
    failed = 0
    for run_dir in map(Path, run_dirs):
        manifest = load_validated_main_run(run_dir / "manifest.json")
        manifests.append(manifest)
        result = json.loads((run_dir / "result.json").read_text(
            encoding="utf-8"))
        if result["status"] != "completed":
            failed += 1
            continue
        metrics.append(compute_run_metrics(run_dir))
    identity_fields = ("protocol_version", "world_artifact_version",
                       "world_artifact_id", "candidate_id", "platform",
                       "scenario_id", "observer_pool_version",
                       "exposure_mode", "exposure_policy_version")
    baseline = manifests[0]
    for manifest in manifests[1:]:
        changed = [field for field in identity_fields
                   if manifest.get(field) != baseline.get(field)]
        if changed:
            raise ValueError(f"Cannot aggregate incompatible runs: {changed}")
    if not metrics:
        raise ValueError("No completed runs to aggregate")
    metric_names = ("attitude_delta", "arousal_delta", "trust_delta",
                    "engagement_intent_delta", "reaction_quality",
                    "dialogue_progress", "conflict_handling",
                    "timing_judgment")
    values = {}
    for name in metric_names:
        samples = [float(getattr(item, name)) for item in metrics]
        mean = statistics.fmean(samples)
        std = statistics.stdev(samples) if len(samples) > 1 else 0.0
        margin = 1.96 * std / math.sqrt(len(samples))
        values[name] = AggregateValue(
            round(mean, 6), round(std, 6),
            (round(mean - margin, 6), round(mean + margin, 6)))
    return AggregateReport(
        baseline["protocol_version"], baseline["candidate_id"],
        baseline["platform"], baseline["scenario_id"], len(metrics), failed,
        values)


def write_aggregate_report(run_dirs: list[str | Path], output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = aggregate_runs(run_dirs)
    output.write_text(json.dumps({
        **asdict(report), "behavioral_archetype": classify_archetype(report),
    }, indent=2) + "\n", encoding="utf-8")
    return output


def intraclass_correlation(score_matrix: list[list[float]]) -> float:
    """Compute ICC(1,1) for subjects measured by the same number of runs."""
    if len(score_matrix) < 2 or any(len(row) < 2 for row in score_matrix):
        raise ValueError("ICC requires at least two subjects and two runs")
    run_count = len(score_matrix[0])
    if any(len(row) != run_count for row in score_matrix):
        raise ValueError("ICC score rows must have equal length")
    subject_count = len(score_matrix)
    subject_means = [statistics.fmean(row) for row in score_matrix]
    grand_mean = statistics.fmean(subject_means)
    between = run_count * sum((value - grand_mean) ** 2
                              for value in subject_means) / (subject_count - 1)
    within = sum(sum((value - subject_means[index]) ** 2 for value in row)
                 for index, row in enumerate(score_matrix)) / (
                     subject_count * (run_count - 1))
    denominator = between + (run_count - 1) * within
    return round((between - within) / denominator, 6) if denominator else 1.0


def classify_archetype(report: AggregateReport) -> str:
    metrics = report.metrics
    conflict = metrics["conflict_handling"].mean
    timing = metrics["timing_judgment"].mean
    reaction = metrics["reaction_quality"].mean
    if conflict >= 0.3 and timing >= 0.7:
        return "conflict-resolving selective operator"
    if conflict >= 0.3:
        return "active de-escalator"
    if timing >= 0.7 and reaction <= 0.05:
        return "cautious selective responder"
    if conflict < 0:
        return "escalation-prone operator"
    return "low-impact generalist"
