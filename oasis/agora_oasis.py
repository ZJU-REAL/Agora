"""Compatibility imports for pre-0.3 Agora clients. Use oasis.world instead."""
from oasis.world import AgoraWorld, WorldConfig

AgoraOasis = AgoraWorld
AgoraOasisConfig = WorldConfig
__all__ = ["AgoraOasis", "AgoraOasisConfig"]
