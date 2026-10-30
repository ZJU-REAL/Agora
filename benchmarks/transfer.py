"""Paired in-context transfer experiments with fresh worlds and public memory."""

from __future__ import annotations

import json
import math
import statistics
import weakref
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from benchmarks.artifacts import WorldArtifact
from benchmarks.budget import EpisodeBudget
from benchmarks.experience import content_hash, export_experience, validate_context
from benchmarks.metrics.cross_cultural import TransferPair, paired_transfer_report
from benchmarks.protocol import ActorRole, EpisodeManifest
from benchmarks.runners.exclusive import ExclusiveRunner


TRANSFER_VERSION = "agora-transfer-v1"
STAGES = (
    "source_preparation",
    "target_preparation",
    "source_reference",
    "target_cold",
    "target_transfer",
    "target_transfer_hidden",
    "target_native",
)
DIMENSIONS = ("attitude", "trust", "engagement_intent")


@dataclass(frozen=True)
class TransferPlan:
    experiment_id: str
    pair_id: str
    axis: str
    source_context: dict[str, str]
    target_context: dict[str, str]
    seeds: tuple[int, ...]
    preparation_ticks: int = 3
    evaluation_ticks: int = 3
    probe_ticks: int = 1
    preparation_budget: dict[str, int] = field(default_factory=dict)
    evaluation_budget: dict[str, int] = field(default_factory=dict)
    memory_max_chars: int = 12000

    def validate(self):
        import re

        for name in (self.experiment_id, self.pair_id):
            if not isinstance(name, str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name
            ):
                raise ValueError("Invalid transfer experiment/pair ID")
        validate_context(self.source_context)
        validate_context(self.target_context)
        changed = {
            key
            for key in self.source_context
            if self.source_context[key] != self.target_context[key]
        }
        if changed != {self.axis}:
            raise ValueError("Transfer must vary exactly the declared context axis")
        if (
            not self.seeds
            or len(set(self.seeds)) != len(self.seeds)
            or any(
                not isinstance(seed, int) or isinstance(seed, bool)
                for seed in self.seeds
            )
        ):
            raise ValueError("Transfer seeds must be unique integers")
        for value in (self.preparation_ticks, self.evaluation_ticks, self.probe_ticks):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("Transfer phase lengths must be positive integers")
        if self.evaluation_ticks < 2 * self.probe_ticks:
            raise ValueError("Initial and final probe windows must not overlap")
        for ticks, limits in (
            (self.preparation_ticks, self.preparation_budget),
            (self.evaluation_ticks, self.evaluation_budget),
        ):
            budget = EpisodeBudget(limits, ticks)
            if budget.limits["max_actions"] != ticks:
                raise ValueError("Phase action budget must equal its declared ticks")
        if (
            not isinstance(self.memory_max_chars, int)
            or isinstance(self.memory_max_chars, bool)
            or not 512 <= self.memory_max_chars <= 64000
        ):
            raise ValueError(
                "Experience character budget must be between 512 and 64000"
            )


def window_scores(run_dir: Path, start: int, end: int):
    """Attribute immediate/delayed deltas to actions in an equal-length window."""
    records = [
        json.loads(line)
        for line in (run_dir / "trajectory.jsonl").read_text().splitlines()
    ]
    steps = [
        row
        for row in records
        if row.get("record_type") == "step" and start <= row["step"] < end
    ]
    selected = {row["action_id"] for row in steps}
    manifest = json.loads((run_dir / "manifest.json").read_text())
    actors = {
        actor["user_id"]: actor["actor_id"]
        for actor in manifest["actors"]
        if actor.get("user_id") is not None
    }
    expected = {
        (row["action_id"], actors[item["user_id"]])
        for row in steps
        for item in row.get("environment_actions", [])
        if item["action"] == "audience_reaction" and item.get("focused_action")
    }
    exposures = len(expected)
    transitions = [
        item
        for row in records
        for item in row.get("state_transitions", [])
        if item["action_id"] in selected
    ]
    pending = records[-1].get("pending_judgments", []) if records else []
    unresolved = any(item["action_id"] in selected for item in pending)
    judged = {
        (item["action_id"], item["target_actor_id"])
        for item in transitions
        if item["judgment"]["confidence"] > 0
    }
    if len(steps) != end - start:
        status = "incomplete_window"
    elif not exposures:
        status = "no_exposure"
    elif not transitions or unresolved or expected - judged:
        status = "missing_or_pending_judgments"
    else:
        status = "measured"
    scores = (
        {
            name: sum(
                item["after"][name] - item["before"][name] for item in transitions
            )
            / exposures
            for name in DIMENSIONS
        }
        if status == "measured"
        else None
    )
    return {
        "status": status,
        "start_step": start,
        "end_step_exclusive": end,
        "exposures": exposures,
        "judgment_count": len(transitions),
        "scores": scores,
    }


