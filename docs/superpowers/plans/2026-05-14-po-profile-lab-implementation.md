# PO Profile Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local-first PO Profile Lab core for initializing customer parsing assets, generating draft outputs through text and vision paths, adjudicating candidate JSON, evaluating approved expected JSON, and publishing only profiles that pass gates.

**Architecture:** Add a focused Python package under `workflows/po-parser/profile_lab/` without restructuring the production `po_parser_service.py`. The package owns customer assets, run manifests, PDF rendering, candidate output files, adjudication artifacts, scoring, and publish checks. Production integration remains file-based through published profiles under `workflows/po-parser/profiles/`.

**Tech Stack:** Python 3.10+, `argparse`, `pathlib`, `json`, `pydantic`, `jsonschema`, `PyMuPDF` (`fitz`), optional OpenAI-compatible client for text and vision model calls, `pytest`.

---

## File Structure

Create and modify these files:

- Create: `workflows/po-parser/profile_lab/__init__.py`
- Create: `workflows/po-parser/profile_lab/__main__.py`
- Create: `workflows/po-parser/profile_lab/paths.py`
- Create: `workflows/po-parser/profile_lab/models.py`
- Create: `workflows/po-parser/profile_lab/json_io.py`
- Create: `workflows/po-parser/profile_lab/customer_assets.py`
- Create: `workflows/po-parser/profile_lab/pdf_pages.py`
- Create: `workflows/po-parser/profile_lab/text_candidate.py`
- Create: `workflows/po-parser/profile_lab/vision_candidate.py`
- Create: `workflows/po-parser/profile_lab/adjudicator.py`
- Create: `workflows/po-parser/profile_lab/evaluator.py`
- Create: `workflows/po-parser/profile_lab/publisher.py`
- Create: `workflows/po-parser/profile_lab/commands.py`
- Create: `workflows/po-parser/profile_lab/templates/prompt.md`
- Create: `workflows/po-parser/profile_lab/templates/field_priority.json`
- Create: `workflows/po-parser/tests/test_profile_lab_assets.py`
- Create: `workflows/po-parser/tests/test_profile_lab_evaluator.py`
- Create: `workflows/po-parser/tests/test_profile_lab_publisher.py`
- Modify: `workflows/po-parser/tests/requirements.txt` only if `jsonschema` or `pydantic` are missing from the local test dependency list.
- Modify: `KNOWLEDGE.md` after implementation to mention the new local profile lab command surface.

Do not modify:

- `workflows/po-parser/service/po_parser_service.py`
- `workflows/po-parser/workflow.json`
- production profile files except through `profile_lab.publisher` tests and explicit publish command behavior.

---

## Task 1: Package Skeleton And CLI Dispatch

**Files:**
- Create: `workflows/po-parser/profile_lab/__init__.py`
- Create: `workflows/po-parser/profile_lab/__main__.py`
- Create: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_assets.py`

- [ ] **Step 1: Write the failing CLI import test**

Add this test file:

```python
import importlib


def test_profile_lab_package_imports():
    module = importlib.import_module("profile_lab")
    assert module.__all__ == ["__version__"]


def test_commands_module_exposes_main():
    commands = importlib.import_module("profile_lab.commands")
    assert callable(commands.main)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py::test_profile_lab_package_imports tests/test_profile_lab_assets.py::test_commands_module_exposes_main -v
```

Expected: FAIL because `profile_lab` does not exist.

- [ ] **Step 3: Create the package skeleton**

Create `workflows/po-parser/profile_lab/__init__.py`:

```python
__version__ = "0.1.0"

__all__ = ["__version__"]
```

Create `workflows/po-parser/profile_lab/__main__.py`:

```python
from .commands import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `workflows/po-parser/profile_lab/commands.py`:

```python
import argparse
from typing import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_customer = subparsers.add_parser("init-customer")
    init_customer.add_argument("--customer", required=True)
    init_customer.add_argument("--display-name", default=None)

    draft = subparsers.add_parser("draft")
    draft.add_argument("--customer", required=True)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    parser.error(f"unsupported command reached: {args.command}")
    return 2
```

- [ ] **Step 4: Run the import tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py::test_profile_lab_package_imports tests/test_profile_lab_assets.py::test_commands_module_exposes_main -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/po-parser/profile_lab/__init__.py workflows/po-parser/profile_lab/__main__.py workflows/po-parser/profile_lab/commands.py workflows/po-parser/tests/test_profile_lab_assets.py
git commit -m "feat: add profile lab cli skeleton"
```

---

## Task 2: Customer Asset Initialization

**Files:**
- Create: `workflows/po-parser/profile_lab/paths.py`
- Create: `workflows/po-parser/profile_lab/json_io.py`
- Create: `workflows/po-parser/profile_lab/models.py`
- Create: `workflows/po-parser/profile_lab/customer_assets.py`
- Create: `workflows/po-parser/profile_lab/templates/prompt.md`
- Create: `workflows/po-parser/profile_lab/templates/field_priority.json`
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_assets.py`

- [ ] **Step 1: Add failing asset initialization tests**

Append to `workflows/po-parser/tests/test_profile_lab_assets.py`:

```python
import json
from pathlib import Path

from profile_lab.customer_assets import init_customer


def test_init_customer_creates_expected_asset_tree(tmp_path):
    root = tmp_path / "profile-lab"

    result = init_customer(
        root=root,
        customer_key="acme",
        display_name="ACME Corp",
    )

    assert result.customer_dir == root / "customers" / "acme"
    assert (result.customer_dir / "samples").is_dir()
    assert (result.customer_dir / "expected").is_dir()
    assert (result.customer_dir / "runs").is_dir()
    assert (result.customer_dir / "customer.json").is_file()
    assert (result.customer_dir / "profile.json").is_file()
    assert (result.customer_dir / "prompt.md").is_file()
    assert (result.customer_dir / "field_priority.json").is_file()

    customer = json.loads((result.customer_dir / "customer.json").read_text(encoding="utf-8"))
    assert customer["customer_key"] == "acme"
    assert customer["display_name"] == "ACME Corp"

    profile = json.loads((result.customer_dir / "profile.json").read_text(encoding="utf-8"))
    assert profile["profile_name"] == "acme"
    assert profile["status"] == "draft"
    assert profile["version"] == "0.1.0"


def test_init_customer_is_idempotent_for_existing_assets(tmp_path):
    root = tmp_path / "profile-lab"
    first = init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    prompt_path = first.customer_dir / "prompt.md"
    prompt_path.write_text("custom prompt\n", encoding="utf-8")

    second = init_customer(root=root, customer_key="acme", display_name="Changed Name")

    assert second.customer_dir == first.customer_dir
    assert prompt_path.read_text(encoding="utf-8") == "custom prompt\n"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py -v
```

