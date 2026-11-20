"""Agora's social simulation services. Native world infrastructure with observable experiment jobs."""

from agora.recommendation import RecommendationConfig, RecommendationEngine
from agora.session import SocialSession

__all__ = [
    "AgoraWorld",
    "RecommendationConfig",
    "RecommendationEngine",
    "SocialSession",
    "WorldConfig",
]
__version__ = "0.7.0"


def __getattr__(name):
    if name in {"AgoraWorld", "WorldConfig"}:
        from agora import world

        return getattr(world, name)
    raise AttributeError(name)
