from typing import Any
from typing import Literal
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


ApprovalState = Literal[
    "draft",
    "generated",
    "evaluated",
    "submitted",
    "changes_requested",
    "approved",
    "published",
]


class ApprovalRecord(BaseModel):
    state: ApprovalState = Field(default="draft")
    submitted_by: Optional[str] = Field(default=None)
    submitted_at: Optional[str] = Field(default=None)
    admin_decision: Optional[Literal["approved", "rejected"]] = Field(default=None)
    admin_by: Optional[str] = Field(default=None)
    admin_at: Optional[str] = Field(default=None)
    note: str = Field(default="")
    notification_status: Optional[str] = Field(default=None)
    notification_error: Optional[str] = Field(default=None)


class ApprovalRequest(BaseModel):
    actor: str = Field(default="business", min_length=1)
    note: str = Field(default="")


class CustomerCreateRequest(BaseModel):
    customer: str = Field(min_length=1)
    display_name: str = Field(default="")


class DraftRunRequest(BaseModel):
    run_id: str = Field(min_length=1)
    text_model: Optional[str] = Field(default=None)
    vision_model: Optional[str] = Field(default=None)
    skip_render: bool = Field(default=False)


class AdminDecisionRequest(BaseModel):
    actor: str = Field(default="admin", min_length=1)
    note: str = Field(default="")


class FieldCorrection(BaseModel):
    field: str = Field(min_length=1)
    correct_value: Any
    note: str = Field(default="")


class CorrectionRequest(BaseModel):
    actor: str = Field(default="business", min_length=1)
    corrections: list[FieldCorrection] = Field(default_factory=list)


class ProfileMarkersRequest(BaseModel):
    markers: list[str] = Field(default_factory=list)
