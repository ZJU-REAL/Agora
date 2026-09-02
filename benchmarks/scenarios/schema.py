from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


@dataclass(frozen=True)
class ScenarioUser:
    actor_id: str
    handle: str
    display_name: str
    role: str
    bio: str = ""


@dataclass(frozen=True)
class ScenarioPost:
    author_actor_id: str
    body: str
    title: str | None = None
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictScenario:
    scenario_id: str
    category: str
    description: str
    candidate_actor_id: str
    users: tuple[ScenarioUser, ...]
    posts: tuple[ScenarioPost, ...]
    max_ticks: int = 3
    expected_outcomes: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ConflictScenario":
        return cls(
            scenario_id=value["scenario_id"],
            category=value["category"],
            description=value["description"],
            candidate_actor_id=value["candidate_actor_id"],
            users=tuple(ScenarioUser(**item) for item in value["users"]),
            posts=tuple(ScenarioPost(
                author_actor_id=item["author_actor_id"], body=item["body"],
                title=item.get("title"), topics=tuple(item.get("topics", [])))
                        for item in value["posts"]),
            max_ticks=int(value.get("max_ticks", 3)),
            expected_outcomes=dict(value.get("expected_outcomes", {})),
            metadata=dict(value.get("metadata", {})),
        )


def load_scenario_suite(path: str | Path) -> tuple[str, tuple[ConflictScenario, ...]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = tuple(ConflictScenario.from_dict({
        **item,
        "metadata": {"platform": value["platform"],
                     **item.get("metadata", {})},
    }) for item in value["scenarios"])
    ids = [scenario.scenario_id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("Scenario IDs must be unique")
    return value["suite_version"], scenarios


def materialize_scenario(scenario: ConflictScenario,
                         world_id: str,
                         data_root: str | Path,
                         seed: int = 0) -> tuple[AgoraOasis, dict[str, int]]:
    platform = scenario.metadata.get("platform", "xiaohongshu")
    sandbox = AgoraOasis.local(world_id, data_root, preset=platform)
    sandbox.set_seed(seed)
    user_ids = {}
    for user in scenario.users:
        if user.role == "npc":
            user_ids[user.actor_id] = sandbox.add_persona(PersonaProfile(
                profile_id=f"{scenario.scenario_id}-{user.actor_id}",
                handle=user.handle, display_name=user.display_name,
                bio=user.bio, locale=("zh-CN" if platform == "xiaohongshu"
                                      else "en-US")))
        else:
            user_ids[user.actor_id] = sandbox.create_user(
                user.handle, user.display_name, user.bio)
    for post in scenario.posts:
        sandbox.create_post(user_ids[post.author_actor_id], body=post.body,
                            title=post.title, topics=list(post.topics),
                            language="zh-CN" if platform == "xiaohongshu"
                            else "en")
    return sandbox, user_ids
