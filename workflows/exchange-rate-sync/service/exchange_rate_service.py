"""FastAPI service for resolving official CFETS CNY central parity rates."""

import logging
import math
import os
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


SERVICE_NAME = "exchange-rate-sync"
SERVICE_VERSION = "0.1.0"
SERVICE_HOST = os.getenv("SERVICE_HOST", "0.0.0.0")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8770"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
USER_AGENT = os.getenv("USER_AGENT", f"{SERVICE_NAME}/{SERVICE_VERSION}")

PROVIDER = "CFETS"
SOURCE_PAGE_URL = "https://www.chinamoney.com.cn/chinese/bkccpr/"
CFETS_HISTORY_URL = os.getenv(
    "CFETS_HISTORY_URL",
    "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew",
)

SUPPORTED_CURRENCIES = ("EUR", "USD", "CAD", "HKD", "SGD", "JPY")
DEFAULT_CURRENCIES = list(SUPPORTED_CURRENCIES)
SOURCE_PAIR_BY_CURRENCY = {
    "EUR": "EUR/CNY",
    "USD": "USD/CNY",
    "CAD": "CAD/CNY",
    "HKD": "HKD/CNY",
    "SGD": "SGD/CNY",
    "JPY": "100JPY/CNY",
}

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Exchange Rate Sync Service", version=SERVICE_VERSION)


class ProviderDataError(RuntimeError):
    """Raised when CFETS data is unavailable or violates the service contract."""


class ExchangeRate(BaseModel):
    from_currency: str
    to_currency: str = "CNY"
    rate: float = Field(gt=0)
    from_factor: int = 1
    to_factor: int = 1
    source_pair: str


class ParsedRates(BaseModel):
    source_date: date
    rates: list[ExchangeRate]


class ResolveRatesRequest(BaseModel):
    requested_date: date
    currencies: list[str] = Field(default_factory=lambda: list(DEFAULT_CURRENCIES))
    lookback_days: int = Field(default=10, ge=1, le=31)

    @field_validator("currencies")
    @classmethod
    def validate_currencies(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("currencies must not be empty")

        normalized: list[str] = []
        for currency in value:
            code = currency.strip().upper()
            if code not in SUPPORTED_CURRENCIES:
                supported = ", ".join(SUPPORTED_CURRENCIES)
                raise ValueError(
                    f"unsupported currency {code or currency!r}; supported: {supported}"
                )
            if code not in normalized:
                normalized.append(code)
        return normalized


class ResolveRatesResponse(BaseModel):
    status: str = "success"
    provider: str = PROVIDER
    requested_date: date
    source_date: date
    fetched_at: str
    source_url: str = CFETS_HISTORY_URL
    rates: list[ExchangeRate]
    warnings: list[str]


def parse_cfets_history(
    payload: dict[str, Any], requested_date: date, currencies: list[str]
) -> ParsedRates:
    """Parse a CFETS history response and select the latest eligible record."""
    head = payload.get("head")
    if not isinstance(head, dict):
        raise ProviderDataError("CFETS response is missing head")

    if str(head.get("rep_code")) != "200":
        message = head.get("rep_message") or head.get("rep_code") or "unknown error"
        raise ProviderDataError(f"CFETS provider error: {message}")

    data = payload.get("data")
    records = payload.get("records")
    if not isinstance(data, dict) or not isinstance(records, list):
        raise ProviderDataError("CFETS response has an invalid data structure")

    source_pairs = data.get("searchlist")
    if not isinstance(source_pairs, list) or not source_pairs:
        raise ProviderDataError("CFETS response is missing searchlist")

    eligible_records: list[tuple[date, list[Any]]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            record_date = date.fromisoformat(str(record.get("date")))
        except ValueError:
            continue
        values = record.get("values")
        if record_date <= requested_date and isinstance(values, list):
            eligible_records.append((record_date, values))

    if not eligible_records:
        raise ProviderDataError(
            f"CFETS returned no published rates on or before {requested_date.isoformat()}"
        )

    source_date, values = max(eligible_records, key=lambda item: item[0])
    if len(values) != len(source_pairs):
        raise ProviderDataError(
            "CFETS response values do not align with the requested currency pairs"
        )

    values_by_pair = dict(zip(source_pairs, values))
    normalized_rates: list[ExchangeRate] = []
    missing_currencies: list[str] = []

    for currency in currencies:
        source_pair = SOURCE_PAIR_BY_CURRENCY[currency]
        raw_value = values_by_pair.get(source_pair)
        try:
            rate_value = float(raw_value)
        except (TypeError, ValueError):
            missing_currencies.append(currency)
            continue

        if not math.isfinite(rate_value) or rate_value <= 0:
            missing_currencies.append(currency)
            continue

        normalized_rates.append(
            ExchangeRate(
                from_currency=currency,
                rate=rate_value,
                from_factor=100 if currency == "JPY" else 1,
                source_pair=source_pair,
            )
        )

    if missing_currencies:
        missing = ", ".join(missing_currencies)
        raise ProviderDataError(f"CFETS response is missing valid rates for: {missing}")

    return ParsedRates(source_date=source_date, rates=normalized_rates)


async def fetch_cfets_rates(
    requested_date: date, currencies: list[str], lookback_days: int
) -> ParsedRates:
    """Fetch and parse official CFETS rates for the requested date window."""
    start_date = requested_date - timedelta(days=lookback_days)
    source_pairs = [SOURCE_PAIR_BY_CURRENCY[currency] for currency in currencies]
    params = {
        "startDate": start_date.isoformat(),
        "endDate": requested_date.isoformat(),
        "currency": ",".join(source_pairs),
        "pageNum": 1,
        "pageSize": max(20, lookback_days + 1),
    }
    headers = {"User-Agent": USER_AGENT, "Referer": SOURCE_PAGE_URL}

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(CFETS_HISTORY_URL, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise ProviderDataError(f"CFETS request failed: {exc}") from exc
    except ValueError as exc:
        raise ProviderDataError("CFETS returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ProviderDataError("CFETS returned a non-object JSON response")

    return parse_cfets_history(payload, requested_date, currencies)


@app.get("/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "port": SERVICE_PORT,
        "provider": PROVIDER,
    }


@app.post("/rates/resolve", response_model=ResolveRatesResponse)
async def resolve_rates(request: ResolveRatesRequest) -> ResolveRatesResponse:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if request.requested_date > today:
        raise HTTPException(status_code=422, detail="requested_date must not be in the future")

    try:
        parsed = await fetch_cfets_rates(
            request.requested_date,
            request.currencies,
            request.lookback_days,
        )
    except ProviderDataError as exc:
        logger.error("CFETS rate resolution failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    warnings: list[str] = []
    if parsed.source_date != request.requested_date:
        warnings.append(
            "requested_date "
            f"{request.requested_date.isoformat()} used source_date "
            f"{parsed.source_date.isoformat()}"
        )

    return ResolveRatesResponse(
        requested_date=request.requested_date,
        source_date=parsed.source_date,
        fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        rates=parsed.rates,
        warnings=warnings,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)
