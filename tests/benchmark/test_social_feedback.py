import asyncio
import json

import pytest

from benchmarks import (
    ActorRole,
    ActorSpec,
    CandidateAction,
    EpisodeManifest,
    WorldArtifact,
)
from benchmarks.adapters import JsonModelCandidate, ModelResponse
from benchmarks.audience import JsonModelAudience
from benchmarks.calibration import (
    CalibrationJudgment,
    calibration_report,
    export_human_calibration_sample,
    load_calibration_judgments,
)
from benchmarks.observers import JsonModelObserver, ScriptedDevelopmentObserver
from benchmarks.runners.exclusive import ExclusiveRunner
from oasis import AgoraOasis
from oasis.agora_types import Observation, PersonaProfile


def make_episode(
    tmp_path, preset="xiaohongshu", ticks=2, metadata=None, resources=None
):
    world = AgoraOasis.local("source", tmp_path, preset=preset)
    world.set_seed(73)
    creator = world.create_user("candidate", "Creator")
    reader = world.add_persona(
        PersonaProfile(
            "reader",
            "reader",
            "Reader",
            posting_probability=0,
            comment_probability=1,
            like_probability=1,
            culture={"community": "evidence-first"},
        )
    )
    post = world.create_post(reader, body="请给出依据和适用限制。")
    artifact = WorldArtifact.create(
        world,
        tmp_path / "artifact",
        artifact_id="feedback",
        version="1",
        observer_pool_version="scripted-dev-1",
        resources=resources,
        metadata={"candidate_asset_keys": list(resources or {})},
    )
    world.close()
    manifest = EpisodeManifest(
        "feedback-v1",
        "1",
        "feedback",
        "candidate",
        preset,
        "feedback-task",
        42,
        "run",
        "scripted-dev-1",
        (
            ActorSpec("candidate", ActorRole.CANDIDATE, "candidate", "1", creator),
            ActorSpec("reader", ActorRole.NPC, "reader", "1", reader),
        ),
        ticks,
        metadata=metadata or {},
    )
    return artifact, manifest, creator, reader, post


class ReplyCandidate:
    policy_id = "candidate"
    policy_version = "1"

    def __init__(self):
        self.contexts = []

    async def act(self, observation, context):
        self.contexts.append(json.loads(json.dumps(context)))
        return CandidateAction(
            "create_comment",
            {
                "post_id": observation.feed[0]["post_id"],
                "content": "谢谢提醒，我会修正建议并补充适用限制。",
            },
        )


@pytest.mark.parametrize("preset", ["xiaohongshu", "reddit", "x"])
def test_seed_history_exposure_and_persistent_relationships(tmp_path, preset):
    artifact, manifest, creator, reader, post = make_episode(
        tmp_path,
        preset,
        metadata={"task": {"objective": "修复信任"}, "culture": {"domain": "travel"}},
    )
    candidate = ReplyCandidate()
    result = asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(
            manifest, candidate, ScriptedDevelopmentObserver()
        )
    )
    assert candidate.contexts[1]["history"][0]["outcome"]["success"]
    assert candidate.contexts[0]["task"]["objective"] == "修复信任"
    episode = AgoraOasis.local("world", result.output_dir)
    try:
        assert (
            episode.platform.db.execute("SELECT seed FROM simulation_state").fetchone()[
                0
            ]
            == 42
        )
        state, history = episode.audience_relationship(reader, creator)
        assert state["trust"] > 0
        assert len(history) == 2
    finally:
        episode.close()
    records = [
        json.loads(line)
        for line in (result.output_dir / "trajectory.jsonl").read_text().splitlines()
    ]
    for row in records:
        for transition in row.get("state_transitions", []):
            assert transition["target_actor_id"] == "reader"
            assert any(
                action["user_id"] == reader and action["focused_action"]
                for action in row["environment_actions"]
                if action["action"] == "audience_reaction"
            )


