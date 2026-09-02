import json

from benchmarks.runners.exclusive.runner import ExclusiveRunner


def test_pending_judgment_round_trip():
    value = {
        "observer_id": "observer", "observer_version": "1",
        "target_actor_id": "npc",
        "delta": {"attitude": 0.1, "arousal": 0, "trust": 0.1,
                  "engagement_intent": 0},
        "confidence": 0.8, "evidence": "delayed bystander effect",
        "delay_ticks": 1, "effect_scope": "bystander",
    }
    restored = ExclusiveRunner._judgment_from_dict(
        json.loads(json.dumps(value)))
    assert restored.delta.attitude == 0.1
    assert restored.effect_scope == "bystander"
