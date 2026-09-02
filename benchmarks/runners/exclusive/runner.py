from __future__ import annotations

import json
import hashlib
import platform as runtime_platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmarks.artifacts import WorldArtifact
from benchmarks.metrics.report import write_run_report
from benchmarks.multimodal import (artifact_asset_parts, post_media_parts,
                                   sandbox_observation_parts)
from benchmarks.protocol import (ActorRole, CandidateAction, CandidatePolicy,
                                 EpisodeManifest, ExposureMode)
from benchmarks.state import (ObserverJudgment, ObserverPolicy, SocialState,
                              StateDelta, StateTransition)
from oasis import AgoraOasis
from oasis.agora_types import AssetInput
from oasis import __version__ as oasis_version


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    ticks_completed: int
    action_count: int
    output_dir: Path


class ExclusiveRunner:
    """Runs one candidate in a private clone of a frozen social world."""

    def __init__(self, artifact: WorldArtifact, output_root: str | Path):
        self.artifact = artifact
        self.output_root = Path(output_root)

    def validate(self, manifest: EpisodeManifest,
                 candidate: CandidatePolicy) -> None:
        manifest.validate()
        artifact_manifest = self.artifact.validate()
        self._validate_compatibility(manifest, artifact_manifest)
        candidate_actor = next(actor for actor in manifest.actors
                               if actor.role == ActorRole.CANDIDATE)
        if candidate.policy_id != candidate_actor.policy_id or (
                candidate.policy_version != candidate_actor.policy_version):
            raise ValueError("Candidate policy does not match episode manifest")

    async def run(self, manifest: EpisodeManifest,
                  candidate: CandidatePolicy,
                  observer: ObserverPolicy | None = None,
                  resume: bool = False) -> RunResult:
        self.validate(manifest, candidate)
        artifact_manifest = self.artifact.manifest
        candidate_actor = next(actor for actor in manifest.actors
                               if actor.role == ActorRole.CANDIDATE)

        output_dir = self.output_root / manifest.run_id
        trajectory_path = output_dir / "trajectory.jsonl"
        if resume:
            self._validate_resume(output_dir, manifest)
        else:
            self.artifact.clone_episode(output_dir, manifest.run_id)
            manifest.write(output_dir / "manifest.json")
            (output_dir / "provenance.json").write_text(json.dumps({
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
                    Path(__file__).parents[3] / "poetry.lock"),
                "configuration_fingerprints": {
                    key: value for key, value in manifest.metadata.items()
                    if key.endswith("_sha256")
                },
            }, indent=2) + "\n", encoding="utf-8")
        sandbox = AgoraOasis.local("world", output_dir,
                                   preset=manifest.platform)
        prior_records = self._step_records(trajectory_path) if resume else []
        action_count = len(prior_records)
        ticks_completed = len(prior_records)
        status = "running"
        social_states = {
            actor.actor_id: SocialState()
            for actor in manifest.actors if actor.role == ActorRole.NPC
        }
        pending_judgments: list[tuple[int, str, Any]] = []
        for record in prior_records:
            for transition in record.get("state_transitions", []):
                social_states[transition["target_actor_id"]] = SocialState(
                    **transition["after"])
        if prior_records:
            pending_judgments = [(
                int(item["due_step"]), item["action_id"],
                self._judgment_from_dict(item["judgment"]))
                for item in prior_records[-1].get("pending_judgments", [])]
        try:
            for step in range(ticks_completed, manifest.max_ticks):
                if manifest.exposure_mode == ExposureMode.CONTROLLED:
                    content_pool = self._content_pool_post_ids(
                        sandbox, candidate_actor.user_id,
                        artifact_manifest.metadata["controlled_post_ids"])
                    observation = sandbox.observe_ranked_pool(
                        candidate_actor.user_id, content_pool)
                else:
                    observation = sandbox.observe(candidate_actor.user_id)
                started = time.monotonic()
                action = await candidate.act(observation, {
                    "scenario_id": manifest.scenario_id,
                    "seed": manifest.seed,
                    "step": step,
                    "available_actions": sandbox.available_actions(),
                    "available_asset_keys": artifact_manifest.metadata.get(
                        "candidate_asset_keys", []),
                    "multimodal_parts": ((
                        sandbox_observation_parts(sandbox, observation)
                        + artifact_asset_parts(
                            self.artifact, artifact_manifest.metadata.get(
                                "candidate_asset_keys", []))) if getattr(
                                    candidate, "supports_multimodal_context",
                                    False) else []),
                })
                model_calls = (candidate.drain_call_records()
                               if hasattr(candidate, "drain_call_records")
                               else [])
                action_id = f"{manifest.run_id}-action-{step}"
                direct_user_id = self._direct_target_user_id(sandbox, action)
                actor_by_user_id = {
                    actor.user_id: actor.actor_id for actor in manifest.actors
                    if actor.user_id is not None
                }
                direct_actor_id = actor_by_user_id.get(direct_user_id)
                outcome = await self._apply_action(
                    sandbox, candidate_actor.user_id, action)
                media_post_id = outcome.get("post_id") or action.arguments.get(
                    "post_id")
                observer_media = (post_media_parts(sandbox, int(media_post_id))
                                  if media_post_id is not None and observer
                                  is not None and getattr(
                                      observer, "supports_multimodal_context",
                                      False) else [])
                transitions = []
                due = [item for item in pending_judgments if item[0] <= step]
                pending_judgments = [item for item in pending_judgments
                                     if item[0] > step]
                for _, source_action_id, judgment in due:
                    transitions.append(self._apply_judgment(
                        social_states, source_action_id, judgment))
                if observer is not None:
                    for target_actor_id in social_states:
                        judgments = await observer.judge(action, outcome, {
                            "scenario_id": manifest.scenario_id,
                            "step": step,
                            "target_actor_id": target_actor_id,
                            "is_direct_target": target_actor_id == direct_actor_id,
                            "multimodal_parts": observer_media,
                        })
                        for judgment in judgments:
                            if judgment.delay_ticks:
                                pending_judgments.append((
                                    step + judgment.delay_ticks, action_id,
                                    judgment))
                            else:
                                transitions.append(self._apply_judgment(
                                    social_states, action_id, judgment))
                observer_calls = (observer.drain_call_records()
                                  if observer is not None
                                  and hasattr(observer, "drain_call_records")
                                  else [])
                controlled_ids = (artifact_manifest.metadata[
                    "controlled_post_ids"] if manifest.exposure_mode ==
                    ExposureMode.CONTROLLED else None)
                content_pool = self._content_pool_post_ids(
                    sandbox, candidate_actor.user_id, controlled_ids)
                npc_user_ids = [actor.user_id for actor in manifest.actors
                                if actor.role == ActorRole.NPC
                                and actor.user_id is not None]
                tick_result = await sandbox.advance(
                    content_pool_post_ids=content_pool,
                    actor_user_ids=npc_user_ids)
                action_count += 1
                ticks_completed += 1
                self._append_jsonl(trajectory_path, {
                    "record_type": "step",
                    "step": step,
                    "tick_before": observation.tick,
                    "action_id": action_id,
                    "candidate_id": manifest.candidate_id,
                    "observation": asdict(observation),
                    "action": asdict(action),
                    "model_calls": model_calls,
                    "observer_calls": observer_calls,
                    "pending_judgments": [{
                        "due_step": due_step, "action_id": source_action_id,
                        "judgment": asdict(judgment),
                    } for due_step, source_action_id, judgment
                        in pending_judgments],
                    "outcome": outcome,
                    "state_transitions": [asdict(item) for item in transitions],
                    "environment_actions": tick_result.actions,
                    "events": tick_result.events,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                })
                if action.action_type == "stop":
                    break
            terminal_due = [item for item in pending_judgments
                            if item[0] <= ticks_completed]
            pending_judgments = [item for item in pending_judgments
                                 if item[0] > ticks_completed]
            if terminal_due:
                terminal_transitions = [self._apply_judgment(
                    social_states, source_action_id, judgment)
                    for _, source_action_id, judgment in terminal_due]
                self._append_jsonl(trajectory_path, {
                    "record_type": "terminal_effects",
                    "tick": sandbox.current_tick,
                    "state_transitions": [asdict(item)
                                          for item in terminal_transitions],
                    "pending_judgments": [{
                        "due_step": due_step,
                        "action_id": source_action_id,
                        "judgment": asdict(judgment),
                    } for due_step, source_action_id, judgment
                        in pending_judgments],
                })
            status = "completed"
        except Exception as error:
            status = "failed"
            self._append_jsonl(trajectory_path, {
                "record_type": "error",
                "error_type": type(error).__name__,
                "message": str(error),
                "ticks_completed": ticks_completed,
                "model_calls": (candidate.drain_call_records()
                                if hasattr(candidate, "drain_call_records")
                                else []),
            })
            raise
        finally:
            sandbox.close()
            (output_dir / "result.json").write_text(json.dumps({
                "run_id": manifest.run_id,
                "status": status,
                "ticks_completed": ticks_completed,
                "action_count": action_count,
                "resumed": resume,
            }, indent=2) + "\n", encoding="utf-8")
        write_run_report(output_dir)
        return RunResult(manifest.run_id, status, ticks_completed,
                         action_count, output_dir)

    @staticmethod
    def _validate_compatibility(manifest: EpisodeManifest,
                                artifact: Any) -> None:
        pairs = (
            ("world_artifact_version", manifest.world_artifact_version,
             artifact.world_artifact_version),
            ("world_artifact_id", manifest.world_artifact_id,
             artifact.artifact_id),
            ("platform", manifest.platform, artifact.platform),
            ("observer_pool_version", manifest.observer_pool_version,
             artifact.observer_pool_version),
            ("exposure_mode", manifest.exposure_mode.value,
             artifact.exposure_mode),
            ("exposure_policy_version", manifest.exposure_policy_version,
             artifact.exposure_policy_version),
        )
        for name, requested, actual in pairs:
            if requested != actual:
                raise ValueError(
                    f"{name} mismatch: requested={requested!r}, actual={actual!r}")

    async def _apply_action(self, sandbox: AgoraOasis, user_id: int,
                            action: CandidateAction) -> dict[str, Any]:
        args = dict(action.arguments)
        if action.action_type == "create_post":
            assets = []
            for item in args.pop("assets", []):
                if not isinstance(item, dict):
                    raise ValueError("Candidate asset entries must be objects")
                if "path" in item:
                    raise ValueError(
                        "Candidate assets must use artifact asset_key, not path")
                asset_key = item.get("asset_key")
                if not isinstance(asset_key, str) or not asset_key:
                    raise ValueError(
                        "Candidate assets require a non-empty asset_key")
                role = item.get("role", "content")
                if role not in {"content", "cover"}:
                    raise ValueError(f"Unsupported candidate asset role: {role}")
                allowed = self.artifact.manifest.metadata.get(
                    "candidate_asset_keys", [])
                if asset_key not in allowed:
                    raise ValueError(f"Unavailable candidate asset: {asset_key}")
                path = (self.artifact.root / "resources" / asset_key).resolve()
                resource_root = (self.artifact.root / "resources").resolve()
                if resource_root not in path.parents or not path.is_file():
                    raise ValueError(f"Invalid artifact asset: {asset_key}")
                authored_metadata = self.artifact.manifest.metadata.get(
                    "candidate_asset_metadata", {}).get(asset_key, {})
                assets.append(AssetInput(
                    path=path, role=role, caption=item.get("caption"),
                    alt_text=authored_metadata.get("alt_text"),
                    transcript=authored_metadata.get("transcript")))
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
            return {"success": sandbox.uncollect_post(
                user_id, args["post_id"])}
        if action.action_type == "follow_user":
            return {"success": sandbox.follow_user(user_id, args["followee_id"])}
        if action.action_type == "unfollow_user":
            return {"success": sandbox.unfollow_user(
                user_id, args["followee_id"])}
        if action.action_type in {"repost", "quote_post"}:
            post_id = sandbox.repost(
                user_id, args["post_id"],
                quote_body=args.get("quote_body") if
                action.action_type == "quote_post" else None,
                community=args.get("community"))
            return {"success": True, "post_id": post_id}
        if action.action_type == "search_posts":
            return {"success": True, "posts": sandbox.search_posts(
                user_id, args["query"], args.get("community"),
                int(args.get("limit", 20)))}
        if action.action_type == "pin_comment":
            return {"success": sandbox.pin_comment(
                user_id, args["comment_id"])}
        if action.action_type == "view_post":
            return {"success": True, "post": sandbox.view_post(
                user_id, args["post_id"])}
        if action.action_type in {"do_nothing", "stop"}:
            return {"success": True}
        raise ValueError(f"Unsupported candidate action: {action.action_type}")

    @staticmethod
    def _content_pool_post_ids(sandbox: AgoraOasis, candidate_user_id: int,
                               frozen_post_ids: list[int] | None) -> list[int]:
        """Mix frozen human content with posts authored by the candidate."""
        if frozen_post_ids is None:
            rows = sandbox.platform.db.execute(
                "SELECT post_id FROM post ORDER BY post_id").fetchall()
            return [int(row[0]) for row in rows]
        candidate_posts = sandbox.platform.db.execute(
            "SELECT post_id FROM post WHERE user_id = ? "
            "AND visibility = 'public' ORDER BY post_id",
            (candidate_user_id, )).fetchall()
        return list(dict.fromkeys([
            *(int(post_id) for post_id in frozen_post_ids),
            *(int(row[0]) for row in candidate_posts),
        ]))

    @staticmethod
    def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _step_records(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [record for record in (
            json.loads(line) for line in path.read_text(
                encoding="utf-8").splitlines())
                if record.get("record_type") == "step"]

    @staticmethod
    def _validate_resume(output_dir: Path,
                         manifest: EpisodeManifest) -> None:
        if not output_dir.is_dir():
            raise FileNotFoundError(f"No episode to resume: {output_dir}")
        stored = json.loads((output_dir / "manifest.json").read_text(
            encoding="utf-8"))
        requested = json.loads(json.dumps(asdict(manifest)))
        if stored != requested:
            raise ValueError("Resume manifest does not match stored episode")
        if not (output_dir / "world" / "sandbox.db").is_file():
            raise ValueError("Resume episode has no writable world database")

    @staticmethod
    def _direct_target_user_id(sandbox: AgoraOasis,
                               action: CandidateAction) -> int | None:
        post_id = action.arguments.get("post_id")
        if post_id is None:
            return None
        row = sandbox.platform.db.execute(
            "SELECT user_id FROM post WHERE post_id = ?", (post_id, )).fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _apply_judgment(states: dict[str, SocialState], action_id: str,
                        judgment: Any) -> StateTransition:
        before = states[judgment.target_actor_id]
        after = before.apply(judgment.delta, judgment.confidence)
        states[judgment.target_actor_id] = after
        return StateTransition(action_id, judgment.target_actor_id, before,
                               after, judgment)

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
            effect_scope=value.get("effect_scope", "direct"))

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
