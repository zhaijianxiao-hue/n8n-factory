# EVYTRA PO Customer Profile Design

> Scope: extend `workflows/po-parser` so EVYTRA purchase orders can be parsed with customer-specific rules while preserving the existing scheduled n8n workflow shape.

## Goal

Support EVYTRA PO PDFs as the first explicit customer profile in `po-parser`, using a profile-driven parser that keeps a single shared workflow and emits a richer, standard JSON payload.

## Current State

- The n8n workflow is a scheduled polling flow: scan incoming PDFs, call the Python parser service, route success/error, and emit a normalized payload.
- The Python service currently uses a single generic extraction path: `PyMuPDF` text extraction plus Ollama JSON extraction.
- The current response model is too shallow for EVYTRA. It only captures a small header subset and a minimal item structure.
- There is no explicit customer detection, no profile registry, and no `review` routing in the current workflow JSON.

## EVYTRA Document Findings

### Stable document markers

- Buyer name: `EVYTRA GmbH`
- PO number marker: `Order 2260892`
- Supplier ID marker: `Your supplier ID: 704000`
- Confirmation mailbox marker: `OrderConfirmation@evytra.com`
- Footer and logo text repeat predictably across pages.

These markers are sufficient to identify EVYTRA as a customer profile without relying on filename conventions.

### Header fields to capture

- `customer_name`: `EVYTRA GmbH`
- `customer_code`: `evytra`
- `po_number`: from `Order <digits>`
- `po_date`: from `Date:` / dated header line, normalized to `YYYY-MM-DD`
- `currency`: inferred from line prices and order amount, `EUR`
- `total_amount`: from `Order amount`
- `buyer_address`
- `supplier_id_at_customer`
- `customer_contact_person`
- `customer_contact_phone`
- `customer_contact_email`
- `supplier_name`
- `supplier_contact_person`
- `supplier_address`
- `delivery_terms`
- `payment_terms`
- `shipment_mode`

### EVYTRA-specific header notes

The following text blocks should be normalized onto `header`, not onto a single item:

- `blanket_order_note`
- `production_note`
- `packaging_note`

The line `>>> Deliver: + / - 0 % <<<` should also be normalized onto `header` and split into:

- `delivery_tolerance_positive_pct`
- `delivery_tolerance_negative_pct`
- `delivery_tolerance_raw`

### Item parsing rules

Each EVYTRA item is composed of a leading row plus one or more following detail rows.

Leading row example:

`10 1.000 pcs 4001391504 TA 735098`

Interpretation for EVYTRA:

- `line_no`: `10`
- `qty`: `1000`
- `unit`: `pcs`
- `customer_material`: `4001391504`
- trailing `TA`: ignore, do not capture
- `material_description`: `735098`

Follow-up rows provide:

- `customer_release_no`: `Order: 30601875`
- `customer_release_pos`: `Pos. 10.000` when present
- `delivery_date`
- `price / unit` expression
- `amount`

### Important business rule confirmations

- `4001391504` is the terminal customer material code and should be captured as the customer material.
- `TA` should be ignored.
- `735098` is the material description.
- Item 30's large amount is not a parsing bug to be masked. The parser should capture the source faithfully and let validation flag it for review.

## Target Output Shape

The parser should emit the existing top-level envelope plus EVYTRA fields:

- top level
  - `source_file`
  - `customer_profile`
  - `file_hash`
  - `process_time`
  - `header`
  - `items`
  - `confidence`
  - `warnings`
  - `status`
  - `output_file`
  - optional `metadata`

- header additions
  - `customer_code`
  - `buyer_address`
  - `supplier_id_at_customer`
  - `customer_contact_person`
  - `customer_contact_phone`
  - `customer_contact_email`
  - `supplier_name`
  - `supplier_contact_person`
  - `supplier_address`
  - `delivery_terms`
  - `payment_terms`
  - `shipment_mode`
  - `delivery_tolerance_positive_pct`
  - `delivery_tolerance_negative_pct`
  - `delivery_tolerance_raw`
  - `blanket_order_note`
  - `production_note`
  - `packaging_note`

- item additions
  - `unit`
  - `customer_material`
  - `material_description`
  - `customer_release_no`
  - `customer_release_pos`
  - `delivery_date`
  - `price_basis_qty`
  - `price_basis_unit`
  - `currency`
  - `description_raw`
  - `article_raw` only if still useful during transition

