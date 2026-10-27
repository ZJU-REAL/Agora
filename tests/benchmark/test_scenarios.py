from pathlib import Path

from benchmarks.scenarios import load_scenario_suite


def test_xhs_conflict_development_suite():
    path = Path("configs/benchmarks/xhs-conflict-dev.scenarios.json")
    version, scenarios = load_scenario_suite(path)
    assert version == "xhs-conflict-dev-1"
    assert len(scenarios) == 10
    assert {scenario.category for scenario in scenarios} == {
        "questioning", "sarcasm", "misunderstanding", "bait",
        "factual_dispute", "hostility", "pile_on", "sincere_question",
        "spam", "cultural_norm"}
    assert all(scenario.expected_outcomes for scenario in scenarios)


def test_cross_platform_suites_have_cultural_pairs():
    all_scenarios = []
    for filename, platform in (
        ("reddit-conflict-dev.scenarios.json", "reddit"),
        ("x-conflict-dev.scenarios.json", "x"),
    ):
        _, scenarios = load_scenario_suite(Path("configs/benchmarks") / filename)
        assert all(item.metadata["platform"] == platform for item in scenarios)
        all_scenarios.extend(scenarios)
    pair_counts = {}
    for scenario in all_scenarios:
        pair_id = scenario.metadata["cultural_pair_id"]
        pair_counts[pair_id] = pair_counts.get(pair_id, 0) + 1
    assert set(pair_counts.values()) == {2}


def test_xhs_development_suites_cover_twenty_scenarios():
    total = 0
    for filename in ("xhs-conflict-dev.scenarios.json",
                     "xhs-conflict-extended.scenarios.json"):
        _, scenarios = load_scenario_suite(Path("configs/benchmarks") / filename)
        total += len(scenarios)
    assert total == 20
