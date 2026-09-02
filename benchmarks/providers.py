from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from typing import Any

import requests

from benchmarks.adapters import ModelResponse


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(
        part.get("text", "[visual input]")
        for part in content if isinstance(part, dict))


def _gemini_parts(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"text": content}]
    parts = []
    for part in content:
        if part.get("type") == "text":
            parts.append({"text": part["text"]})
        elif part.get("type") == "image_url":
            url = part["image_url"]["url"]
            header, encoded = url.split(",", 1)
            mime = header.removeprefix("data:").split(";", 1)[0]
            base64.b64decode(encoded, validate=True)
            parts.append({"inlineData": {"mimeType": mime, "data": encoded}})
    return parts


@dataclass(frozen=True)
class ProviderLimits:
    timeout_seconds: float = 30.0
    max_requests: int = 5
    max_output_tokens: int = 256

    def __post_init__(self):
        if self.timeout_seconds <= 0 or self.max_requests < 1:
            raise ValueError("Provider timeout and request budget must be positive")
        if not 1 <= self.max_output_tokens <= 4096:
            raise ValueError("max_output_tokens must be between 1 and 4096")


class _BudgetedClient:
    def __init__(self, limits: ProviderLimits):
        self.limits = limits
        self.request_count = 0

    def _consume_request(self) -> None:
        if self.request_count >= self.limits.max_requests:
            raise RuntimeError("Provider request budget exhausted")
        self.request_count += 1


class GeminiClient(_BudgetedClient):
    """Google Generative Language API client using an environment-only key."""

    def __init__(self, model_id: str = "gemini-2.5-flash-lite",
                 api_key_env: str = "GEMINI_API_KEY",
                 limits: ProviderLimits = ProviderLimits()):
        super().__init__(limits)
        self.model_id = model_id
        self.api_key_env = api_key_env

    async def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        return await asyncio.to_thread(self._complete_sync, messages)

    def _complete_sync(self, messages):
        self._consume_request()
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(f"Missing credential environment: {self.api_key_env}")
        system = "\n".join(_text_content(item["content"]) for item in messages
                           if item["role"] == "system")
        contents = [{"role": "model" if item["role"] == "assistant" else "user",
                     "parts": _gemini_parts(item["content"])}
                    for item in messages if item["role"] != "system"]
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_id}:generateContent",
            params={"key": key}, timeout=self.limits.timeout_seconds,
            json={"systemInstruction": {"parts": [{"text": system}]},
                  "contents": contents,
                  "generationConfig": {
                      "temperature": 0,
                      "maxOutputTokens": self.limits.max_output_tokens,
                      "responseMimeType": "application/json"}})
        response.raise_for_status()
        value = response.json()
        text = value["candidates"][0]["content"]["parts"][0]["text"]
        usage = value.get("usageMetadata", {})
        return ModelResponse(
            text=text, model_id=self.model_id,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            provider_request_id=response.headers.get("x-request-id"))


class OpenAICompatibleClient(_BudgetedClient):
    """Minimal MaaS client for gateways exposing `/chat/completions`."""

    def __init__(self, base_url: str, model_id: str,
                 api_key_env: str = "AGORA_MAAS_API_KEY",
                 limits: ProviderLimits = ProviderLimits(),
                 auth_style: str = "bearer",
                 trust_env: bool = True,
                 extra_body: dict[str, Any] | None = None):
        super().__init__(limits)
        if not base_url.startswith("https://"):
            raise ValueError("Provider base_url must use HTTPS")
        if auth_style not in {"bearer", "api-key", "both"}:
            raise ValueError("auth_style must be bearer, api-key, or both")
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.api_key_env = api_key_env
        self.auth_style = auth_style
        self.trust_env = trust_env
        self.extra_body = dict(extra_body or {})

    async def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        return await asyncio.to_thread(self._complete_sync, messages)

    def _complete_sync(self, messages):
        self._consume_request()
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(f"Missing credential environment: {self.api_key_env}")
        headers = {"Content-Type": "application/json"}
        if self.auth_style in {"bearer", "both"}:
            headers["Authorization"] = f"Bearer {key}"
        if self.auth_style in {"api-key", "both"}:
            headers["api-key"] = key
        payload = {"model": self.model_id, "messages": messages,
                   "temperature": 0,
                   "max_tokens": self.limits.max_output_tokens,
                   "response_format": {"type": "json_object"}}
        payload.update(self.extra_body)
        session = requests.Session()
        session.trust_env = self.trust_env
        response = session.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            timeout=self.limits.timeout_seconds,
            json=payload)
        response.raise_for_status()
        value: dict[str, Any] = response.json()
        usage = value.get("usage", {})
        return ModelResponse(
            text=value["choices"][0]["message"]["content"],
            model_id=value.get("model", self.model_id),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            provider_request_id=value.get("id"))


