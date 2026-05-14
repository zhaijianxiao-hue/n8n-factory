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


class AdminDecisionRequest(BaseModel):
    actor: str = Field(default="admin", min_length=1)
    note: str = Field(default="")
