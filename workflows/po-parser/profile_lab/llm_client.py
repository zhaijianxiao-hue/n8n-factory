import json
import os
import re
from typing import Protocol
from typing import Any

from .env_loader import load_profile_lab_env


DEFAULT_MAX_TOKENS = 16384
MAX_TOKENS_ENV = "PO_PROFILE_LAB_OPENAI_MAX_TOKENS"


class JsonClient(Protocol):
    def create_json(self, messages: list[dict], model: str) -> dict:
        ...


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
