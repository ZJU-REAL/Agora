"""Audience behavior policies, independent of benchmark evaluation judges."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AudienceReaction:
    valence: float = 0.0
    trust_delta: float = 0.0
    engagement_delta: float = 0.0
    comment: str = ""
    like: bool | None = None
    collect: bool = False
    follow: bool = False
    unfollow: bool = False
    unlike: bool = False

    def __post_init__(self):
        for name in ("valence", "trust_delta", "engagement_delta"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or (not math.isfinite(value) or not -1 <= value <= 1)
            ):
                raise ValueError(f"Invalid audience {name}")
        if not isinstance(self.comment, str) or len(self.comment) > 4000:
            raise ValueError("Invalid audience comment")
        if self.like is not None and not isinstance(self.like, bool):
            raise ValueError("Audience like must be boolean or null")
        for name in ("collect", "follow", "unfollow", "unlike"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"Audience {name} must be boolean")
        if self.follow and self.unfollow:
            raise ValueError("Cannot follow and unfollow simultaneously")
        if self.like is True and self.unlike:
            raise ValueError("Cannot like and unlike simultaneously")


class AudiencePolicy(Protocol):
    policy_id: str
    policy_version: str

    async def react(self, context: dict[str, Any]) -> AudienceReaction: ...


class ScriptedDevelopmentAudience:
    """Transparent lexical development baseline, not a human simulator oracle."""

    policy_id = "contextual-scripted-development"
    policy_version = "1"
    uses_behavior_probabilities = True

    async def react(self, context):
        content = context["content"].casefold()
        persona = context["persona"]
        norms = persona.get("culture", {})
        hostile = any(
            word.casefold() in content
            for word in (
                "闭嘴",
                "愚蠢",
                "不在乎",
                "与你无关",
                "与我无关",
                "shut up",
                "idiot",
                "don't care",
                *norms.get("avoid_phrases", []),
            )
        )
        correction = any(
            word.casefold() in content
            for word in (
                "调整",
                "修正",
                "来源",
                "限制",
                "依据",
                "更正",
                "说清楚",
                "update",
                "source",
                "correct",
                "constraint",
                "evidence",
                *norms.get("prefer_phrases", []),
            )
        )
        valence = -1.0 if hostile else 0.6 if correction else 0.0
        excerpt = context["content"][:100]
        english = persona.get("locale", "zh-CN").startswith("en")
        if hostile:
            comment = (
                f'I disagree with "{excerpt}". Please address my concern.'
                if english
                else f"我不接受“{excerpt}”这种回应，请回应具体问题。"
            )
        elif correction:
            comment = (
                f'The clarification in "{excerpt}" helps; I will check it.'
                if english
                else f"“{excerpt}”回应了部分问题，我会继续核实。"
            )
        else:
            comment = (
                f'What evidence or constraints support "{excerpt}"?'
                if english
                else f"关于“{excerpt}”，能补充依据和适用条件吗？"
            )
        return AudienceReaction(
            valence=valence,
            trust_delta=valence * 0.2,
            engagement_delta=valence * 0.15,
            comment=comment,
        )
