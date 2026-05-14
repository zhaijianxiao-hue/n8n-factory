from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def dump_model(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class CustomerInitResult(BaseModel):
    customer_dir: Path


class RunManifest(BaseModel):
    run_id: str
    customer: str
    profile_version: str
    prompt_version: str = "0.1.0"
    model_text: str | None = None
    model_vision: str | None = None
    samples: list[str]
    created_at: str


class RunCreateResult(BaseModel):
    run_dir: Path
    manifest: RunManifest


class CustomerConfig(BaseModel):
    customer_key: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    default_currency: str | None = None
    language: list[str] = Field(default_factory=list)


class ProfileConfig(BaseModel):
    profile_name: str
    version: str = "0.1.0"
    status: str = "draft"
    markers: list[str] = Field(default_factory=list)
    number_format: dict[str, str] = Field(
        default_factory=lambda: {
            "decimal_separator": ".",
            "thousands_separator": ",",
        }
    )
    item_rules: dict[str, Any] = Field(default_factory=dict)
    last_run_id: str | None = None
    last_score: dict[str, Any] | None = None
    published_at: str | None = None


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
