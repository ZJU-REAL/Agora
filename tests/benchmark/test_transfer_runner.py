import asyncio
import json
from dataclasses import replace

import pytest

from benchmarks import WorldArtifact
from benchmarks.adapters import JsonModelCandidate, ModelResponse
from benchmarks.cli import _episode_from_config, main
from benchmarks.experience import (
    canonical_json,
    content_hash,
    export_experience,
    validate_experience,
)
from benchmarks.observers import ScriptedDevelopmentObserver
from benchmarks.policies import FeedbackAdaptiveDevelopmentCandidate
from benchmarks.transfer import STAGES, TransferPlan, TransferRunner, window_scores
from examples.agora_oasis.transfer_demo import build_demo
from oasis import AgoraOasis
from oasis.audience import ScriptedDevelopmentAudience


def fixture_plan(tmp_path, seeds=(1,)):
    root = tmp_path / "demo"
    config = build_demo(root, seeds)
    value = json.loads(config.read_text())
    templates = {
        kind: _episode_from_config(
            json.loads((root / f"{kind}-episode.json").read_text())
        )
        for kind in ("source", "target")
    }
    plan = TransferPlan(
        value["experiment_id"],
        value["pair_id"],
        value["axis"],
        value["source"]["context"],
        value["target"]["context"],
        seeds,
    )
    runner = TransferRunner(
        WorldArtifact(root / "artifacts/source"),
        WorldArtifact(root / "artifacts/target"),
        root / "experiment",
    )
    return config, plan, runner, templates


def execute(
    runner,
    plan,
    templates,
    candidate_factory=FeedbackAdaptiveDevelopmentCandidate,
    **kwargs,
):
    return asyncio.run(
        runner.run(
            plan,
            templates["source"],
            templates["target"],
            candidate_factory,
            ScriptedDevelopmentObserver,
            ScriptedDevelopmentAudience,
            **kwargs,
        )
    )


def test_full_paired_transfer_has_fresh_worlds_and_explicit_memory(tmp_path):
    _, plan, runner, templates = fixture_plan(tmp_path)

    class RecordingCandidate(FeedbackAdaptiveDevelopmentCandidate):
        initial = []

        async def act(self, observation, context):
            if context["step"] == 0:
                self.initial.append(
                    (observation.own_recent_posts, json.loads(json.dumps(context)))
                )
            return await super().act(observation, context)

    report = execute(runner, plan, templates, RecordingCandidate)
    assert report["successful_pairs"] == 1
    assert report["failed_seeds"] == 0
    assert set(report["items"][0]["runs"]) == set(STAGES)
    assert len(RecordingCandidate.initial) == 7
    assert all(posts == [] for posts, _ in RecordingCandidate.initial)
    memories = [
        context.get("transfer_experience") for _, context in RecordingCandidate.initial
    ]
    assert memories[0] is None and memories[1] is None and memories[3] is None
    assert memories[2] == memories[4] == memories[5]
    assert memories[6]["origin_context"] == plan.target_context
    assert memories[4]["origin_context"] == plan.source_context
    for run in report["items"][0]["runs"].values():
        world = AgoraOasis.local("world", runner.output_root / "runs" / run["run_id"])
        assert (
            world.platform.db.execute("SELECT seed FROM simulation_state").fetchone()[0]
            == 1
        )
        world.close()
    curve = report["paired_transfer"]["dimensions"]["trust"]
    assert curve["initial_transfer_drop"]["mean"] > 0
    assert curve["adaptation_gain"]["mean"] > 0
    assert curve["native_target_gap"]["confidence_interval_95"] is None
    assert report["contrasts"]["comment_feedback_effect_final"]["trust"]["mean"] > 0
    assert report["evaluation_status"] == "uncalibrated-development"
    assert "source_preparation" in report["items"][0]["phase_costs"]
    costs = report["items"][0]["standalone_condition_costs"]
    assert costs["target_transfer"]["actions"] == costs["target_native"]["actions"] == 6
    assert costs["target_cold"]["actions"] == 3


def test_cli_resume_reuses_completed_phases_and_rejects_plan_changes(tmp_path, capsys):
    config, _, runner, _ = fixture_plan(tmp_path)
    assert main(["transfer-run", str(config)]) == 0
    before = {
        path: path.read_bytes()
        for path in (runner.output_root / "runs").glob("*/trajectory.jsonl")
    }
    assert main(["transfer-run", str(config), "--resume"]) == 0
    assert all(path.read_bytes() == content for path, content in before.items())
    value = json.loads(config.read_text())
    value["memory_max_chars"] = 6000
    config.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="changed"):
        main(["transfer-run", str(config), "--resume"])
    assert "successful_pairs" in capsys.readouterr().out


