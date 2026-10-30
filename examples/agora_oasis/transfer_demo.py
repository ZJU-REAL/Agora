"""Build and run an offline toy transfer experiment, not a cultural benchmark."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from benchmarks import ActorRole, ActorSpec, EpisodeManifest, WorldArtifact
from benchmarks.cli import main as benchmark_main
from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


def build_demo(output: Path, seeds=(1, 2)):
    output.mkdir(parents=True, exist_ok=False)
    contexts = {}
    for kind, culture, prefer, avoid, feedback in (
        ("source", "toy-encouragement", ["肯定"], [], "请先肯定我的努力，再调整建议。"),
        (
            "target",
            "toy-evidence",
            ["来源"],
            ["先肯定"],
            "请提供来源和适用限制，不要只给泛泛的鼓励。",
        ),
    ):
        context = {
            "platform": "xiaohongshu",
            "culture": culture,
            "domain": "travel",
            "language": "zh-CN",
        }
        contexts[kind] = context
        world = AgoraOasis.local(kind, output / "worlds", preset="xiaohongshu")
        try:
            candidate_id = world.create_user("creator", "旅行博主")
            reader_id = world.add_persona(
                PersonaProfile(
                    "reader",
                    "reader",
                    "示例读者",
                    posting_probability=0,
                    comment_probability=1,
                    like_probability=1,
                    culture={
                        "community": culture,
                        "prefer_phrases": prefer,
                        "avoid_phrases": avoid,
                    },
                )
            )
            world.create_post(
                reader_id, body="请分享一条周末旅行建议。", topics=["旅行"]
            )
            artifact = WorldArtifact.create(
                world,
                output / "artifacts" / kind,
                artifact_id=f"transfer-toy-{kind}",
                version="1",
                scenario_suite_version="transfer-toy-v1",
                observer_pool_version="scripted-dev-3",
                metadata={
                    "context": context,
                    "transfer_pair_id": "travel-pair",
                    "task": {"objective": "发布旅行建议，根据受众反馈调整。"},
                },
            )
        finally:
            world.close()
        manifest = EpisodeManifest(
            "agora-transfer-v1",
            "1",
            artifact.manifest.artifact_id,
            "candidate",
            "xiaohongshu",
            "travel-pair",
            0,
            f"{kind}-template",
            "scripted-dev-3",
            (
                ActorSpec(
                    "candidate",
                    ActorRole.CANDIDATE,
                    "candidate-unbound",
                    "1",
                    candidate_id,
                ),
                ActorSpec(
                    "reader",
                    ActorRole.NPC,
                    "contextual-scripted-development",
                    "1",
                    reader_id,
                ),
            ),
            3,
            metadata={
                "feedback_schedule": [
                    {
                        "tick": 1,
                        "actor_id": "reader",
                        "post_id": "latest_candidate",
                        "content": feedback,
                        "valence": "negative",
                    }
                ]
            },
        )
        (output / f"{kind}-episode.json").write_text(
            json.dumps(
                {"artifact_dir": f"artifacts/{kind}", "episode": asdict(manifest)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
    value = {
        "experiment_id": "toy-cultural-transfer",
        "pair_id": "travel-pair",
        "axis": "culture",
        "source": {
            "episode_config": "source-episode.json",
            "context": contexts["source"],
        },
        "target": {
            "episode_config": "target-episode.json",
            "context": contexts["target"],
        },
        "seeds": list(seeds),
        "preparation": {"max_ticks": 3, "budget": {"max_actions": 3}},
        "evaluation": {"max_ticks": 3, "probe_ticks": 1, "budget": {"max_actions": 3}},
        "memory_max_chars": 12000,
        "output_root": "experiment",
        "runtime": {
            "candidate_policy": "feedback-adaptive-development",
            "observer": "scripted-development",
            "audience": {"type": "scripted-development"},
        },
    }
    config = output / "transfer.json"
    config.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", default="1,2")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    config = build_demo(args.output, tuple(int(item) for item in args.seeds.split(",")))
    print(f"Transfer config: {config}")
    if not args.prepare_only:
        raise SystemExit(benchmark_main(["transfer-run", str(config)]))
