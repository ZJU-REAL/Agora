from benchmarks.metrics import (PlatformCapability,
                                build_cross_cultural_profile)
from benchmarks.tasks import load_creator_tasks


def test_multimodal_creator_task_suite():
    tasks = load_creator_tasks("configs/benchmarks/creator-tasks-dev.json")
    assert {task.content_format for task in tasks} == {
        "text", "image", "gallery", "video"}
    assert {task.platform for task in tasks} == {"xiaohongshu", "reddit", "x"}


def test_cross_cultural_profile_reports_retention_and_dimension_shift():
    profile = build_cross_cultural_profile([
        PlatformCapability("reddit", 0.8, {"conflict": 0.9, "timing": 0.7}),
        PlatformCapability("xiaohongshu", 0.6,
                           {"conflict": 0.5, "timing": 0.8}),
        PlatformCapability("x", 0.7, {"conflict": 0.7, "timing": 0.6}),
    ])
    assert profile.strongest_platform == "reddit"
    assert profile.transfer_retention == 0.75
    assert profile.dimension_shifts == {"conflict": -0.4, "timing": 0.1}
