"""Local research console. A single owner thread serializes world mutations."""

from __future__ import annotations

import asyncio
import json
import selectors
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agora.api import AgentAPI, PlatformHub
from agora.recommendation import RecommendationEngine
from agora.session import SocialSession
from agora.web_support import page, validate_mount


def make_handler(
    world,
    manager=None,
    hub=None,
    api_only=False,
    base_path="",
    public_origin=None,
    registry=None,
):
    validate_mount(base_path, public_origin)
    RecommendationEngine(world.db)
    hub = hub or PlatformHub(world, manager=manager)
    native = AgentAPI(hub)

    class Handler(BaseHTTPRequestHandler):
        def parsed(self):
            parsed = urlparse(self.path)
            if base_path:
                if parsed.path == base_path:
                    return parsed._replace(path="/")
                if not parsed.path.startswith(base_path + "/"):
                    raise FileNotFoundError("Unknown mount path")
                return parsed._replace(path=parsed.path[len(base_path) :])
            return parsed

        def valid_origin(self):
            origin = self.headers.get("Origin")
            return not origin or origin in {
                f"http://{self.headers.get('Host')}",
                public_origin,
            }

        def log_message(self, format, *args):
            pass

        def reply(self, status, value, content_type="application/json; charset=utf-8"):
            body = (
                json.dumps(value, ensure_ascii=False).encode()
                if isinstance(value, (dict, list))
                else value
            )
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                parsed = self.parsed()
                query = parse_qs(parsed.query)
                if parsed.path.startswith("/v1/"):
                    status, value, mime = native.dispatch(
                        "GET", parsed.path, query, {}, self.headers.get("Authorization")
                    )
                    self.reply(status, value, mime or "application/json; charset=utf-8")
                    return
                if api_only or self.headers.get("Authorization", "").startswith(
                    "Bearer "
                ):
                    self.reply(
                        403,
                        {
                            "error": "AI accounts use the /v1 API; research routes are unavailable here"
                        },
                    )
                    return
                world, manager = hub.select(query.get("platform", [None])[0])
                if parsed.path in {
                    "/static/native.js",
                    "/static/native.css",
                    "/static/studio.js",
                    "/static/studio.css",
                    "/static/embed.css",
                }:
                    self.reply(
                        200,
                        (
                            Path(__file__).parent
                            / "web"
                            / parsed.path.rsplit("/", 1)[-1]
                        ).read_bytes(),
                        "text/javascript; charset=utf-8"
                        if parsed.path.endswith(".js")
                        else "text/css; charset=utf-8",
                    )
                elif parsed.path == "/api/platforms":
                    self.reply(
                        200,
                        {
                            "platforms": hub.metadata(),
                            "default": hub.primary.preset.name,
                        },
                    )
                elif parsed.path in {"/", "/developer", "/viewer"}:
                    self.reply(
                        200,
                        page(
                            "studio.html",
                            base_path,
                            "viewer" if parsed.path == "/viewer" else "developer",
                        ),
                        "text/html; charset=utf-8",
                    )
                elif parsed.path == "/experiments":
                    self.reply(
                        200,
                        page("experiments.html", base_path),
                        "text/html; charset=utf-8",
                    )
                elif parsed.path == "/account":
                    self.reply(
                        200,
                        page("index.html", base_path),
                        "text/html; charset=utf-8",
                    )
                elif parsed.path == "/api/providers" and registry is not None:
                    self.reply(200, {"providers": registry.options()})
                elif parsed.path == "/api/runs":
                    self.reply(
                        200,
                        {
                            "runs": manager.list(),
                            "providers": manager.provider_options(),
                        },
                    )
                elif parsed.path.startswith("/api/runs/"):
                    run_id = parsed.path.split("/")[3]
                    manager = hub.run_manager(run_id)
                    self.reply(
                        200,
                        manager.export(run_id)
                        if parsed.path.endswith("/export")
                        else manager.inspect(run_id),
                    )
                elif parsed.path in {
                    "/api/run-world",
                    "/api/run-session",
                    "/api/run-media",
                }:
                    query = parse_qs(parsed.query)
                    run_id = query["run"][0]
                    manager = hub.run_manager(run_id)
                    with manager.snapshot(run_id) as snapshot:
                        if parsed.path == "/api/run-world":
                            users = [
                                {"user_id": row[0], "handle": row[1], "name": row[2]}
                                for row in snapshot.db.execute(
                                    "SELECT user_id, user_name, name FROM user"
                                )
                            ]
                            ids = manager.jobs[run_id]["session_ids"]
                            sessions = [
                                {
                                    "session_id": row[0],
                                    "user_id": row[1],
                                    "status": row[2],
                                }
                                for sid in ids
                                for row in snapshot.db.execute(
                                    "SELECT session_id, user_id, status FROM agora_session WHERE session_id = ?",
                                    (sid,),
                                )
                            ]
                            self.reply(
                                200,
                                {
                                    "world_id": run_id,
                                    "preset": snapshot.preset.name,
                                    "tick": snapshot.current_tick,
                                    "users": users,
                                    "sessions": sessions,
                                },
                            )
                        elif parsed.path == "/api/run-session":
                            sid = int(query["id"][0])
                            if sid not in manager.jobs[run_id]["session_ids"]:
                                raise PermissionError(
                                    "Session does not belong to this run"
                                )
                            session = SocialSession(snapshot, sid)
                            self.reply(
                                200,
                                {
                                    "observation": session.observe(),
                                    "trajectory": session.trajectory(
                                        after_step=int(query.get("after", [0])[0])
                                    ),
                                    "requests": session.diagnostics(),
                                },
                            )
                        else:
                            row = snapshot.db.execute(
                                "SELECT object_key, mime_type FROM media_asset WHERE asset_id = ?",
                                (query["id"][0],),
                            ).fetchone()
                            if row is None:
                                raise KeyError("Unknown media")
                            self.reply(
                                200,
                                snapshot.media.path_for(row[0]).read_bytes(),
                                row[1],
                            )
                elif parsed.path == "/api/world":
                    users = [
                        {"user_id": row[0], "handle": row[1], "name": row[2]}
                        for row in world.db.execute(
                            "SELECT user_id, user_name, name FROM user ORDER BY user_id"
                        )
                    ]
                    sessions = [
                        {"session_id": row[0], "user_id": row[1], "status": row[2]}
                        for row in world.db.execute(
                            "SELECT session_id, user_id, status FROM agora_session ORDER BY session_id"
                        )
                    ]
                    self.reply(
                        200,
                        {
                            "world_id": world.config.world_id,
                            "preset": world.preset.name,
                            "tick": world.current_tick,
                            "users": users,
                            "sessions": sessions,
                        },
                    )
                elif parsed.path == "/api/session":
                    session = SocialSession(world, int(parse_qs(parsed.query)["id"][0]))
                    self.reply(
                        200,
                        {
                            "observation": session.observe(),
                            "trajectory": session.trajectory(),
                            "requests": session.diagnostics(),
                        },
                    )
                elif parsed.path.startswith("/media/"):
                    # Media URLs address database IDs, never arbitrary paths.
                    asset_id = parsed.path.removeprefix("/media/")
                    row = world.db.execute(
                        "SELECT object_key, mime_type FROM media_asset WHERE asset_id = ?",
                        (asset_id,),
                    ).fetchone()
                    if row is None:
                        raise KeyError("Unknown media")
                    self.reply(200, world.media.path_for(row[0]).read_bytes(), row[1])
                else:
                    self.reply(404, {"error": "Unknown route"})
            except (
                KeyError,
                ValueError,
                PermissionError,
                FileNotFoundError,
                TypeError,
            ) as error:
                self.reply(
                    403 if isinstance(error, PermissionError) else 400,
                    {"error": str(error)},
                )

        def do_POST(self):
            # This console owns the full research world, including replay and
            # diagnostics. Keep mutations same-origin and bound to loopback.
            if not self.valid_origin():
                self.reply(403, {"error": "Cross-origin mutation rejected"})
                return
            try:
                parsed = self.parsed()
                length = int(self.headers.get("Content-Length", "0"))
                if (
                    not 0
                    < length
                    <= (
                        12 * 1024 * 1024
                        if parsed.path in {"/v1/assets", "/api/assets"}
                        else 1024 * 1024
                    )
                ):
                    raise ValueError(
                        "Request body is empty or exceeds the endpoint payload limit"
                    )
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise TypeError("Request body must be an object")
                query = parse_qs(parsed.query)
                if parsed.path.startswith("/v1/"):
                    status, body, mime = native.dispatch(
                        "POST",
                        parsed.path,
                        query,
                        value,
                        self.headers.get("Authorization"),
                    )
                    self.reply(status, body, mime or "application/json; charset=utf-8")
                    return
                if api_only or self.headers.get("Authorization", "").startswith(
                    "Bearer "
                ):
                    self.reply(
                        403, {"error": "AI accounts cannot operate research routes"}
                    )
                    return
                platform = value.pop("platform", query.get("platform", [None])[0])
                world, manager = hub.select(platform)
                if parsed.path == "/api/providers" and registry is not None:
                    self.reply(201, registry.save(value))
                elif parsed.path == "/api/providers/test" and registry is not None:
                    self.reply(200, registry.test(value.get("provider_id")))
                elif parsed.path == "/api/assets":
                    uid = value.pop("user_id")
                    self.reply(201, native.upload(world, uid, value))
                elif parsed.path == "/api/runs":
                    self.reply(201, manager.start(value))
                elif parsed.path.startswith("/api/runs/") and parsed.path.endswith(
                    "/control"
                ):
                    manager = hub.run_manager(parsed.path.split("/")[3])
                    manager.control(parsed.path.split("/")[3], value["command"])
                    self.reply(200, {"success": True})
                elif parsed.path == "/api/session":
                    if type(value.get("user_id")) is not int:
                        raise ValueError("user_id must be an integer")
                    session = SocialSession.start(world, value["user_id"])
                    self.reply(201, {"session_id": session.session_id})
                elif parsed.path == "/api/action":
                    if type(value.get("session_id")) is not int:
                        raise ValueError("session_id must be an integer")
                    session = SocialSession(world, value["session_id"])
                    import uuid

                    from agora.decisions import DecisionJournal

                    action = {
                        "action_type": value["action_type"],
                        "arguments": value.get("arguments", {}),
                    }
                    receipt = asyncio.run(
                        DecisionJournal(world).execute(
                            session,
                            "ui:" + uuid.uuid4().hex,
                            action,
                            advance_clock=True,
                        )
                    )
                    self.reply(
                        200,
                        {
                            "result": receipt["result"],
                            "observation": receipt["observation"],
                        },
                    )
                else:
                    self.reply(404, {"error": "Unknown route"})
            except (
                KeyError,
                ValueError,
                PermissionError,
                TypeError,
                FileNotFoundError,
            ) as error:
                self.reply(
                    403 if isinstance(error, PermissionError) else 400,
                    {"error": str(error)},
                )

        def do_DELETE(self):
            if not self.valid_origin():
                self.reply(403, {"error": "Cross-origin mutation rejected"})
                return
            try:
                status, value, mime = native.dispatch(
                    "DELETE",
                    self.parsed().path,
                    {},
                    {},
                    self.headers.get("Authorization"),
                )
                self.reply(status, value, mime or "application/json; charset=utf-8")
            except (ValueError, PermissionError, KeyError, FileNotFoundError) as error:
                self.reply(403, {"error": str(error)})

    return Handler


