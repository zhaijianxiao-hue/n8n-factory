from pathlib import Path

from .json_io import read_json, write_json
from .models import current_timestamp


class PublishGateError(RuntimeError):
    pass


def publish_profile(root: Path, customer_key: str, run_id: str, production_dir: Path) -> Path:
    customer_dir = root / "customers" / customer_key
    summary_path = customer_dir / "runs" / run_id / "evaluation" / "summary.json"
    summary = read_json(summary_path)
    if not summary.get("publishable"):
        raise PublishGateError(f"profile is not publishable for customer={customer_key} run={run_id}")

    profile = read_json(customer_dir / "profile.json")
    profile["status"] = "production"
    profile["last_run_id"] = run_id
    profile["last_score"] = summary
    profile["published_at"] = current_timestamp()

    production_dir.mkdir(parents=True, exist_ok=True)
    output_path = production_dir / f"{customer_key}.json"
    write_json(output_path, profile)
    write_json(customer_dir / "profile.json", profile)
    return output_path