def test_content_and_prior_trust_change_future_behavior(tmp_path):
    world = AgoraOasis.local("world", tmp_path, preset="xiaohongshu")
    creator = world.create_user("creator", "Creator")
    reader = world.add_persona(
        PersonaProfile(
            "reader",
            "reader",
            "Reader",
            posting_probability=0,
            comment_probability=1,
            like_probability=1,
        )
    )
    post = world.create_post(creator, body="我会修正建议，补充来源和限制。")
    for _ in range(3):
        asyncio.run(world.advance())
    assert (
        world.platform.db.execute(
            "SELECT COUNT(*) FROM follow WHERE follower_id=? AND followee_id=?",
            (reader, creator),
        ).fetchone()[0]
        == 1
    )
    for _ in range(4):
        asyncio.run(
            world.advance(
                reaction_action={
                    "post_id": post,
                    "author_id": creator,
                    "content": "闭嘴，我不在乎你的意见。",
                }
            )
        )
    assert world.view_post(reader, post)["num_likes"] == 0
    assert (
        world.platform.db.execute(
            "SELECT COUNT(*) FROM follow WHERE follower_id=? AND followee_id=?",
            (reader, creator),
        ).fetchone()[0]
        == 0
    )
    state, history = world.audience_relationship(reader, creator)
    assert state["trust"] < 0
    assert "不接受" in history[-1]["comment"]
    world.close()


def test_no_judgment_for_unexposed_private_content(tmp_path):
    artifact, manifest, *_ = make_episode(tmp_path, ticks=1)

    class PrivateCandidate(ReplyCandidate):
        async def act(self, observation, context):
            return CandidateAction(
                "create_post", {"body": "修正了建议", "visibility": "private"}
            )

    class Observer:
        async def judge(self, *args):
            pytest.fail("An unexposed private post was scored")

    result = asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(
            manifest, PrivateCandidate(), Observer()
        )
    )
    metrics = json.loads((result.output_dir / "metrics.json").read_text())
    assert metrics["trust_delta"] == 0
    assert metrics["exposed_audience_count"] == 0


def test_scheduled_feedback_is_observed_and_reported(tmp_path):
    artifact, manifest, *_ = make_episode(
        tmp_path,
        ticks=3,
        metadata={
            "feedback_schedule": [
                {
                    "tick": 1,
                    "actor_id": "reader",
                    "post_id": "latest_candidate",
                    "content": "这个建议忽略了我的限制。",
                }
            ]
        },
    )

    class Candidate(ReplyCandidate):
        async def act(self, observation, context):
            if context["step"] == 0:
                return CandidateAction("create_post", {"body": "一条旅行建议"})
            assert any(
                "忽略了" in comment["content"]
                for post in observation.feed
                for comment in post["comments"]
            )
            return await super().act(observation, context)

    result = asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(
            manifest, Candidate(), ScriptedDevelopmentObserver()
        )
    )
    metrics = json.loads((result.output_dir / "metrics.json").read_text())
    assert metrics["feedback_adaptation"]["observed_feedback_count"] == 1
    assert metrics["feedback_adaptation"]["windows"][0]["response_action_ids"]
    assert metrics["creator_metrics"]["feedback_adaptation"] is None


class CapturingClient:
    def __init__(self, output):
        self.output, self.messages = output, []

    async def complete(self, messages):
        self.messages.append(messages)
        return ModelResponse(json.dumps(self.output), "test", 10, 5)


