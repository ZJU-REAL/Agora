"""Isolated experiment jobs with persistent manifests and observable progress."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

from agora.recommendation import RecommendationConfig
from agora.runner import JsonSessionPolicy, run_sessions
from agora.world import open_world
from oasis.agora_types import PLATFORM_PRESETS
from oasis.media import LocalMediaStore
from oasis.world import AgoraWorld, WorldConfig


class ExperimentManager:
    def __init__(self, source_world, providers=None, max_active=4):
        self.source = source_world
        self.root = source_world.config.world_dir / "experiments"
        self.root.mkdir(exist_ok=True)
        self.providers = providers or {}
        self.max_active = max_active
        self.lock = threading.RLock()
        self.jobs = {}
        self.controls = {}
        self.threads = {}
        for path in self.root.glob("*/manifest.json"):
            value = json.loads(path.read_text())
            if value["status"] in {
                "running",
                "queued",
                "paused",
                "pausing",
                "stopping",
            }:
                value["status"] = "interrupted"
            self.jobs[value["run_id"]] = value

    def provider_options(self):
        return [
            {
                "provider_id": key,
                "model_id": spec["model_id"],
                "supports_vision": bool(spec.get("supports_vision", False)),
                "credential_available": (
                    os.path.isdir(spec.get("model_path", ""))
                    if spec.get("provider") == "local-transformers"
                    else bool(
                        os.environ.get(spec.get("api_key_env", "AGORA_MAAS_API_KEY"))
                    )
                ),
                "limits": spec.get("limits", {}),
            }
            for key, spec in self.providers.items()
        ]

    def _write(self, run_id):
        target = self.root / run_id / "manifest.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.jobs[run_id], ensure_ascii=False, indent=2)
        )
        temporary.replace(target)

    def list(self):
        with self.lock:
            return json.loads(
                json.dumps(
                    sorted(
                        self.jobs.values(),
                        key=lambda value: value["created_at"],
                        reverse=True,
                    )
                )
            )

    def start(self, config):
        if not isinstance(config, dict) or set(config) - {
            "name",
            "user_ids",
            "ticks",
            "steps_per_tick",
            "seed",
            "goal",
            "provider_id",
            "recommendation",
            "events",
            "pace_ms",
        }:
            raise ValueError("Unknown experiment configuration fields")
        users = config.get("user_ids", [])
        known = {row[0] for row in self.source.db.execute("SELECT user_id FROM user")}
        if (
            not isinstance(users, list)
            or not 1 <= len(users) <= 100
            or any(type(user) is not int or user not in known for user in users)
            or len(users) != len(set(users))
        ):
            raise ValueError("Select 1–100 distinct users from the source world")
        ticks, steps = config.get("ticks", 6), config.get("steps_per_tick", 8)
        pace = config.get("pace_ms", 0)
        if type(pace) is not int or not 0 <= pace <= 2000:
            raise ValueError("pace_ms must be an integer from 0 to 2000")
        if (
            type(ticks) is not int
            or not 1 <= ticks <= 100
            or type(steps) is not int
            or not 1 <= steps <= 30
        ):
            raise ValueError("ticks must be 1–100 and steps_per_tick 1–30")
        if type(config.get("seed", 42)) is not int:
            raise ValueError("seed must be an integer")
        if (
            not isinstance(config.get("goal", ""), str)
            or len(config.get("goal", "")) > 4000
        ):
            raise ValueError("goal must be at most 4000 characters")
        if (
            not isinstance(config.get("name", ""), str)
            or len(config.get("name", "")) > 200
        ):
            raise ValueError("name must be at most 200 characters")
        RecommendationConfig(**config.get("recommendation", {}))
        provider = config.get("provider_id", "development")
        if provider != "development" and provider not in self.providers:
            raise ValueError("Unknown provider; register one when starting agora serve")
        if provider != "development":
            option = next(
                item
                for item in self.provider_options()
                if item["provider_id"] == provider
            )
            if not option["credential_available"]:
                raise ValueError(
                    "Selected provider credential environment variable is not set"
                )
        events = config.get("events", [])
        if not isinstance(events, list) or len(events) > 20:
            raise ValueError("events must be a list of up to 20 interventions")
        for event in events:
            if (
                not isinstance(event, dict)
                or set(event) - {"tick", "user_id", "body", "title", "topics"}
                or type(event.get("tick")) is not int
                or not 0 <= event["tick"] < ticks
                or event.get("user_id") not in known
                or not isinstance(event.get("body"), str)
                or not event["body"].strip()
            ):
                raise ValueError("Invalid intervention tick, user or content")
        config = {
            "name": "社交模拟",
            "ticks": ticks,
            "steps_per_tick": steps,
            "seed": 42,
            "goal": "浏览社区、创作内容并根据公开反馈经营账号。",
            "provider_id": provider,
            "pace_ms": pace,
            "recommendation": asdict(
                RecommendationConfig(**config.get("recommendation", {}))
            ),
            **config,
        }
        config["recommendation"] = asdict(
            RecommendationConfig(**config.get("recommendation", {}))
        )
        with self.lock:
            if (
                sum(
                    job["status"]
                    in {"queued", "running", "paused", "pausing", "stopping"}
                    for job in self.jobs.values()
                )
                >= self.max_active
            ):
                raise ValueError("Active experiment limit reached")
            run_id = uuid.uuid4().hex[:12]
            directory = self.root / run_id
            world_dir = directory / "world"
            try:
                world_dir.mkdir(parents=True)
                destination = sqlite3.connect(world_dir / "sandbox.db")
                try:
                    self.source.db.backup(destination)
                finally:
                    destination.close()
                shutil.copytree(self.source.config.media_path, world_dir / "media")
                media_manifest = []
                for asset, key, checksum, size in self.source.db.execute(
                    "SELECT asset_id, object_key, checksum_sha256, byte_size FROM media_asset WHERE status = 'ready' ORDER BY asset_id"
                ):
                    path = (world_dir / "media" / key).resolve()
                    if (world_dir / "media").resolve() not in path.parents:
                        raise ValueError("Media key escapes the experiment")
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        while chunk := stream.read(1024 * 1024):
                            digest.update(chunk)
                    if digest.hexdigest() != checksum or path.stat().st_size != size:
                        raise ValueError("Source media checksum mismatch")
                    media_manifest.append(
                        {
                            "asset_id": asset,
                            "object_key": key,
                            "sha256": checksum,
                            "bytes": size,
                        }
                    )
                (world_dir / "world.json").write_text(
                    json.dumps(
                        {
                            "world_id": "world",
                            "preset": self.source.preset.name,
                            "format_version": 1,
                        }
                    )
                )
                initial_sha = hashlib.sha256(
                    (world_dir / "sandbox.db").read_bytes()
                ).hexdigest()
                value = {
                    "run_id": run_id,
                    "name": config["name"],
                    "status": "queued",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "config": config,
                    "source_world": self.source.config.world_id,
                    "engine_version": "0.3.0",
                    "media_manifest": media_manifest,
                    "initial_database_sha256": initial_sha,
                    "config_sha256": hashlib.sha256(
                        json.dumps(config, sort_keys=True).encode()
                    ).hexdigest(),
                    "model": self.providers[provider]["model_id"]
                    if provider != "development"
                    else "persona-development",
                    "provider_config_sha256": hashlib.sha256(
                        json.dumps(self.providers[provider], sort_keys=True).encode()
                    ).hexdigest()
                    if provider != "development"
                    else None,
                    "session_ids": [],
                    "attempted_actions": 0,
                    "total_actions": len(users) * ticks * steps,
                    "completed_ticks": 0,
                }
            except BaseException:
                shutil.rmtree(directory, ignore_errors=True)
                raise
            self.jobs[run_id] = value
            self.controls[run_id] = {
                "pause": False,
                "stop": False,
                "condition": threading.Condition(self.lock),
            }
            self._write(run_id)
            thread = threading.Thread(
                target=self._worker, args=(run_id,), daemon=True, name=f"agora-{run_id}"
            )
            self.threads[run_id] = thread
            thread.start()
            return json.loads(json.dumps(value))

    def control(self, run_id, command):
        with self.lock:
            if run_id not in self.controls or self.jobs[run_id]["status"] not in {
                "queued",
                "running",
                "paused",
                "pausing",
                "stopping",
            }:
                raise ValueError("Experiment is not active in this process")
            flags = self.controls[run_id]
            if command == "pause":
                flags["pause"] = True
                self.jobs[run_id]["status"] = "pausing"
            elif command == "resume":
                flags["pause"] = False
                self.jobs[run_id]["status"] = "running"
            elif command == "stop":
                flags["stop"] = True
                self.jobs[run_id]["status"] = "stopping"
            else:
                raise ValueError("Control must be pause, resume or stop")
            flags["condition"].notify_all()
            self._write(run_id)

    def _gate(self, run_id):
        with self.lock:
            flags = self.controls[run_id]
            while flags["pause"] and not flags["stop"]:
                self.jobs[run_id]["status"] = "paused"
                self._write(run_id)
                flags["condition"].wait()
            return not flags["stop"]

    def _worker(self, run_id):
        world = None
        try:
            config = self.jobs[run_id]["config"]
            world = open_world("world", self.root / run_id)
            world.set_seed(config["seed"])
            with self.lock:
                self.jobs[run_id]["status"] = "running"
                self._write(run_id)

            def progress(value):
                with self.lock:
                    self.jobs[run_id].update(value)
                    self._write(run_id)
                if config["pace_ms"] and value.get("actor_user_id") is not None:
                    time.sleep(config["pace_ms"] / 1000)

            factory = None
            if config["provider_id"] != "development":
                from agora.backends.visual import session_visual_parts
                from agora.models import build_model_client

                spec = self.providers[config["provider_id"]]

                def factory(user):
                    row = world.db.execute(
                        "SELECT persona_json FROM persona WHERE user_id = ?", (user,)
                    ).fetchone()
                    return JsonSessionPolicy(
                        build_model_client(spec),
                        config["goal"],
                        json.loads(row[0]) if row else {},
                        visual_builder=(
                            lambda observation: session_visual_parts(world, observation)
                        )
                        if spec.get("supports_vision")
                        else None,
                        expected_model_id=spec["model_id"],
                    )

            report = asyncio.run(
                run_sessions(
                    world,
                    config["user_ids"],
                    config["ticks"],
                    config["steps_per_tick"],
                    factory,
                    RecommendationConfig(**config["recommendation"]),
                    progress,
                    lambda: self._gate(run_id),
                    config.get("events", []),
                )
            )
            with self.lock:
                self.jobs[run_id].update(
                    report=report,
                    status="canceled" if report["canceled"] else "completed",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                self._write(run_id)
        except Exception as error:  # noqa: BLE001 - persist failed jobs independently
            with self.lock:
                self.jobs[run_id].update(
                    status="failed", error_type=type(error).__name__
                )
                self._write(run_id)
        finally:
            if world:
                world.close()

    @contextmanager
    def snapshot(self, run_id):
        if run_id not in self.jobs:
            raise KeyError("Unknown run")
        root = self.root / run_id
        db = sqlite3.connect(f"file:{root / 'world' / 'sandbox.db'}?mode=ro", uri=True)
        world = AgoraWorld.__new__(AgoraWorld)
        world.config = WorldConfig("world", root, self.source.preset.name)
        world.preset = PLATFORM_PRESETS[self.source.preset.name]
        world.store = SimpleNamespace(db=db)
        world.media = LocalMediaStore(world.config.media_path)
        try:
            db.execute("BEGIN")
            yield world
        finally:
            db.close()

    def inspect(self, run_id):
        with self.lock:
            metadata = json.loads(json.dumps(self.jobs[run_id]))
        with self.snapshot(run_id) as world:
            ids = metadata["session_ids"]
            events, calls = [], []
            for sid in ids:
                for row in world.db.execute(
                    "SELECT e.step, e.tick, e.elapsed_ms, e.action_json, e.result_json, s.user_id, e.event_id FROM agora_session_event e JOIN agora_session s ON s.session_id = e.session_id WHERE e.session_id = ? ORDER BY step",
                    (sid,),
                ):
                    events.append(
                        {
                            "event_id": row[6],
                            "session_id": sid,
                            "user_id": row[5],
                            "step": row[0],
                            "tick": row[1],
                            "elapsed_ms": row[2],
                            "action": json.loads(row[3]),
                            "result": json.loads(row[4]),
                        }
                    )
                calls.extend(
                    [
                        dict(
                            zip(
                                (
                                    "session_id",
                                    "step",
                                    "tick",
                                    "status",
                                    "model_id",
                                    "input_tokens",
                                    "output_tokens",
                                    "elapsed_ms",
                                    "error_type",
                                ),
                                row,
                            )
                        )
                        for row in world.db.execute(
                            "SELECT session_id, step, tick, status, model_id, input_tokens, output_tokens, elapsed_ms, error_type FROM agent_model_call WHERE session_id = ?",
                            (sid,),
                        )
                    ]
                )
            events.sort(key=lambda event: event["event_id"])
            users = [
                {"user_id": row[0], "name": row[1], "followers": row[2]}
                for row in world.db.execute(
                    "SELECT user_id, name, num_followers FROM user"
                )
            ]
            graph = [
                {"source": row[0], "target": row[1]}
                for row in world.db.execute(
                    "SELECT follower_id, followee_id FROM follow"
                )
            ]
            created = [
                event
                for event in events
                if event["action"]["action_type"] in {"create_post", "publish_draft"}
                and event["result"].get("success")
            ]
            metadata.update(
                events=events,
                model_calls=calls,
                users=users,
                graph=graph,
                metrics={
                    "created_posts": len(created),
                    "drafts": sum(
                        event["action"]["action_type"] == "save_draft"
                        for event in events
                    ),
                    "comments": sum(
                        event["action"]["action_type"] == "create_comment"
                        and event["result"].get("success", False)
                        for event in events
                    ),
                    "model_calls": len(calls),
                    "input_tokens": sum(call["input_tokens"] or 0 for call in calls),
                    "output_tokens": sum(call["output_tokens"] or 0 for call in calls),
                    "exposures": sum(
                        world.db.execute(
                            "SELECT COUNT(*) FROM agora_exposure WHERE session_id = ?",
                            (sid,),
                        ).fetchone()[0]
                        for sid in ids
                    ),
                },
            )
        return metadata

    def shutdown(self):
        with self.lock:
            for flags in self.controls.values():
                flags["stop"] = True
                flags["condition"].notify_all()
        for thread in self.threads.values():
            thread.join(timeout=2)

    def export(self, run_id):
        value = self.inspect(run_id)
        from agora.session import SocialSession

        with self.snapshot(run_id) as world:
            value["trajectories"] = [
                {
                    "session_id": sid,
                    "trajectory": SocialSession(world, sid).trajectory(),
                    "recommendations": SocialSession(world, sid).diagnostics(),
                }
                for sid in value["session_ids"]
            ]
            value["world_events"] = world.events()
        value["format_version"] = "agora-experiment-v1"
        return value
