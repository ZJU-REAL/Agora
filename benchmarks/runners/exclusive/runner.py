from __future__ import annotations

import json
import hashlib
import platform as runtime_platform
import sys
import time
import sqlite3
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from benchmarks.budget import EpisodeBudget
from benchmarks.artifacts import WorldArtifact
from benchmarks.metrics.report import write_run_report
from benchmarks.multimodal import (
    artifact_asset_parts,
    post_media_parts,
    sandbox_observation_parts,
)
from benchmarks.protocol import (
    ActorRole,
    CandidateAction,
    CandidatePolicy,
    EpisodeManifest,
    ExposureMode,
)
from benchmarks.state import (
    ObserverJudgment,
    ObserverPolicy,
    SocialState,
    StateDelta,
    StateTransition,
)
from oasis import AgoraOasis
from oasis.agora_types import AssetInput
from oasis.audience import ScriptedDevelopmentAudience
from oasis import __version__ as oasis_version


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    ticks_completed: int
    action_count: int
    output_dir: Path


ENGINE_VERSION = "social-feedback-v1"


class ExclusiveRunner:
    """Runs one candidate in a private clone of a frozen social world."""

    def __init__(self, artifact: WorldArtifact, output_root: str | Path):
        self.artifact = artifact
        self.output_root = Path(output_root)

    def validate(self, manifest: EpisodeManifest, candidate: CandidatePolicy) -> None:
        manifest.validate()
        artifact_manifest = self.artifact.validate()
        self._validate_compatibility(manifest, artifact_manifest)
        candidate_actor = next(
            actor for actor in manifest.actors if actor.role == ActorRole.CANDIDATE
        )
        if candidate.policy_id != candidate_actor.policy_id or (
            candidate.policy_version != candidate_actor.policy_version
        ):
            raise ValueError("Candidate policy does not match episode manifest")

    async def run(
        self,
        manifest: EpisodeManifest,
        candidate: CandidatePolicy,
        observer: ObserverPolicy | None = None,
        resume: bool = False,
        audience_policy=None,
    ) -> RunResult:
        self.validate(manifest, candidate)
        artifact_manifest = self.artifact.manifest
        candidate_actor = next(
            actor for actor in manifest.actors if actor.role == ActorRole.CANDIDATE
        )
        audience_policy = audience_policy or ScriptedDevelopmentAudience()
        budget = EpisodeBudget(manifest.metadata.get("budget", {}), manifest.max_ticks)

        output_dir = self.output_root / manifest.run_id
        trajectory_path = output_dir / "trajectory.jsonl"
        if resume:
            self._validate_resume(output_dir, manifest)
            provenance = json.loads((output_dir / "provenance.json").read_text())
            if provenance.get("runtime_fingerprint") != self._runtime_fingerprint(
                candidate, observer, audience_policy
            ):
                raise ValueError(
                    "Resume model, observer or provider configuration changed"
                )
            if provenance.get("source_fingerprint") != self._source_fingerprint():
                raise ValueError("Resume implementation changed; start a new run")
            if provenance.get("artifact_manifest_sha256") != self._file_hash(
                self.artifact.manifest_path
            ):
                raise ValueError("Resume artifact metadata changed")
            if (
                provenance.get("audience_policy_id"),
                provenance.get("audience_policy_version"),
            ) != (audience_policy.policy_id, audience_policy.policy_version):
                raise ValueError("Resume audience policy does not match")
            previous_result = json.loads((output_dir / "result.json").read_text())
            if previous_result["status"] == "completed":
                if (
                    not (output_dir / "metrics.json").is_file()
                    or not (output_dir / "attribution.json").is_file()
                ):
                    write_run_report(output_dir)
                return RunResult(
                    manifest.run_id,
                    "completed",
                    previous_result["ticks_completed"],
                    previous_result["action_count"],
                    output_dir,
                )
        else:
            self.artifact.clone_episode(output_dir, manifest.run_id)
            manifest.write(output_dir / "manifest.json")
            (output_dir / "provenance.json").write_text(
                json.dumps(
                    {
                        "engine_version": ENGINE_VERSION,
                        "artifact_manifest_sha256": self._file_hash(
                            self.artifact.manifest_path
                        ),
                        "runtime_fingerprint": self._runtime_fingerprint(
                            candidate, observer, audience_policy
                        ),
                        "audience_policy_id": audience_policy.policy_id,
                        "audience_policy_version": audience_policy.policy_version,
                        "python_version": sys.version.split()[0],
                        "runtime_platform": runtime_platform.platform(),
                        "agora_oasis_version": oasis_version,
                        "protocol_version": manifest.protocol_version,
                        "world_artifact_id": manifest.world_artifact_id,
                        "world_artifact_version": manifest.world_artifact_version,
                        "candidate_policy_id": candidate.policy_id,
                        "candidate_policy_version": candidate.policy_version,
                        "observer_pool_version": manifest.observer_pool_version,
                        "exposure_mode": manifest.exposure_mode.value,
                        "exposure_policy_version": manifest.exposure_policy_version,
                        "source_fingerprint": self._source_fingerprint(),
                        "dependency_lock_sha256": self._file_hash(
                            Path(__file__).parents[3] / "poetry.lock"
                        ),
                        "configuration_fingerprints": {
                            key: value
                            for key, value in manifest.metadata.items()
                            if key.endswith("_sha256")
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        sandbox = AgoraOasis.local("world", output_dir, preset=manifest.platform)
        if not resume:
            sandbox.set_seed(manifest.seed)
        audience_policy.sandbox = sandbox
        prior_records = self._step_records(trajectory_path) if resume else []
        all_prior = (
            [
                json.loads(line)
                for line in trajectory_path.read_text(encoding="utf-8").splitlines()
            ]
            if resume
            else []
        )
        checkpoint_path = output_dir / "checkpoint.db"
        marker_path = output_dir / "checkpoint.json"
        if resume and marker_path.is_file():
            marker = json.loads(marker_path.read_text())
            if marker["step"] == len(prior_records):
                if not all_prior or all_prior[-1].get("record_type") != "error":
                    sandbox.close()
                    raise ValueError(
                        "Interrupted step has unrecorded usage; start a new run"
                    )
                restore = sqlite3.connect(checkpoint_path)
                restore.backup(sandbox.platform.db)
                restore.close()
        if sandbox.current_tick != artifact_manifest.tick + len(prior_records):
            sandbox.close()
            raise ValueError("Episode world and trajectory checkpoints disagree")
        try:
            for record in all_prior:
                budget.charge_calls(record.get("model_calls", []))
        except Exception:
            sandbox.close()
            raise
        budget.actions = len(prior_records)
        self._restore_provider_counts(candidate, observer, audience_policy, all_prior)
        initial_followers = sandbox.platform.db.execute(
            "SELECT num_followers FROM user WHERE user_id = ?",
            (candidate_actor.user_id,),
        ).fetchone()[0]
        history = [
            {
                "step": record["step"],
                "action": record["action"],
                "outcome": record["outcome"],
            }
            for record in prior_records
        ]
        task = {
            **artifact_manifest.metadata.get("task", {}),
            **manifest.metadata.get("task", {}),
        }
        culture = {
            **artifact_manifest.metadata.get("culture", {}),
            **manifest.metadata.get("culture", {}),
        }
        task.setdefault(
            "objective", "Operate the account and respond to audience feedback."
        )
        termination_reason = "max_ticks"
        checkpoint = sqlite3.connect(checkpoint_path)
        model_calls = []
        action_count = len(prior_records)
        ticks_completed = len(prior_records)
        status = "running"
        social_states = {
            actor.actor_id: SocialState()
            for actor in manifest.actors
            if actor.role == ActorRole.NPC
        }
        pending_judgments: list[tuple[int, str, Any]] = []
        for record in prior_records:
            for transition in record.get("state_transitions", []):
                social_states[transition["target_actor_id"]] = SocialState(
                    **transition["after"]
                )
        if prior_records:
            pending_judgments = [
                (
                    int(item["due_step"]),
                    item["action_id"],
                    self._judgment_from_dict(item["judgment"]),
                )
                for item in prior_records[-1].get("pending_judgments", [])
            ]
        try:
            for step in range(ticks_completed, manifest.max_ticks):
                if budget.exhausted():
                    termination_reason = "budget_exhausted"
                    break
                client = getattr(candidate, "client", None)
                if (
                    hasattr(client, "limits")
                    and client.request_count >= client.limits.max_requests
                ):
                    termination_reason = "provider_budget_exhausted"
                    break
                sandbox.platform.db.backup(checkpoint)
                marker_temp = output_dir / "checkpoint.json.tmp"
                marker_temp.write_text(json.dumps({"step": step}))
                marker_temp.replace(marker_path)
                model_calls = []
                await self._inject_feedback(sandbox, manifest, candidate_actor.user_id)
                if manifest.exposure_mode == ExposureMode.CONTROLLED:
                    content_pool = self._content_pool_post_ids(
                        sandbox,
                        candidate_actor.user_id,
                        artifact_manifest.metadata["controlled_post_ids"],
                    )
                    observation = sandbox.observe_ranked_pool(
                        candidate_actor.user_id, content_pool
                    )
                else:
                    observation = sandbox.observe(candidate_actor.user_id)
                if manifest.metadata.get("feedback_condition", "visible") == "hidden":
                    observation = replace(
                        observation,
                        feed=self._hide_feedback(
                            observation.feed, candidate_actor.user_id
                        ),
                        own_recent_posts=self._hide_feedback(
                            observation.own_recent_posts, candidate_actor.user_id
                        ),
                    )
                started = time.monotonic()
                budget.prepare(candidate)
                action = await candidate.act(
                    observation,
                    {
                        "scenario_id": manifest.scenario_id,
                        "seed": manifest.seed,
                        "step": step,
                        "task": task,
                        "culture": culture,
                        "history": (
                            self._hide_feedback(history, candidate_actor.user_id)
                            if manifest.metadata.get("feedback_condition") == "hidden"
                            else history
                        ),
                        "remaining_budget": budget.remaining(),
                        "available_actions": sandbox.available_actions(),
                        "available_asset_keys": artifact_manifest.metadata.get(
                            "candidate_asset_keys", []
                        ),
                        "multimodal_parts": (
                            (
                                sandbox_observation_parts(sandbox, observation)
                                + artifact_asset_parts(
                                    self.artifact,
                                    artifact_manifest.metadata.get(
                                        "candidate_asset_keys", []
                                    ),
                                )
                            )
                            if getattr(candidate, "supports_multimodal_context", False)
                            else []
                        ),
                    },
                )
                model_calls = (
                    candidate.drain_call_records()
                    if hasattr(candidate, "drain_call_records")
                    else []
                )
                budget.charge_calls(model_calls)
                action_id = f"{manifest.run_id}-action-{step}"
                direct_user_id = self._direct_target_user_id(sandbox, action)
                actor_by_user_id = {
                    actor.user_id: actor.actor_id
                    for actor in manifest.actors
                    if actor.user_id is not None
                }
                direct_actor_id = actor_by_user_id.get(direct_user_id)
                outcome = await self._apply_action(
                    sandbox, candidate_actor.user_id, action
                )
                media_post_id = outcome.get("post_id") or action.arguments.get(
                    "post_id"
                )
                observer_media = (
                    post_media_parts(sandbox, int(media_post_id))
                    if media_post_id is not None
                    and observer is not None
                    and getattr(observer, "supports_multimodal_context", False)
                    else []
                )
                transitions = []
                due = [item for item in pending_judgments if item[0] <= step]
                pending_judgments = [
                    item for item in pending_judgments if item[0] > step
                ]
                for _, source_action_id, judgment in due:
                    transitions.append(
                        self._apply_judgment(social_states, source_action_id, judgment)
                    )
                controlled_ids = (
                    artifact_manifest.metadata["controlled_post_ids"]
                    if manifest.exposure_mode == ExposureMode.CONTROLLED
                    else None
                )
                content_pool = self._content_pool_post_ids(
                    sandbox, candidate_actor.user_id, controlled_ids
                )
                npc_user_ids = [
                    actor.user_id
                    for actor in manifest.actors
                    if actor.role == ActorRole.NPC and actor.user_id is not None
                ]
                content = (
                    action.arguments.get("content")
                    or action.arguments.get("body")
                    or action.arguments.get("quote_body")
                )
                if action.action_type == "create_post":
                    content = " ".join(
                        filter(None, [action.arguments.get("title"), content])
                    )
                    content = content or "[Media post]"
                focused_action = (
                    {
                        "post_id": media_post_id,
                        "author_id": candidate_actor.user_id,
                        "content": content,
                    }
                    if content and media_post_id
                    else None
                )
                tick_result = await sandbox.advance(
                    content_pool_post_ids=content_pool,
                    actor_user_ids=npc_user_ids,
                    audience_policy=audience_policy,
                    reaction_action=focused_action,
                )
                observed = {
                    item["user_id"]: item
                    for item in tick_result.actions
                    if item["action"] == "observe_feed"
                }
                reactions = {
                    item["user_id"]: item
                    for item in tick_result.actions
                    if item["action"] == "audience_reaction" and item["focused_action"]
                }
                if observer is not None:
                    for actor in manifest.actors:
                        if (
                            actor.role != ActorRole.NPC
                            or actor.user_id not in reactions
                        ):
                            continue
                        exposure = observed[actor.user_id]
                        persona = exposure["persona"]
                        original_post = next(
                            (
                                item
                                for item in observation.feed
                                if item["post_id"] == media_post_id
                            ),
                            None,
                        )
                        judgments = await observer.judge(
                            action,
                            outcome,
                            {
                                "scenario_id": manifest.scenario_id,
                                "step": step,
                                "target_actor_id": actor.actor_id,
                                "is_direct_target": actor.actor_id == direct_actor_id,
                                "persona": persona,
                                "culture": {**culture, **persona.get("culture", {})},
                                "relationship_before": asdict(
                                    social_states[actor.actor_id]
                                ),
                                "history": history,
                                "original_post": original_post,
                                "observed_reaction": reactions[actor.user_id][
                                    "public_actions"
                                ],
                                "multimodal_parts": observer_media,
                            },
                        )
                        for judgment in judgments:
                            if judgment.target_actor_id != actor.actor_id:
                                raise ValueError("Observer judged an unexposed target")
                            if judgment.delay_ticks:
                                pending_judgments.append(
                                    (step + judgment.delay_ticks, action_id, judgment)
                                )
                            else:
                                transitions.append(
                                    self._apply_judgment(
                                        social_states, action_id, judgment
                                    )
                                )
                observer_calls = (
                    observer.drain_call_records()
                    if observer is not None and hasattr(observer, "drain_call_records")
                    else []
                )
                audience_calls = (
                    audience_policy.drain_call_records()
                    if hasattr(audience_policy, "drain_call_records")
                    else []
                )
                budget.actions += 1
                history.append(
                    {"step": step, "action": asdict(action), "outcome": outcome}
                )
                action_count += 1
                ticks_completed += 1
                self._append_jsonl(
                    trajectory_path,
                    {
                        "record_type": "step",
                        "step": step,
                        "tick_before": observation.tick,
                        "action_id": action_id,
                        "candidate_id": manifest.candidate_id,
                        "observation": asdict(observation),
                        "action": asdict(action),
                        "model_calls": model_calls,
                        "observer_calls": observer_calls,
                        "audience_calls": audience_calls,
                        "remaining_budget": budget.remaining(),
                        "initial_followers": (
                            prior_records[0].get("initial_followers", initial_followers)
                            if prior_records
                            else initial_followers
                        ),
                        "pending_judgments": [
                            {
                                "due_step": due_step,
                                "action_id": source_action_id,
                                "judgment": asdict(judgment),
                            }
                            for due_step, source_action_id, judgment in pending_judgments
                        ],
                        "outcome": outcome,
                        "state_transitions": [asdict(item) for item in transitions],
                        "environment_actions": tick_result.actions,
                        "events": tick_result.events,
                        "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                    },
                )
                if action.action_type == "stop":
                    termination_reason = "candidate_stop"
                    break
            terminal_due = [
                item for item in pending_judgments if item[0] <= ticks_completed
            ]
            pending_judgments = [
                item for item in pending_judgments if item[0] > ticks_completed
            ]
            if terminal_due:
                terminal_transitions = [
                    self._apply_judgment(social_states, source_action_id, judgment)
                    for _, source_action_id, judgment in terminal_due
                ]
                self._append_jsonl(
                    trajectory_path,
                    {
                        "record_type": "terminal_effects",
                        "tick": sandbox.current_tick,
                        "state_transitions": [
                            asdict(item) for item in terminal_transitions
                        ],
                        "pending_judgments": [
                            {
                                "due_step": due_step,
                                "action_id": source_action_id,
                                "judgment": asdict(judgment),
                            }
                            for due_step, source_action_id, judgment in pending_judgments
                        ],
                    },
                )
            status = "completed"
        except Exception as error:
            status = "failed"
            sandbox.platform.db.rollback()
            previous_media = {
                row[0]
                for row in checkpoint.execute("SELECT object_key FROM media_asset")
            }
            added_media = [
                row[0]
                for row in sandbox.platform.db.execute(
                    "SELECT object_key FROM media_asset"
                )
                if row[0] not in previous_media
            ]
            checkpoint.backup(sandbox.platform.db)
            for object_key in added_media:
                try:
                    sandbox.media.path_for(object_key).unlink()
                except FileNotFoundError:
                    pass
            failed_calls = (
                candidate.drain_call_records()
                if hasattr(candidate, "drain_call_records")
                else []
            )
            try:
                budget.charge_calls(failed_calls)
            except ValueError:
                pass  # The original failure is recorded; counters are still charged.
            self._append_jsonl(
                trajectory_path,
                {
                    "record_type": "error",
                    "error_type": type(error).__name__,
                    "message": str(error),
                    "ticks_completed": ticks_completed,
                    "model_calls": model_calls + failed_calls,
                    "observer_calls": (
                        observer.drain_call_records()
                        if observer is not None
                        and hasattr(observer, "drain_call_records")
                        else []
                    ),
                    "audience_calls": (
                        audience_policy.drain_call_records()
                        if hasattr(audience_policy, "drain_call_records")
                        else []
                    ),
                },
            )
            raise
        finally:
            checkpoint.close()
            sandbox.close()
            (output_dir / "result.json").write_text(
                json.dumps(
                    {
                        "run_id": manifest.run_id,
                        "status": status,
                        "ticks_completed": ticks_completed,
                        "action_count": action_count,
                        "resumed": resume,
                        "termination_reason": termination_reason,
                        "budget": {
                            "limits": budget.limits,
                            "calls": budget.calls,
                            "tokens": budget.tokens,
                            "usage_complete": not budget.unknown_usage,
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        write_run_report(output_dir)
        return RunResult(
            manifest.run_id, status, ticks_completed, action_count, output_dir
        )

    @staticmethod
    def _hide_feedback(value, candidate_id):
        if isinstance(value, list):
            return [
                ExclusiveRunner._hide_feedback(item, candidate_id) for item in value
            ]
        if isinstance(value, dict):
            return {
                name: (
                    ExclusiveRunner._hide_feedback(
                        [
                            comment
                            for comment in item
                            if comment.get("author_id") == candidate_id
                        ],
                        candidate_id,
                    )
                    if name in {"comments", "replies"} and isinstance(item, list)
                    else ExclusiveRunner._hide_feedback(item, candidate_id)
                )
                for name, item in value.items()
            }
        return value

    @staticmethod
    def _runtime_fingerprint(candidate, observer, audience):
        def describe(policy):
            client = getattr(policy, "client", None)
            value = {
                name: getattr(policy, name, None)
                for name in (
                    "policy_id",
                    "policy_version",
                    "observer_id",
                    "observer_version",
                    "max_attempts",
                    "supports_multimodal_context",
                    "supports_vision",
                    "parse_failure_mode",
                    "expected_model_id",
                )
            }
            value["class"] = type(policy).__qualname__
            if client is not None:
                value["provider"] = {
                    name: getattr(client, name, None)
                    for name in (
                        "model_id",
                        "model_path",
                        "base_url",
                        "url",
                        "auth_style",
                        "trust_env",
                        "extra_body",
                        "api_key_env",
                    )
                }
                if hasattr(client, "limits"):
                    value["limits"] = asdict(
                        getattr(client, "configured_limits", client.limits)
                    )
            if hasattr(policy, "observers"):
                value["members"] = [describe(member) for member in policy.observers]
                value["weights"] = [
                    [*identity, weight]
                    for identity, weight in sorted(policy.weights.items())
                ]
            return value

        encoded = json.dumps(
            [describe(item) for item in (candidate, observer, audience)], sort_keys=True
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _restore_provider_counts(candidate, observer, audience, records):
        for policy in (
            candidate,
            audience,
            *getattr(observer, "observers", (observer,)),
        ):
            client = getattr(policy, "client", None)
            if hasattr(client, "configured_limits"):
                client.limits = client.configured_limits
        if hasattr(getattr(candidate, "client", None), "request_count"):
            candidate.client.request_count = sum(
                len(row.get("model_calls", [])) for row in records
            )
        if hasattr(getattr(audience, "client", None), "request_count"):
            audience.client.request_count = sum(
                len(row.get("audience_calls", [])) for row in records
            )
        members = getattr(observer, "observers", (observer,))
        for member in members:
            if hasattr(getattr(member, "client", None), "request_count"):
                member.client.request_count = sum(
                    1
                    for row in records
                    for call in row.get("observer_calls", [])
                    if call.get("observer_id", member.observer_id) == member.observer_id
                )

    @staticmethod
    async def _inject_feedback(sandbox, manifest, candidate_user_id):
        actors = {
            actor.actor_id: actor
            for actor in manifest.actors
            if actor.role == ActorRole.NPC
        }
        for index, event in enumerate(manifest.metadata.get("feedback_schedule", [])):
            if event["tick"] != sandbox.current_tick:
                continue
            actor = actors[event["actor_id"]]
            post_id = event["post_id"]
            if post_id == "latest_candidate":
                row = sandbox.platform.db.execute(
                    "SELECT post_id FROM post WHERE user_id = ? "
                    "ORDER BY post_id DESC LIMIT 1",
                    (candidate_user_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Scheduled feedback has no candidate post")
                post_id = row[0]
            sandbox.view_post(actor.user_id, post_id)
            result = await sandbox.create_comment(
                actor.user_id, post_id, event["content"]
            )
            if not result.get("success"):
                raise ValueError("Scheduled feedback could not be published")
            sandbox._record_event(
                "scheduled_feedback",
                actor.user_id,
                "post",
                post_id,
                {
                    "schedule_index": index,
                    "content": event["content"],
                    "comment_id": result["comment_id"],
                    "valence": event.get("valence", "negative"),
                    "candidate_user_id": candidate_user_id,
                },
            )

    @staticmethod
    def _validate_compatibility(manifest: EpisodeManifest, artifact: Any) -> None:
        pairs = (
            (
                "world_artifact_version",
                manifest.world_artifact_version,
                artifact.world_artifact_version,
            ),
            ("world_artifact_id", manifest.world_artifact_id, artifact.artifact_id),
            ("platform", manifest.platform, artifact.platform),
            (
                "observer_pool_version",
                manifest.observer_pool_version,
                artifact.observer_pool_version,
            ),
            ("exposure_mode", manifest.exposure_mode.value, artifact.exposure_mode),
            (
                "exposure_policy_version",
                manifest.exposure_policy_version,
                artifact.exposure_policy_version,
            ),
        )
        for name, requested, actual in pairs:
            if requested != actual:
                raise ValueError(
                    f"{name} mismatch: requested={requested!r}, actual={actual!r}"
                )

    async def _apply_action(
        self, sandbox: AgoraOasis, user_id: int, action: CandidateAction
    ) -> dict[str, Any]:
        args = dict(action.arguments)
        if action.action_type not in set(sandbox.available_actions()) | {
            "do_nothing",
            "stop",
        }:
            raise ValueError(f"Unavailable platform action: {action.action_type}")
        if "post_id" in args:
            sandbox.view_post(user_id, args["post_id"])
        if action.action_type == "create_post":
            assets = []
            for item in args.pop("assets", []):
                if not isinstance(item, dict):
                    raise ValueError("Candidate asset entries must be objects")
                if "path" in item:
                    raise ValueError(
                        "Candidate assets must use artifact asset_key, not path"
                    )
                asset_key = item.get("asset_key")
                if not isinstance(asset_key, str) or not asset_key:
                    raise ValueError("Candidate assets require a non-empty asset_key")
                role = item.get("role", "content")
                if role not in {"content", "cover"}:
                    raise ValueError(f"Unsupported candidate asset role: {role}")
                allowed = self.artifact.manifest.metadata.get(
                    "candidate_asset_keys", []
                )
                if asset_key not in allowed:
                    raise ValueError(f"Unavailable candidate asset: {asset_key}")
                path = (self.artifact.root / "resources" / asset_key).resolve()
                resource_root = (self.artifact.root / "resources").resolve()
                if resource_root not in path.parents or not path.is_file():
                    raise ValueError(f"Invalid artifact asset: {asset_key}")
                authored_metadata = self.artifact.manifest.metadata.get(
                    "candidate_asset_metadata", {}
                ).get(asset_key, {})
                assets.append(
                    AssetInput(
                        path=path,
                        role=role,
                        caption=item.get("caption"),
                        alt_text=authored_metadata.get("alt_text"),
                        transcript=authored_metadata.get("transcript"),
                    )
                )
            args["assets"] = assets
            post_id = sandbox.create_post(user_id, **args)
            return {"success": True, "post_id": post_id}
        if action.action_type in {"create_comment", "reply_comment"}:
            return await sandbox.create_comment(user_id, **args)
        if action.action_type == "like_post":
            return {"success": sandbox.like_post(user_id, args["post_id"])}
        if action.action_type == "unlike_post":
            return {"success": sandbox.unlike_post(user_id, args["post_id"])}
        if action.action_type == "dislike_post":
            return {"success": sandbox.dislike_post(user_id, args["post_id"])}
        if action.action_type == "collect_post":
            return {"success": sandbox.collect_post(user_id, args["post_id"])}
        if action.action_type == "uncollect_post":
            return {"success": sandbox.uncollect_post(user_id, args["post_id"])}
        if action.action_type == "follow_user":
            return {"success": sandbox.follow_user(user_id, args["followee_id"])}
        if action.action_type == "unfollow_user":
            return {"success": sandbox.unfollow_user(user_id, args["followee_id"])}
        if action.action_type in {"repost", "quote_post"}:
            post_id = sandbox.repost(
                user_id,
                args["post_id"],
                quote_body=args.get("quote_body")
                if action.action_type == "quote_post"
                else None,
                community=args.get("community"),
            )
            return {"success": True, "post_id": post_id}
        if action.action_type == "search_posts":
            return {
                "success": True,
                "posts": sandbox.search_posts(
                    user_id,
                    args["query"],
                    args.get("community"),
                    int(args.get("limit", 20)),
                ),
            }
        if action.action_type == "pin_comment":
            return {"success": sandbox.pin_comment(user_id, args["comment_id"])}
        if action.action_type == "view_post":
            return {
                "success": True,
                "post": sandbox.view_post(user_id, args["post_id"]),
            }
        if action.action_type in {"do_nothing", "stop"}:
            return {"success": True}
        raise ValueError(f"Unsupported candidate action: {action.action_type}")

    @staticmethod
    def _content_pool_post_ids(
        sandbox: AgoraOasis, candidate_user_id: int, frozen_post_ids: list[int] | None
    ) -> list[int]:
        """Mix frozen human content with posts authored by the candidate."""
        if frozen_post_ids is None:
            rows = sandbox.platform.db.execute(
                "SELECT post_id FROM post ORDER BY post_id"
            ).fetchall()
            return [int(row[0]) for row in rows]
        candidate_posts = sandbox.platform.db.execute(
            "SELECT post_id FROM post WHERE user_id = ? "
            "AND visibility = 'public' ORDER BY post_id",
            (candidate_user_id,),
        ).fetchall()
        return list(
            dict.fromkeys(
                [
                    *(int(post_id) for post_id in frozen_post_ids),
                    *(int(row[0]) for row in candidate_posts),
                ]
            )
        )

    @staticmethod
    def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _step_records(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [
            record
            for record in (
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            )
            if record.get("record_type") == "step"
        ]

    @staticmethod
    def _validate_resume(output_dir: Path, manifest: EpisodeManifest) -> None:
        if not output_dir.is_dir():
            raise FileNotFoundError(f"No episode to resume: {output_dir}")
        stored = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        requested = json.loads(json.dumps(asdict(manifest)))
        if stored != requested:
            raise ValueError("Resume manifest does not match stored episode")
        provenance = json.loads((output_dir / "provenance.json").read_text())
        if provenance.get("engine_version") != ENGINE_VERSION:
            raise ValueError("Cannot resume an episode from a different engine version")
        if not (output_dir / "world" / "sandbox.db").is_file():
            raise ValueError("Resume episode has no writable world database")

    @staticmethod
    def _direct_target_user_id(
        sandbox: AgoraOasis, action: CandidateAction
    ) -> int | None:
        if action.arguments.get("parent_comment_id") is not None:
            row = sandbox.platform.db.execute(
                "SELECT user_id FROM comment WHERE comment_id = ?",
                (action.arguments["parent_comment_id"],),
            ).fetchone()
            return int(row[0]) if row else None
        post_id = action.arguments.get("post_id")
        if post_id is None:
            return None
        row = sandbox.platform.db.execute(
            "SELECT user_id FROM post WHERE post_id = ?", (post_id,)
        ).fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _apply_judgment(
        states: dict[str, SocialState], action_id: str, judgment: Any
    ) -> StateTransition:
        before = states[judgment.target_actor_id]
        after = before.apply(judgment.delta, judgment.confidence)
        states[judgment.target_actor_id] = after
        return StateTransition(
            action_id, judgment.target_actor_id, before, after, judgment
        )

    @staticmethod
    def _judgment_from_dict(value: dict[str, Any]) -> ObserverJudgment:
        return ObserverJudgment(
            observer_id=value["observer_id"],
            observer_version=value["observer_version"],
            target_actor_id=value["target_actor_id"],
            delta=StateDelta(**value["delta"]),
            confidence=float(value["confidence"]),
            evidence=value["evidence"],
            delay_ticks=int(value.get("delay_ticks", 0)),
            effect_scope=value.get("effect_scope", "direct"),
        )

    @staticmethod
    def _file_hash(path: Path) -> str | None:
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _source_fingerprint() -> str:
        root = Path(__file__).parents[3]
        digest = hashlib.sha256()
        for package in (root / "oasis", root / "benchmarks"):
            for path in sorted(package.rglob("*.py")):
                digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                digest.update(path.read_bytes())
        return digest.hexdigest()