@pytest.mark.parametrize(
    "change", ["two_axes", "overlap", "duplicate_seed", "bad_budget", "empty_context"]
)
def test_plan_rejects_confounded_or_unfair_comparisons(tmp_path, change):
    _, plan, _, _ = fixture_plan(tmp_path)
    if change == "two_axes":
        plan = replace(
            plan, target_context={**plan.target_context, "language": "en-US"}
        )
    elif change == "overlap":
        plan = replace(plan, evaluation_ticks=1)
    elif change == "duplicate_seed":
        plan = replace(plan, seeds=(1, 1))
    elif change == "bad_budget":
        plan = replace(plan, evaluation_budget={"max_actions": 1})
    else:
        plan = replace(plan, source_context={**plan.source_context, "culture": ""})
    with pytest.raises(ValueError):
        plan.validate()


def test_factories_cannot_share_candidate_state_between_phases(tmp_path):
    _, plan, runner, templates = fixture_plan(tmp_path)
    singleton = FeedbackAdaptiveDevelopmentCandidate()
    report = execute(runner, plan, templates, lambda: singleton)
    assert report["failed_seeds"] == 1
    assert "fresh instances" in report["items"][0]["error"]["message"]
    assert report["paired_transfer"] is None


def test_factories_cannot_hide_cross_phase_memory_in_a_shared_client(tmp_path):
    _, plan, runner, templates = fixture_plan(tmp_path)

    class Client:
        pass

    client = Client()

    def make_candidate():
        candidate = FeedbackAdaptiveDevelopmentCandidate()
        candidate.client = client
        return candidate

    report = execute(runner, plan, templates, make_candidate)
    assert report["failed_seeds"] == 1
    assert "fresh clients" in report["items"][0]["error"]["message"]


def test_artifact_context_can_be_frozen_through_cli(tmp_path):
    config, plan, _, _ = fixture_plan(tmp_path)
    context_path = config.parent / "context.json"
    context_path.write_text(json.dumps(plan.source_context))
    artifact = config.parent / "cli-artifact"
    assert (
        main(
            [
                "artifact-create",
                "source",
                str(artifact),
                "--data-root",
                str(config.parent / "worlds"),
                "--artifact-id",
                "cli-world",
                "--version",
                "1",
                "--context-config",
                str(context_path),
                "--transfer-pair-id",
                plan.pair_id,
                "--candidate-user-id",
                "1",
            ]
        )
        == 0
    )
    metadata = WorldArtifact(artifact).validate().metadata
    assert metadata["context"] == plan.source_context
    assert metadata["transfer_pair_id"] == plan.pair_id


def test_candidate_cannot_mutate_experience_supplied_to_other_conditions(tmp_path):
    _, plan, runner, templates = fixture_plan(tmp_path)

    class Candidate(FeedbackAdaptiveDevelopmentCandidate):
        first = True
        lengths = []

        async def act(self, observation, context):
            memory = context.get("transfer_experience")
            if context["step"] == 0 and memory:
                self.lengths.append(len(memory["memories"]))
                if type(self).first:
                    type(self).first = False
                    memory["memories"].clear()
            return await super().act(observation, context)

    report = execute(runner, plan, templates, Candidate)
    assert report["failed_seeds"] == 0
    assert all(length > 0 for length in Candidate.lengths)


def test_episode_budget_failure_is_reported_without_fake_zero_scores(tmp_path):
    _, plan, runner, templates = fixture_plan(tmp_path)

    class BrokenCandidate(FeedbackAdaptiveDevelopmentCandidate):
        async def act(self, observation, context):
            raise RuntimeError("temporary provider failure")

    report = execute(runner, plan, templates, BrokenCandidate)
    assert report["failed_seeds"] == 1
    assert report["successful_pairs"] == 0
    assert report["paired_transfer"] is None
    assert "source_preparation" in report["items"][0]["phase_costs"]
    report = execute(runner, plan, templates, BrokenCandidate, resume=True)
    assert "spent budget" in report["items"][0]["error"]["message"]


def write_public_run(root, hidden=False):
    root.mkdir()
    (root / "result.json").write_text('{"status":"completed"}')
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "actors": [{"role": "candidate", "user_id": 7}],
                "metadata": {"feedback_condition": "hidden" if hidden else "visible"},
            }
        )
    )
    records = []
    for step in range(2):
        records.append(
            {
                "record_type": "step",
                "step": step,
                "observation": {
                    "feed": [
                        {
                            "post_id": 999,
                            "author_id": 8,
                            "body": "public question",
                            "comments": [
                                {
                                    "comment_id": 456,
                                    "author_id": 8,
                                    "content": "VISIBLE_FEEDBACK",
                                }
                            ],
                            "assets": [
                                {
                                    "asset_key": "secret.png",
                                    "object_key": "/private/path",
                                    "alt_text": "blue",
                                }
                            ],
                        }
                    ]
                },
                "action": {
                    "action_type": "search_posts",
                    "arguments": {"query": "question"},
                    "rationale": "PRIVATE_REASONING",
                },
                "outcome": {
                    "posts": [
                        {
                            "post_id": 999,
                            "body": "QUERY_RESULT"
                            if step == 0
                            else "UNOBSERVED_FINAL_RESULT",
                            "comments": [
                                {"author_id": 8, "content": "HIDDEN_TOOL_FEEDBACK"}
                            ],
                        }
                    ]
                },
                "state_transitions": [{"trust": "PRIVATE_JUDGE"}],
                "environment_actions": [{"persona": "PRIVATE_PERSONA"}],
                "model_calls": [{"raw_output": "PRIVATE_MODEL_CALL"}],
            }
        )
    if hidden:
        for record in records:
            record["observation"]["feed"][0]["comments"] = []
    (root / "trajectory.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in records)
    )


