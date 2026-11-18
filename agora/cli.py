from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agora.demo import populate
from agora.recommendation import RecommendationConfig
from agora.runner import JsonSessionPolicy, run_sessions
from agora.server import serve
from agora.session import SocialSession
from agora.world import open_world


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
    console.add_argument(
        "--base-path", default="", help="Reverse-proxy mount, e.g. /agora"
    )
    console.add_argument("--public-origin", help="HTTPS origin served by IAP")
    console.add_argument("--max-active-agents", type=int, default=32)
    console.add_argument("--max-active-runs", type=int, default=1)
    console.add_argument("--max-run-actions", type=int, default=2400)
    console.add_argument(
        "--api-port", type=int, help="AI account API port (default console port + 1)"
    )
    console.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create a synthetic source world when empty",
    )
    console.add_argument(
        "--provider-config",
        action="append",
        default=[],
        help="Register model provider JSON files for the experiment console",
    )
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
        and not (args.command == "serve" and args.bootstrap)
        and not (Path(args.data_root) / args.world_id / "sandbox.db").is_file()
    ):
        parser.error(
            "World does not exist; use agora serve --bootstrap or agora-world world-create"
        )
    world = open_world(
        args.world_id,
        args.data_root,
        preset="xiaohongshu"
        if args.command == "demo" or args.command == "serve" and args.bootstrap
        else None,
    )
    try:
        if args.command == "demo":
            output = populate(world)
            world.set_seed(args.seed)
            output["simulation"] = asyncio.run(
                run_sessions(world, [output["reader_id"], *output["creator_ids"][:2]])
            )
        elif args.command == "serve":
            if (
                args.bootstrap
                and not world.db.execute("SELECT 1 FROM user LIMIT 1").fetchone()
            ):
                populate(world)
            from agora.models import load_provider_config

            providers = {
                Path(path).stem: load_provider_config(path)
                for path in args.provider_config
            }
            serve(
                world,
                port=args.port,
                api_port=args.api_port,
                providers=providers,
                bootstrap=args.bootstrap,
                base_path=args.base_path,
                public_origin=args.public_origin,
                max_active_agents=args.max_active_agents,
                max_active_runs=args.max_active_runs,
                max_run_actions=args.max_run_actions,
            )
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
                from agora.models import (
                    build_model_client,
                    load_provider_config,
                )

                spec = load_provider_config(args.provider_config)

                def factory(user):
                    row = world.db.execute(
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
