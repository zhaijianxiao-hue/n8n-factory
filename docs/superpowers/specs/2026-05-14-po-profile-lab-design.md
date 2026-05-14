# PO Profile Lab Design

> Scope: design a local-first training, evaluation, and tuning lab for onboarding many customer PO PDF formats into `workflows/po-parser`.

## Goal

Build a customer PO parsing profile factory.

For a new customer, the lab should take a small PDF sample set, generate two parsing candidates, visually adjudicate the result, help a human approve the standard expected JSON, evaluate profile quality, and publish only profiles that meet clear quality gates.

The first version focuses on accelerating new customer onboarding. It does not replace the production parser service and does not automatically deploy new profiles.

## Problem

The current `po-parser` service can parse only a small number of known customer formats well. EVYTRA is the current reference implementation: customer detection, deterministic parsing, schema validation, test fixtures, and `review` routing.

That pattern is reliable, but scaling it one customer at a time to roughly 200 customer formats would become a long manual adapter project.

The hard part is not the final output shape. The output schema is already fixed. The hard part is determining whether a customer's PDF can be parsed correctly, finding layout-specific mistakes, iterating prompts or profile hints, and proving that the profile is good enough to use.

## Key Decision

Create a local-first `PO Profile Lab` before building a Web UI.

Version 1 should produce the core evaluation assets and workflow:

```text
customer PDF samples
  -> text/parser candidate
  -> vision LLM candidate
  -> visual adjudicator agent
  -> merged draft JSON
  -> human-approved expected JSON
  -> evaluation report
  -> publishable customer profile
```

Expected JSON is a long-lived test asset. LLM output may create the first draft, but a human must approve or correct it before it becomes the evaluation baseline.

## Non-Goals For V1

- No Web UI.
- No automatic production deployment.
- No automatic editing of `po_parser_service.py`.
- No fully automatic profile approval.
- No reliance on a single parsing path.
- No use of raw LLM output as the trusted expected result.

## Architecture

### 1. Text Candidate Runner

This runner reuses the existing parser capabilities:

- `PyMuPDF` text extraction.
- Existing deterministic customer parser when available.
- Generic text LLM extraction when no deterministic parser exists.

It emits `candidate_text.json`.

The value of this path is speed, cost, and continuity with the current service. Its main risk is that text extraction can lose table structure or shift columns without making that failure obvious.

### 2. Vision Candidate Runner

This runner renders each PDF page to an image and asks a vision LLM to extract the fixed PO JSON shape from the visual document.

It emits `candidate_vision.json`.

The value of this path is layout awareness. It can inspect columns, row boundaries, page breaks, and visual grouping that may be damaged in plain text extraction.

### 3. Adjudicator Agent

The adjudicator is the central reviewer. It receives the PDF page images, both candidate JSON files, the output schema, field priority rules, and optional customer context.

It compares the two candidates against the visual PDF evidence and emits:

- `merged_draft.json`
- `conflict_report.md`
- `field_evidence.json`
- `profile_suggestions.md`

The adjudicator should generate the expected JSON draft and identify conflicts that need human review. It may suggest prompt or profile improvements, but V1 should not automatically apply those suggestions.

### 4. Human Approval

A human reviews `merged_draft.json` and `conflict_report.md`, then saves the corrected standard result as `expected/*.json`.

This step is mandatory. The expected JSON becomes the stable regression target for that customer.

### 5. Evaluator

The evaluator compares actual parser output against approved expected JSON and produces a report with field-level errors, item-level errors, business-rule checks, and publishability status.

### 6. Publisher

The publisher exports a lightweight customer profile only when evaluation gates pass.

The complete lab assets stay under `profile-lab/customers/<customer>/`. The production parser should load only published profile files from `workflows/po-parser/profiles/`.

## Proposed Directory Layout

```text
workflows/po-parser/profile-lab/
  customers/
    evytra/
      customer.json
      field_priority.json
      prompt.md
      profile.json

      samples/
        po-001.pdf
        po-002.pdf

      expected/
        po-001.json
        po-002.json

      runs/
        2026-05-14-153000/
          manifest.json

          inputs/
            po-001.pdf
            po-002.pdf

          pages/
            po-001/
              page-001.png
              page-002.png

          candidates/
            text/
              po-001.json
            vision/
              po-001.json

          adjudication/
            po-001.merged_draft.json
            po-001.conflict_report.md
            po-001.field_evidence.json
            po-001.profile_suggestions.md

          evaluation/
            po-001.report.json
            summary.json
            summary.md
```

