import asyncio

import pytest

from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


@pytest.mark.parametrize("preset", ["xiaohongshu", "reddit", "x"])
def test_platform_runs_deterministic_multi_tick_episode(tmp_path, preset):
    worlds = []
    for suffix in ("a", "b"):
        sandbox = AgoraOasis.local(
            f"{preset}-{suffix}", tmp_path / "worlds", preset=preset)
        sandbox.set_seed(42)
        sandbox.add_persona(PersonaProfile(
            profile_id=f"creator-{suffix}", handle=f"creator_{suffix}",
            display_name="Creator", posting_probability=1.0,
            example_posts=("Frozen deterministic post",)))
        first = asyncio.run(sandbox.advance())
        second = asyncio.run(sandbox.advance())
        worlds.append((
            [item["action"] for item in first.actions + second.actions],
            [row[0] for row in sandbox.platform.db.execute(
                "SELECT content FROM post ORDER BY post_id").fetchall()],
            sandbox.current_tick,
        ))
        sandbox.close()
    assert worlds[0] == worlds[1]
    assert worlds[0][2] == 2
