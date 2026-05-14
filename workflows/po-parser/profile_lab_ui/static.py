from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    dist_dir = Path(dist_dir)
    index_path = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="profile_lab_assets")

    @app.get("/")
    def serve_index():
        return FileResponse(index_path)

    @app.get("/{path:path}")
    def serve_spa(path: str):
        status_code = 404 if path.startswith("api/") else 200
        return FileResponse(index_path, status_code=status_code)
