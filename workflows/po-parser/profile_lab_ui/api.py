from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException

from profile_lab.paths import DEFAULT_LAB_ROOT

from .artifacts import ArtifactNotFoundError
from .artifacts import ArtifactRepository


def create_app(lab_root: Path = DEFAULT_LAB_ROOT) -> FastAPI:
    app = FastAPI(title="PO Profile Lab UI API")
    repository = ArtifactRepository(lab_root=lab_root)

    @app.get("/api/customers")
    def list_customers():
        return repository.list_customers()

    @app.get("/api/customers/{customer}/runs")
    def list_runs(customer: str):
        return repository.list_runs(customer)

    @app.get("/api/customers/{customer}/runs/{run_id}")
    def get_run(customer: str, run_id: str):
        try:
            return repository.get_run(customer, run_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run not found") from exc

    return app
