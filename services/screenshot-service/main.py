"""
Screenshot Service
将网页渲染并截图，返回 base64 PNG 供 n8n 后续节点发送到飞书
"""

import os
import logging
import base64
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

SCREENSHOT_TIMEOUT = int(os.getenv("SCREENSHOT_TIMEOUT", "30"))
SCREENSHOT_MAX_WIDTH = int(os.getenv("SCREENSHOT_MAX_WIDTH", "3840"))
SCREENSHOT_MAX_HEIGHT = int(os.getenv("SCREENSHOT_MAX_HEIGHT", "2160"))
API_PORT = int(os.getenv("SCREENSHOT_PORT", "8767"))
ALLOWED_PRIVATE_HOSTS = {
    host.strip()
    for host in os.getenv("SCREENSHOT_ALLOWED_PRIVATE_HOSTS", "").split(",")
    if host.strip()
}

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def _resolve_ip(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        try:
            return ipaddress.ip_address(socket.gethostbyname(hostname))
        except (socket.gaierror, OSError):
            raise HTTPException(status_code=400, detail="Cannot resolve hostname")


def _is_private_host(hostname: str) -> bool:
    ip = _resolve_ip(hostname)
    for network in _PRIVATE_NETWORKS:
        if ip in network:
            return True
    return False


def _is_allowed_private_host(hostname: str) -> bool:
    if hostname in ALLOWED_PRIVATE_HOSTS:
        return True

    resolved_ip = str(_resolve_ip(hostname))
    return resolved_ip in ALLOWED_PRIVATE_HOSTS


def validate_url(url: str) -> None:
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http and https URLs are allowed")

    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must contain a hostname")

    if _is_private_host(parsed.hostname) and not _is_allowed_private_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="Access to internal/private addresses is not allowed")


app = FastAPI(
    title="Screenshot Service",
    version="1.0.0",
    description="网页截图服务，返回 base64 PNG",
)


class ScreenshotRequest(BaseModel):
    url: str = Field(..., description="要截图的网页地址")
    width: int = Field(default=1280, ge=320, le=SCREENSHOT_MAX_WIDTH, description="浏览器视口宽度")
    height: int = Field(default=720, ge=240, le=SCREENSHOT_MAX_HEIGHT, description="浏览器视口高度")
    full_page: bool = Field(default=False, description="是否截取整页")
    delay_ms: int = Field(default=1000, ge=0, le=30000, description="页面加载后额外等待毫秒数")


class ScreenshotResponse(BaseModel):
    status: str
    image_base64: Optional[str] = None
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.post("/screenshot", response_model=ScreenshotResponse)
async def screenshot(req: ScreenshotRequest):
    validate_url(req.url)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Playwright not installed. Run: pip install playwright && playwright install chromium",
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=os.getenv("CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium-browser"),
        )
        page = await browser.new_page(viewport={"width": req.width, "height": req.height})

        try:
            await page.goto(req.url, wait_until="domcontentloaded", timeout=SCREENSHOT_TIMEOUT * 1000)
            await page.wait_for_timeout(req.delay_ms)

            screenshot_bytes = await page.screenshot(full_page=req.full_page)
            image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            logger.info(f"Screenshot captured: {req.url} ({len(screenshot_bytes)} bytes)")
            return ScreenshotResponse(status="ok", image_base64=image_base64)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Screenshot failed for {req.url}: {e}")
            raise HTTPException(status_code=500, detail="Screenshot failed")
        finally:
            await browser.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
