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
    "COPPER_SOURCE_URL", "https://www.jinritongjia.com/d/tong.js"
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

    gold_row = soup.find("tr", id="g1")
    if not gold_row:
        raise ValueError("Gold price row not found in HTML")

    price_cells = gold_row.find_all("td")
    if len(price_cells) < 4:
        raise ValueError("Gold price cells not found")

    price_cell = gold_row.find("td", class_="red")
    if not price_cell:
        price_cell = price_cells[2]

    price_text = price_cell.get_text(strip=True)
    try:
        price = float(price_text)
    except ValueError:
        raise ValueError(f"Cannot parse gold price: {price_text}")

    date_cell = gold_row.find("td", class_="daTime")
    price_date = (
        date_cell.get_text(strip=True)
        if date_cell
        else datetime.utcnow().strftime("%Y-%m-%d")
    )

    return {
        "metal_code": "gold",
        "price": price,
        "currency": "CNY",
        "unit": "g",
        "price_date": price_date,
        "source_url": GOLD_SOURCE_URL,
    }


def parse_copper_price(js_content: str) -> Dict[str, Any]:
    match = re.search(r'var hq_str_nf_CU0="([^"]+)"', js_content)
    if not match:
        raise ValueError("Copper price data not found in JS")

    csv_data = match.group(1)
    fields = csv_data.split(",")

    if len(fields) < 9:
        raise ValueError(f"Insufficient copper price fields: {len(fields)}")

    try:
        price = float(fields[8])
    except ValueError:
        raise ValueError(f"Cannot parse copper price: {fields[8]}")

    price_date = (
        fields[17] if len(fields) > 17 else datetime.utcnow().strftime("%Y-%m-%d")
    )

    return {
        "metal_code": "copper",
        "price": price,
        "currency": "CNY",
        "unit": "t",
        "price_date": price_date,
        "source_url": COPPER_SOURCE_URL,
    }


def parse_copper_price_from_data(
    data: Dict[str, Any], source_url: str = COPPER_SOURCE_URL
) -> Dict[str, Any]:
    """
    从铜数据API响应解析价格

    Args:
        data: API返回的数据结构（通常是JSON）
        source_url: 来源URL

    Returns:
        标准化的金属价格字典

    Raises:
        ValueError: 无法解析价格或数据结构异常
    """
    try:
        if "data" in data and "list" in data["data"]:
            items = data["data"]["list"]
            for item in items:
                name = item.get("name", "")
                if "铜" in name or "copper" in name.lower():
                    price_text = item.get("price", "")
                    if price_text:
                        price_value = float(price_text)
                        unit_text = item.get("unit", "元/吨")

                        unit = "t" if "吨" in unit_text else "kg"

                        price_date = item.get(
                            "date", datetime.utcnow().strftime("%Y-%m-%d")
                        )

                        return {
                            "metal_code": "copper",
                            "source_url": source_url,
                            "price": price_value,
                            "currency": "CNY",
                            "unit": unit,
                            "price_date": price_date,
                        }

            raise ValueError("Copper price not found in data list")

        raise ValueError("Unexpected data structure for copper price")

    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Failed to parse copper price: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