## Architecture

### 1. Keep one shared workflow

The n8n workflow should remain one scheduled pipeline for all customers:

`scan -> parse -> validate status -> route done/review/error -> output`

The customer-specific behavior belongs in the Python service, not in duplicated n8n branches per customer.

### 2. Add customer profile detection to the Python service

The parser service should detect the customer profile from extracted text before deciding how to parse fields.

For EVYTRA, detection can be rule-based using a small set of required markers.

### 3. Prefer rules first, LLM second

For EVYTRA, the parser should not rely on the LLM for stable fields that are easy to parse deterministically.

Rules should extract:

- customer identity
- header metadata
- item block boundaries
- quantities and dates
- order amount
- incoterms and payment terms
- EVYTRA note blocks
- delivery tolerance split fields

LLM use should be limited to fallback or difficult free-text interpretation, not basic row extraction.

### 4. Add a validation layer

After extraction, the parser should validate:

- required header fields present
- at least one item exists
- all items have `line_no`, `qty`, and `delivery_date`
- currency is consistent
- item amounts sum to order total within a tolerance or produce a review warning
- unusual unit-price basis or mismatched amount expressions produce warnings instead of silent correction

### 5. Introduce explicit `review`

The parser result should support `status = review` when extraction succeeds but business confidence is not high enough for straight-through processing.

For EVYTRA, review triggers should include:

- missing required fields
- ambiguous item structure
- mismatched totals
- inconsistent price basis across items
- suspicious numeric outliers such as item 30

## File Structure Proposal

### New files

- `workflows/po-parser/profiles/evytra.json`
  - customer detection markers, numeric format, field mapping rules, and review thresholds
- `workflows/po-parser/tests/fixtures/evytra/expected.json`
  - approved target output for the sample EVYTRA PDF
- `workflows/po-parser/tests/test_evytra_profile.py`
  - regression tests for EVYTRA profile parsing and validation

### Modified files

- `workflows/po-parser/service/po_parser_service.py`
  - add profile detection, EVYTRA rule parser, richer response models, and validation
- `workflows/po-parser/schemas/po-output.schema.json`
  - extend schema for richer header and item fields
- `workflows/po-parser/workflow.json`
  - add `review` handling if the n8n branch is updated now instead of later
- `KNOWLEDGE.md`
  - record the customer-profile parsing pattern if implemented

## Parsing Strategy For EVYTRA

### Detection

Detect EVYTRA when the extracted text includes enough of these markers:

- `EVYTRA GmbH`
- `Your supplier ID:`
- `OrderConfirmation@evytra.com`
- `Order <digits>`

### Number normalization

Use German number parsing rules:

- decimal separator: `,`
- thousands separator: `.`

Examples:

- `1.000` -> `1000`
- `45,00` -> `45.00`
- `46.350,00` -> `46350.00`

### Item boundary extraction

Start a new item when a line matches the EVYTRA item header pattern:

- line number
- quantity
- unit
- material token
- ignored `TA`
- description token

Continue consuming following lines until the next item header or document footer section.

### Delivery tolerance extraction

Parse `Deliver: + / - 0 %` into separate positive and negative percentages.

Store both normalized numbers and original text.

## Validation And Routing

### Success

Only use `success` when:

- required fields are present
- no structural ambiguity remains
- totals reconcile or are within accepted tolerance
- no high-severity warnings exist

### Review

Use `review` when:

- extraction is mostly complete but business anomalies exist
- a field was captured but needs human confirmation
- totals or unit-price basis look suspicious

### Error

Use `error` when:

- file cannot be read
- no meaningful text is extracted
- no supported customer profile can be detected and generic parsing also fails

## Recommended Implementation Order

1. Freeze the EVYTRA target JSON fixture.
2. Add EVYTRA profile configuration and test coverage.
3. Extend the parser service models and validation rules.
4. Add EVYTRA deterministic parsing.
5. Add or defer n8n `review` routing, depending on rollout preference.
6. Update knowledge/documentation with the customer-profile pattern.

## Decision Summary

- Use one shared n8n workflow.
- Put customer-specific behavior in the Python service via profiles.
- Parse EVYTRA with deterministic rules first.
- Preserve suspicious values rather than auto-correcting them.
- Route anomalies to `review` rather than `error`.
