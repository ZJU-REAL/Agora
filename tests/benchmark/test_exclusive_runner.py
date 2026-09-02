import json

import pytest

from benchmarks import (ActorRole, ActorSpec, CandidateAction, EpisodeManifest,
                        ExposureMode, WorldArtifact)
from benchmarks.metrics import validate_main_run
from benchmarks.observers import ScriptedDevelopmentObserver
from benchmarks.runners.exclusive import ExclusiveRunner
from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


class CommentCandidate:
    policy_id = "comment-first"
    policy_version = "1"

    async def act(self, observation, context):
        return CandidateAction(
            "create_comment",
            {"post_id": observation.feed[0]["post_id"],
             "content": "谢谢你的提醒，我们可以把问题说清楚。"},
        )


class PostingCandidate:
    policy_id = "post-first"
    policy_version = "1"

    async def act(self, observation, context):
        return CandidateAction("create_post", {
            "body": "Candidate-created content", "topics": ["evaluation"],
        })


def _manifest(candidate_user_id):
    return EpisodeManifest(
        protocol_version="agora-dev-1",
        world_artifact_version="xhs-conflict-dev-1",
        world_artifact_id="xhs-conflict-dev",
        candidate_id="candidate-a",
        platform="xiaohongshu",
        scenario_id="misunderstanding-001",
        seed=7,
        run_id="candidate-a-seed-7",
        observer_pool_version="scripted-dev-1",
        actors=(ActorSpec("candidate-a", ActorRole.CANDIDATE,
                          "comment-first", "1", candidate_user_id),
                ActorSpec("hostile-npc", ActorRole.NPC,
                          "scripted-hostile", "1", 1)),
        max_ticks=2,
    )


@pytest.mark.asyncio
async def test_artifact_clone_and_exclusive_run(tmp_path):
    sandbox = AgoraOasis.local("source", tmp_path / "worlds",
                               preset="xiaohongshu")
    npc_id = sandbox.create_user("skeptic", "质疑者")
    candidate_id = sandbox.create_user("candidate", "候选博主")
    sandbox.create_post(npc_id, body="这个说法真的靠谱吗？")
    sandbox.set_seed(5)

    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifacts" / "xhs-conflict-dev",
        artifact_id="xhs-conflict-dev", version="xhs-conflict-dev-1",
        npc_seed=11, event_seed=13,
        observer_pool_version="scripted-dev-1")
    sandbox.close()
    artifact.validate()

    runner = ExclusiveRunner(artifact, tmp_path / "outputs")
    manifest = _manifest(candidate_id)
    result = await runner.run(manifest, CommentCandidate(),
                              ScriptedDevelopmentObserver())

    assert result.status == "completed"
    assert result.ticks_completed == 2
    assert (result.output_dir / "world" / "sandbox.db").is_file()
    records = [json.loads(line) for line in
               (result.output_dir / "trajectory.jsonl").read_text(
                   encoding="utf-8").splitlines()]
    assert [record["action"]["action_type"] for record in records] == [
        "create_comment", "create_comment"]
    assert records[0]["candidate_id"] == "candidate-a"
    transition = records[0]["state_transitions"][0]
    assert transition["action_id"] == records[0]["action_id"]
    assert transition["after"]["attitude"] > 0

    source = AgoraOasis.local("source", tmp_path / "worlds")
    assert source.platform.db.execute(
        "SELECT COUNT(*) FROM comment").fetchone()[0] == 0
    source.close()

    resumed = await runner.run(manifest, CommentCandidate(),
                               ScriptedDevelopmentObserver(), resume=True)
    assert resumed.ticks_completed == 2
    assert len((resumed.output_dir / "trajectory.jsonl").read_text(
        encoding="utf-8").splitlines()) == 2


@pytest.mark.asyncio
async def test_candidate_post_is_mixed_into_npc_tick_pool(tmp_path):
    sandbox = AgoraOasis.local("source", tmp_path / "worlds",
                               preset="xiaohongshu")
    candidate_id = sandbox.create_user("candidate", "Candidate")
    npc_id = sandbox.add_persona(PersonaProfile(
        "npc", "npc", "NPC", posting_probability=0,
        comment_probability=0, like_probability=1))
    human_post = sandbox.create_post(npc_id, body="Imported human content")
    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="mixed-world",
        version="1", observer_pool_version="scripted-dev-1")
    sandbox.close()
    manifest = EpisodeManifest(
        protocol_version="agora-dev-1", world_artifact_version="1",
        world_artifact_id="mixed-world", candidate_id="candidate",
        platform="xiaohongshu", scenario_id="mixed-content", seed=3,
        run_id="mixed-content-run", observer_pool_version="scripted-dev-1",
        actors=(ActorSpec("candidate", ActorRole.CANDIDATE,
                          "post-first", "1", candidate_id),
                ActorSpec("npc", ActorRole.NPC, "scripted", "1", npc_id)),
        max_ticks=1)

    result = await ExclusiveRunner(artifact, tmp_path / "outputs").run(
        manifest, PostingCandidate(), ScriptedDevelopmentObserver())
    record = json.loads((result.output_dir / "trajectory.jsonl").read_text(
        encoding="utf-8").splitlines()[0])
    candidate_post = record["outcome"]["post_id"]
    npc_observation = next(
        action for action in record["environment_actions"]
        if action["action"] == "observe_feed")
    assert set(npc_observation["content_pool_post_ids"]) == {
        human_post, candidate_post}
    assert candidate_post in npc_observation["post_ids"]


def test_main_protocol_rejects_multiple_candidates():
    value = {
        "protocol_version": "v1", "world_artifact_version": "w1",
        "world_artifact_id": "world", "candidate_id": "a",
        "platform": "xiaohongshu", "scenario_id": "s1", "seed": 1,
        "run_id": "r1", "observer_pool_version": "o1",
        "exposure_mode": "controlled_exposure",
        "exposure_policy_version": "controlled-v1",
        "actors": [
            {"actor_id": "a", "role": "candidate"},
            {"actor_id": "b", "role": "candidate"},
        ],
    }
    with pytest.raises(ValueError, match="exactly one candidate"):
        validate_main_run(value)


def test_artifact_detects_tampering(tmp_path):
    sandbox = AgoraOasis.local("source", tmp_path / "worlds",
                               preset="xiaohongshu")
    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="world",
        version="1", observer_pool_version="scripted-dev-1")
    sandbox.close()
    with (artifact.root / "baseline.db").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        artifact.validate()


def test_artifact_freezes_versioned_resources(tmp_path):
    sandbox = AgoraOasis.local("source", tmp_path / "worlds",
                               preset="xiaohongshu")
    resource = tmp_path / "suite.json"
    resource.write_text('{"version":"1"}', encoding="utf-8")
    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="world", version="1",
        resources={"scenario-suite.json": resource})
    sandbox.close()
    assert (artifact.root / "resources" / "scenario-suite.json").is_file()
    resource.write_text('{"version":"changed"}', encoding="utf-8")
    artifact.validate()


def test_main_protocol_rejects_learned_recommender(candidate_user_id=1):
    manifest = _manifest(candidate_user_id)
    value = EpisodeManifest(**{
        **manifest.__dict__,
        "exposure_mode": ExposureMode.LEARNED_RECOMMENDER,
    })
    with pytest.raises(ValueError, match="Learned recommenders"):
        value.validate()
