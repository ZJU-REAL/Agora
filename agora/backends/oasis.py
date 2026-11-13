"""The transitional OASIS backend. New simulation services live in agora/."""

from oasis import AgoraOasis


def open_world(world_id, data_root="data/worlds", preset=None):
    return AgoraOasis.local(world_id, data_root, preset=preset)
