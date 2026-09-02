from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONTENT_FORMATS = {"text", "image", "gallery", "video"}


@dataclass(frozen=True)
class CreatorTask:
    task_id: str
    platform: str
    content_format: str
    objective: str
    max_ticks: int
    feedback_ticks: tuple[int, ...] = ()
    required_assets: int = 0
    persona_constraints: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.platform not in {"xiaohongshu", "reddit", "x"}:
            raise ValueError(f"Unsupported platform: {self.platform}")
        if self.content_format not in CONTENT_FORMATS:
            raise ValueError(f"Unsupported content format: {self.content_format}")
        expected = {"text": 0, "image": 1, "gallery": 2, "video": 1}
        if self.required_assets < expected[self.content_format]:
            raise ValueError("Task does not provide enough required assets")
        if self.max_ticks < 1 or any(
                tick < 1 or tick >= self.max_ticks for tick in self.feedback_ticks):
            raise ValueError("Feedback ticks must occur inside the episode")


@dataclass(frozen=True)
class OperationTask:
    task_id: str
    platform: str
    objective: str
    max_ticks: int
    allowed_formats: tuple[str, ...]
    persona_id: str
    pressure_event_ticks: tuple[int, ...] = ()

    def validate(self) -> None:
        if self.max_ticks < 2:
            raise ValueError("Operation tasks require at least two ticks")
        if not self.allowed_formats or not set(self.allowed_formats) <= CONTENT_FORMATS:
            raise ValueError("Operation task has invalid content formats")
        if any(tick < 1 or tick >= self.max_ticks
               for tick in self.pressure_event_ticks):
            raise ValueError("Pressure event tick is outside the episode")


def load_creator_tasks(path: str | Path) -> tuple[CreatorTask, ...]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = tuple(CreatorTask(
        task_id=item["task_id"], platform=item["platform"],
        content_format=item["content_format"], objective=item["objective"],
        max_ticks=int(item["max_ticks"]),
        feedback_ticks=tuple(item.get("feedback_ticks", [])),
        required_assets=int(item.get("required_assets", 0)),
        persona_constraints=dict(item.get("persona_constraints", {})))
                  for item in value["tasks"])
    for task in tasks:
        task.validate()
    return tasks