Expected: FAIL because `profile_lab.customer_assets` does not exist.

- [ ] **Step 3: Add path helpers and JSON I/O**

Create `workflows/po-parser/profile_lab/paths.py`:

```python
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PO_PARSER_DIR = PACKAGE_DIR.parent
DEFAULT_LAB_ROOT = PO_PARSER_DIR / "profile-lab"
SCHEMA_PATH = PO_PARSER_DIR / "schemas" / "po-output.schema.json"
PRODUCTION_PROFILE_DIR = PO_PARSER_DIR / "profiles"
```

Create `workflows/po-parser/profile_lab/json_io.py`:

```python
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
```

- [ ] **Step 4: Add models**

Create `workflows/po-parser/profile_lab/models.py`:

```python
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CustomerInitResult(BaseModel):
    customer_dir: Path


class CustomerConfig(BaseModel):
    customer_key: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    default_currency: str | None = None
    language: list[str] = Field(default_factory=list)


class ProfileConfig(BaseModel):
    profile_name: str
    version: str = "0.1.0"
    status: str = "draft"
    markers: list[str] = Field(default_factory=list)
    number_format: dict[str, str] = Field(
        default_factory=lambda: {
            "decimal_separator": ".",
            "thousands_separator": ",",
        }
    )
    item_rules: dict[str, Any] = Field(default_factory=dict)
    last_run_id: str | None = None
    last_score: dict[str, Any] | None = None
    published_at: str | None = None
```

- [ ] **Step 5: Add customer asset initializer and templates**

Create `workflows/po-parser/profile_lab/customer_assets.py`:

```python
from pathlib import Path

from .json_io import write_json
from .models import CustomerConfig, CustomerInitResult, ProfileConfig


DEFAULT_FIELD_PRIORITY = {
    "p0": [
        "header.customer_name",
        "header.po_number",
        "header.po_date",
        "items.customer_material",
        "items.qty",
        "items.delivery_date",
    ],
    "p1": [
        "header.currency",
        "header.total_amount",
        "items.unit_price",
        "items.amount",
        "items.unit",
        "items.customer_release_no",
        "items.sap_material",
    ],
    "p2": [
        "header.customer_contact_person",
        "header.customer_contact_phone",
        "header.customer_contact_email",
        "header.buyer_address",
        "header.supplier_address",
        "header.payment_terms",
        "header.delivery_terms",
        "header.shipment_mode",
        "header.production_note",
        "header.packaging_note",
        "items.description_raw",
        "items.article_raw",
    ],
}


DEFAULT_PROMPT = """You are extracting purchase order data for a fixed JSON schema.

Use the customer profile hints when available.
Return only JSON that matches the target purchase order schema.
When uncertain, preserve the visible value and explain the uncertainty in warnings.
"""


def write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json_if_missing(path: Path, data: object) -> None:
    if path.exists():
        return
    write_json(path, data)


def init_customer(
    root: Path,
    customer_key: str,
    display_name: str | None = None,
) -> CustomerInitResult:
    customer_dir = root / "customers" / customer_key
    for child in ("samples", "expected", "runs"):
        (customer_dir / child).mkdir(parents=True, exist_ok=True)

    customer = CustomerConfig(
        customer_key=customer_key,
        display_name=display_name or customer_key,
        aliases=[display_name] if display_name else [],
    )
    profile = ProfileConfig(profile_name=customer_key)

    write_json_if_missing(customer_dir / "customer.json", customer.model_dump())
    write_json_if_missing(customer_dir / "profile.json", profile.model_dump())
    write_json_if_missing(customer_dir / "field_priority.json", DEFAULT_FIELD_PRIORITY)
    write_if_missing(customer_dir / "prompt.md", DEFAULT_PROMPT)

    return CustomerInitResult(customer_dir=customer_dir)
```

Create `workflows/po-parser/profile_lab/templates/prompt.md`:

```markdown
You are extracting purchase order data for a fixed JSON schema.

Use the customer profile hints when available.
Return only JSON that matches the target purchase order schema.
When uncertain, preserve the visible value and explain the uncertainty in warnings.
```

Create `workflows/po-parser/profile_lab/templates/field_priority.json`:

```json
{
  "p0": [
    "header.customer_name",
    "header.po_number",
    "header.po_date",
    "items.customer_material",
    "items.qty",
    "items.delivery_date"
  ],
  "p1": [
    "header.currency",
    "header.total_amount",
    "items.unit_price",
    "items.amount",
    "items.unit",
    "items.customer_release_no",
    "items.sap_material"
  ],
  "p2": [
    "header.customer_contact_person",
    "header.customer_contact_phone",
    "header.customer_contact_email",
    "header.buyer_address",
    "header.supplier_address",
    "header.payment_terms",
    "header.delivery_terms",
    "header.shipment_mode",
    "header.production_note",
    "header.packaging_note",
    "items.description_raw",
    "items.article_raw"
  ]
}
```

- [ ] **Step 6: Wire init-customer into the CLI**

Modify `workflows/po-parser/profile_lab/commands.py` so it calls `init_customer`:

```python
import argparse
from pathlib import Path
from typing import Sequence

from .customer_assets import init_customer
from .paths import DEFAULT_LAB_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-lab")
    parser.add_argument("--lab-root", default=str(DEFAULT_LAB_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_customer_parser = subparsers.add_parser("init-customer")
    init_customer_parser.add_argument("--customer", required=True)
    init_customer_parser.add_argument("--display-name", default=None)

    draft = subparsers.add_parser("draft")
    draft.add_argument("--customer", required=True)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    lab_root = Path(args.lab_root)

    if args.command == "init-customer":
        result = init_customer(
            root=lab_root,
            customer_key=args.customer,
            display_name=args.display_name,
        )
        print(f"initialized customer assets: {result.customer_dir}")
        return 0

    parser.error(f"unsupported command reached: {args.command}")
    return 2
```