## Run Manifest

Each run should have a `manifest.json` so results remain traceable.

```json
{
  "run_id": "2026-05-14-153000",
  "customer": "evytra",
  "profile_version": "0.1.0",
  "prompt_version": "0.1.0",
  "model_text": "qwen2.5:7b",
  "model_vision": "vision-model-name",
  "samples": ["po-001.pdf", "po-002.pdf"],
  "created_at": "2026-05-14T15:30:00+08:00"
}
```

## Customer Files

### customer.json

Customer identity and basic context.

```json
{
  "customer_key": "evytra",
  "display_name": "EVYTRA GmbH",
  "aliases": ["EVYTRA"],
  "default_currency": "EUR",
  "language": ["en", "de"]
}
```

### profile.json

Parsing strategy and customer-specific profile hints.

```json
{
  "profile_name": "evytra",
  "version": "0.1.0",
  "status": "draft",
  "markers": ["EVYTRA GmbH", "Your supplier ID:"],
  "number_format": {
    "decimal_separator": ",",
    "thousands_separator": "."
  },
  "item_rules": {
    "ignore_tokens": ["TA"]
  }
}
```

### prompt.md

The current customer prompt used by the vision and adjudication steps. Prompt changes should create a new run.

### field_priority.json

Customer-specific overrides for the global P0, P1, and P2 field priorities.

## Adjudicator Input

```text
1. PDF page images
2. candidate_text.json
3. candidate_vision.json
4. po-output.schema.json
5. field_priority.json
6. customer_context.md or customer.json
```

## Adjudicator Output

### merged_draft.json

The best current draft of the standard output JSON. A human edits or approves this file into `expected/*.json`.

### conflict_report.md

Human-readable conflict report.

Example:

```md
# Conflict Report

## Blocking Review Required

### items[2].qty
- text candidate: 100
- vision candidate: 1000
- adjudicator choice: 1000
- reason: PDF shows "1.000" under Qty column. Customer uses European number format.
- priority: P0
- human_review_required: true
```

### field_evidence.json

Machine-readable evidence for chosen values.

```json
{
  "items[2].qty": {
    "chosen_value": 1000,
    "chosen_source": "vision",
    "confidence": 0.92,
    "page": 1,
    "evidence_text": "1.000",
    "reason": "Value appears under Qty column and uses European thousands separator.",
    "human_review_required": true
  }
}
```

### profile_suggestions.md

Non-applied suggestions for prompt and profile tuning.

```md
# Profile Suggestions

- Set number_format.decimal_separator to ",".
- Set number_format.thousands_separator to ".".
- Treat "TA" as an ignore token in item rows.
- Delivery date appears in the rightmost item table column.
```

## Adjudicator Rules

1. If both candidates agree and the value passes schema validation, accept the value as low risk.
2. If candidates conflict and visual evidence is clear, choose the visually supported value and record evidence.
3. If candidates conflict and visual evidence is unclear, mark `human_review_required=true`.
4. If a P0 field conflicts, always include it in `conflict_report.md`.
5. For numeric fields, check both candidate disagreement and business consistency.
6. For item tables, compare row count before comparing row fields.
7. If row count differs, mark a P0 blocking issue but still perform best-effort row matching for diagnostics.

## Field Priority

### P0 Blocking Fields

Any P0 mismatch blocks publication.

- `header.customer_name`
- `header.po_number`
- `header.po_date`
- item row count
- `items.customer_material`
- `items.qty`
- `items.delivery_date`

### P1 Business Fields

P1 errors may allow review, but they prevent publication if the P1 score is below the gate.

- `header.currency`
- `header.total_amount`
- `items.unit_price`
- `items.amount`
- `items.unit`
- `items.customer_release_no`
- `items.sap_material` when material mapping is in scope

### P2 Supporting Fields

P2 fields contribute to quality but do not block publication.

