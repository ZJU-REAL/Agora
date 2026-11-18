"""Account-bound AI API and a hub of independently stored social platforms."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import secrets
import tempfile
from pathlib import Path
from types import SimpleNamespace

from agora.decisions import DecisionJournal
from agora.experiments import ExperimentManager
from agora.http_media import MediaResponse
from agora.platforms import contract_for
from agora.session import SocialSession
from agora.world import open_world
from oasis import PersonaProfile
from oasis.agora_types import PLATFORM_PRESETS
from oasis.world import WorldConfig


class PlatformHub:
    def __init__(
        self,
        primary,
        providers=None,
        manager=None,
        max_active_agents=32,
        max_active_runs=1,
        max_run_actions=2400,
    ):
        self.primary = primary
        self.worlds = {primary.preset.name: primary}
        self.managers = {
            primary.preset.name: manager or ExperimentManager(primary, providers)
        }
        self.providers = providers if providers is not None else {}
        self.archives = {}
        self.max_active_agents, self.max_active_runs, self.max_run_actions = (
            max_active_agents,
            max_active_runs,
            max_run_actions,
        )
        if min(max_active_agents, max_active_runs, max_run_actions) < 1:
            raise ValueError("Run limits must be positive")

    def capacity(self):
        agents, runs = 0, 0
        for manager in self.managers.values():
            with manager.lock:
                for job in manager.jobs.values():
                    if job["status"] in {
                        "queued",
                        "running",
                        "pausing",
                        "paused",
                        "stopping",
                    }:
                        runs += 1
                        agents += len(job["config"]["user_ids"])
        return {
            "max_active_agents": self.max_active_agents,
            "max_active_runs": self.max_active_runs,
            "max_run_actions": self.max_run_actions,
            "active_agents": agents,
            "active_runs": runs,
        }

    def admit(self, config):
        count = config.get("agent_count", len(config.get("user_ids", [])))
        if type(count) is not int or count < 1:
            raise ValueError("Select a positive agent count")
        ticks, steps = config.get("ticks", 6), config.get("steps_per_tick", 8)
        if type(ticks) is not int or type(steps) is not int:
            raise ValueError("Run periods and action limits must be integers")
        limits = self.capacity()
        if limits["active_runs"] >= self.max_active_runs:
            raise ValueError("已有模拟占用运行槽，请先停止或完成当前模拟。")
        if limits["active_agents"] + count > self.max_active_agents:
            raise ValueError(
                f"当前服务最多同时运行 {self.max_active_agents} 个 agent。"
            )
        if count * ticks * steps > self.max_run_actions:
            raise ValueError(
                f"单次模拟的动作上限为 {self.max_run_actions}；请减少账号、轮数或每轮动作数。"
            )
        recommendation = config.get("recommendation", {})
        if (
            recommendation.get("slate_size", 30) > 30
            or recommendation.get("page_size", 6) > 12
        ):
            raise ValueError("网页沙盒每次推荐最多 30 条、每页最多 12 条。")
        for key in ("provider_id", "background_provider_id"):
            if (
                self.providers.get(config.get(key), {}).get("provider")
                == "local-transformers"
            ):
                raise ValueError(
                    "网页沙盒请连接独立模型 API，不在平台进程加载本地权重。"
                )

    def add_platforms(self, bootstrap=False):
        from agora.demo import populate

        for name in ("xiaohongshu", "x", "reddit"):
            if name in self.worlds:
                continue
            world = open_world(
                self.primary.config.world_id[:100] + "-" + name,
                self.primary.config.data_root,
                name,
            )
            if (
                bootstrap
                and not world.db.execute("SELECT 1 FROM user LIMIT 1").fetchone()
            ):
                populate(world)
            self.worlds[name] = world
            self.managers[name] = ExperimentManager(world, self.providers)

    def select(self, platform=None):
        platform = {"twitter": "x", "xhs": "xiaohongshu"}.get(platform, platform)
        platform = platform or self.primary.preset.name
        if platform not in self.worlds:
            raise ValueError("Unknown platform")
        return self.worlds[platform], self.managers[platform]

    def run_manager(self, run_id):
        for manager in self.managers.values():
            if run_id in manager.jobs:
                return manager
        if not re.fullmatch(r"[a-f0-9]{12}", run_id):
            raise KeyError("Unknown run")
        for directory in self.primary.config.data_root.iterdir():
            if (
                not (directory / "experiments" / run_id / "manifest.json").is_file()
                or not (directory / "world.json").is_file()
            ):
                continue
            if directory.name not in self.archives:
                import json

                preset = json.loads((directory / "world.json").read_text())["preset"]
                source = SimpleNamespace(
                    config=WorldConfig(
                        directory.name, self.primary.config.data_root, preset
                    ),
                    preset=PLATFORM_PRESETS[preset],
                )
                self.archives[directory.name] = ExperimentManager(
                    source, self.providers
                )
            return self.archives[directory.name]
        raise KeyError("Unknown run")

    def metadata(self):
        return [
            {
                **contract_for(world).to_dict(),
                "world_id": world.config.world_id,
                "users": world.db.execute("SELECT COUNT(*) FROM user").fetchone()[0],
            }
            for name, world in self.worlds.items()
        ]

    def shutdown(self):
        for manager in self.managers.values():
            manager.shutdown()
        for world in self.worlds.values():
            if world is not self.primary:
                world.close()


class AgentAPI:
    def __init__(self, hub):
        self.hub = hub

    def authenticate(self, authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("An AI account bearer token is required")
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        for world in self.hub.worlds.values():
            row = world.db.execute(
                "SELECT user_id FROM agent_api_token WHERE token_hash=? AND revoked=0",
                (digest,),
            ).fetchone()
            if row:
                return world, row[0]
        raise PermissionError("Invalid or revoked account token")

    def register(self, value):
        if set(value) - {
            "platform",
            "handle",
            "display_name",
            "bio",
            "interests",
            "locale",
        }:
            raise ValueError("Unknown account fields")
        world, _ = self.hub.select(value.get("platform"))
        handle = value.get("handle", "")
        maximum = 15 if world.preset.name == "x" else 20
        if not isinstance(handle, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]{2," + str(maximum - 1) + "}", handle
        ):
            raise ValueError(
                f"Handle must contain 3–{maximum} ASCII letters, digits or underscores"
            )
        if world.db.execute(
            "SELECT 1 FROM user WHERE lower(user_name)=lower(?)", (handle,)
        ).fetchone():
            raise ValueError("Handle is already registered on this platform")
        name, bio = value.get("display_name", handle), value.get("bio", "")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 80
            or not isinstance(bio, str)
            or len(bio) > 300
        ):
            raise ValueError("Invalid display name or bio")
        interests = value.get("interests", {})
        if (
            not isinstance(interests, dict)
            or len(interests) > 20
            or any(
                not isinstance(key, str)
                or not isinstance(weight, (int, float))
                or not 0 <= weight <= 3
                for key, weight in interests.items()
            )
        ):
            raise ValueError("Interests map text topics to weights from 0 to 3")
        token = secrets.token_urlsafe(32)
        with world.atomic():
            user = world.add_persona(
                PersonaProfile(
                    "api-" + secrets.token_hex(8),
                    handle,
                    name,
                    bio=bio,
                    interests=interests,
                    locale=value.get("locale", "zh-CN"),
                    posting_probability=0,
                )
            )
            world.db.execute(
                "INSERT INTO agent_api_token(token_hash,user_id) VALUES (?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), user),
            )
        return {
            "user_id": user,
            "platform": world.preset.name,
            "token": token,
            "contract": contract_for(world).to_dict(),
        }

    @staticmethod
    def session(world, user, session_id):
        if not world.db.execute(
            "SELECT 1 FROM agora_session WHERE session_id=? AND user_id=?",
            (session_id, user),
        ).fetchone():
            raise PermissionError("Session belongs to another account")
        return SocialSession(world, session_id)

    def dispatch(self, method, path, query, value, authorization):
        if method == "GET" and path == "/v1/platforms":
            return 200, {"platforms": self.hub.metadata()}, None
        if method == "POST" and path == "/v1/accounts":
            return 201, self.register(value), None
        world, user = self.authenticate(authorization)
        if path == "/v1/memory":
            from agora.memory import AgentMemory

            return (
                200,
                {
                    "memory": AgentMemory(world).retrieve(
                        user, query.get("query", [""])[0]
                    )
                },
                None,
            )
        if path == "/v1/account":
            row = world.db.execute(
                "SELECT user_id,user_name,name,bio FROM user WHERE user_id=?", (user,)
            ).fetchone()
            return (
                200,
                dict(zip(("user_id", "handle", "display_name", "bio"), row)),
                None,
            )
        if path == "/v1/token" and method == "DELETE":
            with world.atomic():
                world.db.execute(
                    "UPDATE agent_api_token SET revoked=1 WHERE token_hash=?",
                    (hashlib.sha256(authorization[7:].encode()).hexdigest(),),
                )
            return 200, {"success": True}, None
        if path == "/v1/sessions":
            if method == "POST":
                session = SocialSession.start(world, user)
                return (
                    201,
                    {
                        "session_id": session.session_id,
                        "observation": session.observe(),
                    },
                    None,
                )
            return (
                200,
                {
                    "sessions": [
                        {"session_id": row[0], "status": row[1]}
                        for row in world.db.execute(
                            "SELECT session_id,status FROM agora_session WHERE user_id=? ORDER BY session_id",
                            (user,),
                        )
                    ]
                },
                None,
            )
        if path.startswith("/v1/sessions/"):
            parts = path.split("/")
            session = self.session(world, user, int(parts[3]))
            if method == "GET" and len(parts) == 4:
                return (
                    200,
                    session.observe_at(int(query["step"][0]))
                    if "step" in query
                    else session.observe(),
                    None,
                )
            if method == "GET" and parts[-1] == "tools":
                from agora.tool_schema import tool_definitions

                return 200, {"tools": tool_definitions(session.observe())}, None
            if method == "GET" and parts[-1] == "trajectory":
                return (
                    200,
                    {
                        "trajectory": session.trajectory(
                            after_step=int(query.get("after", [0])[0]),
                            include_observations=False,
                            compact=True,
                        )
                    },
                    None,
                )
            if method == "POST" and parts[-1] == "actions":
                if set(value) - {"action_type", "arguments", "rationale", "request_id"}:
                    raise ValueError("Unknown action fields")
                key = value.get("request_id")
                if not isinstance(key, str) or not re.fullmatch(
                    r"[A-Za-z0-9_.:-]{1,128}", key
                ):
                    raise ValueError(
                        "Provide a unique request_id; reuse it when retrying the same action"
                    )
                action = {
                    key: value[key]
                    for key in ("action_type", "arguments", "rationale")
                    if key in value
                }
                journal = DecisionJournal(world)
                receipt = asyncio.run(
                    journal.execute(
                        session,
                        f"api:{user}:{session.session_id}:{key}",
                        action,
                        advance_clock=True,
                    )
                )
                return 200, receipt, None
        if path == "/v1/assets" and method == "POST":
            return 201, self.upload(world, user, value), None
        if path.startswith("/v1/assets/") and method == "GET":
            asset = path.split("/")[-1]
            owned = world.db.execute(
                "SELECT 1 FROM creator_asset WHERE user_id=? AND asset_id=?",
                (user, asset),
            ).fetchone()
            if not owned:
                ids = [
                    row[0]
                    for row in world.db.execute(
                        "SELECT post_id FROM post_asset WHERE asset_id=?", (asset,)
                    )
                ]
                if not world.get_feed(
                    user,
                    1,
                    record_impressions=False,
                    eligible_post_ids=ids,
                    include_comments=False,
                ):
                    raise PermissionError("Asset is not visible to this account")
            row = world.db.execute(
                "SELECT object_key,mime_type FROM media_asset WHERE asset_id=?",
                (asset,),
            ).fetchone()
            if row is None:
                raise KeyError("Unknown asset")
            return 200, MediaResponse(world.media.path_for(row[0])), row[1]
        raise ValueError("Unknown AI API route")

    @staticmethod
    def upload(world, user, value):
        if set(value) - {"filename", "data_base64", "alt_text", "transcript"}:
            raise ValueError("Unknown asset fields")
        name = value.get("filename", "")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or Path(name).suffix.lower()
            not in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov"}
        ):
            raise ValueError("Provide a supported image/video filename without a path")
        data = base64.b64decode(value.get("data_base64", ""), validate=True)
        if not 0 < len(data) <= 8 * 1024 * 1024:
            raise ValueError("API uploads must be between 1 byte and 8 MiB")
        with tempfile.TemporaryDirectory(prefix="agora-upload-") as temporary:
            path = Path(temporary) / name
            path.write_bytes(data)
            with world.atomic():
                media = world.import_media(path)
                world.db.execute(
                    "INSERT INTO creator_asset(user_id,asset_id,alt_text,transcript) VALUES (?, ?, ?, ?) ON CONFLICT(user_id,asset_id) DO UPDATE SET alt_text=COALESCE(excluded.alt_text,creator_asset.alt_text), transcript=COALESCE(excluded.transcript,creator_asset.transcript)",
                    (
                        user,
                        media.asset_id,
                        value.get("alt_text"),
                        value.get("transcript"),
                    ),
                )
                world._record_event(
                    "asset_uploaded",
                    user,
                    "asset",
                    media.asset_id,
                    {"media_type": media.media_type},
                )
        return next(
            asset
            for asset in world.asset_library(user)
            if asset["asset_id"] == media.asset_id
        )
