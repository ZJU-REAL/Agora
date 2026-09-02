from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from oasis.agora_types import Observation


class ActorRole(str, Enum):
    CANDIDATE = "candidate"
    NPC = "npc"
    OBSERVER = "observer"
    ANCHOR = "anchor"


class ExposureMode(str, Enum):
    CONTROLLED = "controlled_exposure"
    DETERMINISTIC_FEED = "deterministic_feed"
    LEARNED_RECOMMENDER = "learned_recommender"


MAIN_LEADERBOARD_EXPOSURE_MODES = {
    ExposureMode.CONTROLLED,
    ExposureMode.DETERMINISTIC_FEED,
}


@dataclass(frozen=True)
class ActorSpec:
    actor_id: str
    role: ActorRole
    policy_id: str
    policy_version: str
    user_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateAction:
    action_type: str
    arguments: dict[str, Any] = field(default_factory=dict)
    rationale: str | None = None


class CandidatePolicy(Protocol):
    policy_id: str
    policy_version: str

    async def act(self, observation: Observation,
                  context: dict[str, Any]) -> CandidateAction:
        ...


@dataclass(frozen=True)
class EpisodeManifest:
    protocol_version: str
    world_artifact_version: str
    world_artifact_id: str
    candidate_id: str
    platform: str
    scenario_id: str
    seed: int
    run_id: str
    observer_pool_version: str
    actors: tuple[ActorSpec, ...]
    max_ticks: int
    exposure_mode: ExposureMode = ExposureMode.CONTROLLED
    exposure_policy_version: str = "controlled-dynamic-v2"
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        identifiers = {
            "protocol_version": self.protocol_version,
            "world_artifact_version": self.world_artifact_version,
            "world_artifact_id": self.world_artifact_id,
            "candidate_id": self.candidate_id,
            "platform": self.platform,
            "scenario_id": self.scenario_id,
            "run_id": self.run_id,
            "observer_pool_version": self.observer_pool_version,
            "exposure_policy_version": self.exposure_policy_version,
        }
        for name, value in identifiers.items():
            if not value or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
                                             value):
                raise ValueError(f"Invalid {name}: {value!r}")
        if self.max_ticks < 1:
            raise ValueError("max_ticks must be at least 1")
        if self.exposure_mode not in MAIN_LEADERBOARD_EXPOSURE_MODES:
            raise ValueError(
                "Learned recommenders are forbidden in main-score episodes")
        candidates = [actor for actor in self.actors
                      if actor.role == ActorRole.CANDIDATE]
        if len(candidates) != 1:
            raise ValueError("Exclusive episodes require exactly one candidate")
        if candidates[0].actor_id != self.candidate_id:
            raise ValueError("candidate_id does not match the candidate actor")
        if candidates[0].user_id is None:
            raise ValueError("Candidate actor requires a sandbox user_id")
        actor_ids = [actor.actor_id for actor in self.actors]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("Actor IDs must be unique")

    def write(self, path: str | Path) -> None:
        self.validate()
        Path(path).write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