- contact name, phone, email
- buyer and supplier addresses
- payment terms
- delivery terms
- shipment mode
- production notes
- packaging notes
- raw description fields

## Evaluation Rules

### Normalization

- Strings: trim, collapse whitespace, and use configurable case sensitivity.
- Dates: normalize to `YYYY-MM-DD`.
- Numbers: normalize according to customer number format.
- Empty values: treat `null`, empty string, and missing optional fields as the same kind of empty.

### Numeric Tolerance

- `qty`: exact match unless a customer-specific unit conversion rule exists.
- `unit_price`: tolerance `0.01`.
- `amount`: tolerance `0.05`.
- `total_amount`: tolerance is the greater of `0.10` or `0.01%`.

### Item Matching

Match expected and actual item rows in this order:

1. `customer_release_no + customer_material`
2. `customer_material + delivery_date`
3. `line_no`
4. array order fallback

If row counts differ, the report should still attempt best-effort matching so users can see which rows are missing or duplicated.

### Business Rule Checks

- `qty * unit_price` approximately equals `amount`.
- Sum of item amounts approximately equals `header.total_amount`.
- Header currency and item currency are consistent.
- `delivery_date` is not earlier than `po_date` unless explicitly allowed.
- Quantity, price, and amount are not negative.
- Duplicate item rows are flagged.

## Evaluation Report

Example `summary.json`:

```json
{
  "overall_score": 0.93,
  "publishable": false,
  "schema_pass": true,
  "p0_pass": false,
  "item_row_count_match": true,
  "scores": {
    "header": 0.98,
    "items": 0.89,
    "p1": 0.94,
    "business_rules": 0.95
  },
  "blocking_errors": [
    {
      "field": "items[3].qty",
      "expected": 1000,
      "actual": 100,
      "reason": "P0 field mismatch"
    }
  ],
  "recommendation": "not_publishable"
}
```

## Publish Gate

A profile is publishable only when all conditions pass:

- Schema validation passes.
- P0 fields pass.
- Item row count matches.
- P1 score is at least `0.95`.
- Business rule score is at least `0.95`.
- No unresolved P0 or P1 `human_review_required` findings remain.

## Profile Lifecycle

```text
draft -> evaluating -> candidate -> production -> deprecated
```

### draft

Initial customer profile. It may contain only customer metadata, samples, and a starter prompt.

### evaluating

The profile has approved expected JSON and at least one evaluation run.

### candidate

The profile meets the publish gate but has not been accepted into production.

### production

The profile has been exported for use by the production parser service. Direct edits should be avoided. Any production issue should go back through profile-lab with new samples and a new run.

### deprecated

The profile is no longer active or has been replaced by a newer production version.

## Minimal V1 Commands

```bash
profile-lab init-customer --customer evytra
profile-lab draft --customer evytra
profile-lab evaluate --customer evytra
profile-lab publish --customer evytra
```

`draft` should render pages, run both candidate paths, run adjudication, and produce the merged draft and conflict reports.

`evaluate` should compare actual output against approved expected JSON.

`publish` should export a lightweight profile only if the publish gate passes.

## Integration With Current po-parser

V1 should not restructure the production service. It should create assets that can later be consumed by `po_parser_service.py`.

The current EVYTRA profile remains the reference for a production-ready customer-specific parser. `PO Profile Lab` generalizes the onboarding process around that pattern.

## Future Web Workbench

After the local evaluation core stabilizes, a Web workbench can be built on top of the same files and reports.

The Web UI should focus on:

- PDF sample upload.
- Side-by-side candidate viewing.
- Visual conflict review.
- JSON correction.
- Evaluation dashboards.
- Profile lifecycle and publish approval.

The local file layout should be treated as the backend contract for that future UI.

## Success Criteria For V1

- A new customer can be initialized with a small PDF sample set.
- The lab can generate text and vision candidates for each sample.
- The adjudicator can produce a merged draft, conflict report, field evidence, and profile suggestions.
- A human can approve expected JSON from the merged draft.
- The evaluator can produce field-level, item-level, and business-rule scoring.
- The publisher refuses profiles that do not meet the publish gate.
- All generated artifacts are traceable to a run manifest.
