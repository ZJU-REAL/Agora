from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path

from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npcs", type=int, default=100)
    parser.add_argument("--ticks", type=int, default=2)
    parser.add_argument("--preset", default="xiaohongshu",
                        choices=("xiaohongshu", "reddit", "x"))
    args = parser.parse_args(argv)
    if args.npcs < 1 or args.ticks < 1:
        raise ValueError("--npcs and --ticks must be positive")

    with tempfile.TemporaryDirectory(prefix="agora-stress-") as temp:
        sandbox = AgoraOasis.local("stress", Path(temp), preset=args.preset)
        sandbox.set_seed(42)
        started = time.monotonic()
        for index in range(args.npcs):
            sandbox.add_persona(PersonaProfile(
                profile_id=f"npc-{index}", handle=f"npc_{index}",
                display_name=f"NPC {index}", posting_probability=0.0,
                comment_probability=0.0))
        setup_seconds = time.monotonic() - started
        started = time.monotonic()
        for _ in range(args.ticks):
            asyncio.run(sandbox.advance())
        run_seconds = time.monotonic() - started
        output = {
            "preset": args.preset,
            "npcs": args.npcs,
            "ticks": args.ticks,
            "setup_seconds": round(setup_seconds, 3),
            "run_seconds": round(run_seconds, 3),
            "final_tick": sandbox.current_tick,
        }
        sandbox.close()
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
