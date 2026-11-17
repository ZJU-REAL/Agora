"""Persistent developer model settings with server-only credentials."""

import asyncio
import copy
import json
import os
import re
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urlsplit

from agora.models import ProviderLimits, build_model_client


class ProviderRegistry:
    def __init__(self, directory, providers=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.path = self.directory / "providers.json"
        self.providers = copy.deepcopy(providers or {})
        self.saved = json.loads(self.path.read_text()) if self.path.exists() else {}
        if self.path.exists():
            self.path.chmod(0o600)
        for name, entry in self.saved.items():
            spec = entry["spec"]
            self.providers[name] = spec
            os.environ[spec["api_key_env"]] = entry["key"]

    def options(self):
        return [
            {
                "provider_id": name,
                "display_name": spec.get("display_name", name),
                "provider": spec["provider"],
                "model_id": spec["model_id"],
                "base_url": spec.get("base_url", spec.get("url", "")),
                "auth_style": spec.get("auth_style", "bearer"),
                "supports_vision": bool(spec.get("supports_vision")),
                "credential_available": bool(
                    os.environ.get(spec.get("api_key_env", "AGORA_MAAS_API_KEY"))
                )
                if spec["provider"] != "local-transformers"
                else os.path.isdir(spec.get("model_path", "")),
                "limits": spec.get("limits", {}),
            }
            for name, spec in self.providers.items()
        ]

    def save(self, value):
        if set(value) - {
            "provider_id",
            "display_name",
            "provider",
            "model_id",
            "base_url",
            "api_key",
            "auth_style",
            "supports_vision",
            "limits",
        }:
            raise ValueError("Unknown model setting")
        name = value.get("provider_id") or "model-" + uuid.uuid4().hex[:8]
        if (
            not isinstance(name, str)
            or name == "development"
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name)
        ):
            raise ValueError("Invalid model configuration ID")
        model = value.get("model_id")
        label = value.get("display_name") or model
        if (
            not isinstance(model, str)
            or not model.strip()
            or len(model) > 200
            or not isinstance(label, str)
            or len(label) > 120
        ):
            raise ValueError("Provide a model ID and short display name")
        protocol = value.get("provider", "openai-compatible")
        if protocol not in {"openai-compatible", "gemini", "rednote-gemini-gateway"}:
            raise ValueError("Unsupported remote model protocol")
        url = value.get("base_url", "")
        if not isinstance(url, str):
            raise TypeError("Model endpoint must be a URL string")
        url = url.rstrip("/")
        if protocol != "gemini":
            parts = urlsplit(url)
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
            ):
                raise ValueError(
                    "Model endpoint must be an HTTPS URL without embedded credentials"
                )
        limits = value.get("limits", {})
        if not isinstance(limits, dict) or set(limits) - {
            "timeout_seconds",
            "max_requests",
            "max_output_tokens",
        }:
            raise ValueError("Unknown model budget setting")
        limits = ProviderLimits(
            **{
                "timeout_seconds": 60,
                "max_requests": 100,
                "max_output_tokens": 1024,
                **limits,
            }
        )
        if (
            not 1 <= limits.timeout_seconds <= 180
            or type(limits.max_requests) is not int
            or not 1 <= limits.max_requests <= 3000
            or type(limits.max_output_tokens) is not int
        ):
            raise ValueError("Model budget exceeds the console limits")
        vision = value.get("supports_vision", False)
        if type(vision) is not bool:
            raise ValueError("supports_vision must be boolean")
        previous = self.providers.get(name, {})
        key = value.get("api_key") or os.environ.get(previous.get("api_key_env", ""))
        if not isinstance(key, str) or not key.strip() or len(key) > 8192:
            raise ValueError("Provide a model API key")
        # A new environment slot keeps credentials frozen for running jobs.
        env = "AGORA_UI_KEY_" + uuid.uuid4().hex.upper()
        spec = {
            "provider": protocol,
            "display_name": label,
            "model_id": model.strip(),
            "api_key_env": env,
            "supports_vision": vision,
            "limits": asdict(limits),
        }
        if protocol == "openai-compatible":
            spec.update(base_url=url, auth_style=value.get("auth_style", "bearer"))
        elif protocol == "rednote-gemini-gateway":
            spec["url"] = url
        build_model_client(spec)  # Validate the protocol without making a request.
        saved = {**self.saved, name: {"spec": spec, "key": key}}
        temporary = self.directory / ("providers-" + uuid.uuid4().hex + ".tmp")
        try:
            with os.fdopen(
                os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
            ) as stream:
                json.dump(saved, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
        self.saved = saved
        os.environ[env] = key
        self.providers[name] = spec
        return next(
            option for option in self.options() if option["provider_id"] == name
        )

    def test(self, provider_id):
        if provider_id not in self.providers:
            raise ValueError("Choose a saved model configuration")
        spec = copy.deepcopy(self.providers[provider_id])
        spec["limits"] = asdict(
            replace(
                ProviderLimits(**spec.get("limits", {})),
                timeout_seconds=10,
                max_requests=1,
            )
        )
        started = time.monotonic()
        try:
            response = asyncio.run(
                build_model_client(spec).complete(
                    [
                        {
                            "role": "system",
                            "content": 'Return a JSON object: {"ok": true}.',
                        },
                        {"role": "user", "content": "Check the model connection."},
                    ]
                )
            )
            if response.model_id != spec["model_id"]:
                return {
                    "success": False,
                    "error": "服务返回的模型 ID 与配置不一致，请核对模型 ID。",
                }
            return {
                "success": True,
                "model_id": response.model_id,
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
        except Exception as error:  # noqa: BLE001 - redact provider errors before returning to the browser
            return {
                "success": False,
                "error": "连接失败，请检查地址、模型 ID、密钥与网络。",
                "error_type": type(error).__name__,
            }