class RednoteGeminiGatewayClient(_BudgetedClient):
    """Gemini generateContent client for Rednote's Runway gateway."""

    DEFAULT_URL = (
        "https://runway.devops.rednote.life/openai/google/v1:generateContent")

    def __init__(self, model_id: str = "runway-gemini-default",
                 url: str = DEFAULT_URL,
                 api_key_env: str = "AGORA_MAAS_API_KEY",
                 limits: ProviderLimits = ProviderLimits()):
        super().__init__(limits)
        if not url.startswith("https://"):
            raise ValueError("Provider URL must use HTTPS")
        self.model_id = model_id
        self.url = url
        self.api_key_env = api_key_env

    async def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        return await asyncio.to_thread(self._complete_sync, messages)

    def _complete_sync(self, messages):
        self._consume_request()
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(f"Missing credential environment: {self.api_key_env}")
        system = "\n\n".join(_text_content(item["content"]) for item in messages
                              if item["role"] == "system")
        user_messages = [item for item in messages if item["role"] != "system"]
        user_parts = [part for item in user_messages
                      for part in _gemini_parts(item["content"])]
        payload = {
            "contents": [{"role": "user", "parts": user_parts}],
            "generationConfig": {
                "temperature": 0,
                "topP": 1,
                "seed": 0,
                "maxOutputTokens": self.limits.max_output_tokens,
                "responseMimeType": "application/json",
                "thinkingConfig": {"includeThoughts": False,
                                   "thinkingLevel": "low"},
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        session = requests.Session()
        # The Runway hostname resolves on the internal network; external proxy
        # settings cannot route it and would fail before authentication.
        session.trust_env = False
        response = session.post(
            self.url,
            headers={"api-key": key, "Content-Type": "application/json"},
            json=payload, timeout=self.limits.timeout_seconds)
        response.raise_for_status()
        value = response.json()
        parts = value.get("candidates", [{}])[0].get(
            "content", {}).get("parts", [])
        text = "\n".join(part.get("text", "") for part in parts
                          if part.get("text") and not part.get("thought")).strip()
        if not text:
            text = "\n".join(part.get("text", "") for part in parts
                              if part.get("text")).strip()
        if not text:
            raise ValueError("Gemini gateway returned no text content")
        usage = value.get("usageMetadata", {})
        return ModelResponse(
            text=text, model_id=self.model_id,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            provider_request_id=(response.headers.get("x-request-id")
                                 or response.headers.get("x-trace-id")))


class LocalTransformersClient(_BudgetedClient):
    """Small local causal model client for zero-API-cost development checks."""

    def __init__(self, model_path: str, model_id: str,
                 limits: ProviderLimits = ProviderLimits(), **_kwargs):
        super().__init__(limits)
        self.model_path = model_path
        self.model_id = model_id
        self._tokenizer = None
        self._model = None

    async def complete(self, messages: list[dict[str, str]]) -> ModelResponse:
        return await asyncio.to_thread(self._complete_sync, messages)

    def _load(self):
        if self._model is not None:
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_path, local_files_only=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path, dtype="auto", device_map="auto",
            local_files_only=True)

    def _complete_sync(self, messages):
        self._consume_request()
        self._load()
        import torch
        text_messages = [{**item, "content": _text_content(item["content"])}
                         for item in messages]
        prompt = self._tokenizer.apply_chat_template(
            text_messages, tokenize=False, add_generation_prompt=True)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(
            self._model.device)
        with torch.inference_mode():
            generated = self._model.generate(
                **inputs, max_new_tokens=self.limits.max_output_tokens,
                do_sample=False)
        output_ids = generated[0][inputs.input_ids.shape[1]:]
        text = self._tokenizer.decode(
            output_ids, skip_special_tokens=True).strip()
        return ModelResponse(
            text=text, model_id=self.model_id,
            input_tokens=int(inputs.input_ids.shape[1]),
            output_tokens=int(output_ids.shape[0]))


def load_provider_config(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as stream:
        value = json.load(stream)
    def contains_secret(item: Any) -> bool:
        if isinstance(item, dict):
            return any(key.lower() in {"api_key", "apikey", "token", "secret"}
                       or contains_secret(child)
                       for key, child in item.items())
        if isinstance(item, list):
            return any(contains_secret(child) for child in item)
        return False

    if contains_secret(value):
        raise ValueError("Provider configs must not contain API keys")
    return value


def build_model_client(config: dict[str, Any]):
    limits = ProviderLimits(**config.get("limits", {}))
    provider = config["provider"]
    common = {
        "model_id": config["model_id"],
        "api_key_env": config.get("api_key_env", "AGORA_MAAS_API_KEY"),
        "limits": limits,
    }
    if provider == "rednote-gemini-gateway":
        return RednoteGeminiGatewayClient(
            url=config.get("url", RednoteGeminiGatewayClient.DEFAULT_URL),
            **common)
    if provider == "gemini":
        return GeminiClient(**common)
    if provider == "openai-compatible":
        return OpenAICompatibleClient(
            base_url=config["base_url"],
            auth_style=config.get("auth_style", "bearer"),
            trust_env=bool(config.get("trust_env", True)),
            extra_body=config.get("extra_body"), **common)
    if provider == "local-transformers":
        return LocalTransformersClient(
            model_path=config["model_path"], model_id=config["model_id"],
            limits=limits)
    raise ValueError(f"Unknown provider: {provider}")
