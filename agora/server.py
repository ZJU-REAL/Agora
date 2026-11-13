"""Local research console. A single owner thread serializes world mutations."""

from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agora.recommendation import RecommendationEngine
from agora.session import SocialSession


def make_handler(world):
    RecommendationEngine(world.platform.db)

    class Handler(BaseHTTPRequestHandler):
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
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self.reply(
                        200,
                        (Path(__file__).parent / "web" / "index.html").read_bytes(),
                        "text/html; charset=utf-8",
                    )
                elif parsed.path == "/api/world":
                    users = [
                        {"user_id": row[0], "handle": row[1], "name": row[2]}
                        for row in world.platform.db.execute(
                            "SELECT user_id, user_name, name FROM user ORDER BY user_id"
                        )
                    ]
                    sessions = [
                        {"session_id": row[0], "user_id": row[1], "status": row[2]}
                        for row in world.platform.db.execute(
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
                    row = world.platform.db.execute(
                        "SELECT object_key, mime_type FROM media_asset WHERE asset_id = ?",
                        (asset_id,),
                    ).fetchone()
                    if row is None:
                        raise KeyError("Unknown media")
                    self.reply(200, world.media.path_for(row[0]).read_bytes(), row[1])
                else:
                    self.reply(404, {"error": "Unknown route"})
            except (KeyError, ValueError, PermissionError, FileNotFoundError) as error:
                self.reply(400, {"error": str(error)})

        def do_POST(self):
            # This console owns the full research world, including replay and
            # diagnostics. Keep mutations same-origin and bound to loopback.
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.reply(403, {"error": "Cross-origin mutation rejected"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    raise ValueError("Request body must be between 1 and 65536 bytes")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise TypeError("Request body must be an object")
                if self.path == "/api/session":
                    if type(value.get("user_id")) is not int:
                        raise ValueError("user_id must be an integer")
                    session = SocialSession.start(world, value["user_id"])
                    self.reply(201, {"session_id": session.session_id})
                elif self.path == "/api/action":
                    if type(value.get("session_id")) is not int:
                        raise ValueError("session_id must be an integer")
                    session = SocialSession(world, value["session_id"])
                    result = asyncio.run(
                        session.act(value["action_type"], value.get("arguments", {}))
                    )
                    self.reply(
                        200, {"result": result, "observation": session.observe()}
                    )
                else:
                    self.reply(404, {"error": "Unknown route"})
            except (KeyError, ValueError, PermissionError, TypeError) as error:
                self.reply(400, {"error": str(error)})

    return Handler


def serve(world, host="127.0.0.1", port=8765):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Research console must bind to loopback")
    with HTTPServer((host, port), make_handler(world)) as server:
        print(f"Agora console: http://{host}:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
