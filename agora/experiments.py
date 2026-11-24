"""Isolated experiment jobs with persistent manifests and observable progress."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from agora.initialization import (
    MODE_FIELDS,
    file_sha256,
    has_user,
    initialize_accounts,
    resolve_accounts,
)
from agora.read_views import prepare_read_views
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
        self.providers = providers if providers is not None else {}
        self.max_active = max_active
        self.lock = threading.RLock()
        self.jobs = {}
        self.controls = {}
        self.threads = {}
        self.run_providers = {}
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
            "agent_count",
            "focal_user_id",
            "background_provider_id",
            *MODE_FIELDS,
        }:
            raise ValueError("Unknown experiment configuration fields")
        users, focal, count, account_options = resolve_accounts(self.source, config)
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
        background = config.get("background_provider_id", "development")
        if background != "development" and (
            background not in self.providers
            or not next(
                item
                for item in self.provider_options()
                if item["provider_id"] == background
            )["credential_available"]
        ):
            raise ValueError("Background model is unavailable")
        specs = {
            key: copy.deepcopy(self.providers[key])
            for key in {provider, background}
            if key != "development"
        }
        events = config.get("events", [])
        if not isinstance(events, list) or len(events) > 20:
            raise ValueError("events must be a list of up to 20 interventions")
        for event in events:
            if (
                not isinstance(event, dict)
                or set(event) - {"tick", "user_id", "body", "title", "topics"}
                or type(event.get("tick")) is not int
                or not 0 <= event["tick"] < ticks
                or not has_user(self.source, event.get("user_id"))
                or not isinstance(event.get("body"), str)
                or not event["body"].strip()
            ):
                raise ValueError("Invalid intervention tick, user or content")
        if events and account_options["world_mode"] == "ai_only":
            raise ValueError("纯 AI 世界请用账号任务启动；背景事件仅用于背景世界。")
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
        config.update(account_options)
        config["user_ids"] = users
        if focal is not None:
            config["focal_user_id"] = focal
        if count is not None:
            config["agent_count"] = count
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
                if config["world_mode"] == "background":
                    destination = sqlite3.connect(world_dir / "sandbox.db")
                    try:
                        self.source.db.backup(destination)
                        destination.execute("DELETE FROM agent_api_token")
                        destination.commit()
                    finally:
                        destination.close()
                    shutil.copytree(self.source.config.media_path, world_dir / "media")
                source_manifest = json.loads(
                    (self.source.config.world_dir / "world.json").read_text()
                )
                (world_dir / "world.json").write_text(
                    json.dumps(
                        {
                            "world_id": "world",
                            "preset": self.source.preset.name,
                            "format_version": 1,
                            "product_limits": source_manifest.get("product_limits", {}),
                            "location_aliases": source_manifest.get(
                                "location_aliases", {}
                            ),
                        }
                    )
                )
                population = open_world("world", directory)
                try:
                    initialize_accounts(self.source, population, config)
                    users = config["user_ids"]
                    media_manifest = []
                    media_count = 0
                    index_path = directory / "initial-media.jsonl"
                    with index_path.open("w", encoding="utf-8") as index:
                        for asset, key, checksum, size in population.db.execute(
                            "SELECT asset_id,object_key,checksum_sha256,byte_size FROM media_asset WHERE status='ready' ORDER BY asset_id"
                        ):
                            path = (world_dir / "media" / key).resolve()
                            if (world_dir / "media").resolve() not in path.parents:
                                raise ValueError("Media key escapes the experiment")
                            if (
                                file_sha256(path) != checksum
                                or path.stat().st_size != size
                            ):
                                raise ValueError("Source media checksum mismatch")
                            item = {
                                "asset_id": asset,
                                "object_key": key,
                                "sha256": checksum,
                                "bytes": size,
                            }
                            index.write(json.dumps(item, ensure_ascii=False) + "\n")
                            media_count += 1
                            if len(media_manifest) < 128:
                                media_manifest.append(item)
                finally:
                    population.close()
                initial_sha = file_sha256(world_dir / "sandbox.db")
                value = {
                    "run_id": run_id,
                    "name": config["name"],
                    "status": "queued",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "config": config,
                    "source_world": self.source.config.world_id,
                    "engine_version": "0.6.0",
                    "media_manifest": media_manifest,
                    "media_manifest_count": media_count,
                    "media_manifest_truncated": media_count > len(media_manifest),
                    "initial_media_sha256": file_sha256(index_path),
                    "initial_database_sha256": initial_sha,
                    "config_sha256": hashlib.sha256(
                        json.dumps(config, sort_keys=True).encode()
                    ).hexdigest(),
                    "model": self.providers[provider]["model_id"]
                    if provider != "development"
                    else "persona-development",
                    "provider_config_sha256": hashlib.sha256(
                        json.dumps(specs[provider], sort_keys=True).encode()
                    ).hexdigest()
                    if provider != "development"
                    else None,
                    "background_model": specs[background]["model_id"]
                    if background != "development"
                    else "persona-development",
                    "background_provider_config_sha256": hashlib.sha256(
                        json.dumps(specs[background], sort_keys=True).encode()
                    ).hexdigest()
                    if background != "development"
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
            self.run_providers[run_id] = specs
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
            legacy = config.get("legacy_shared_policy", False)
            if self.run_providers[run_id] or (
                not legacy and config.get("focal_user_id") is not None
            ):
                from agora.backends.visual import session_visual_parts
                from agora.models import build_model_client

                def factory(user):
                    selected = (
                        config["provider_id"]
                        if legacy or config.get("focal_user_id", user) == user
                        else config.get("background_provider_id", "development")
                    )
                    row = world.db.execute(
                        "SELECT persona_json FROM persona WHERE user_id = ?", (user,)
                    ).fetchone()
                    persona = json.loads(row[0]) if row else {}
                    if selected == "development":
                        from agora.policies import PersonaPolicy

                        creator = (
                            (not legacy and user == config.get("focal_user_id"))
                            or bool(
                                world.db.execute(
                                    "SELECT 1 FROM post WHERE user_id=? LIMIT 1",
                                    (user,),
                                ).fetchone()
                            )
                            or user % 3 == 0
                        )
                        return PersonaPolicy(
                            config["seed"] + user * 1009, persona, creator=creator
                        )
                    spec = self.run_providers[run_id][selected]
                    return JsonSessionPolicy(
                        build_model_client(spec),
                        config["agent_goals"].get(str(user), config["goal"]),
                        persona,
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
                    goals=config["agent_goals"],
                )
            )
            if not self.run_providers[run_id]:
                report["policy"] = "persona-development"
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
        prepare_read_views(db)
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

    def inspect(self, run_id, event_limit=200):
        from agora.replay import preview_action

        with self.lock:
            metadata = json.loads(json.dumps(self.jobs[run_id]))
        with self.snapshot(run_id) as world:
            ids = json.dumps(metadata["session_ids"])
            actors = json.dumps(metadata["config"]["user_ids"])
            restriction = "e.session_id IN (SELECT value FROM json_each(?))"
            query = (
                "SELECT e.step,e.tick,e.elapsed_ms,e.action_json,e.result_json,s.user_id,e.event_id,e.session_id FROM agora_session_event e JOIN agora_session s ON s.session_id=e.session_id WHERE "
                + restriction
                + " ORDER BY e.event_id DESC"
            )
            params = (ids,)
            if event_limit is not None:
                query += " LIMIT ?"
                params += (event_limit,)
            events = []
            for row in world.db.execute(query, params):
                action, result = json.loads(row[3]), json.loads(row[4])
                shortened = False
                if event_limit is not None:
                    action, result, shortened = preview_action(action, result)
                events.append(
                    {
                        "event_id": row[6],
                        "session_id": row[7],
                        "user_id": row[5],
                        "step": row[0],
                        "tick": row[1],
                        "elapsed_ms": row[2],
                        "action": action,
                        "result": result,
                        "preview_truncated": shortened,
                    }
                )
            events.reverse()
            calls = [
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
                    "SELECT session_id,step,tick,status,model_id,input_tokens,output_tokens,elapsed_ms,error_type FROM agent_model_call WHERE session_id IN (SELECT value FROM json_each(?)) ORDER BY call_id DESC LIMIT 200",
                    (ids,),
                )
            ]
            total_calls, input_tokens, output_tokens = world.db.execute(
                "SELECT COUNT(*),COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0) FROM agent_model_call WHERE session_id IN (SELECT value FROM json_each(?))",
                (ids,),
            ).fetchone()
            users = [
                {"user_id": r[0], "name": r[1], "followers": r[2]}
                for r in world.db.execute(
                    "SELECT user_id,name,num_followers FROM user WHERE user_id IN (SELECT value FROM json_each(?))",
                    (actors,),
                )
            ]
            graph = [
                {"source": r[0], "target": r[1]}
                for r in world.db.execute(
                    "SELECT follower_id,followee_id FROM follow WHERE follower_id IN (SELECT value FROM json_each(?)) AND followee_id IN (SELECT value FROM json_each(?)) LIMIT 2000",
                    (actors, actors),
                )
            ]
            counts = dict(
                world.db.execute(
                    "SELECT json_extract(e.action_json,'$.action_type'),COUNT(*) FROM agora_session_event e WHERE "
                    + restriction
                    + " AND COALESCE(json_extract(e.result_json,'$.success'),1)=1 GROUP BY json_extract(e.action_json,'$.action_type')",
                    (ids,),
                )
            )
            total_events = world.db.execute(
                "SELECT COUNT(*) FROM agora_session_event e WHERE " + restriction,
                (ids,),
            ).fetchone()[0]
            actor_counts = {
                str(r[0]): r[1]
                for r in world.db.execute(
                    "SELECT s.user_id,COUNT(*) FROM agora_session_event e JOIN agora_session s ON s.session_id=e.session_id WHERE "
                    + restriction
                    + " AND json_extract(e.action_json,'$.action_type') NOT IN ('start_session','end_session') GROUP BY s.user_id",
                    (ids,),
                )
            }
            exposures = world.db.execute(
                "SELECT COUNT(*) FROM agora_exposure WHERE session_id IN (SELECT value FROM json_each(?))",
                (ids,),
            ).fetchone()[0]
            metadata.update(
                events=events,
                events_total=total_events,
                events_truncated=len(events) < total_events,
                actor_action_counts=actor_counts,
                model_calls=calls,
                model_calls_truncated=len(calls) < total_calls,
                users=users,
                graph=graph,
                metrics={
                    "created_posts": counts.get("create_post", 0)
                    + counts.get("publish_draft", 0),
                    "drafts": counts.get("save_draft", 0),
                    "comments": counts.get("create_comment", 0),
                    "replies": counts.get("reply_post", 0),
                    "model_calls": total_calls,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "exposures": exposures,
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

    def export_file(self, run_id):
        metadata = self.inspect(run_id)
        if metadata["status"] not in {
            "completed",
            "canceled",
            "failed",
            "interrupted",
            "paused",
        }:
            raise ValueError("请暂停或结束模拟后导出完整记录。")
        directory = self.root / run_id
        fd, name = tempfile.mkstemp(prefix="export-", suffix=".json", dir=directory)
        os.close(fd)
        path = Path(name)
        try:
            with (
                self.snapshot(run_id) as world,
                path.open("w", encoding="utf-8") as stream,
            ):

                def write(value):
                    stream.write(value)
                    if stream.tell() > 128 * 1024 * 1024:
                        raise ValueError(
                            "完整导出超过 128 MiB，请缩小单次运行或分批导出。"
                        )

                def array(values):
                    write("[")
                    first = True
                    for value in values:
                        if not first:
                            write(",")
                        write(value)
                        first = False
                    write("]")

                encode = lambda value: json.dumps(value, ensure_ascii=False)
                ids = encode(metadata["session_ids"])
                metadata = {
                    k: v
                    for k, v in metadata.items()
                    if k not in {"events", "model_calls"}
                }
                metadata.update(
                    format_version="agora-experiment-v1",
                    events_truncated=False,
                    model_calls_truncated=False,
                )
                write(encode(metadata)[:-1])
                if metadata.get("media_manifest_truncated"):
                    index = self.root / run_id / "initial-media.jsonl"
                    if file_sha256(index) != metadata["initial_media_sha256"]:
                        raise ValueError("Initial media index checksum mismatch")
                    write(',"initial_media_manifest":')
                    with index.open(encoding="utf-8") as media:
                        array(line.strip() for line in media if line.strip())
                write(',"events":')

                def events():
                    for row in world.db.execute(
                        "SELECT e.event_id,e.session_id,s.user_id,e.step,e.tick,e.elapsed_ms,e.action_json,e.result_json FROM agora_session_event e JOIN agora_session s ON s.session_id=e.session_id WHERE e.session_id IN (SELECT value FROM json_each(?)) ORDER BY e.event_id",
                        (ids,),
                    ):
                        yield (
                            '{"event_id":'
                            + str(row[0])
                            + ',"session_id":'
                            + str(row[1])
                            + ',"user_id":'
                            + str(row[2])
                            + ',"step":'
                            + str(row[3])
                            + ',"tick":'
                            + str(row[4])
                            + ',"elapsed_ms":'
                            + str(row[5])
                            + ',"action":'
                            + row[6]
                            + ',"result":'
                            + row[7]
                            + "}"
                        )

                array(events())
                write(',"model_calls":')
                array(
                    encode(
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
                    )
                    for row in world.db.execute(
                        "SELECT session_id,step,tick,status,model_id,input_tokens,output_tokens,elapsed_ms,error_type FROM agent_model_call WHERE session_id IN (SELECT value FROM json_each(?))",
                        (ids,),
                    )
                )
                write(',"trajectories":[')
                for index, sid in enumerate(metadata["session_ids"]):
                    if index:
                        write(",")
                    write('{"session_id":' + str(sid) + ',"trajectory":')
                    array(
                        '{"step":'
                        + str(row[0])
                        + ',"tick":'
                        + str(row[1])
                        + ',"elapsed_ms":'
                        + str(row[2])
                        + ',"action":'
                        + row[3]
                        + ',"result":'
                        + row[4]
                        + ',"observation":'
                        + row[5]
                        + "}"
                        for row in world.db.execute(
                            "SELECT step,tick,elapsed_ms,action_json,result_json,observation_json FROM agora_session_event WHERE session_id=? ORDER BY step",
                            (sid,),
                        )
                    )
                    write(',"recommendations":')
                    array(
                        '{"request_id":'
                        + str(row[0])
                        + ',"feed_type":'
                        + encode(row[1])
                        + ',"diagnostics":'
                        + row[2]
                        + "}"
                        for row in world.db.execute(
                            "SELECT request_id,feed_type,diagnostics_json FROM agora_request WHERE session_id=? ORDER BY request_id",
                            (sid,),
                        )
                    )
                    write("}")
                write('],"world_events":')
                array(
                    '{"event_id":'
                    + str(row[0])
                    + ',"tick":'
                    + str(row[1])
                    + ',"event_sequence":'
                    + str(row[2])
                    + ',"event_type":'
                    + encode(row[3])
                    + ',"actor_user_id":'
                    + encode(row[4])
                    + ',"target_type":'
                    + encode(row[5])
                    + ',"target_id":'
                    + encode(row[6])
                    + ',"payload":'
                    + row[7]
                    + "}"
                    for row in world.db.execute(
                        "SELECT event_id,tick,event_sequence,event_type,actor_user_id,target_type,target_id,payload FROM sandbox_event ORDER BY tick,event_sequence"
                    )
                )
                write("}")
            return path
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def export(self, run_id):
        value = self.inspect(run_id, event_limit=None)
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