def _summary(values):
    mean = statistics.fmean(values)
    margin = (
        1.96 * statistics.stdev(values) / math.sqrt(len(values))
        if len(values) > 1
        else None
    )
    return {
        "mean": round(mean, 12),
        "samples": len(values),
        "confidence_interval_95": (
            [round(mean - margin, 12), round(mean + margin, 12)]
            if margin is not None
            else None
        ),
    }


class TransferRunner:
    def __init__(
        self, source: WorldArtifact, target: WorldArtifact, output_root: str | Path
    ):
        self.source, self.target = source, target
        self.output_root = Path(output_root)

    async def run(
        self,
        plan: TransferPlan,
        source_template: EpisodeManifest,
        target_template: EpisodeManifest,
        candidate_factory,
        observer_factory,
        audience_factory,
        *,
        resume=False,
    ):
        plan.validate()
        if observer_factory is None:
            raise ValueError("Transfer experiments require an independent observer")
        source_manifest, target_manifest = (
            self.source.validate(),
            self.target.validate(),
        )
        for name in (
            "scenario_suite_version",
            "observer_pool_version",
            "exposure_mode",
            "exposure_policy_version",
            "tick",
        ):
            if getattr(source_manifest, name) != getattr(target_manifest, name):
                raise ValueError(
                    f"Paired worlds disagree on controlled setting: {name}"
                )
        if content_hash(
            json.loads(self.source.manifest_path.read_text())
        ) == content_hash(json.loads(self.target.manifest_path.read_text())):
            raise ValueError("Different contexts require independently frozen worlds")
        for artifact, template, context in (
            (source_manifest, source_template, plan.source_context),
            (target_manifest, target_template, plan.target_context),
        ):
            if (
                artifact.platform != context["platform"]
                or template.platform != context["platform"]
            ):
                raise ValueError("Context platform does not match episode/artifact")
            if "transfer_experience" in template.metadata:
                raise ValueError(
                    "Transfer templates must start without injected experience"
                )
            if (
                artifact.metadata.get("context") != context
                or artifact.metadata.get("transfer_pair_id") != plan.pair_id
            ):
                raise ValueError(
                    "Artifact must freeze the declared context and transfer_pair_id"
                )
            for event in template.metadata.get("feedback_schedule", []):
                relative = event["tick"] - artifact.tick
                if relative < plan.probe_ticks or relative >= min(
                    plan.preparation_ticks, plan.evaluation_ticks
                ):
                    raise ValueError(
                        "Scheduled feedback must follow the initial probe and fit every phase"
                    )
        if sorted(actor.role.value for actor in source_template.actors) != sorted(
            actor.role.value for actor in target_template.actors
        ):
            raise ValueError("Paired worlds require the same actor-role composition")
        live = {
            role: weakref.WeakValueDictionary()
            for role in (
                "candidate",
                "observer",
                "audience",
                "candidate_client",
                "observer_client",
                "audience_client",
            )
        }

        def fresh(factory, role):
            value = factory()
            if value is None:
                raise ValueError(f"Transfer {role} factory returned None")
            if id(value) in live[role]:
                raise ValueError(f"Transfer {role} factory must return fresh instances")
            live[role][id(value)] = value

            def inspect_clients(policy):
                client = getattr(policy, "client", None)
                if client is not None:
                    seen = live[f"{role}_client"]
                    if id(client) in seen:
                        raise ValueError(
                            f"Transfer {role} factory must return fresh clients"
                        )
                    seen[id(client)] = client
                for member in getattr(policy, "observers", ()):
                    inspect_clients(member)

            inspect_clients(value)
            return value

        candidate, observer, audience = (
            fresh(candidate_factory, "candidate"),
            fresh(observer_factory, "observer"),
            fresh(audience_factory, "audience"),
        )
        runtime_fingerprint = ExclusiveRunner._runtime_fingerprint(
            candidate, observer, audience
        )
        policy_id, policy_version = candidate.policy_id, candidate.policy_version
        source_hash = content_hash(json.loads(self.source.manifest_path.read_text()))
        target_hash = content_hash(json.loads(self.target.manifest_path.read_text()))
        frozen = {
            "protocol_version": TRANSFER_VERSION,
            "plan": asdict(plan),
            "source_template": asdict(source_template),
            "target_template": asdict(target_template),
            "source_artifact_sha256": source_hash,
            "target_artifact_sha256": target_hash,
            "runtime_fingerprint": runtime_fingerprint,
            "implementation_sha256": ExclusiveRunner._source_fingerprint(),
        }
        # JSON normalizes tuple fields before comparing a resumed experiment.
        frozen = json.loads(json.dumps(frozen))
        for template, artifact in (
            (source_template, self.source),
            (target_template, self.target),
        ):
            bound = replace(
                template,
                actors=tuple(
                    replace(actor, policy_id=policy_id, policy_version=policy_version)
                    if actor.role == ActorRole.CANDIDATE
                    else actor
                    for actor in template.actors
                ),
            )
            ExclusiveRunner(artifact, self.output_root).validate(bound, candidate)
        if self.output_root.exists():
            if not resume or not (self.output_root / "experiment.json").is_file():
                raise FileExistsError(
                    "Use a fresh transfer output directory or --resume"
                )
            if json.loads((self.output_root / "experiment.json").read_text()) != frozen:
                raise ValueError(
                    "Transfer plan, runtime, implementation or artifacts changed"
                )
        else:
            self.output_root.mkdir(parents=True)
            self._write(self.output_root / "experiment.json", frozen)
        # Preflight objects are deliberately discarded; every phase gets new clients/state.
        del candidate, observer, audience
        items = []
        pairs = []
        contrasts = []
        for seed in plan.seeds:
            item = {"seed": seed, "status": "running", "runs": {}, "error": None}
            capsules = {}
            try:
                for stage in STAGES:
                    is_source = stage in {"source_preparation", "source_reference"}
                    is_preparation = stage.endswith("preparation")
                    artifact, template = (
                        (self.source, source_template)
                        if is_source
                        else (self.target, target_template)
                    )
                    context = plan.source_context if is_source else plan.target_context
                    ticks = (
                        plan.preparation_ticks
                        if is_preparation
                        else plan.evaluation_ticks
                    )
                    limits = (
                        plan.preparation_budget
                        if is_preparation
                        else plan.evaluation_budget
                    )
                    memory = (
                        capsules.get("source")
                        if stage
                        in {
                            "source_reference",
                            "target_transfer",
                            "target_transfer_hidden",
                        }
                        else capsules.get("target")
                        if stage == "target_native"
                        else None
                    )
                    metadata = {
                        **template.metadata,
                        "budget": EpisodeBudget(limits, ticks).limits,
                        "culture": {**template.metadata.get("culture", {}), **context},
                        "feedback_condition": "hidden"
                        if stage == "target_transfer_hidden"
                        else "visible",
                        "transfer": {
                            "protocol_version": TRANSFER_VERSION,
                            "experiment_id": plan.experiment_id,
                            "pair_id": plan.pair_id,
                            "axis": plan.axis,
                            "stage": stage,
                        },
                    }
                    if memory is not None:
                        metadata.update(
                            transfer_experience=memory,
                            transfer_experience_sha256=content_hash(memory),
                        )
                        origin_stage = (
                            "target-preparation"
                            if stage == "target_native"
                            else "source-preparation"
                        )
                        metadata["transfer"]["experience_source_run_id"] = (
                            f"seed-{seed}-{origin_stage}"
                        )
                    manifest = replace(
                        template,
                        protocol_version=TRANSFER_VERSION,
                        run_id=f"seed-{seed}-{stage.replace('_', '-')}",
                        seed=seed,
                        max_ticks=ticks,
                        actors=tuple(
                            replace(
                                actor,
                                policy_id=policy_id,
                                policy_version=policy_version,
                            )
                            if actor.role == ActorRole.CANDIDATE
                            else actor
                            for actor in template.actors
                        ),
                        metadata=metadata,
                    )
                    candidate, observer, audience = (
                        fresh(candidate_factory, "candidate"),
                        fresh(observer_factory, "observer"),
                        fresh(audience_factory, "audience"),
                    )
                    if (
                        ExclusiveRunner._runtime_fingerprint(
                            candidate, observer, audience
                        )
                        != runtime_fingerprint
                    ):
                        raise ValueError("Transfer runtime changed between phases")
                    run_dir = self.output_root / "runs" / manifest.run_id
                    item["runs"][stage] = {
                        "run_id": manifest.run_id,
                        "status": "running",
                    }
                    if run_dir.exists():
                        if not resume:
                            raise FileExistsError(run_dir)
                        stored = json.loads((run_dir / "result.json").read_text())
                        if stored["status"] != "completed":
                            raise ValueError(
                                "Failed transfer phase cannot reuse spent budget; start a new experiment"
                            )
                    result = await ExclusiveRunner(
                        artifact, self.output_root / "runs"
                    ).run(
                        manifest,
                        candidate,
                        observer,
                        audience_policy=audience,
                        resume=run_dir.exists(),
                    )
                    if is_preparation:
                        capsule = export_experience(
                            result.output_dir, context, plan.memory_max_chars
                        )
                        kind = "source" if is_source else "target"
                        capsules[kind] = capsule
                        self._write(
                            self.output_root / f"seed-{seed}-{kind}-experience.json",
                            capsule,
                        )
                    phase_result = json.loads(
                        (result.output_dir / "result.json").read_text()
                    )
                    item["runs"][stage] = {
                        "run_id": manifest.run_id,
                        "status": "completed",
                        "ticks_completed": result.ticks_completed,
                        "budget": phase_result["budget"],
                        "termination_reason": phase_result["termination_reason"],
                        "experience_sha256": metadata.get("transfer_experience_sha256"),
                    }
                    if not is_preparation:
                        item["runs"][stage].update(
                            initial=window_scores(
                                result.output_dir, 0, plan.probe_ticks
                            ),
                            final=window_scores(
                                result.output_dir, ticks - plan.probe_ticks, ticks
                            ),
                        )
                    del candidate, observer, audience
                required = (
                    item["runs"]["source_reference"]["initial"],
                    item["runs"]["target_transfer"]["initial"],
                    item["runs"]["target_transfer"]["final"],
                    item["runs"]["target_native"]["final"],
                )
                if all(window["scores"] is not None for window in required):
                    pairs.append(
                        TransferPair(
                            plan.pair_id,
                            seed,
                            plan.source_context,
                            plan.target_context,
                            *(window["scores"] for window in required),
                        )
                    )
                    item["status"] = "completed"
                else:
                    item["status"] = "incomplete_measurement"
                values = {}
                for label, left_stage, right_stage, window in (
                    (
                        "source_experience_effect_initial",
                        "target_transfer",
                        "target_cold",
                        "initial",
                    ),
                    (
                        "source_experience_effect_final",
                        "target_transfer",
                        "target_cold",
                        "final",
                    ),
                    (
                        "comment_feedback_effect_final",
                        "target_transfer",
                        "target_transfer_hidden",
                        "final",
                    ),
                    (
                        "target_experience_effect_initial",
                        "target_native",
                        "target_cold",
                        "initial",
                    ),
                ):
                    left, right = (
                        item["runs"][left_stage][window]["scores"],
                        item["runs"][right_stage][window]["scores"],
                    )
                    values[label] = (
                        {name: left[name] - right[name] for name in DIMENSIONS}
                        if left is not None and right is not None
                        else None
                    )
                contrasts.append(values)
            except Exception as error:
                item.update(
                    status="failed",
                    error={"type": type(error).__name__, "message": str(error)},
                )
                if stage in item["runs"] and item["runs"][stage]["status"] == "running":
                    item["runs"][stage]["status"] = "failed"
            item["phase_costs"] = {}
            for stage, run in item["runs"].items():
                run_dir = self.output_root / "runs" / run["run_id"]
                trajectory = run_dir / "trajectory.jsonl"
                rows = (
                    [json.loads(line) for line in trajectory.read_text().splitlines()]
                    if trajectory.is_file()
                    else []
                )
                item["phase_costs"][stage] = {}
                for role, field_name in (
                    ("candidate", "model_calls"),
                    ("observer", "observer_calls"),
                    ("audience", "audience_calls"),
                ):
                    calls = [call for row in rows for call in row.get(field_name, [])]
                    complete = all(
                        call.get("input_tokens") is not None
                        and call.get("output_tokens") is not None
                        for call in calls
                    )
                    item["phase_costs"][stage][role] = {
                        "calls": len(calls),
                        "tokens": sum(
                            call["input_tokens"] + call["output_tokens"]
                            for call in calls
                        )
                        if complete
                        else None,
                        "usage_complete": complete,
                    }
            item["standalone_condition_costs"] = {}
            for condition, preparation in (
                ("source_reference", "source_preparation"),
                ("target_cold", None),
                ("target_transfer", "source_preparation"),
                ("target_transfer_hidden", "source_preparation"),
                ("target_native", "target_preparation"),
            ):
                components = [preparation, condition] if preparation else [condition]
                if not all(stage in item["phase_costs"] for stage in components):
                    continue
                cost = {
                    "components": components,
                    "actions": sum(
                        item["runs"][stage]["ticks_completed"] for stage in components
                    )
                    if all(
                        "ticks_completed" in item["runs"][stage] for stage in components
                    )
                    else None,
                }
                for role in ("candidate", "observer", "audience"):
                    parts = [item["phase_costs"][stage][role] for stage in components]
                    complete = all(part["usage_complete"] for part in parts)
                    cost[role] = {
                        "calls": sum(part["calls"] for part in parts),
                        "tokens": sum(part["tokens"] for part in parts)
                        if complete
                        else None,
                        "usage_complete": complete,
                    }
                item["standalone_condition_costs"][condition] = cost
            items.append(item)
            self._write(self.output_root / "progress.json", {"items": items})
        report = {
            "protocol_version": TRANSFER_VERSION,
            "experiment_id": plan.experiment_id,
            "evaluation_status": "uncalibrated-development",
            "axis": plan.axis,
            "score_definition": "observer_delta_per_actual_exposure_in_equal_action_windows",
            "successful_pairs": len(pairs),
            "requested_seeds": len(plan.seeds),
            "failed_seeds": sum(item["status"] == "failed" for item in items),
            "incomplete_seeds": sum(
                item["status"] == "incomplete_measurement" for item in items
            ),
            "paired_transfer": paired_transfer_report(pairs) if pairs else None,
            "contrasts": {},
            "items": items,
        }
        for label in (
            "source_experience_effect_initial",
            "source_experience_effect_final",
            "comment_feedback_effect_final",
            "target_experience_effect_initial",
        ):
            complete = [item[label] for item in contrasts if item[label] is not None]
            report["contrasts"][label] = (
                {
                    name: _summary([item[name] for item in complete])
                    for name in DIMENSIONS
                }
                if complete
                else None
            )
        self._write(self.output_root / "transfer-report.json", report)
        return report

    @staticmethod
    def _write(path, value):
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        temporary.replace(path)
