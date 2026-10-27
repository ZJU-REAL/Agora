from benchmarks.ablations import build_ablation_matrix


def test_ablation_matrix_separates_mechanism_variants():
    conditions = build_ablation_matrix(
        ("pool-a", "pool-b"), ("balanced", "hostile-heavy"))
    assert len(conditions) == 8
    assert len({item.condition_id for item in conditions}) == 8
    assert {item.evaluation_awareness for item in conditions} == {False, True}
