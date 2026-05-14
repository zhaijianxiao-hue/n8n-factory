import json
import os
import re
from typing import Protocol


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

    def create_json(self, messages: list[dict], model: str) -> dict:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        return extract_json_object(content)
