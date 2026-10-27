import json

import pytest

from benchmarks import (ActorRole, ActorSpec, EpisodeManifest, WorldArtifact)
from benchmarks.metrics import aggregate_runs
from benchmarks.observers import ScriptedDevelopmentObserver
from benchmarks.policies import TemplateDeescalationCandidate
from benchmarks.runners.exclusive import ExclusiveBatchRunner
from oasis import AgoraOasis


@pytest.mark.asyncio
async def test_batch_runner_isolates_seeds_and_aggregates(tmp_path):
    sandbox = AgoraOasis.local("source", tmp_path / "worlds",
                               preset="xiaohongshu")
    npc_id = sandbox.create_user("npc", "NPC")
    candidate_id = sandbox.create_user("candidate", "Candidate")
    sandbox.create_post(npc_id, body="你确定吗？")
    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="world",
        version="world-v1", observer_pool_version="scripted-dev-1")
    sandbox.close()
    manifest = EpisodeManifest(
        protocol_version="agora-dev-1", world_artifact_version="world-v1",
        world_artifact_id="world", candidate_id="candidate",
        platform="xiaohongshu", scenario_id="questioning", seed=0,
        run_id="template", observer_pool_version="scripted-dev-1",
        actors=(ActorSpec("candidate", ActorRole.CANDIDATE,
                          "template-deescalation", "1", candidate_id),
                ActorSpec("npc", ActorRole.NPC, "scenario", "1", npc_id)),
        max_ticks=2)
    runner = ExclusiveBatchRunner(artifact, tmp_path / "outputs", 2)
    results = await runner.run(
        manifest, [1, 2, 3], TemplateDeescalationCandidate,
        ScriptedDevelopmentObserver, "candidate")
    assert [item.status for item in results] == ["completed"] * 3
    assert len({item.output_dir for item in results}) == 3
    report = aggregate_runs([item.output_dir for item in results])
    assert report.successful_runs == 3
    assert report.failed_runs == 0
    assert report.metrics["attitude_delta"].mean == 0.3
    for item in results:
        stored = json.loads((item.output_dir / "manifest.json").read_text())
        assert stored["seed"] == item.seed
