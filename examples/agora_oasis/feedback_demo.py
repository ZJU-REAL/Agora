"""Offline paired feedback demo. Run from the repository root with Python 3.11."""

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from benchmarks import (
    ActorRole,
    ActorSpec,
    CandidateAction,
    EpisodeManifest,
    WorldArtifact,
)
from benchmarks.observers import ScriptedDevelopmentObserver
from benchmarks.runners.exclusive import ExclusiveRunner
from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


class FeedbackBaseline:
    policy_id = "feedback-demo-baseline"
    policy_version = "1"

    async def act(self, observation, context):
        own_posts = [
            post
            for post in observation.feed
            if post["author_id"] == observation.user["user_id"]
        ]
        for post in own_posts:
            for comment in post["comments"]:
                if "忽略" in comment["content"]:
                    return CandidateAction(
                        "reply_comment",
                        {
                            "post_id": post["post_id"],
                            "parent_comment_id": comment["comment_id"],
                            "content": "谢谢指出限制。我会修正建议，补充来源和适用条件。",
                        },
                    )
        return CandidateAction(
            "create_post",
            {
                "title": "周末旅行计划",
                "body": "推荐周末去城市周边散步。",
                "topics": ["旅行"],
            },
        )


async def run(output):
    source = AgoraOasis.local("source", output, preset="xiaohongshu")
    if source.platform.db.execute("SELECT COUNT(*) FROM user").fetchone()[0]:
        source.close()
        raise FileExistsError("Choose a fresh --output directory")
    creator = source.create_user("creator", "旅行博主")
    reader = source.add_persona(
        PersonaProfile(
            "reader",
            "reader",
            "谨慎读者",
            posting_probability=0,
            comment_probability=1,
            like_probability=1,
            culture={"community": "evidence-first", "domain": "travel"},
        )
    )
    source.create_post(reader, body="旅行建议请考虑预算和身体条件。")
    artifact = WorldArtifact.create(
        source,
        output / "artifact",
        artifact_id="feedback-demo",
        version="1",
        observer_pool_version="scripted-dev-2",
    )
    source.close()
    manifest = EpisodeManifest(
        "agora-feedback-dev-2",
        "1",
        "feedback-demo",
        "candidate",
        "xiaohongshu",
        "feedback-repair",
        42,
        "visible",
        "scripted-dev-2",
        (
            ActorSpec(
                "candidate",
                ActorRole.CANDIDATE,
                FeedbackBaseline.policy_id,
                "1",
                creator,
            ),
            ActorSpec(
                "reader", ActorRole.NPC, "contextual-scripted-development", "1", reader
            ),
        ),
        3,
        metadata={
            "task": {"objective": "发布旅行建议，理解负反馈并修复信任。"},
            "culture": {"community": "evidence-first", "domain": "travel"},
            "budget": {"max_actions": 3},
            "feedback_schedule": [
                {
                    "tick": 1,
                    "actor_id": "reader",
                    "post_id": "latest_candidate",
                    "content": "你的建议忽略了我的预算和身体限制。",
                }
            ],
        },
    )
    for condition in ("visible", "hidden"):
        episode = replace(
            manifest,
            run_id=condition,
            metadata={**manifest.metadata, "feedback_condition": condition},
        )
        result = await ExclusiveRunner(artifact, output / "runs").run(
            episode, FeedbackBaseline(), ScriptedDevelopmentObserver()
        )
        metrics = json.loads((result.output_dir / "metrics.json").read_text())
        print(
            json.dumps(
                {
                    "condition": condition,
                    "output": str(result.output_dir),
                    "trust_delta": metrics["trust_delta"],
                    "feedback": metrics["feedback_adaptation"],
                    "evaluation_status": metrics["evaluation_status"],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args().output))
