import json
from pathlib import Path
from typing import Any

from profile_lab.paths import DEFAULT_LAB_ROOT

from .approval import load_approval


_REQUIRED = object()


class ArtifactNotFoundError(FileNotFoundError):
    pass


def read_json(path: Path, default: Any = _REQUIRED) -> Any:
    target = Path(path)
    if not target.exists():
        if default is _REQUIRED:
            raise ArtifactNotFoundError(str(target))
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def customer_dir(lab_root: Path, customer: str) -> Path:
    return Path(lab_root) / "customers" / customer


def run_dir(lab_root: Path, customer: str, run_id: str) -> Path:
    path = customer_dir(lab_root, customer) / "runs" / run_id
    if not path.exists():
        raise ArtifactNotFoundError(str(path))
    return path


def list_customers(lab_root: Path) -> list[dict[str, Any]]:
    return ArtifactRepository(lab_root=lab_root).list_customers()


def list_runs(lab_root: Path, customer: str) -> list[dict[str, Any]]:
    return ArtifactRepository(lab_root=lab_root).list_runs(customer)


def load_run(lab_root: Path, customer: str, run_id: str) -> dict[str, Any]:
    return ArtifactRepository(lab_root=lab_root).get_run(customer, run_id)


class ArtifactRepository:
    def __init__(self, lab_root: Path = DEFAULT_LAB_ROOT):
        self.lab_root = Path(lab_root)

    def list_customers(self) -> list[dict[str, Any]]:
        customers_dir = self.lab_root / "customers"
        if not customers_dir.exists():
            return []

        rows = []
        for customer_dir in customers_dir.iterdir():
            if not customer_dir.is_dir():
                continue
            metadata = read_json(customer_dir / "customer.json", default={})
            customer_key = metadata.get("customer_key", customer_dir.name)
            display_name = metadata.get("display_name", customer_key)
            rows.append(
                {
                    "customer_key": customer_key,
                    "display_name": display_name,
                    "run_count": len(self._run_dirs(customer_dir.name)),
                }
            )
        return sorted(rows, key=lambda row: row["customer_key"])

    def list_runs(self, customer: str) -> list[dict[str, Any]]:
        rows = []
        for run_dir in self._run_dirs(customer):
            manifest = read_json(run_dir / "manifest.json", default={})
            evaluation = read_json(run_dir / "evaluation" / "summary.json", default={})
            approval = dump_model(load_approval(run_dir))
            rows.append(
                {
                    "run_id": manifest.get("run_id", run_dir.name),
                    "customer": manifest.get("customer", customer),
                    "created_at": manifest.get("created_at"),
                    "sample_count": evaluation.get("sample_count", len(manifest.get("samples", []))),
                    "evaluation": evaluation,
                    "approval": approval,
                }
            )
        return sorted(rows, key=lambda row: (row["created_at"] or "", row["run_id"]), reverse=True)

    def get_run(self, customer: str, run_id: str) -> dict[str, Any]:
        run_dir = self._run_dir(customer, run_id)

        manifest = read_json(run_dir / "manifest.json")
        evaluation = read_json(run_dir / "evaluation" / "summary.json", default={})
        approval = dump_model(load_approval(run_dir))
        return {
            "manifest": manifest,
            "evaluation": evaluation,
            "approval": approval,
            "samples": self._sample_artifacts(run_dir, manifest),
        }

    def _customer_dir(self, customer: str) -> Path:
        return customer_dir(self.lab_root, customer)

    def _run_dir(self, customer: str, run_id: str) -> Path:
        return run_dir(self.lab_root, customer, run_id)

    def _run_dirs(self, customer: str) -> list[Path]:
        runs_dir = self._customer_dir(customer) / "runs"
        if not runs_dir.exists():
            return []
        return sorted(path for path in runs_dir.iterdir() if path.is_dir())

    def _sample_artifacts(self, run_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
        samples = []
        for sample in manifest.get("samples", []):
            sample_key = Path(sample).stem
            samples.append(
                {
                    "sample_key": sample_key,
                    "source_file": sample,
                    "text_candidate": read_json(run_dir / "candidates" / "text" / f"{sample_key}.json", default={}),
                    "vision_candidate": read_json(run_dir / "candidates" / "vision" / f"{sample_key}.json", default={}),
                    "merged_draft": read_json(run_dir / "adjudication" / f"{sample_key}.merged_draft.json", default={}),
                    "report": read_json(run_dir / "evaluation" / f"{sample_key}.report.json", default={}),
                }
            )
        return samples
