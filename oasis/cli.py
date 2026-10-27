from __future__ import annotations

import argparse
import asyncio
import json

from oasis import AgoraOasis, AssetInput, DatasetImporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agora-oasis")
    parser.add_argument("--data-root", default="data/worlds")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("world-create", help="Create a local world")
    create.add_argument("world_id")
    create.add_argument("--seed", type=int, default=0)
    create.add_argument("--preset", default="generic",
                        choices=("generic", "xiaohongshu", "reddit", "x"))

    import_data = commands.add_parser("data-import",
                                      help="Import a dataset manifest")
    import_data.add_argument("world_id")
    import_data.add_argument("manifest")

    inspect = commands.add_parser("world-inspect",
                                  help="Show world entity counts")
    inspect.add_argument("world_id")

    user = commands.add_parser("user-create", help="Create a local user")
    user.add_argument("world_id")
    user.add_argument("handle")
    user.add_argument("--display-name")

    post = commands.add_parser("post-create", help="Publish text or media")
    post.add_argument("world_id")
    post.add_argument("--author-id", type=int, required=True)
    post.add_argument("--body", default="")
    post.add_argument("--title")
    post.add_argument("--image", action="append", default=[],
                      help="Image path; repeat to publish an ordered gallery")
    post.add_argument("--video", help="Video path")
    post.add_argument("--cover", help="Optional video cover image path")
    post.add_argument("--topic", action="append", default=[])
    post.add_argument("--location")
    post.add_argument("--community")
    post.add_argument("--language")

    view = commands.add_parser("post-view", help="Read a post and its media")
    view.add_argument("world_id")
    view.add_argument("post_id", type=int)
    view.add_argument("--user-id", type=int, required=True)

    run = commands.add_parser("run", help="Advance scripted AI creators")
    run.add_argument("world_id")
    run.add_argument("--ticks", type=int, default=1)

    snapshot = commands.add_parser("snapshot", help="Snapshot a world")
    snapshot.add_argument("world_id")
    snapshot.add_argument("--snapshot-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    preset = args.preset if args.command == "world-create" else None
    sandbox = AgoraOasis.local(args.world_id, args.data_root, preset=preset)
    try:
        if args.command == "world-create":
            sandbox.set_seed(args.seed)
            output = {
                "world_id": args.world_id,
                "database": str(sandbox.config.database_path),
                "media": str(sandbox.config.media_path),
                "seed": args.seed,
                "preset": sandbox.preset.name,
            }
        elif args.command == "data-import":
            report = asyncio.run(
                DatasetImporter(sandbox).import_manifest(args.manifest))
            output = report.__dict__
        elif args.command == "world-inspect":
            output = _world_summary(sandbox)
        elif args.command == "user-create":
            user_id = sandbox.create_user(
                args.handle, args.display_name or args.handle)
            output = {"user_id": user_id, "handle": args.handle}
        elif args.command == "post-create":
            if args.video and args.image:
                raise ValueError("--video cannot be combined with --image")
            if args.cover and not args.video:
                raise ValueError("--cover requires --video")
            if args.video:
                post_type = "video"
                assets = [AssetInput(args.video)]
                if args.cover:
                    assets.append(AssetInput(args.cover, role="cover"))
            else:
                post_type = ("gallery" if len(args.image) > 1 else
                             "image" if args.image else "text")
                assets = [AssetInput(path) for path in args.image]
            post_id = sandbox.create_post(
                args.author_id, body=args.body, title=args.title,
                post_type=post_type, assets=assets, topics=args.topic,
                location=args.location, community=args.community,
                language=args.language)
            output = {"success": True, "post_id": post_id,
                      "post_type": post_type, "asset_count": len(assets)}
        elif args.command == "post-view":
            output = sandbox.view_post(args.user_id, args.post_id)
        elif args.command == "run":
            if args.ticks < 1:
                raise ValueError("--ticks must be at least 1")
            results = [asyncio.run(sandbox.advance()) for _ in range(args.ticks)]
            output = {
                "ticks": len(results),
                "current_tick": sandbox.current_tick,
                "actions": sum(len(result.actions) for result in results),
            }
        elif args.command == "snapshot":
            path = sandbox.snapshot(args.snapshot_id)
            output = {"snapshot": str(path), "tick": sandbox.current_tick}
        else:
            raise AssertionError(args.command)
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        sandbox.close()


def _world_summary(sandbox: AgoraOasis) -> dict:
    db = sandbox.platform.db
    tables = ("user", "persona", "post", "comment", "media_asset",
              "sandbox_event")
    counts = {
        table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    return {
        "world_id": sandbox.config.world_id,
        "preset": sandbox.preset.name,
        "current_tick": sandbox.current_tick,
        "counts": counts,
    }


if __name__ == "__main__":
    raise SystemExit(main())
