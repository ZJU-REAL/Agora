"""Public world entry point. No upstream agent/platform scheduler is used."""

from agora.core.world import AgoraWorld, WorldConfig


def open_world(world_id, data_root="data/worlds", preset=None):
    return AgoraWorld.local(world_id, data_root, preset=preset)


__all__ = ["AgoraWorld", "WorldConfig", "open_world"]
