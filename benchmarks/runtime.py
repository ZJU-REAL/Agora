from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import hashlib

from benchmarks.adapters import JsonModelCandidate
from benchmarks.observers import (ConfiguredScriptedObserver,
                                  JsonModelObserver, ObserverPool,
                                  ScriptedDevelopmentObserver)
from benchmarks.policies import POLICIES
from benchmarks.providers import build_model_client, load_provider_config


def _resolve_provider_config(spec: dict[str, Any], config_dir: Path) -> dict:
    if "provider_config" in spec:
        path = Path(spec["provider_config"])
        if not path.is_absolute():
            path = config_dir / path
        expected = spec.get("provider_config_sha256")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected is not None and expected != actual:
            raise ValueError("Provider config checksum mismatch")
        return load_provider_config(str(path))
    provider = dict(spec["provider"])
    if "api_key" in provider:
        raise ValueError("Runtime provider configs must not contain API keys")
    return provider


def candidate_factory(value: dict[str, Any],
                      config_path: str | Path) -> tuple[Callable, str, str]:
    spec = value.get("candidate")
    if spec is None:
        policy_name = value["candidate_policy"]
        if policy_name not in POLICIES:
            raise ValueError(f"Unknown built-in policy: {policy_name}")
        policy = POLICIES[policy_name]()
        return POLICIES[policy_name], policy.policy_id, policy.policy_version
    if spec.get("type") != "model":
        raise ValueError(f"Unknown candidate type: {spec.get('type')}")
    provider = _resolve_provider_config(spec, Path(config_path).parent)
    policy_id = spec["policy_id"]
    policy_version = spec["policy_version"]
    attempts = int(spec.get("max_attempts", 1))

    def create():
        client = build_model_client(provider)
        return JsonModelCandidate(
            policy_id, policy_version, client, attempts,
            expected_model_id=provider["model_id"],
            supports_vision=bool(provider.get("supports_vision", False)))

    return create, policy_id, policy_version


def observer_factory(value: dict[str, Any],
                     config_path: str | Path) -> Callable | None:
    spec_config_path = Path(config_path)
    spec = value.get("observer")
    if spec is None and value.get("observer_pool_config"):
        path = Path(value["observer_pool_config"])
        if not path.is_absolute():
            path = Path(config_path).parent / path
        expected = value.get("observer_pool_config_sha256")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected is not None and expected != actual:
            raise ValueError("Observer pool config checksum mismatch")
        spec = load_provider_config(str(path))
        spec_config_path = path
    if spec is None or spec == "none":
        return None
    if spec == "scripted-development":
        return ScriptedDevelopmentObserver
    if not isinstance(spec, dict):
        raise ValueError(f"Unknown observer specification: {spec!r}")
    if spec.get("type") == "pool":
        member_factories = [observer_factory(
            {"observer": member}, spec_config_path)
                            for member in spec["observers"]]

        def create_pool():
            return ObserverPool(spec["pool_version"], tuple(
                factory() for factory in member_factories if factory))

        return create_pool
    if spec.get("type") == "scripted":
        return lambda: ConfiguredScriptedObserver(
            spec["observer_id"], spec["observer_version"])
    if spec.get("type") != "model":
        raise ValueError(f"Unknown observer specification: {spec!r}")
    provider = _resolve_provider_config(spec, spec_config_path.parent)
    observer_id = spec["observer_id"]
    observer_version = spec["observer_version"]

    def create():
        return JsonModelObserver(
            observer_id, observer_version, build_model_client(provider),
            parse_failure_mode=spec.get("parse_failure_mode", "raise"),
            supports_vision=bool(provider.get("supports_vision", False)))

    return create