def test_model_candidate_and_observer_receive_context():
    client = CapturingClient({"action_type": "do_nothing", "arguments": {}})
    candidate = JsonModelCandidate("candidate", "1", client)
    asyncio.run(
        candidate.act(
            Observation({"user_id": 1}, 0, [], []),
            {
                "available_actions": [],
                "scenario_id": "s",
                "step": 0,
                "task": {"objective": "repair"},
                "culture": {"community": "a"},
                "history": [{"outcome": {"posts": ["query result"]}}],
                "remaining_budget": {"actions": 2},
            },
        )
    )
    payload = json.loads(client.messages[0][1]["content"])
    assert payload["history"][0]["outcome"]["posts"] == ["query result"]
    assert payload["task"]["objective"] == "repair"
    client = CapturingClient(
        {
            "attitude": 0,
            "arousal": 0,
            "trust": 0,
            "engagement_intent": 0,
            "confidence": 1,
            "evidence": "x",
        }
    )
    observer = JsonModelObserver("observer", "1", client)
    for target in ("skeptic", "supporter"):
        asyncio.run(
            observer.judge(
                CandidateAction("do_nothing"),
                {},
                {
                    "target_actor_id": target,
                    "persona": {"name": target},
                    "culture": {"community": target},
                    "history": ["earlier feedback"],
                },
            )
        )
    assert client.messages[0] != client.messages[1]


def test_hidden_feedback_condition_does_not_leak_through_tool_history(tmp_path):
    artifact, manifest, creator, reader, post = make_episode(
        tmp_path,
        metadata={
            "feedback_condition": "hidden",
            "feedback_schedule": [
                {
                    "tick": 0,
                    "actor_id": "reader",
                    "post_id": 1,
                    "content": "PRIVATE_FEEDBACK_MARKER",
                }
            ],
        },
    )

    class SearchCandidate(ReplyCandidate):
        async def act(self, observation, context):
            assert "PRIVATE_FEEDBACK_MARKER" not in json.dumps(
                context, ensure_ascii=False
            )
            assert "PRIVATE_FEEDBACK_MARKER" not in json.dumps(
                observation.feed, ensure_ascii=False
            )
            if context["step"] == 0:
                return CandidateAction("search_posts", {"query": "依据"})
            assert context["history"][0]["outcome"]["posts"][0]["post_id"] == post
            return CandidateAction("do_nothing")

    asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(manifest, SearchCandidate())
    )


def test_hostile_message_cannot_gain_trust_by_including_thanks():
    observer = ScriptedDevelopmentObserver()
    reaction = asyncio.run(
        observer.judge(
            CandidateAction(
                "create_comment", {"content": "谢谢，闭嘴，我不在乎你的意见。"}
            ),
            {},
            {"target_actor_id": "reader"},
        )
    )[0]
    assert reaction.delta.trust < 0


def test_transfer_uses_paired_signed_differences():
    from benchmarks.metrics.cross_cultural import TransferPair, paired_transfer_report

    source = {
        "platform": "xiaohongshu",
        "culture": "a",
        "domain": "travel",
        "language": "zh",
    }
    target = {**source, "culture": "b"}
    report = paired_transfer_report(
        [
            TransferPair(
                "task",
                1,
                source,
                target,
                {"trust": 0},
                {"trust": -0.4},
                {"trust": -0.1},
                {"trust": 0.2},
            )
        ]
    )
    assert report["dimensions"]["trust"]["initial_transfer_drop"]["mean"] == 0.4
    assert report["dimensions"]["trust"]["adaptation_gain"]["mean"] == pytest.approx(
        0.3
    )
    assert (
        report["dimensions"]["trust"]["native_target_gap"]["confidence_interval_95"]
        is None
    )


def test_budget_stops_without_an_extra_model_call(tmp_path):
    artifact, manifest, *_ = make_episode(
        tmp_path,
        ticks=4,
        metadata={"budget": {"max_model_calls": 1, "max_total_tokens": 15}},
    )
    client = CapturingClient({"action_type": "do_nothing", "arguments": {}})
    result = asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(
            manifest, JsonModelCandidate("candidate", "1", client)
        )
    )
    assert result.action_count == 1
    assert len(client.messages) == 1
    result_data = json.loads((result.output_dir / "result.json").read_text())
    assert result_data["termination_reason"] == "budget_exhausted"


