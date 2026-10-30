from __future__ import annotations

from dataclasses import dataclass
import math
import statistics


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
    """Legacy platform spread summary; this does not measure cultural transfer."""
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


@dataclass(frozen=True)
class TransferPair:
    pair_id: str
    seed: int
    source_context: dict[str, str]
    target_context: dict[str, str]
    source_scores: dict[str, float]
    target_initial_scores: dict[str, float]
    target_adapted_scores: dict[str, float]
    native_target_scores: dict[str, float]


def paired_transfer_report(pairs: list[TransferPair]) -> dict:
    """Report paired dimension differences, never a strongest/weakest ratio."""
    if not pairs or len({(pair.pair_id, pair.seed) for pair in pairs}) != len(pairs):
        raise ValueError("Transfer requires unique task/seed pairs")
    contexts = (pairs[0].source_context, pairs[0].target_context)
    dimensions = set(pairs[0].source_scores)
    for pair in pairs:
        for context in (pair.source_context, pair.target_context):
            if set(context) != {"platform", "culture", "domain", "language"}:
                raise ValueError("Transfer context needs platform, culture, domain and language")
        if (pair.source_context, pair.target_context) != contexts or contexts[0] == contexts[1]:
            raise ValueError("Transfer pairs must share a distinct source/target context")
        for scores in (pair.source_scores, pair.target_initial_scores,
                       pair.target_adapted_scores, pair.native_target_scores):
            if not dimensions or set(scores) != dimensions or any(
                    isinstance(value, bool) or not math.isfinite(value) for value in scores.values()):
                raise ValueError("Transfer dimensions must match and be finite")
    def summarize(values):
        mean = statistics.fmean(values)
        margin = (1.96 * statistics.stdev(values) / math.sqrt(len(values))
                  if len(values) > 1 else None)
        return {"mean": round(mean, 12), "confidence_interval_95": (
            [round(mean - margin, 12), round(mean + margin, 12)] if margin is not None else None)}
    return {"source_context": contexts[0], "target_context": contexts[1],
            "pair_count": len(pairs), "dimensions": {name: {
                "initial_transfer_drop": summarize([
                    pair.source_scores[name] - pair.target_initial_scores[name] for pair in pairs]),
                "adaptation_gain": summarize([
                    pair.target_adapted_scores[name] - pair.target_initial_scores[name] for pair in pairs]),
                "native_target_gap": summarize([
                    pair.native_target_scores[name] - pair.target_adapted_scores[name] for pair in pairs]),
            } for name in sorted(dimensions)}}
