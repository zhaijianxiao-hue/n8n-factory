from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CustomerInitResult(BaseModel):
    customer_dir: Path


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
