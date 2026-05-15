import json
import os
import re
from typing import Any
from typing import Protocol
from urllib import error
from urllib import request

from .env_loader import load_profile_lab_env


DEFAULT_MAX_TOKENS = 16384
MAX_TOKENS_ENV = "PO_PROFILE_LAB_OPENAI_MAX_TOKENS"
PROVIDER_ENV = "PO_PROFILE_LAB_PROVIDER"
OLLAMA_URL_ENV = "PO_PROFILE_LAB_OLLAMA_URL"
OLLAMA_THINK_ENV = "PO_PROFILE_LAB_OLLAMA_THINK"
OLLAMA_TIMEOUT_ENV = "PO_PROFILE_LAB_OLLAMA_TIMEOUT"
DEFAULT_PROVIDER = "openai-compatible"
DEFAULT_OLLAMA_TIMEOUT = 600


class JsonClient(Protocol):
    def create_json(self, messages: list[dict], model: str) -> dict:
        ...


def create_json_client() -> JsonClient:
    load_profile_lab_env()
    provider = os.environ.get(PROVIDER_ENV, DEFAULT_PROVIDER).strip().lower()
    if provider == "ollama":
        return OllamaJsonClient()
    if provider in {"openai", "openai-compatible", "openai_compatible"}:
        return OpenAICompatibleJsonClient()
    raise RuntimeError(f"{PROVIDER_ENV} must be 'ollama' or 'openai-compatible'")


def extract_json_object(content: str) -> dict:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    starts = [idx for idx in (content.find("{"), content.find("[")) if idx != -1]
    if starts:
        try:
            result, _ = json.JSONDecoder().raw_decode(content[min(starts):])
            return result
        except json.JSONDecodeError:
            pass

    raise ValueError("No JSON object found in model response")


class OpenAICompatibleJsonClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        load_profile_lab_env()
        resolved_api_key = api_key or os.environ.get("PO_PROFILE_LAB_OPENAI_API_KEY")
        if not resolved_api_key:
            raise RuntimeError(
                "PO_PROFILE_LAB_OPENAI_API_KEY is required for model-backed profile lab candidates"
            )

        from openai import OpenAI

        self.client = OpenAI(
            base_url=base_url or os.environ.get("PO_PROFILE_LAB_OPENAI_BASE_URL"),
            api_key=resolved_api_key,
        )
        self.max_tokens = _resolve_max_tokens()

    def create_json(self, messages: list[dict], model: str) -> dict:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        try:
            return extract_json_object(content)
        except ValueError as exc:
            diagnostics = _response_diagnostics(choice, content)
            raise ValueError(f"No JSON object found in model response ({diagnostics})") from exc


def _resolve_max_tokens() -> int:
    raw_value = os.environ.get(MAX_TOKENS_ENV)
    if not raw_value:
        return DEFAULT_MAX_TOKENS
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{MAX_TOKENS_ENV} must be an integer") from exc


def _response_diagnostics(choice: Any, content: str) -> str:
    message = choice.message
    reasoning = getattr(message, "reasoning", None) or ""
    return (
        f"finish_reason={choice.finish_reason!r}, "
        f"content_len={len(content)}, "
            f"reasoning_len={len(reasoning)}"
    )


class OllamaJsonClient:
    def __init__(self, base_url: str | None = None, think: bool | None = None) -> None:
        load_profile_lab_env()
        self.base_url = (base_url or _resolve_ollama_url()).rstrip("/")
        self.max_tokens = _resolve_max_tokens()
        self.think = _resolve_ollama_think() if think is None else think
        self.timeout = _resolve_ollama_timeout()

    def create_json(self, messages: list[dict], model: str) -> dict:
        payload = {
            "model": model,
            "messages": _to_ollama_messages(messages),
            "stream": False,
            "think": self.think,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": self.max_tokens,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Ollama chat request failed: {exc}") from exc

        content = ((response_data.get("message") or {}).get("content") or "").strip()
        try:
            return extract_json_object(content)
        except ValueError as exc:
            diagnostics = (
                f"done_reason={response_data.get('done_reason')!r}, "
                f"content_len={len(content)}, "
                f"think={self.think}"
            )
            raise ValueError(f"No JSON object found in Ollama response ({diagnostics})") from exc


def _resolve_ollama_url() -> str:
    url = os.environ.get(OLLAMA_URL_ENV)
    if url:
        return url
    openai_url = os.environ.get("PO_PROFILE_LAB_OPENAI_BASE_URL")
    if openai_url and openai_url.rstrip("/").endswith("/v1"):
        return openai_url.rstrip("/")[:-3]
    if openai_url:
        return openai_url
    return "http://localhost:11434"


def _resolve_ollama_think() -> bool:
    return os.environ.get(OLLAMA_THINK_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_ollama_timeout() -> int:
    raw_value = os.environ.get(OLLAMA_TIMEOUT_ENV)
    if not raw_value:
        return DEFAULT_OLLAMA_TIMEOUT
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{OLLAMA_TIMEOUT_ENV} must be an integer") from exc


def _to_ollama_messages(messages: list[dict]) -> list[dict]:
    converted = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts = []
            images = []
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    image_url = (part.get("image_url") or {}).get("url", "")
                    image = _image_data_from_url(image_url)
                    if image:
                        images.append(image)
            converted_message = {
                "role": role,
                "content": "\n".join(text for text in text_parts if text).strip(),
            }
            if images:
                converted_message["images"] = images
            converted.append(converted_message)
        else:
            converted.append({"role": role, "content": str(content)})
    return converted


def _image_data_from_url(image_url: str) -> str | None:
    if not image_url:
        return None
    if image_url.startswith("data:"):
        marker = "base64,"
        if marker not in image_url:
            return None
        return image_url.split(marker, 1)[1]
    return None
