from pathlib import Path

from .json_io import write_json
from .models import CustomerConfig, CustomerInitResult, ProfileConfig, dump_model


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

    write_json_if_missing(customer_dir / "customer.json", dump_model(customer))
    write_json_if_missing(customer_dir / "profile.json", dump_model(profile))
    write_json_if_missing(customer_dir / "field_priority.json", DEFAULT_FIELD_PRIORITY)
    write_if_missing(customer_dir / "prompt.md", DEFAULT_PROMPT)

    return CustomerInitResult(customer_dir=customer_dir)
