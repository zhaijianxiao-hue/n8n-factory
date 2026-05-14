import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class NotificationResult:
    status: str
    error: str


def build_approval_payload(
    customer: str,
    run_id: str,
    summary: dict[str, Any],
    review_url: str,
) -> dict[str, Any]:
    return {
        "event": "profile_lab.approval_requested",
        "customer": customer,
        "run_id": run_id,
        "overall_score": summary.get("overall_score"),
        "publishable": summary.get("publishable"),
        "review_url": review_url,
    }


def send_approval_notification(
    payload: dict[str, Any],
    webhook_url: str | None = None,
) -> NotificationResult:
    url = webhook_url or os.getenv("PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL")
    if not url:
        return NotificationResult(
            status="skipped",
            error="approval webhook URL is not configured",
        )

    try:
        response = httpx.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        return NotificationResult(status="failed", error=str(exc))

    return NotificationResult(status="sent", error="")