@pytest.mark.parametrize("hidden", [False, True])
def test_experience_exports_only_seen_public_data_without_foreign_ids(tmp_path, hidden):
    root = tmp_path / "run"
    write_public_run(root, hidden)
    context = {
        "platform": "xiaohongshu",
        "culture": "a",
        "domain": "travel",
        "language": "zh",
    }
    capsule = export_experience(root, context)
    text = canonical_json(capsule)
    for secret in (
        "post_id",
        "comment_id",
        "author_id",
        "asset_key",
        "object_key",
        "PRIVATE_",
        "UNOBSERVED_FINAL_RESULT",
    ):
        assert secret not in text
    assert "QUERY_RESULT" in text
    assert ("HIDDEN_TOOL_FEEDBACK" in text) is not hidden
    validate_experience(capsule)
    capsule["memories"][0]["action"]["post_id"] = 999
    with pytest.raises(ValueError, match="private fields"):
        validate_experience(capsule)


def test_experience_budget_is_fixed_and_hash_reaches_model(tmp_path):
    root = tmp_path / "run"
    write_public_run(root)
    context = {
        "platform": "xiaohongshu",
        "culture": "a",
        "domain": "travel",
        "language": "zh",
    }
    capsule = export_experience(root, context, max_chars=1500)
    assert len(canonical_json(capsule)) <= 1500

    class Client:
        messages = None

        async def complete(self, messages):
            self.messages = messages
            return ModelResponse(
                '{"action_type":"do_nothing","arguments":{}}', "fake", 1, 1
            )

    from oasis.agora_types import Observation

    client = Client()
    asyncio.run(
        JsonModelCandidate("fake", "1", client).act(
            Observation({}, 0, [], []),
            {
                "available_actions": [],
                "scenario_id": "s",
                "step": 0,
                "transfer_experience": capsule,
            },
        )
    )
    assert json.loads(client.messages[1]["content"])["transfer_experience"] == capsule
    assert len(content_hash(capsule)) == 64


def test_window_scores_attribute_delayed_effects_to_original_actions(tmp_path):
    _, plan, runner, templates = fixture_plan(tmp_path)
    report = execute(runner, plan, templates)
    run = report["items"][0]["runs"]["source_reference"]["run_id"]
    window = window_scores(runner.output_root / "runs" / run, 0, 1)
    assert window["status"] == "measured"
    assert window["scores"]["trust"] > 0
    assert window["judgment_count"] == window["exposures"]


def test_early_stop_does_not_create_a_zero_transfer_loss(tmp_path):
    from benchmarks import CandidateAction

    _, plan, runner, templates = fixture_plan(tmp_path)

    class StopCandidate(FeedbackAdaptiveDevelopmentCandidate):
        async def act(self, observation, context):
            return CandidateAction("stop")

    report = execute(runner, plan, templates, StopCandidate)
    assert report["failed_seeds"] == 0
    assert report["incomplete_seeds"] == 1
    assert report["paired_transfer"] is None
    assert (
        report["items"][0]["runs"]["target_transfer"]["final"]["status"]
        == "incomplete_window"
    )


@pytest.mark.parametrize("confidence", [0, 1])
def test_unjudged_exposure_is_not_silently_scored_zero(tmp_path, confidence):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"actors": [{"user_id": 2, "actor_id": "reader"}]})
    )
    before = {"attitude": 0, "trust": 0, "engagement_intent": 0}
    after = {"attitude": 0.2, "trust": 0.2, "engagement_intent": 0.2}
    rows = [
        {
            "record_type": "step",
            "step": 0,
            "action_id": "a0",
            "environment_actions": [
                {"action": "audience_reaction", "user_id": 2, "focused_action": True}
            ],
            "state_transitions": [],
        },
        {
            "record_type": "terminal_effects",
            "pending_judgments": [],
            "state_transitions": [
                {
                    "action_id": "a0",
                    "target_actor_id": "reader",
                    "before": before,
                    "after": after,
                    "judgment": {"confidence": confidence},
                }
            ],
        },
    ]
    (tmp_path / "trajectory.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )
    result = window_scores(tmp_path, 0, 1)
    assert (result["scores"] is not None) == bool(confidence)
