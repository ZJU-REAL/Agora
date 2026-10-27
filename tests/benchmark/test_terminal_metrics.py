import json

from benchmarks.metrics import compute_run_metrics


def test_metrics_include_terminal_delayed_effects(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "protocol_version": "v1", "world_artifact_version": "w1",
        "world_artifact_id": "world", "candidate_id": "candidate",
        "platform": "xiaohongshu", "scenario_id": "scenario", "seed": 1,
        "run_id": "run", "observer_pool_version": "pool",
        "exposure_mode": "controlled_exposure",
        "exposure_policy_version": "controlled-v1",
        "actors": [{"actor_id": "candidate", "role": "candidate"}],
    }), encoding="utf-8")
    before = {"attitude": 0, "arousal": 0, "trust": 0,
              "engagement_intent": 0}
    after = {"attitude": 0.2, "arousal": -0.1, "trust": 0.1,
             "engagement_intent": 0.1}
    records = [
        {"record_type": "step", "action": {"action_type": "do_nothing"},
         "state_transitions": []},
        {"record_type": "terminal_effects", "state_transitions": [
            {"before": before, "after": after}]},
    ]
    (tmp_path / "trajectory.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in records),
        encoding="utf-8")
    metrics = compute_run_metrics(tmp_path)
    assert metrics.attitude_delta == 0.2
    assert metrics.ticks == 1