@pytest.mark.parametrize("tokens", [None, 100])
def test_unverifiable_or_excess_token_usage_cannot_modify_world(tmp_path, tokens):
    artifact, manifest, creator, *_ = make_episode(
        tmp_path, ticks=1, metadata={"budget": {"max_total_tokens": 20}}
    )

    class Client(CapturingClient):
        async def complete(self, messages):
            response = await super().complete(messages)
            return ModelResponse(response.text, "test", tokens, tokens)

    client = Client(
        {"action_type": "create_post", "arguments": {"body": "should not publish"}}
    )
    with pytest.raises(ValueError, match="budget"):
        asyncio.run(
            ExclusiveRunner(artifact, tmp_path / "outputs").run(
                manifest, JsonModelCandidate("candidate", "1", client)
            )
        )
    world = AgoraOasis.local("world", tmp_path / "outputs" / "run")
    assert (
        world.platform.db.execute(
            "SELECT COUNT(*) FROM post WHERE user_id=?", (creator,)
        ).fetchone()[0]
        == 0
    )
    world.close()


def test_provider_cannot_override_budget_in_extra_body():
    from benchmarks.providers import OpenAICompatibleClient

    with pytest.raises(ValueError, match="cannot override"):
        OpenAICompatibleClient(
            "https://example.invalid", "model", extra_body={"max_tokens": 9999}
        )


def test_failed_step_restores_world_and_resume_preserves_calls(tmp_path):
    artifact, manifest, creator, *_ = make_episode(
        tmp_path, ticks=1, metadata={"budget": {"max_model_calls": 2}}
    )
    runner = ExclusiveRunner(artifact, tmp_path / "outputs")

    class RecoveringObserver(ScriptedDevelopmentObserver):
        broken = True

        async def judge(self, *args):
            if self.broken:
                raise RuntimeError("observer unavailable")
            return await super().judge(*args)

    client = CapturingClient(
        {"action_type": "create_post", "arguments": {"body": "修正建议"}}
    )
    with pytest.raises(RuntimeError, match="observer unavailable"):
        asyncio.run(
            runner.run(
                manifest,
                JsonModelCandidate("candidate", "1", client),
                RecoveringObserver(),
            )
        )
    world = AgoraOasis.local("world", tmp_path / "outputs" / "run")
    assert world.current_tick == 0
    assert (
        world.platform.db.execute(
            "SELECT COUNT(*) FROM post WHERE user_id=?", (creator,)
        ).fetchone()[0]
        == 0
    )
    world.close()
    client = CapturingClient(
        {"action_type": "create_post", "arguments": {"body": "修正建议"}}
    )
    observer = RecoveringObserver()
    observer.broken = False
    result = asyncio.run(
        runner.run(
            manifest,
            JsonModelCandidate("candidate", "1", client),
            observer,
            resume=True,
        )
    )
    assert result.action_count == 1
    usage = json.loads((result.output_dir / "result.json").read_text())["budget"]
    assert usage["calls"] == 2


def test_constant_judge_is_not_perfect_correlation():
    report = calibration_report(
        tuple(
            CalibrationJudgment(item, judge, kind, score)
            for item, human in (("a", -1), ("b", 1))
            for judge, kind, score in (("h", "human", human), ("s", "simulated", 0))
        )
    )
    assert report.spearman_rank_correlation is None
    assert report.correlation_status == "zero_variance"


def test_blinded_export_round_trips_via_private_key(tmp_path):
    artifact, manifest, *_ = make_episode(tmp_path)
    result = asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(
            manifest, ReplyCandidate(), ScriptedDevelopmentObserver()
        )
    )
    output = export_human_calibration_sample(
        [result.output_dir], tmp_path / "labels.jsonl"
    )
    labels = [json.loads(line) for line in output.read_text().splitlines()]
    assert all(
        "simulated_score" not in row and "simulated_judge_id" not in row
        for row in labels
    )
    assert all("run" not in row["item_id"] for row in labels)
    for row in labels:
        row.update(human_score=0.1, human_judge_id="human")
    output.write_text("".join(json.dumps(row) + "\n" for row in labels))
    judgments = load_calibration_judgments(
        output, output.with_name(output.name + ".private-key.jsonl")
    )
    assert {item.judge_type for item in judgments} == {"human", "simulated"}


