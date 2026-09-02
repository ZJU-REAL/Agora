from benchmarks.calibration import (CalibrationJudgment, calibration_report,
                                    load_calibration_judgments,
                                    repeated_judgment_agreement)


def test_calibration_reports_human_alignment():
    judgments = tuple(
        CalibrationJudgment(item, judge, kind, score)
        for item, human, simulated in (
            ("a", 0.8, 0.7), ("b", 0.2, 0.3), ("c", -0.5, -0.4))
        for judge, kind, score in (
            ("human-1", "human", human),
            ("sim-1", "simulated", simulated)))
    report = calibration_report(judgments)
    assert report.spearman_rank_correlation == 1.0
    assert report.pairwise_direction_agreement == 1.0


def test_repeated_judgment_agreement():
    judgments = (
        CalibrationJudgment("a", "judge", "simulated", 0.5),
        CalibrationJudgment("a", "judge", "simulated", 0.5),
    )
    assert repeated_judgment_agreement(judgments, "judge") == 1.0


def test_load_completed_human_export_format(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text(
        '{"item_id":"a","human_score":0.5,"human_judge_id":"h1",'
        '"simulated_score":0.4,"simulated_judge_id":"o1"}\n',
        encoding="utf-8")
    judgments = load_calibration_judgments(path)
    assert [(item.judge_type, item.score) for item in judgments] == [
        ("human", 0.5), ("simulated", 0.4)]
