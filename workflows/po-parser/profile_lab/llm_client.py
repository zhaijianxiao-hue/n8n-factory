import json
import os
import re
from typing import Protocol


class JsonClient(Protocol):
    def create_json(self, messages: list[dict], model: str) -> dict:
        ...


def extract_json_object(content: str) -> dict:
    match = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", content, re.DOTALL)
    if match:
        content = match.group(1)
    return json.loads(content)


class OpenAICompatibleJsonClient:
    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(
            base_url=os.environ.get("PO_PROFILE_LAB_OPENAI_BASE_URL"),
            api_key=os.environ.get("PO_PROFILE_LAB_OPENAI_API_KEY"),
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