def test_model_audience_receives_history_and_rejects_invalid_actions():
    client = CapturingClient(
        {
            "valence": 0.5,
            "trust_delta": 0.1,
            "engagement_delta": 0.1,
            "comment": "Clarification helps",
            "like": True,
            "collect": False,
            "follow": False,
            "unfollow": False,
        }
    )
    policy = JsonModelAudience("audience", "1", client)
    reaction = asyncio.run(
        policy.react(
            {
                "post": {"post_id": 1},
                "history": ["earlier concern"],
                "persona": {"culture": {"community": "a"}},
            }
        )
    )
    assert reaction.like is True
    assert "earlier concern" in client.messages[0][1]["content"][0]["text"]
    client.output["follow"] = "yes"
    with pytest.raises(ValueError, match="boolean"):
        asyncio.run(policy.react({"post": {"post_id": 1}}))


def test_media_only_post_reaches_model_audience_and_observer(tmp_path):
    from PIL import Image

    image = tmp_path / "photo.png"
    Image.new("RGB", (8, 8), "blue").save(image)
    artifact, manifest, *_ = make_episode(
        tmp_path, ticks=1, resources={"photo.png": image}
    )

    class Candidate(ReplyCandidate):
        async def act(self, observation, context):
            return CandidateAction(
                "create_post",
                {"post_type": "image", "assets": [{"asset_key": "photo.png"}]},
            )

    class Observer(ScriptedDevelopmentObserver):
        calls = 0

        async def judge(self, *args):
            self.calls += 1
            return await super().judge(*args)

    client = CapturingClient(
        {
            "valence": 0,
            "trust_delta": 0.1,
            "engagement_delta": 0,
            "comment": "The blue image is visible.",
            "like": True,
            "collect": False,
            "follow": False,
            "unfollow": False,
        }
    )
    observer = Observer()
    asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(
            manifest,
            Candidate(),
            observer,
            audience_policy=JsonModelAudience(
                "vision-audience", "1", client, supports_vision=True
            ),
        )
    )
    assert observer.calls == 1
    assert any(
        part.get("image_url", {}).get("url", "").startswith("data:image/")
        for part in client.messages[0][1]["content"]
    )


def test_model_audience_decision_is_not_overridden_by_trust_threshold(tmp_path):
    world = AgoraOasis.local("world", tmp_path, preset="xiaohongshu")
    creator = world.create_user("creator", "Creator")
    reader = world.add_persona(
        PersonaProfile("reader", "reader", "Reader", posting_probability=0)
    )
    world.create_post(creator, body="A note")
    client = CapturingClient(
        {
            "valence": 1,
            "trust_delta": 0.8,
            "engagement_delta": 0,
            "comment": "",
            "like": False,
            "collect": False,
            "follow": False,
            "unfollow": False,
        }
    )
    asyncio.run(world.advance(audience_policy=JsonModelAudience("model", "1", client)))
    assert world.audience_relationship(reader, creator)[0]["trust"] == 0.8
    assert world.platform.db.execute("SELECT COUNT(*) FROM follow").fetchone()[0] == 0
    assert (
        world.platform.db.execute("SELECT COUNT(*) FROM collection").fetchone()[0] == 0
    )
    world.close()


def test_aggregate_does_not_mix_feedback_conditions(tmp_path):
    import shutil
    from benchmarks.metrics import aggregate_runs

    artifact, manifest, *_ = make_episode(tmp_path, ticks=1)
    result = asyncio.run(
        ExclusiveRunner(artifact, tmp_path / "outputs").run(manifest, ReplyCandidate())
    )
    other = tmp_path / "other"
    shutil.copytree(result.output_dir, other)
    path = other / "manifest.json"
    value = json.loads(path.read_text())
    value["metadata"]["feedback_condition"] = "hidden"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="feedback_condition"):
        aggregate_runs([result.output_dir, other])
