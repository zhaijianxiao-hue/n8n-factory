"""
Metal Price Sync Service
FastAPI服务，抓取并标准化黄金和铜价格
"""

import re
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import httpx
from bs4 import BeautifulSoup


app = FastAPI(title="Metal Price Sync Service", version="0.1.0")

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8766"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
USER_AGENT = os.getenv("USER_AGENT", "metal-price-sync/0.1.0")

GOLD_SOURCE_URL = os.getenv(
    "GOLD_SOURCE_URL", "http://www.huangjinjiage.cn/quote/119023.html"
)
COPPER_SOURCE_URL = os.getenv(
    "COPPER_SOURCE_URL", "https://www.jinritongjia.com/hutong/"
)


class MetalPrice(BaseModel):
    metal_code: str
    source_url: str
    price: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    price_date: Optional[str] = None
    raw_text: Optional[str] = None


class SourceStatus(BaseModel):
    gold: str
    copper: str


class PriceResponse(BaseModel):
    status: str
    fetched_at: str
    source_status: SourceStatus
    prices: Dict[str, Optional[MetalPrice]]
    warnings: List[str] = []


class ErrorResponse(BaseModel):
    status: str = "error"
    fetched_at: str
    source_status: SourceStatus
    prices: Dict[str, Optional[MetalPrice]]
    warnings: List[str] = []
    errors: List[Dict[str, str]] = []


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "metal-price-sync", "port": SERVICE_PORT}


@app.get("/prices/latest")
async def get_latest_prices():
    fetched_at = datetime.utcnow().isoformat() + "Z"

    gold_result = await fetch_gold_price()
    copper_result = await fetch_copper_price()

    gold_status = "success" if gold_result.price is not None else "error"
    copper_status = "success" if copper_result.price is not None else "error"

    overall_status = (
        "success"
        if gold_status == "success" and copper_status == "success"
        else "error"
    )

    response = PriceResponse(
        status=overall_status,
        fetched_at=fetched_at,
        source_status=SourceStatus(gold=gold_status, copper=copper_status),
        prices={
            "gold": gold_result if gold_result.price is not None else None,
            "copper": copper_result if copper_result.price is not None else None,
        },
        warnings=[],
    )

    return response


async def fetch_gold_price() -> MetalPrice:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                GOLD_SOURCE_URL, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()

            html_content = response.text
            parsed = parse_gold_price(html_content)

            return MetalPrice(
                metal_code="gold",
                source_url=GOLD_SOURCE_URL,
                price=parsed["price"],
                currency=parsed["currency"],
                unit=parsed["unit"],
                price_date=parsed["price_date"],
                raw_text=None,
            )
    except Exception as e:
        return MetalPrice(
            metal_code="gold",
            source_url=GOLD_SOURCE_URL,
            price=None,
            currency=None,
            unit=None,
            price_date=None,
            raw_text=str(e),
        )


async def fetch_copper_price() -> MetalPrice:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                COPPER_SOURCE_URL, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()

            html_content = response.text
            parsed = parse_copper_price(html_content)

            return MetalPrice(
                metal_code="copper",
                source_url=COPPER_SOURCE_URL,
                price=parsed["price"],
                currency=parsed["currency"],
                unit=parsed["unit"],
                price_date=parsed["price_date"],
                raw_text=None,
            )
    except Exception as e:
        return MetalPrice(
            metal_code="copper",
            source_url=COPPER_SOURCE_URL,
            price=None,
            currency=None,
            unit=None,
            price_date=None,
            raw_text=str(e),
        )


def parse_gold_price(html_content: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html_content, "html.parser")

    price_element = soup.find("span", class_="price-value")
    if not price_element:
        raise ValueError("Gold price not found in HTML")

    price_text = price_element.get_text(strip=True)
    try:
        price = float(price_text)
    except ValueError:
        raise ValueError(f"Cannot parse gold price: {price_text}")

    unit_element = soup.find("span", class_="price-unit")
    unit_text = unit_element.get_text(strip=True) if unit_element else "元/克"

    unit_normalized = "g"
    if "克" in unit_text or "g" in unit_text.lower():
        unit_normalized = "g"
    elif "公斤" in unit_text or "kg" in unit_text.lower():
        unit_normalized = "kg"

    date_element = soup.find("div", class_="price-date")
    price_date = (
        date_element.get_text(strip=True)
        if date_element
        else datetime.utcnow().strftime("%Y-%m-%d")
    )

    return {
        "metal_code": "gold",
        "price": price,
        "currency": "CNY",
        "unit": unit_normalized,
        "price_date": price_date,
        "source_url": GOLD_SOURCE_URL,
    }


def parse_copper_price(html_content: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html_content, "html.parser")

    script_tags = soup.find_all("script")
    for script in script_tags:
        if script.string and "list" in script.string:
            match = re.search(r'"price"\s*:\s*"(\d+)"', script.string)
            if match:
                price_text = match.group(1)
                try:
                    price = float(price_text)
                except ValueError:
                    raise ValueError(f"Cannot parse copper price: {price_text}")

                return {
                    "metal_code": "copper",
                    "price": price,
                    "currency": "CNY",
                    "unit": "t",
                    "price_date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "source_url": COPPER_SOURCE_URL,
                }

    raise ValueError("Copper price not found in HTML")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