- [ ] **Step 7: Run the tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add workflows/po-parser/profile_lab workflows/po-parser/tests/test_profile_lab_assets.py
git commit -m "feat: initialize profile lab customer assets"
```

---

## Task 3: Run Creation And PDF Page Rendering

**Files:**
- Create: `workflows/po-parser/profile_lab/pdf_pages.py`
- Modify: `workflows/po-parser/profile_lab/models.py`
- Modify: `workflows/po-parser/profile_lab/customer_assets.py`
- Test: `workflows/po-parser/tests/test_profile_lab_assets.py`

- [ ] **Step 1: Add failing tests for run directories and page rendering guardrails**

Append to `workflows/po-parser/tests/test_profile_lab_assets.py`:

```python
from profile_lab.customer_assets import create_run
from profile_lab.pdf_pages import sample_key_from_pdf


def test_create_run_copies_samples_and_writes_manifest(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")

    run = create_run(root=root, customer_key="acme", run_id="2026-05-14-153000")

    assert run.run_dir == root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    assert (run.run_dir / "inputs" / "po-001.pdf").is_file()
    manifest = json.loads((run.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["customer"] == "acme"
    assert manifest["samples"] == ["po-001.pdf"]


def test_sample_key_from_pdf_removes_extension():
    assert sample_key_from_pdf(Path("PO-001.pdf")) == "PO-001"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py::test_create_run_copies_samples_and_writes_manifest tests/test_profile_lab_assets.py::test_sample_key_from_pdf_removes_extension -v
```

Expected: FAIL because `create_run` and `sample_key_from_pdf` do not exist.

- [ ] **Step 3: Add run models**

Append to `workflows/po-parser/profile_lab/models.py`:

```python
from datetime import datetime


class RunManifest(BaseModel):
    run_id: str
    customer: str
    profile_version: str
    prompt_version: str = "0.1.0"
    model_text: str | None = None
    model_vision: str | None = None
    samples: list[str]
    created_at: str


class RunCreateResult(BaseModel):
    run_dir: Path
    manifest: RunManifest


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
```

- [ ] **Step 4: Add PDF page helpers**

Create `workflows/po-parser/profile_lab/pdf_pages.py`:

```python
from pathlib import Path

import fitz


def sample_key_from_pdf(pdf_path: Path) -> str:
    return pdf_path.stem


def render_pdf_pages(pdf_path: Path, output_dir: Path, zoom: float = 2.0) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    matrix = fitz.Matrix(zoom, zoom)

    document = fitz.open(pdf_path)
    try:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = output_dir / f"page-{index:03d}.png"
            pixmap.save(image_path)
            rendered.append(image_path)
    finally:
        document.close()

    return rendered
```

- [ ] **Step 5: Add run creation**

Append to `workflows/po-parser/profile_lab/customer_assets.py`:

```python
import shutil

from .json_io import read_json
from .models import RunCreateResult, RunManifest, current_timestamp


def list_sample_pdfs(customer_dir: Path) -> list[Path]:
    samples_dir = customer_dir / "samples"
    return sorted(path for path in samples_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")


def create_run(root: Path, customer_key: str, run_id: str) -> RunCreateResult:
    customer_dir = root / "customers" / customer_key
    profile = read_json(customer_dir / "profile.json")
    samples = list_sample_pdfs(customer_dir)
    run_dir = customer_dir / "runs" / run_id
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    for sample in samples:
        shutil.copy2(sample, inputs_dir / sample.name)

    manifest = RunManifest(
        run_id=run_id,
        customer=customer_key,
        profile_version=profile.get("version", "0.1.0"),
        samples=[sample.name for sample in samples],
        created_at=current_timestamp(),
    )
    write_json(run_dir / "manifest.json", manifest.model_dump())
    return RunCreateResult(run_dir=run_dir, manifest=manifest)
```

- [ ] **Step 6: Run the asset tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add workflows/po-parser/profile_lab workflows/po-parser/tests/test_profile_lab_assets.py
git commit -m "feat: create profile lab runs"
```

---

## Task 4: Candidate Draft Command With Deterministic Local Outputs

**Files:**
- Create: `workflows/po-parser/profile_lab/text_candidate.py`
- Create: `workflows/po-parser/profile_lab/vision_candidate.py`
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_assets.py`

This task creates deterministic local candidate files first. Real model calls are added behind the same interfaces in a later task so evaluator work can proceed without network or model credentials.

- [ ] **Step 1: Add failing test for draft artifact layout**

Append to `workflows/po-parser/tests/test_profile_lab_assets.py`:

```python
from profile_lab.commands import main


def test_draft_command_creates_candidate_files(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")

    exit_code = main([
        "--lab-root",
        str(root),
        "draft",
        "--customer",
        "acme",
        "--run-id",
        "2026-05-14-153000",
        "--skip-render",
    ])

    assert exit_code == 0
    run_dir = root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    assert (run_dir / "candidates" / "text" / "po-001.json").is_file()
    assert (run_dir / "candidates" / "vision" / "po-001.json").is_file()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py::test_draft_command_creates_candidate_files -v
```

Expected: FAIL because `draft` has no implementation.

- [ ] **Step 3: Add candidate modules**

Create `workflows/po-parser/profile_lab/text_candidate.py`:

```python
from pathlib import Path


def build_empty_candidate(source_file: str, source: str) -> dict:
    return {
        "source_file": source_file,
        "customer_profile": None,
        "header": {
            "customer_name": None,
            "po_number": None,
            "po_date": None,
            "currency": None,
            "total_amount": None,
        },
        "items": [],
        "confidence": 0.0,
        "warnings": [f"{source} candidate is empty because model extraction is not configured"],
        "status": "review",
        "metadata": {
            "candidate_source": source,
        },
    }


def generate_text_candidate(pdf_path: Path) -> dict:
    return build_empty_candidate(source_file=pdf_path.name, source="text")
```

Create `workflows/po-parser/profile_lab/vision_candidate.py`:

```python
from pathlib import Path

from .text_candidate import build_empty_candidate


def generate_vision_candidate(pdf_path: Path, page_paths: list[Path]) -> dict:
    candidate = build_empty_candidate(source_file=pdf_path.name, source="vision")
    candidate["metadata"]["page_count"] = len(page_paths)
    return candidate
```

- [ ] **Step 4: Wire draft command**

Modify `workflows/po-parser/profile_lab/commands.py`:

```python
import argparse
from pathlib import Path
from typing import Sequence

from .customer_assets import create_run, init_customer
from .json_io import write_json
from .paths import DEFAULT_LAB_ROOT
from .pdf_pages import render_pdf_pages, sample_key_from_pdf
from .text_candidate import generate_text_candidate
from .vision_candidate import generate_vision_candidate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profile-lab")
    parser.add_argument("--lab-root", default=str(DEFAULT_LAB_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_customer_parser = subparsers.add_parser("init-customer")
    init_customer_parser.add_argument("--customer", required=True)
    init_customer_parser.add_argument("--display-name", default=None)

    draft = subparsers.add_parser("draft")
    draft.add_argument("--customer", required=True)
    draft.add_argument("--run-id", required=True)
    draft.add_argument("--skip-render", action="store_true")

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)

    return parser


def run_draft(lab_root: Path, customer_key: str, run_id: str, skip_render: bool) -> Path:
    run = create_run(root=lab_root, customer_key=customer_key, run_id=run_id)
    for pdf_path in sorted((run.run_dir / "inputs").glob("*.pdf")):
        sample_key = sample_key_from_pdf(pdf_path)
        pages_dir = run.run_dir / "pages" / sample_key
        page_paths = [] if skip_render else render_pdf_pages(pdf_path, pages_dir)
        write_json(
            run.run_dir / "candidates" / "text" / f"{sample_key}.json",
            generate_text_candidate(pdf_path),
        )
        write_json(
            run.run_dir / "candidates" / "vision" / f"{sample_key}.json",
            generate_vision_candidate(pdf_path, page_paths),
        )
    return run.run_dir


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    lab_root = Path(args.lab_root)

    if args.command == "init-customer":
        result = init_customer(
            root=lab_root,
            customer_key=args.customer,
            display_name=args.display_name,
        )
        print(f"initialized customer assets: {result.customer_dir}")
        return 0

    if args.command == "draft":
        run_dir = run_draft(
            lab_root=lab_root,
            customer_key=args.customer,
            run_id=args.run_id,
            skip_render=args.skip_render,
        )
        print(f"created draft run: {run_dir}")
        return 0

    parser.error(f"unsupported command reached: {args.command}")
    return 2
```

- [ ] **Step 5: Run the asset tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab workflows/po-parser/tests/test_profile_lab_assets.py
git commit -m "feat: generate profile lab candidate drafts"
```

---

## Task 5: Adjudicator Artifacts

**Files:**
- Create: `workflows/po-parser/profile_lab/adjudicator.py`
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_assets.py`

- [ ] **Step 1: Add failing adjudication artifact test**

Append to `workflows/po-parser/tests/test_profile_lab_assets.py`:

```python
def test_draft_command_creates_adjudication_artifacts(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    sample = root / "customers" / "acme" / "samples" / "po-001.pdf"
    sample.write_bytes(b"%PDF-1.4\n")

    exit_code = main([
        "--lab-root",
        str(root),
        "draft",
        "--customer",
        "acme",
        "--run-id",
        "2026-05-14-153000",
        "--skip-render",
    ])

    assert exit_code == 0
    run_dir = root / "customers" / "acme" / "runs" / "2026-05-14-153000"
    assert (run_dir / "adjudication" / "po-001.merged_draft.json").is_file()
    assert (run_dir / "adjudication" / "po-001.conflict_report.md").is_file()
    assert (run_dir / "adjudication" / "po-001.field_evidence.json").is_file()
    assert (run_dir / "adjudication" / "po-001.profile_suggestions.md").is_file()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py::test_draft_command_creates_adjudication_artifacts -v
```

Expected: FAIL because adjudication artifacts are not created.

- [ ] **Step 3: Add deterministic adjudicator**

Create `workflows/po-parser/profile_lab/adjudicator.py`:

```python
from pathlib import Path


def choose_candidate(text_candidate: dict, vision_candidate: dict) -> tuple[dict, str]:
    text_items = text_candidate.get("items") or []
    vision_items = vision_candidate.get("items") or []
    if vision_items and not text_items:
        return vision_candidate, "vision"
    if text_items and not vision_items:
        return text_candidate, "text"
    if vision_candidate.get("confidence", 0) >= text_candidate.get("confidence", 0):
        return vision_candidate, "vision"
    return text_candidate, "text"


def build_conflict_report(sample_key: str, chosen_source: str, text_candidate: dict, vision_candidate: dict) -> str:
    return "\n".join(
        [
            f"# Conflict Report: {sample_key}",
            "",
            "## Summary",
            f"- chosen_source: {chosen_source}",
            f"- text_items: {len(text_candidate.get('items') or [])}",
            f"- vision_items: {len(vision_candidate.get('items') or [])}",
            "- human_review_required: true",
            "",
            "The merged draft is a model-assisted starting point. A human must approve expected JSON before evaluation.",
            "",
        ]
    )


def build_field_evidence(chosen: dict, chosen_source: str) -> dict:
    evidence = {}
    header = chosen.get("header") or {}
    for key, value in header.items():
        evidence[f"header.{key}"] = {
            "chosen_value": value,
            "chosen_source": chosen_source,
            "confidence": chosen.get("confidence", 0),
            "human_review_required": True,
        }
    return evidence


def build_profile_suggestions() -> str:
    return "\n".join(
        [
            "# Profile Suggestions",
            "",
            "- Review number format for the customer.",
            "- Review item table row boundaries.",
            "- Review date format and delivery date column location.",
            "",
        ]
    )


def adjudicate_sample(sample_key: str, text_candidate: dict, vision_candidate: dict, output_dir: Path) -> None:
    chosen, chosen_source = choose_candidate(text_candidate, vision_candidate)
    output_dir.mkdir(parents=True, exist_ok=True)
    from .json_io import write_json

    write_json(output_dir / f"{sample_key}.merged_draft.json", chosen)
    write_json(output_dir / f"{sample_key}.field_evidence.json", build_field_evidence(chosen, chosen_source))
    (output_dir / f"{sample_key}.conflict_report.md").write_text(
        build_conflict_report(sample_key, chosen_source, text_candidate, vision_candidate),
        encoding="utf-8",
    )
    (output_dir / f"{sample_key}.profile_suggestions.md").write_text(
        build_profile_suggestions(),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Wire adjudication into draft**

In `workflows/po-parser/profile_lab/commands.py`, import and call `adjudicate_sample`:

```python
from .adjudicator import adjudicate_sample
from .json_io import read_json, write_json
```

Then update the end of `run_draft` loop:

```python
        text_path = run.run_dir / "candidates" / "text" / f"{sample_key}.json"
        vision_path = run.run_dir / "candidates" / "vision" / f"{sample_key}.json"
        write_json(text_path, generate_text_candidate(pdf_path))
        write_json(vision_path, generate_vision_candidate(pdf_path, page_paths))
        adjudicate_sample(
            sample_key=sample_key,
            text_candidate=read_json(text_path),
            vision_candidate=read_json(vision_path),
            output_dir=run.run_dir / "adjudication",
        )
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workflows/po-parser/profile_lab workflows/po-parser/tests/test_profile_lab_assets.py
git commit -m "feat: add profile lab adjudication artifacts"
```

---

## Task 6: OpenAI-Compatible Candidate Providers

**Files:**
- Create: `workflows/po-parser/profile_lab/llm_client.py`
- Modify: `workflows/po-parser/profile_lab/text_candidate.py`
- Modify: `workflows/po-parser/profile_lab/vision_candidate.py`
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_assets.py`

This task makes the two candidate paths real while preserving offline testability. Tests use a fake client. Runtime model calls use an OpenAI-compatible chat completions API.

- [ ] **Step 1: Add failing JSON extraction and fake-client tests**

Append to `workflows/po-parser/tests/test_profile_lab_assets.py`:

```python
from profile_lab.llm_client import extract_json_object
from profile_lab.text_candidate import generate_text_candidate_with_model
from profile_lab.vision_candidate import generate_vision_candidate_with_model


class FakeJsonClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def create_json(self, messages, model):
        self.calls.append({"messages": messages, "model": model})
        return self.payload


def test_extract_json_object_strips_markdown_fence():
    content = "```json\n{\"header\": {\"po_number\": \"PO-1\"}, \"items\": []}\n```"
    assert extract_json_object(content)["header"]["po_number"] == "PO-1"


def test_text_candidate_uses_model_client(tmp_path):
    pdf_path = tmp_path / "po-001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    client = FakeJsonClient(
        {
            "header": {"customer_name": "ACME", "po_number": "PO-1"},
            "items": [],
            "confidence": 0.8,
            "warnings": [],
        }
    )

    result = generate_text_candidate_with_model(
        pdf_path=pdf_path,
        extracted_text="Purchase Order PO-1",
        prompt="Return JSON",
        model="text-model",
        client=client,
    )

    assert result["source_file"] == "po-001.pdf"
    assert result["metadata"]["candidate_source"] == "text"
    assert result["header"]["po_number"] == "PO-1"
    assert client.calls[0]["model"] == "text-model"


def test_vision_candidate_uses_model_client(tmp_path):
    pdf_path = tmp_path / "po-001.pdf"
    page_path = tmp_path / "page-001.png"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    page_path.write_bytes(b"png")
    client = FakeJsonClient(
        {
            "header": {"customer_name": "ACME", "po_number": "PO-1"},
            "items": [],
            "confidence": 0.9,
            "warnings": [],
        }
    )

    result = generate_vision_candidate_with_model(
        pdf_path=pdf_path,
        page_paths=[page_path],
        prompt="Return JSON",
        model="vision-model",
        client=client,
    )

    assert result["source_file"] == "po-001.pdf"
    assert result["metadata"]["candidate_source"] == "vision"
    assert result["metadata"]["page_count"] == 1
    assert result["header"]["po_number"] == "PO-1"
    assert client.calls[0]["model"] == "vision-model"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py::test_extract_json_object_strips_markdown_fence tests/test_profile_lab_assets.py::test_text_candidate_uses_model_client tests/test_profile_lab_assets.py::test_vision_candidate_uses_model_client -v
```

Expected: FAIL because `llm_client` and model-backed candidate functions do not exist.

- [ ] **Step 3: Add OpenAI-compatible client wrapper**

Create `workflows/po-parser/profile_lab/llm_client.py`:

```python
import json
import os
import re
from typing import Protocol


class JsonClient(Protocol):
    def create_json(self, messages: list[dict], model: str) -> dict:
        raise NotImplementedError


def extract_json_object(content: str) -> dict:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


class OpenAICompatibleJsonClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(
            base_url=base_url or os.getenv("PO_PROFILE_LAB_OPENAI_BASE_URL"),
            api_key=api_key or os.getenv("PO_PROFILE_LAB_OPENAI_API_KEY"),
        )

    def create_json(self, messages: list[dict], model: str) -> dict:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json_object(content)
```

- [ ] **Step 4: Add text model candidate function**

Append to `workflows/po-parser/profile_lab/text_candidate.py`:

```python
from .llm_client import JsonClient


def generate_text_candidate_with_model(
    pdf_path: Path,
    extracted_text: str,
    prompt: str,
    model: str,
    client: JsonClient,
) -> dict:
    messages = [
        {
            "role": "system",
            "content": "You extract purchase order data. Return JSON only.",
        },
        {
            "role": "user",
            "content": f"{prompt}\n\nPDF text:\n{extracted_text}",
        },
    ]
    result = client.create_json(messages=messages, model=model)
    result["source_file"] = pdf_path.name
    result.setdefault("warnings", [])
    result.setdefault("items", [])
    result.setdefault("confidence", 0.0)
    result["metadata"] = {
        **(result.get("metadata") or {}),
        "candidate_source": "text",
        "model": model,
    }
    return result
```

- [ ] **Step 5: Add vision model candidate function**

Append to `workflows/po-parser/profile_lab/vision_candidate.py`:

```python
import base64

from .llm_client import JsonClient


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def generate_vision_candidate_with_model(
    pdf_path: Path,
    page_paths: list[Path],
    prompt: str,
    model: str,
    client: JsonClient,
) -> dict:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for page_path in page_paths:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{encode_image(page_path)}",
                },
            }
        )
    messages = [
        {
            "role": "system",
            "content": "You visually inspect purchase order PDF pages and return JSON only.",
        },
        {
            "role": "user",
            "content": content,
        },
    ]
    result = client.create_json(messages=messages, model=model)
    result["source_file"] = pdf_path.name
    result.setdefault("warnings", [])
    result.setdefault("items", [])
    result.setdefault("confidence", 0.0)
    result["metadata"] = {
        **(result.get("metadata") or {}),
        "candidate_source": "vision",
        "model": model,
        "page_count": len(page_paths),
    }
    return result
```

- [ ] **Step 6: Add model flags to draft command**

Update the `draft` parser in `commands.py`:

```python
    draft.add_argument("--text-model", default=None)
    draft.add_argument("--vision-model", default=None)
```

Add imports:

```python
from .llm_client import OpenAICompatibleJsonClient
from .text_candidate import generate_text_candidate, generate_text_candidate_with_model
from .vision_candidate import generate_vision_candidate, generate_vision_candidate_with_model
```

Update the `run_draft` signature:

```python
def run_draft(
    lab_root: Path,
    customer_key: str,
    run_id: str,
    skip_render: bool,
    text_model: str | None = None,
    vision_model: str | None = None,
) -> Path:
```

Inside `run_draft`, before the loop, read the prompt and create a client only when needed:

```python
    customer_dir = lab_root / "customers" / customer_key
    prompt = (customer_dir / "prompt.md").read_text(encoding="utf-8")
    model_client = OpenAICompatibleJsonClient() if text_model or vision_model else None
```

Replace candidate generation inside the loop:

```python
        if text_model and model_client:
            extracted_text = pdf_path.read_bytes().decode("latin-1", errors="ignore")
            text_candidate = generate_text_candidate_with_model(
                pdf_path=pdf_path,
                extracted_text=extracted_text,
                prompt=prompt,
                model=text_model,
                client=model_client,
            )
        else:
            text_candidate = generate_text_candidate(pdf_path)

        if vision_model and model_client:
            vision_candidate = generate_vision_candidate_with_model(
                pdf_path=pdf_path,
                page_paths=page_paths,
                prompt=prompt,
                model=vision_model,
                client=model_client,
            )
        else:
            vision_candidate = generate_vision_candidate(pdf_path, page_paths)

        write_json(text_path, text_candidate)
        write_json(vision_path, vision_candidate)
```

Update the `main` draft call:

```python
        run_dir = run_draft(
            lab_root=lab_root,
            customer_key=args.customer,
            run_id=args.run_id,
            skip_render=args.skip_render,
            text_model=args.text_model,
            vision_model=args.vision_model,
        )
```

- [ ] **Step 7: Run candidate provider tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add workflows/po-parser/profile_lab workflows/po-parser/tests/test_profile_lab_assets.py
git commit -m "feat: add model-backed profile lab candidates"
```

---

## Task 7: Evaluator Scoring Core

**Files:**
- Create: `workflows/po-parser/profile_lab/evaluator.py`
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_evaluator.py`

- [ ] **Step 1: Write evaluator tests**

Create `workflows/po-parser/tests/test_profile_lab_evaluator.py`:

```python
from profile_lab.evaluator import evaluate_po_result, normalize_value


def test_normalize_value_collapses_string_whitespace():
    assert normalize_value("  PO   123  ") == "PO 123"


def test_evaluate_po_result_passes_matching_p0_fields():
    expected = {
        "header": {
            "customer_name": "ACME Corp",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "currency": "EUR",
            "total_amount": 100.0,
        },
        "items": [
            {
                "line_no": 10,
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 50,
                "amount": 100,
            }
        ],
    }
    actual = {
        "header": {
            "customer_name": " ACME   Corp ",
            "po_number": "PO-1",
            "po_date": "2026-05-14",
            "currency": "EUR",
            "total_amount": 100.0,
        },
        "items": [
            {
                "line_no": 10,
                "customer_material": "MAT-1",
                "qty": 2,
                "delivery_date": "2026-06-01",
                "unit_price": 50,
                "amount": 100,
            }
        ],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is True
    assert report["publishable"] is True
    assert report["blocking_errors"] == []


def test_evaluate_po_result_blocks_qty_mismatch():
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    actual = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 3, "delivery_date": "2026-06-01"}],
    }

    report = evaluate_po_result(expected=expected, actual=actual)

    assert report["p0_pass"] is False
    assert report["publishable"] is False
    assert report["blocking_errors"][0]["field"] == "items[0].qty"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_evaluator.py -v
```

Expected: FAIL because `profile_lab.evaluator` does not exist.

- [ ] **Step 3: Implement evaluator core**

Create `workflows/po-parser/profile_lab/evaluator.py`:

```python
import math
import re
from typing import Any


P0_HEADER_FIELDS = ["customer_name", "po_number", "po_date"]
P0_ITEM_FIELDS = ["customer_material", "qty", "delivery_date"]


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def numbers_equal(expected: Any, actual: Any, tolerance: float = 0.0) -> bool:
    try:
        expected_number = float(expected)
        actual_number = float(actual)
    except (TypeError, ValueError):
        return False
    return math.isclose(expected_number, actual_number, abs_tol=tolerance)


def values_equal(field: str, expected: Any, actual: Any) -> bool:
    if field in {"qty"}:
        return numbers_equal(expected, actual, tolerance=0.0)
    if field in {"unit_price"}:
        return numbers_equal(expected, actual, tolerance=0.01)
    if field in {"amount"}:
        return numbers_equal(expected, actual, tolerance=0.05)
    if field in {"total_amount"}:
        try:
            tolerance = max(0.10, abs(float(expected)) * 0.0001)
        except (TypeError, ValueError):
            tolerance = 0.10
        return numbers_equal(expected, actual, tolerance=tolerance)
    return normalize_value(expected) == normalize_value(actual)


def add_blocking_error(errors: list[dict], field: str, expected: Any, actual: Any, reason: str) -> None:
    errors.append(
        {
            "field": field,
            "expected": expected,
            "actual": actual,
            "reason": reason,
        }
    )


def evaluate_po_result(expected: dict, actual: dict) -> dict:
    blocking_errors: list[dict] = []
    expected_header = expected.get("header") or {}
    actual_header = actual.get("header") or {}

    for field in P0_HEADER_FIELDS:
        if not values_equal(field, expected_header.get(field), actual_header.get(field)):
            add_blocking_error(
                blocking_errors,
                f"header.{field}",
                expected_header.get(field),
                actual_header.get(field),
                "P0 field mismatch",
            )

    expected_items = expected.get("items") or []
    actual_items = actual.get("items") or []
    item_row_count_match = len(expected_items) == len(actual_items)
    if not item_row_count_match:
        add_blocking_error(
            blocking_errors,
            "items",
            len(expected_items),
            len(actual_items),
            "P0 item row count mismatch",
        )

    for index, expected_item in enumerate(expected_items):
        actual_item = actual_items[index] if index < len(actual_items) else {}
        for field in P0_ITEM_FIELDS:
            if not values_equal(field, expected_item.get(field), actual_item.get(field)):
                add_blocking_error(
                    blocking_errors,
                    f"items[{index}].{field}",
                    expected_item.get(field),
                    actual_item.get(field),
                    "P0 field mismatch",
                )

    p0_pass = len(blocking_errors) == 0
    p1_score = 1.0
    business_rule_score = 1.0
    publishable = p0_pass and item_row_count_match and p1_score >= 0.95 and business_rule_score >= 0.95

    return {
        "overall_score": 1.0 if publishable else 0.0,
        "publishable": publishable,
        "schema_pass": True,
        "p0_pass": p0_pass,
        "item_row_count_match": item_row_count_match,
        "scores": {
            "header": 1.0 if p0_pass else 0.0,
            "items": 1.0 if p0_pass else 0.0,
            "p1": p1_score,
            "business_rules": business_rule_score,
        },
        "blocking_errors": blocking_errors,
        "recommendation": "publishable" if publishable else "not_publishable",
    }
```

- [ ] **Step 4: Run evaluator tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_evaluator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/po-parser/profile_lab/evaluator.py workflows/po-parser/tests/test_profile_lab_evaluator.py
git commit -m "feat: add profile lab evaluator"
```

---

## Task 8: Evaluate Command And Summary Reports

**Files:**
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_evaluator.py`

- [ ] **Step 1: Add failing evaluate command test**

Append to `workflows/po-parser/tests/test_profile_lab_evaluator.py`:

```python
import json

from profile_lab.commands import main
from profile_lab.customer_assets import init_customer
from profile_lab.json_io import write_json


def test_evaluate_command_writes_summary(tmp_path):
    root = tmp_path / "profile-lab"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    expected = {
        "header": {"customer_name": "ACME", "po_number": "PO-1", "po_date": "2026-05-14"},
        "items": [{"customer_material": "MAT-1", "qty": 2, "delivery_date": "2026-06-01"}],
    }
    write_json(customer_dir / "expected" / "po-001.json", expected)
    write_json(
        customer_dir / "runs" / "run-1" / "adjudication" / "po-001.merged_draft.json",
        expected,
    )

    exit_code = main([
        "--lab-root",
        str(root),
        "evaluate",
        "--customer",
        "acme",
        "--run-id",
        "run-1",
    ])

    assert exit_code == 0
    summary_path = customer_dir / "runs" / "run-1" / "evaluation" / "summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["publishable"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_evaluator.py::test_evaluate_command_writes_summary -v
```

Expected: FAIL because `evaluate` is not wired.

- [ ] **Step 3: Wire evaluate command**

Update the `evaluate` parser in `commands.py`:

```python
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--customer", required=True)
    evaluate.add_argument("--run-id", required=True)
```

Add imports:

```python
from .evaluator import evaluate_po_result
```

Add this helper:

```python
def run_evaluate(lab_root: Path, customer_key: str, run_id: str) -> Path:
    customer_dir = lab_root / "customers" / customer_key
    run_dir = customer_dir / "runs" / run_id
    evaluation_dir = run_dir / "evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    sample_reports = []
    for expected_path in sorted((customer_dir / "expected").glob("*.json")):
        sample_key = expected_path.stem
        actual_path = run_dir / "adjudication" / f"{sample_key}.merged_draft.json"
        report = evaluate_po_result(
            expected=read_json(expected_path),
            actual=read_json(actual_path),
        )
        write_json(evaluation_dir / f"{sample_key}.report.json", report)
        sample_reports.append(report)

    publishable = bool(sample_reports) and all(report["publishable"] for report in sample_reports)
    summary = {
        "customer": customer_key,
        "run_id": run_id,
        "sample_count": len(sample_reports),
        "publishable": publishable,
        "reports": sample_reports,
    }
    write_json(evaluation_dir / "summary.json", summary)
    (evaluation_dir / "summary.md").write_text(
        f"# Evaluation Summary\n\n- customer: {customer_key}\n- run_id: {run_id}\n- publishable: {str(publishable).lower()}\n- sample_count: {len(sample_reports)}\n",
        encoding="utf-8",
    )
    return evaluation_dir
```

Add to `main` before the final parser error:

```python
    if args.command == "evaluate":
        evaluation_dir = run_evaluate(
            lab_root=lab_root,
            customer_key=args.customer,
            run_id=args.run_id,
        )
        print(f"wrote evaluation: {evaluation_dir}")
        return 0
```

- [ ] **Step 4: Run evaluator tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_evaluator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/po-parser/profile_lab/commands.py workflows/po-parser/tests/test_profile_lab_evaluator.py
git commit -m "feat: write profile lab evaluation summaries"
```

---

## Task 9: Publisher Gate

**Files:**
- Create: `workflows/po-parser/profile_lab/publisher.py`
- Modify: `workflows/po-parser/profile_lab/commands.py`
- Test: `workflows/po-parser/tests/test_profile_lab_publisher.py`

- [ ] **Step 1: Write publisher tests**

Create `workflows/po-parser/tests/test_profile_lab_publisher.py`:

```python
import json

import pytest

from profile_lab.customer_assets import init_customer
from profile_lab.json_io import write_json
from profile_lab.publisher import PublishGateError, publish_profile


def test_publish_profile_copies_profile_when_gate_passes(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        {"publishable": True, "sample_count": 1},
    )

    output_path = publish_profile(
        root=root,
        customer_key="acme",
        run_id="run-1",
        production_dir=production_dir,
    )

    assert output_path == production_dir / "acme.json"
    published = json.loads(output_path.read_text(encoding="utf-8"))
    assert published["profile_name"] == "acme"
    assert published["status"] == "production"
    assert published["last_run_id"] == "run-1"


def test_publish_profile_blocks_failed_gate(tmp_path):
    root = tmp_path / "profile-lab"
    production_dir = tmp_path / "profiles"
    init_customer(root=root, customer_key="acme", display_name="ACME Corp")
    customer_dir = root / "customers" / "acme"
    write_json(
        customer_dir / "runs" / "run-1" / "evaluation" / "summary.json",
        {"publishable": False, "sample_count": 1},
    )

    with pytest.raises(PublishGateError):
        publish_profile(
            root=root,
            customer_key="acme",
            run_id="run-1",
            production_dir=production_dir,
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_publisher.py -v
```

Expected: FAIL because `profile_lab.publisher` does not exist.

- [ ] **Step 3: Implement publisher**

Create `workflows/po-parser/profile_lab/publisher.py`:

```python
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
```

- [ ] **Step 4: Wire publish command**

Update `commands.py` imports:

```python
from .paths import DEFAULT_LAB_ROOT, PRODUCTION_PROFILE_DIR
from .publisher import PublishGateError, publish_profile
```

Update the `publish` parser:

```python
    publish = subparsers.add_parser("publish")
    publish.add_argument("--customer", required=True)
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--production-dir", default=str(PRODUCTION_PROFILE_DIR))
```

Add to `main` before final parser error:

```python
    if args.command == "publish":
        try:
            output_path = publish_profile(
                root=lab_root,
                customer_key=args.customer,
                run_id=args.run_id,
                production_dir=Path(args.production_dir),
            )
        except PublishGateError as exc:
            print(str(exc))
            return 1
        print(f"published profile: {output_path}")
        return 0
```

- [ ] **Step 5: Run publisher tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_publisher.py -v
```

Expected: PASS.

- [ ] **Step 6: Run all profile lab tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py tests/test_profile_lab_evaluator.py tests/test_profile_lab_publisher.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add workflows/po-parser/profile_lab workflows/po-parser/tests/test_profile_lab_publisher.py
git commit -m "feat: gate profile lab publishing"
```

---

## Task 10: Documentation And Knowledge Update

**Files:**
- Modify: `KNOWLEDGE.md`
- Create: `workflows/po-parser/profile-lab/README.md`
- Test: command help and profile lab tests

- [ ] **Step 1: Add profile lab README**

Create `workflows/po-parser/profile-lab/README.md`:

```markdown
# PO Profile Lab

Local-first training, evaluation, and tuning assets for onboarding customer PO PDF formats.

## Workflow

```bash
cd workflows/po-parser
python -m profile_lab init-customer --customer evytra --display-name "EVYTRA GmbH"
python -m profile_lab draft --customer evytra --run-id 2026-05-14-153000
python -m profile_lab evaluate --customer evytra --run-id 2026-05-14-153000
python -m profile_lab publish --customer evytra --run-id 2026-05-14-153000
```

## Human Approval

The draft command creates `adjudication/*.merged_draft.json`.
Copy and correct the approved result into `expected/*.json` before running evaluation.

## Publishing

Publishing is blocked unless evaluation summary says `publishable: true`.
Published profiles are exported to `workflows/po-parser/profiles/`.
```

- [ ] **Step 2: Update root knowledge index**

Add this bullet under the PO parser service section in `KNOWLEDGE.md`:

```markdown
- `po-parser profile lab` (`workflows/po-parser/profile_lab/` + `workflows/po-parser/profile-lab/`)
  - 本地优先的客户 PO 解析 Profile 训练/评测/调优核心
  - 命令入口：`cd workflows/po-parser && python -m profile_lab init-customer --customer evytra`
  - 产物：customer assets、runs、candidate JSON、adjudication reports、evaluation reports、published profiles
```

- [ ] **Step 3: Verify CLI help**

Run:

```bash
cd workflows/po-parser
python -m profile_lab --help
```

Expected: output lists `init-customer`, `draft`, `evaluate`, and `publish`.

- [ ] **Step 4: Run all profile lab tests**

Run:

```bash
cd workflows/po-parser
python -m pytest tests/test_profile_lab_assets.py tests/test_profile_lab_evaluator.py tests/test_profile_lab_publisher.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add KNOWLEDGE.md workflows/po-parser/profile-lab/README.md
git commit -m "docs: document po profile lab"
```

---

## Self-Review Checklist

- Spec coverage:
  - Local-first core is covered by Tasks 1-9.
  - Offline dual candidate files are covered by Task 4.
  - Adjudication artifacts are covered by Task 5.
  - OpenAI-compatible text and vision model candidates are covered by Task 6.
  - Human-approved expected JSON is represented by Task 7 inputs.
  - P0 gate and scoring are covered by Tasks 7-9.
  - Publish lifecycle is covered by Task 9.
  - Future Web UI is intentionally outside implementation scope.
- Placeholder scan:
  - The plan contains no open-ended implementation steps.
  - Deterministic candidate files are introduced first, then real model-backed candidates are added behind the same interfaces.
- Type consistency:
  - `CustomerInitResult`, `RunManifest`, and `RunCreateResult` are defined before use.
  - CLI flags are introduced before tests rely on them.
  - `publish_profile` uses the same `summary.json` shape emitted by `run_evaluate`.
