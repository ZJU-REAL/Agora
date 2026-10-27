from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from benchmarks.protocol import CandidateAction


def _bounded(value: float) -> float:
    return max(-1.0, min(1.0, round(value, 6)))


@dataclass(frozen=True)
class SocialState:
    attitude: float = 0.0
    arousal: float = 0.0
    trust: float = 0.0
    engagement_intent: float = 0.0

    def apply(self, delta: "StateDelta", confidence: float = 1.0,
              decay: float = 0.0) -> "SocialState":
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not 0.0 <= decay <= 1.0:
            raise ValueError("decay must be between 0 and 1")
        retained = 1.0 - decay
        return SocialState(
            attitude=_bounded(self.attitude * retained
                              + delta.attitude * confidence),
            arousal=_bounded(self.arousal * retained
                             + delta.arousal * confidence),
            trust=_bounded(self.trust * retained + delta.trust * confidence),
            engagement_intent=_bounded(
                self.engagement_intent * retained
                + delta.engagement_intent * confidence),
        )


@dataclass(frozen=True)
class StateDelta:
    attitude: float = 0.0
    arousal: float = 0.0
    trust: float = 0.0
    engagement_intent: float = 0.0

    def __post_init__(self):
        for name, value in self.__dict__.items():
            if not -1.0 <= value <= 1.0:
                raise ValueError(f"{name} delta must be between -1 and 1")


@dataclass(frozen=True)
class ObserverJudgment:
    observer_id: str
    observer_version: str
    target_actor_id: str
    delta: StateDelta
    confidence: float
    evidence: str
    delay_ticks: int = 0
    effect_scope: str = "direct"

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.delay_ticks < 0:
            raise ValueError("delay_ticks cannot be negative")
        if self.effect_scope not in {"direct", "bystander"}:
            raise ValueError("effect_scope must be direct or bystander")


class ObserverPolicy(Protocol):
    observer_id: str
    observer_version: str

    async def judge(self, action: CandidateAction, outcome: dict,
                    context: dict) -> tuple[ObserverJudgment, ...]:
        ...


@dataclass(frozen=True)
class StateTransition:
    action_id: str
    target_actor_id: str
    before: SocialState
    after: SocialState
    judgment: ObserverJudgment