def serve(
    world,
    host="127.0.0.1",
    port=8765,
    providers=None,
    api_port=None,
    bootstrap=False,
    multi_platform=True,
    base_path="",
    public_origin=None,
):
    validate_mount(base_path, public_origin)
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Research console must bind to loopback")
    from agora.provider_registry import ProviderRegistry

    registry = ProviderRegistry(world.config.world_dir / ".private", providers)
    hub = PlatformHub(world, registry.providers)
    if multi_platform:
        hub.add_platforms(bootstrap)
    api_port = port + 1 if api_port is None else api_port
    if api_port == port:
        raise ValueError("The AI API uses a separate port from the research console")
    with (
        HTTPServer(
            (host, port),
            make_handler(
                world,
                hub=hub,
                base_path=base_path,
                public_origin=public_origin,
                registry=registry,
            ),
        ) as console,
        HTTPServer(
            (host, api_port),
            make_handler(world, hub=hub, api_only=True, public_origin=public_origin),
        ) as ai_server,
    ):
        print(
            f"Agora console: http://{host}:{console.server_port}{base_path}/developer",
            flush=True,
        )
        print(f"AI account API: http://{host}:{ai_server.server_port}/v1", flush=True)
        selector = selectors.DefaultSelector()
        selector.register(console, selectors.EVENT_READ)
        selector.register(ai_server, selectors.EVENT_READ)
        try:
            while True:
                for key, _ in selector.select(timeout=0.5):
                    key.fileobj._handle_request_noblock()
        except KeyboardInterrupt:
            pass
        finally:
            selector.close()
            hub.shutdown()
