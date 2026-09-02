from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformCapability:
    platform: str
    score: float
    dimensions: dict[str, float]


@dataclass(frozen=True)
class CrossCulturalProfile:
    strongest_platform: str
    weakest_platform: str
    base_effectiveness: float
    transfer_retention: float
    dimension_shifts: dict[str, float]


def build_cross_cultural_profile(
        capabilities: list[PlatformCapability]) -> CrossCulturalProfile:
    if len({item.platform for item in capabilities}) < 2:
        raise ValueError("Cross-cultural profiles require at least two platforms")
    strongest = max(capabilities, key=lambda item: item.score)
    weakest = min(capabilities, key=lambda item: item.score)
    retention = (weakest.score / strongest.score
                 if strongest.score > 0 else 0.0)
    dimensions = set(strongest.dimensions) & set(weakest.dimensions)
    shifts = {name: round(weakest.dimensions[name]
                          - strongest.dimensions[name], 6)
              for name in sorted(dimensions)}
    return CrossCulturalProfile(
        strongest.platform, weakest.platform, round(strongest.score, 6),
        round(retention, 6), shifts)
