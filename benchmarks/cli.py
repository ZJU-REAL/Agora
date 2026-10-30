from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import hashlib
from dataclasses import asdict
from pathlib import Path

from benchmarks.artifacts import WorldArtifact
from benchmarks.ablations import build_ablation_matrix
from benchmarks.calibration import (calibration_report,
                                    export_human_calibration_sample,
                                    load_calibration_judgments)
from benchmarks.metrics import (load_validated_main_run,
                                write_aggregate_report)
from benchmarks.policies import POLICIES
from benchmarks.protocol import (ActorRole, ActorSpec, EpisodeManifest,
                                 ExposureMode)
from benchmarks.providers import load_provider_config
from benchmarks.provider_smoke import smoke_test_observer
from benchmarks.reproducibility import compare_reproductions
from benchmarks.runners.exclusive import ExclusiveBatchRunner, ExclusiveRunner
from benchmarks.runtime import candidate_factory, observer_factory, audience_factory
from benchmarks.scenarios import load_scenario_suite, materialize_scenario
from oasis import AgoraOasis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agora-benchmark")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("artifact-create")
    create.add_argument("world_id")
    create.add_argument("artifact_dir")
    create.add_argument("--data-root", default="data/worlds")
    create.add_argument("--artifact-id", required=True)
    create.add_argument("--version", required=True)
    create.add_argument("--actor-pool-version", default="development")
    create.add_argument("--observer-pool-version", default="development")
    create.add_argument("--scenario-suite-version", default="development")
    create.add_argument("--npc-seed", type=int, default=0)
    create.add_argument("--event-seed", type=int, default=0)
    create.add_argument("--scenario-id")
    create.add_argument(
        "--content-topic", action="append", default=[],
        help="Freeze posts matching this topic into the shared tick pool; repeatable")
    create.add_argument("--candidate-user-id", type=int)
    create.add_argument("--candidate-actor-id", default="candidate")
    create.add_argument("--npc-user-ids",
                        help="Comma-separated Persona user IDs; defaults to all Personas")
    create.add_argument("--candidate-asset", action="append", default=[],
                        metavar="KEY=PATH")
    create.add_argument("--candidate-asset-metadata",
                        help="JSON mapping asset keys to alt_text/transcript")

    validate = commands.add_parser("artifact-validate")
    validate.add_argument("artifact_dir")

    build = commands.add_parser("scenario-build")
    build.add_argument("suite")
    build.add_argument("scenario_id")
    build.add_argument("artifact_dir")
    build.add_argument("--artifact-id", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--seed", type=int, default=0)
    build.add_argument("--observer-pool-version", default="scripted-dev-1")
    build.add_argument("--observer-pool-config")
    for command in (create, build):
        command.add_argument("--context-config", help="Freeze platform/culture/domain/language JSON")
        command.add_argument("--transfer-pair-id", help="Matched task pair ID for transfer")

    configure = commands.add_parser("episode-init")
    configure.add_argument("artifact_dir")
    configure.add_argument("output")
    configure.add_argument("--candidate-policy", default="template-deescalation",
                           choices=tuple(POLICIES))
    configure.add_argument("--candidate-provider-config")
    configure.add_argument("--candidate-policy-id")
    configure.add_argument("--candidate-policy-version", default="1")
    configure.add_argument("--candidate-max-attempts", type=int, default=1)
    configure.add_argument("--observer-provider-config")
    configure.add_argument("--observer-pool-config")
    configure.add_argument("--observer-id", default="model-observer")
    configure.add_argument("--observer-version", default="1")
    configure.add_argument("--candidate-actor-id", default="candidate")
    configure.add_argument("--protocol-version", default="agora-feedback-dev-2")
    configure.add_argument("--run-id", required=True)
    configure.add_argument("--seed", type=int, default=0)
    configure.add_argument("--max-ticks", type=int, default=3)
    configure.add_argument("--output-root", default="benchmarks/outputs")

    run = commands.add_parser("run")
    run.add_argument("config", help="Episode configuration JSON")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    batch = commands.add_parser("batch-run")
    batch.add_argument("config", help="Episode configuration JSON")
    batch.add_argument("--seeds", required=True,
                       help="Comma-separated unique integer seeds")
    batch.add_argument("--max-concurrency", type=int, default=1)
    batch.add_argument("--run-prefix")

    report = commands.add_parser("aggregate")
    report.add_argument("output")
    report.add_argument("run_dirs", nargs="+")

    debug = commands.add_parser("inspect-run")
    debug.add_argument("run_dir")
    debug.add_argument("--step", type=int)

    calibration = commands.add_parser("calibration-export")
    calibration.add_argument("output")
    calibration.add_argument("run_dirs", nargs="+")
    calibration.add_argument("--max-items-per-run", type=int, default=10)

    calibration_result = commands.add_parser("calibration-report")
    calibration_result.add_argument("judgments")
    calibration_result.add_argument("--output")
    calibration_result.add_argument("--private-key",
                                    help="Private alignment key from calibration-export")

    ablations = commands.add_parser("ablation-init")
    ablations.add_argument("output")
    ablations.add_argument("--observer-pools", required=True)
    ablations.add_argument("--persona-distributions", required=True)

    reproduce = commands.add_parser("reproduce-check")
    reproduce.add_argument("first_run")
    reproduce.add_argument("second_run")

    check = commands.add_parser("run-validate")
    check.add_argument("manifest")

    smoke = commands.add_parser("observer-smoke")
    smoke.add_argument("provider_config")
    smoke.add_argument("--output")

    transfer = commands.add_parser("transfer-run", help="Run paired source/target transfer experiments")
    transfer.add_argument("config")
    transfer.add_argument("--output-root")
    transfer.add_argument("--resume", action="store_true")
    return parser


def _episode_from_config(value: dict) -> EpisodeManifest:
    actors = tuple(ActorSpec(
        actor_id=item["actor_id"], role=ActorRole(item["role"]),
        policy_id=item["policy_id"], policy_version=item["policy_version"],
        user_id=item.get("user_id"), metadata=item.get("metadata", {}))
                   for item in value["episode"]["actors"])
    episode = dict(value["episode"])
    episode["exposure_mode"] = ExposureMode(
        episode.get("exposure_mode", "controlled_exposure"))
    return EpisodeManifest(actors=actors, **{
        key: item for key, item in episode.items() if key != "actors"
    })


def _transfer_annotation(args, platform):
    if bool(args.context_config) != bool(args.transfer_pair_id):
        raise ValueError("--context-config and --transfer-pair-id must be supplied together")
    if not args.context_config:
        return {}
    from benchmarks.experience import validate_context
    context = load_provider_config(args.context_config)
    validate_context(context)
    if context["platform"] != platform:
        raise ValueError("Context platform does not match the world")
    return {"context": context, "transfer_pair_id": args.transfer_pair_id}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "transfer-run":
        from benchmarks.transfer import TransferPlan, TransferRunner
        value = load_provider_config(args.config)
        base = Path(args.config).resolve().parent
        templates, artifacts, contexts = {}, {}, {}
        for kind in ("source", "target"):
            path = Path(value[kind]["episode_config"])
            path = path if path.is_absolute() else base / path
            episode = load_provider_config(str(path))
            templates[kind] = _episode_from_config(episode)
            artifact_path = Path(episode["artifact_dir"])
            artifacts[kind] = WorldArtifact(artifact_path if artifact_path.is_absolute() else path.parent / artifact_path)
            contexts[kind] = value[kind]["context"]
        preparation, evaluation = value["preparation"], value["evaluation"]
        plan = TransferPlan(value["experiment_id"], value["pair_id"], value["axis"],
            contexts["source"], contexts["target"], tuple(value["seeds"]),
            preparation_ticks=preparation["max_ticks"], evaluation_ticks=evaluation["max_ticks"],
            probe_ticks=evaluation.get("probe_ticks", 1),
            preparation_budget=preparation.get("budget", {}), evaluation_budget=evaluation.get("budget", {}),
            memory_max_chars=value.get("memory_max_chars", 12000))
        runtime = value["runtime"]
        make_candidate, _, _ = candidate_factory(runtime, args.config)
        make_observer = observer_factory(runtime, args.config)
        make_audience = audience_factory(runtime, args.config)
        output_root = (Path(args.output_root) if args.output_root else
                       base / value.get("output_root", f"outputs/{plan.experiment_id}"))
        report = asyncio.run(TransferRunner(artifacts["source"], artifacts["target"], output_root).run(
            plan, templates["source"], templates["target"], make_candidate, make_observer,
            make_audience, resume=args.resume))
        print(json.dumps({"report": str(output_root / "transfer-report.json"),
            "successful_pairs": report["successful_pairs"], "failed_seeds": report["failed_seeds"],
            "incomplete_seeds": report["incomplete_seeds"]}, ensure_ascii=False, indent=2))
        return 1 if report["failed_seeds"] or report["incomplete_seeds"] else 0
    elif args.command == "artifact-create":
        sandbox = AgoraOasis.local(args.world_id, args.data_root)
        try:
            resources = {}
            for assignment in args.candidate_asset:
                if "=" not in assignment:
                    raise ValueError("--candidate-asset must use KEY=PATH")
                key, source = assignment.split("=", 1)
                if not key or not source or key in resources:
                    raise ValueError("Candidate asset keys must be unique")
                resources[key] = source
            metadata = {"scenario_id": args.scenario_id or args.world_id,
                        "candidate_asset_keys": list(resources),
                        **_transfer_annotation(args, sandbox.preset.name)}
            content_topics = list(dict.fromkeys(
                topic.strip().lstrip("#") for topic in args.content_topic
                if topic.strip().lstrip("#")))
            if content_topics:
                placeholders = ",".join("?" for _ in content_topics)
                controlled_post_ids = [int(row[0]) for row in
                                       sandbox.platform.db.execute(
                    "SELECT DISTINCT p.post_id FROM post p "
                    "JOIN post_topic pt ON pt.post_id = p.post_id "
                    "JOIN topic t ON t.topic_id = pt.topic_id "
                    f"WHERE p.visibility = 'public' AND t.name IN "
                    f"({placeholders}) ORDER BY p.post_id",
                    content_topics).fetchall()]
                if not controlled_post_ids:
                    raise ValueError(
                        "No posts match the requested content topics")
                metadata.update({"content_topics": content_topics,
                                 "controlled_post_ids": controlled_post_ids})
            if args.candidate_asset_metadata:
                metadata["candidate_asset_metadata"] = json.loads(Path(
                    args.candidate_asset_metadata).read_text(encoding="utf-8"))
            if args.candidate_user_id is not None:
                existing_ids = {int(row[0]) for row in sandbox.platform.db.execute(
                    "SELECT user_id FROM user").fetchall()}
                if args.candidate_user_id not in existing_ids:
                    raise ValueError("Candidate user ID does not exist in world")
                persona_ids = {int(row[0]) for row in
                               sandbox.platform.db.execute(
                    "SELECT user_id FROM persona").fetchall()}
                npc_ids = ([int(item) for item in args.npc_user_ids.split(",")
                            if item] if args.npc_user_ids is not None else
                           sorted(persona_ids - {args.candidate_user_id}))
                if (args.candidate_user_id in npc_ids
                        or not set(npc_ids) <= persona_ids):
                    raise ValueError(
                        "NPC user IDs must identify imported Persona accounts")
                actor_ids = {args.candidate_actor_id: args.candidate_user_id,
                             **{f"npc-{user_id}": user_id for user_id in npc_ids}}
                metadata.update({
                    "actor_user_ids": actor_ids,
                    "actor_roles": {actor_id: (
                        "candidate" if actor_id == args.candidate_actor_id else "npc")
                                    for actor_id in actor_ids},
                    "actor_policies": {actor_id: {
                        "policy_id": ("candidate-unbound" if actor_id ==
                                      args.candidate_actor_id else
                                      "world-scripted"),
                        "policy_version": args.actor_pool_version,
                        "persona_version": args.actor_pool_version,
                        "prompt_sha256": None,
                        "sampling": {"temperature": 0.0,
                                     "seed": args.npc_seed},
                    } for actor_id in actor_ids},
                })
            artifact = WorldArtifact.create(
                sandbox, args.artifact_dir, artifact_id=args.artifact_id,
                version=args.version, npc_seed=args.npc_seed,
                event_seed=args.event_seed,
                actor_pool_version=args.actor_pool_version,
                observer_pool_version=args.observer_pool_version,
                scenario_suite_version=args.scenario_suite_version,
                resources=resources, metadata=metadata)
            output = asdict(artifact.manifest)
        finally:
            sandbox.close()
    elif args.command == "artifact-validate":
        output = asdict(WorldArtifact(args.artifact_dir).validate())
    elif args.command == "scenario-build":
        suite_version, scenarios = load_scenario_suite(args.suite)
        observer_pool_version = args.observer_pool_version
        resources = {"scenario-suite.json": args.suite}
        if args.observer_pool_config:
            pool_config = load_provider_config(args.observer_pool_config)
            if pool_config.get("type") != "pool":
                raise ValueError("Observer pool config must have type=pool")
            observer_pool_version = pool_config["pool_version"]
            resources["observer-pool.json"] = args.observer_pool_config
        matches = [item for item in scenarios
                   if item.scenario_id == args.scenario_id]
        if not matches:
            raise ValueError(f"Unknown scenario_id: {args.scenario_id}")
        with tempfile.TemporaryDirectory(prefix="agora-scenario-") as temp:
            sandbox, user_ids = materialize_scenario(
                matches[0], "source", Path(temp), args.seed)
            try:
                artifact = WorldArtifact.create(
                    sandbox, args.artifact_dir,
                    artifact_id=args.artifact_id, version=args.version,
                    npc_seed=args.seed, event_seed=args.seed,
                    actor_pool_version=suite_version,
                    observer_pool_version=observer_pool_version,
                    scenario_suite_version=suite_version,
                    resources=resources,
                    metadata={"scenario_id": args.scenario_id,
                              **_transfer_annotation(args, sandbox.preset.name),
                              "task": {"objective": matches[0].description},
                              "culture": matches[0].metadata.get("culture", {}),
                              "actor_user_ids": user_ids,
                              "actor_roles": {
                                  user.actor_id: user.role
                                  for user in matches[0].users},
                              "actor_policies": {
                                  user.actor_id: {
                                      "policy_id": ("candidate-unbound"
                                                    if user.role == "candidate"
                                                    else "scenario-scripted"),
                                      "policy_version": suite_version,
                                      "persona_version": suite_version,
                                      "prompt_sha256": None,
                                      "sampling": {"temperature": 0.0,
                                                   "seed": args.seed},
                                  } for user in matches[0].users}})
                output = asdict(artifact.manifest)
            finally:
                sandbox.close()
    elif args.command == "run-validate":
        output = load_validated_main_run(args.manifest)
    elif args.command == "episode-init":
        artifact = WorldArtifact(args.artifact_dir).validate()
        actor_ids = artifact.metadata.get("actor_user_ids", {})
        actor_roles = artifact.metadata.get("actor_roles", {})
        if args.candidate_actor_id not in actor_ids:
            raise ValueError("Candidate actor is missing from artifact metadata")
        if args.candidate_provider_config:
            if not args.candidate_policy_id:
                raise ValueError(
                    "--candidate-policy-id is required with a provider config")
            policy_id = args.candidate_policy_id
            policy_version = args.candidate_policy_version
        else:
            policy = POLICIES[args.candidate_policy]()
            policy_id = policy.policy_id
            policy_version = policy.policy_version
        actors = []
        for actor_id, user_id in actor_ids.items():
            is_candidate = actor_id == args.candidate_actor_id
            actors.append({
                "actor_id": actor_id,
                "role": "candidate" if is_candidate else actor_roles.get(
                    actor_id, "npc"),
                "policy_id": policy_id if is_candidate else "scenario",
                "policy_version": policy_version if is_candidate else
                artifact.actor_pool_version,
                "user_id": user_id,
            })
        candidate_config = (args.candidate_policy if not
                            args.candidate_provider_config else None)
        if args.observer_provider_config and args.observer_pool_config:
            raise ValueError("Choose one observer provider or observer pool config")
        frozen_pool = Path(args.artifact_dir) / "resources" / "observer-pool.json"
        default_observer = (None if frozen_pool.is_file()
                            else "scripted-development")
        provenance_metadata = {}
        if args.candidate_provider_config:
            provenance_metadata["candidate_provider_config_sha256"] = (
                hashlib.sha256(Path(
                    args.candidate_provider_config).read_bytes()).hexdigest())
        if args.observer_provider_config:
            provenance_metadata["observer_provider_config_sha256"] = (
                hashlib.sha256(Path(
                    args.observer_provider_config).read_bytes()).hexdigest())
        config = {
            "artifact_dir": str(Path(args.artifact_dir).resolve()),
            "output_root": args.output_root,
            "observer": ({
                "type": "model",
                "observer_id": args.observer_id,
                "observer_version": args.observer_version,
                "provider_config": str(Path(
                    args.observer_provider_config).resolve()),
                "provider_config_sha256": hashlib.sha256(Path(
                    args.observer_provider_config).read_bytes()).hexdigest(),
            } if args.observer_provider_config else default_observer),
            "episode": {
                "protocol_version": args.protocol_version,
                "world_artifact_version": artifact.world_artifact_version,
                "world_artifact_id": artifact.artifact_id,
                "candidate_id": args.candidate_actor_id,
                "platform": artifact.platform,
                "scenario_id": artifact.metadata["scenario_id"],
                "seed": args.seed,
                "run_id": args.run_id,
                "observer_pool_version": artifact.observer_pool_version,
                "exposure_mode": artifact.exposure_mode,
                "exposure_policy_version": artifact.exposure_policy_version,
                "actors": actors,
                "max_ticks": args.max_ticks,
                "metadata": provenance_metadata,
            },
        }
        if frozen_pool.is_file() and not (
                args.observer_provider_config or args.observer_pool_config):
            config.pop("observer")
            config["observer_pool_config"] = str(frozen_pool.resolve())
            pool_hash = hashlib.sha256(frozen_pool.read_bytes()).hexdigest()
            config["observer_pool_config_sha256"] = pool_hash
            config["episode"]["metadata"][
                "observer_pool_config_sha256"] = pool_hash
        if args.observer_pool_config:
            config.pop("observer")
            pool_path = Path(args.observer_pool_config)
            pool_hash = hashlib.sha256(pool_path.read_bytes()).hexdigest()
            config["observer_pool_config"] = str(pool_path.resolve())
            config["observer_pool_config_sha256"] = pool_hash
            config["episode"]["metadata"][
                "observer_pool_config_sha256"] = pool_hash
        if candidate_config:
            config["candidate_policy"] = candidate_config
        else:
            config["candidate"] = {
                "type": "model", "policy_id": policy_id,
                "policy_version": policy_version,
                "provider_config": str(Path(
                    args.candidate_provider_config).resolve()),
                "provider_config_sha256": hashlib.sha256(Path(
                    args.candidate_provider_config).read_bytes()).hexdigest(),
                "max_attempts": args.candidate_max_attempts,
            }
        Path(args.output).write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        output = {"config": str(args.output), "run_id": args.run_id}
    elif args.command in {"run", "batch-run"}:
        value = json.loads(Path(args.config).read_text(encoding="utf-8"))
        manifest = _episode_from_config(value)
        make_candidate, policy_id, policy_version = candidate_factory(
            value, args.config)
        candidate_actor = next(actor for actor in manifest.actors
                               if actor.role == ActorRole.CANDIDATE)
        if (candidate_actor.policy_id, candidate_actor.policy_version) != (
                policy_id, policy_version):
            raise ValueError(
                "Configured candidate identity does not match episode actor")
        artifact = WorldArtifact(value["artifact_dir"])
        output_root = value.get("output_root", "benchmarks/outputs")
        make_observer = observer_factory(value, args.config)
        make_audience = audience_factory(value, args.config)
        if make_observer:
            observer_probe = make_observer()
            observer_spec = value.get("observer")
            if observer_spec is None and value.get("observer_pool_config"):
                observer_spec = load_provider_config(
                    value["observer_pool_config"])
            declared_pool_version = (
                observer_spec.get("pool_version")
                if isinstance(observer_spec, dict) else None)
            if (declared_pool_version is not None
                    and declared_pool_version != manifest.observer_pool_version):
                raise ValueError(
                    "Configured observer version does not match episode manifest")
        if args.command == "run":
            runner = ExclusiveRunner(artifact, output_root)
            candidate = make_candidate()
            if args.dry_run:
                runner.validate(manifest, candidate)
                output = {"valid": True, "run_id": manifest.run_id,
                          "artifact": manifest.world_artifact_id}
            else:
                result = asyncio.run(runner.run(
                    manifest, candidate,
                    observer_probe if make_observer else None,
                    resume=args.resume, audience_policy=make_audience()))
                output = {**result.__dict__,
                          "output_dir": str(result.output_dir)}
        else:
            seeds = [int(item) for item in args.seeds.split(",")]
            runner = ExclusiveBatchRunner(
                artifact, output_root, args.max_concurrency)
            results = asyncio.run(runner.run(
                manifest, seeds, make_candidate, make_observer,
                args.run_prefix, audience_factory=make_audience))
            output = {"runs": [
                {**asdict(item), "output_dir": str(item.output_dir)}
                for item in results]}
    elif args.command == "aggregate":
        path = write_aggregate_report(args.run_dirs, args.output)
        output = {"report": str(path), "run_count": len(args.run_dirs)}
    elif args.command == "inspect-run":
        run_dir = Path(args.run_dir)
        records = [json.loads(line) for line in (
            run_dir / "trajectory.jsonl").read_text(
                encoding="utf-8").splitlines()]
        if args.step is not None:
            records = [item for item in records
                       if item.get("step") == args.step]
        output = {
            "manifest": load_validated_main_run(run_dir / "manifest.json"),
            "result": json.loads((run_dir / "result.json").read_text()),
            "records": records,
        }
    elif args.command == "calibration-export":
        path = export_human_calibration_sample(
            args.run_dirs, args.output, args.max_items_per_run)
        output = {"calibration_sample": str(path)}
    elif args.command == "calibration-report":
        report = asdict(calibration_report(
            load_calibration_judgments(args.judgments, args.private_key)))
        if args.output:
            Path(args.output).write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        output = report
    elif args.command == "ablation-init":
        conditions = build_ablation_matrix(
            tuple(item for item in args.observer_pools.split(",") if item),
            tuple(item for item in args.persona_distributions.split(",")
                  if item))
        Path(args.output).write_text(json.dumps({
            "conditions": [asdict(item) for item in conditions],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output = {"output": args.output, "conditions": len(conditions)}
    elif args.command == "reproduce-check":
        output = compare_reproductions(args.first_run, args.second_run)
    elif args.command == "observer-smoke":
        provider = load_provider_config(args.provider_config)
        output = asyncio.run(smoke_test_observer(provider))
        if args.output:
            Path(args.output).write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
    else:
        raise AssertionError(args.command)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
