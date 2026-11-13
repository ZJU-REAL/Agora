from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agora.backends.oasis import open_world
from agora.demo import populate
from agora.recommendation import RecommendationConfig
from agora.runner import JsonSessionPolicy, run_sessions
from agora.server import serve
from agora.session import SocialSession


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agora")
    parser.add_argument("--data-root", default="data/worlds")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser(
        "demo", help="Create a synthetic world and browsing trajectories"
    )
    demo.add_argument("world_id", nargs="?", default="agora-demo")
    demo.add_argument("--seed", type=int, default=42)
    console = commands.add_parser(
        "serve", help="Open the local social sandbox and replay console"
    )
    console.add_argument("world_id")
    console.add_argument("--port", type=int, default=8765)
    simulate = commands.add_parser(
        "simulate", help="Run accounts through persistent browsing sessions"
    )
    simulate.add_argument("world_id")
    simulate.add_argument("--user-id", type=int, action="append", required=True)
    simulate.add_argument("--ticks", type=int, default=3)
    simulate.add_argument("--steps-per-tick", type=int, default=4)
    simulate.add_argument(
        "--recommendation-config", help="JSON RecommendationConfig file"
    )
    simulate.add_argument(
        "--provider-config",
        help="Optional model provider JSON; keys use environment variables",
    )
    simulate.add_argument("--goal", default="浏览、创作并经营这个社交账号。")
    export = commands.add_parser(
        "export", help="Export a session's public trajectory and researcher diagnostics"
    )
    export.add_argument("world_id")
    export.add_argument("--session-id", type=int, required=True)
    export.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if (
        args.command != "demo"
        and not (Path(args.data_root) / args.world_id / "sandbox.db").is_file()
    ):
        parser.error(
            "World does not exist; create it with agora demo or agora-oasis world-create"
        )
    world = open_world(
        args.world_id,
        args.data_root,
        preset="xiaohongshu" if args.command == "demo" else None,
    )
    try:
        if args.command == "demo":
            output = populate(world)
            world.set_seed(args.seed)
            output["simulation"] = asyncio.run(
                run_sessions(world, [output["reader_id"], *output["creator_ids"][:2]])
            )
        elif args.command == "serve":
            serve(world, port=args.port)
            return 0
        elif args.command == "simulate":
            config = (
                RecommendationConfig(
                    **json.loads(Path(args.recommendation_config).read_text())
                )
                if args.recommendation_config
                else None
            )
            factory = None
            if args.provider_config:
                # Provider implementations are temporarily shared with the
                # benchmark layer; the session contract itself is independent.
                from benchmarks.providers import (
                    build_model_client,
                    load_provider_config,
                )

                spec = load_provider_config(args.provider_config)

                def factory(user):
                    row = world.platform.db.execute(
                        "SELECT persona_json FROM persona WHERE user_id = ?", (user,)
                    ).fetchone()
                    from agora.backends.visual import session_visual_parts

                    return JsonSessionPolicy(
                        build_model_client(spec),
                        args.goal,
                        json.loads(row[0]) if row else {},
                        visual_builder=(
                            lambda observation: session_visual_parts(world, observation)
                        )
                        if spec.get("supports_vision", False)
                        else None,
                    )

            output = asyncio.run(
                run_sessions(
                    world,
                    args.user_id,
                    args.ticks,
                    args.steps_per_tick,
                    factory,
                    config,
                )
            )
        else:
            session = SocialSession(world, args.session_id)
            output = {
                "format_version": "agora-session-v1",
                "world_id": args.world_id,
                "session_id": args.session_id,
                "config": session.config.__dict__,
                "trajectory": session.trajectory(),
                "requests": session.diagnostics(),
            }
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            output = {"output": str(target), "events": len(output["trajectory"])}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    finally:
        world.close()


if __name__ == "__main__":
    raise SystemExit(main())
