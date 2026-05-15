import shutil
from pathlib import Path

from .json_io import read_json, write_json
from .models import (
    CustomerConfig,
    CustomerInitResult,
    ProfileConfig,
    RunCreateResult,
    RunManifest,
    current_timestamp,
    dump_model,
)


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


DEFAULT_PROMPT = """You are a purchase order JSON extraction engine.

Return one valid JSON object only. Do not use markdown, prose, or comments.
Use null when a field is not visible. Preserve visible values when uncertain and explain uncertainty in warnings.

Target object:
{
  "customer_profile": "customer key or null",
  "header": {
    "customer_name": "buyer/customer name",
    "customer_code": null,
    "buyer_address": null,
    "supplier_id_at_customer": null,
    "customer_contact_person": null,
    "customer_contact_phone": null,
    "customer_contact_fax": null,
    "customer_contact_email": null,
    "supplier_name": null,
    "supplier_contact_person": null,
    "supplier_address": null,
    "po_number": null,
    "po_date": "YYYY-MM-DD or null",
    "currency": "EUR/USD/CNY/JPY/GBP/HKD/OTHER or null",
    "total_amount": null,
    "total_qty": null,
    "payment_terms": null,
    "delivery_terms": null,
    "shipment_mode": null,
    "delivery_tolerance_positive_pct": null,
    "delivery_tolerance_negative_pct": null,
    "delivery_tolerance_raw": null,
    "blanket_order_note": null,
    "production_note": null,
    "packaging_note": null
  },
  "items": [
    {
      "line_no": 10,
      "customer_material": null,
      "sap_material": null,
      "material_description": null,
      "qty": null,
      "unit": null,
      "customer_release_no": null,
      "customer_release_pos": null,
      "price_basis_qty": null,
      "price_basis_unit": null,
      "unit_price": null,
      "currency": null,
      "amount": null,
      "delivery_date": "YYYY-MM-DD or null",
      "remarks": null,
      "description_raw": null,
      "article_raw": null
    }
  ],
  "confidence": 0.0,
  "warnings": [],
  "status": "success or review"
}

Line item rules:
- Extract every PO item row. Do not collapse multiple delivery lines into one item.
- Keep line_no as a number when visible.
- Use customer_material for the customer's part/material/article code visible on the PO.
- Use customer_release_no and customer_release_pos for customer order/release references such as "Order: ... Pos. ...".
- Convert European dates like 23.03.2026 to 2026-03-23.
- Convert European numbers like 46.350,00 to 46350.00 and 1.000 to 1000.
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

    write_json_if_missing(customer_dir / "customer.json", dump_model(customer))
    write_json_if_missing(customer_dir / "profile.json", dump_model(profile))
    write_json_if_missing(customer_dir / "field_priority.json", DEFAULT_FIELD_PRIORITY)
    write_if_missing(customer_dir / "prompt.md", DEFAULT_PROMPT)

    return CustomerInitResult(customer_dir=customer_dir)


def list_sample_pdfs(customer_dir: Path) -> list[Path]:
    samples_dir = customer_dir / "samples"
    if not samples_dir.exists():
        return []
    return sorted(
        path for path in samples_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def create_run(root: Path, customer_key: str, run_id: str) -> RunCreateResult:
    customer_dir = root / "customers" / customer_key
    profile = read_json(customer_dir / "profile.json")
    sample_paths = list_sample_pdfs(customer_dir)
    run_dir = customer_dir / "runs" / run_id
    if not sample_paths:
        raise ValueError(f"no PDF samples found for customer: {customer_key}")
    if run_dir.exists():
        raise FileExistsError(f"run already exists: {run_dir}")

    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    for sample_path in sample_paths:
        shutil.copy2(sample_path, inputs_dir / sample_path.name)

    manifest = RunManifest(
        run_id=run_id,
        customer=customer_key,
        profile_version=profile["version"],
        samples=[sample_path.name for sample_path in sample_paths],
        created_at=current_timestamp(),
    )
    write_json(run_dir / "manifest.json", dump_model(manifest))

    return RunCreateResult(run_dir=run_dir, manifest=manifest)
