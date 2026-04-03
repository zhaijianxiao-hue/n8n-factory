# EVYTRA PO Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add EVYTRA as the first explicit customer profile in `workflows/po-parser` with deterministic parsing, richer JSON output, and review-oriented validation.

**Architecture:** Keep the existing n8n workflow as a shared orchestration layer and move customer-specific behavior into the Python parser service. Add an EVYTRA profile, deterministic extraction helpers, richer response models, and regression tests using the sample EVYTRA PDF.

**Tech Stack:** FastAPI, Pydantic, PyMuPDF, Python regex parsing, JSON Schema, pytest-style regression testing

---

### Task 1: Freeze EVYTRA Expected Output

**Files:**
- Create: `workflows/po-parser/tests/fixtures/evytra/expected.json`
- Reference: `workflows/po-parser/pdf-examples/evytra/evytra-Order2260892.pdf`
- Reference: `docs/superpowers/specs/2026-04-03-evytra-po-design.md`

- [ ] **Step 1: Write the expected EVYTRA JSON fixture**

Include the agreed business mapping:
- `4001391504` as `customer_material`
- ignore `TA`
- `735098` as `material_description`
- header-level delivery tolerance and notes
- item 30 amount preserved as captured and flagged via warnings later

- [ ] **Step 2: Review the fixture against the sample PDF text**

Check:
- 4 items present
- `po_number = 2260892`
- `po_date = 2026-03-23`
- `currency = EUR`
- `total_amount = 46350.00`

- [ ] **Step 3: Commit**

```bash
git add "workflows/po-parser/tests/fixtures/evytra/expected.json" "docs/superpowers/specs/2026-04-03-evytra-po-design.md" "docs/superpowers/plans/2026-04-03-evytra-po-implementation.md"
git commit -m "docs: define EVYTRA PO parsing target"
```

### Task 2: Add EVYTRA Profile Configuration

**Files:**
- Create: `workflows/po-parser/profiles/evytra.json`
- Modify: `workflows/po-parser/service/po_parser_service.py`

- [ ] **Step 1: Write the failing test for EVYTRA profile detection**

Create a test that passes EVYTRA sample text into a profile detection function and expects `evytra`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k detect -v`
Expected: FAIL because the profile detection function does not exist yet.

- [ ] **Step 3: Add `profiles/evytra.json`**

Include:
- identifying markers
- number format metadata
- supported note fields
- review trigger hints

- [ ] **Step 4: Implement minimal profile detection code**

Add a helper in `po_parser_service.py` that matches EVYTRA markers in extracted text.

- [ ] **Step 5: Run the detection test again**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k detect -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add "workflows/po-parser/profiles/evytra.json" "workflows/po-parser/service/po_parser_service.py" "workflows/po-parser/tests/test_evytra_profile.py"
git commit -m "feat: add EVYTRA profile detection"
```

### Task 3: Extend Output Models And Schema

**Files:**
- Modify: `workflows/po-parser/service/po_parser_service.py`
- Modify: `workflows/po-parser/schemas/po-output.schema.json`
- Test: `workflows/po-parser/tests/test_evytra_profile.py`

- [ ] **Step 1: Write the failing schema/model test**

Add assertions that parsed EVYTRA output includes:
- header tolerance fields
- header notes
- item `customer_material`
- item `material_description`
- item `customer_release_no`
- item `delivery_date`

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k shape -v`
Expected: FAIL due to missing fields in the current model.

- [ ] **Step 3: Expand Pydantic response models**

Add only the fields needed by EVYTRA and agreed standardization.

- [ ] **Step 4: Expand `po-output.schema.json`**

Align schema with the service models. Preserve backward compatibility for untouched fields where possible.

- [ ] **Step 5: Run the shape test again**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k shape -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add "workflows/po-parser/service/po_parser_service.py" "workflows/po-parser/schemas/po-output.schema.json" "workflows/po-parser/tests/test_evytra_profile.py"
git commit -m "feat: extend PO output for EVYTRA fields"
```

### Task 4: Implement Deterministic EVYTRA Parsing

**Files:**
- Modify: `workflows/po-parser/service/po_parser_service.py`
- Test: `workflows/po-parser/tests/test_evytra_profile.py`
- Reference: `workflows/po-parser/tests/fixtures/evytra/expected.json`

- [ ] **Step 1: Write the failing end-to-end EVYTRA parser test**

Test the deterministic parser against the EVYTRA sample PDF text and compare selected fields to `expected.json`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k evytra_parse -v`
Expected: FAIL because deterministic EVYTRA parsing is not implemented.

- [ ] **Step 3: Implement German number parsing helpers**

Support `1.000`, `45,00`, and `46.350,00` normalization.

- [ ] **Step 4: Implement EVYTRA header extraction**

Extract deterministic header fields and note blocks.

- [ ] **Step 5: Implement EVYTRA item block extraction**

Group multi-line item blocks and populate item fields using the agreed mappings.

- [ ] **Step 6: Keep suspicious values intact**

Do not “fix” item 30. Preserve the parsed amount and let validation flag it.

- [ ] **Step 7: Run the EVYTRA parser test again**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k evytra_parse -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add "workflows/po-parser/service/po_parser_service.py" "workflows/po-parser/tests/test_evytra_profile.py" "workflows/po-parser/tests/fixtures/evytra/expected.json"
git commit -m "feat: add deterministic EVYTRA PO parsing"
```

### Task 5: Add Validation And Review Status

**Files:**
- Modify: `workflows/po-parser/service/po_parser_service.py`
- Test: `workflows/po-parser/tests/test_evytra_profile.py`

- [ ] **Step 1: Write the failing validation test**

Assert that the EVYTRA sample returns `status = review` and includes warnings for suspicious pricing or amount inconsistency.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k review -v`
Expected: FAIL because the current parser returns only generic `success/error` behavior.

- [ ] **Step 3: Implement minimal validation rules**

Add:
- required field checks
- total reconciliation warning
- suspicious item warning
- review status selection

- [ ] **Step 4: Run the validation test again**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -k review -v`
Expected: PASS

- [ ] **Step 5: Run the full EVYTRA test file**

Run: `pytest workflows/po-parser/tests/test_evytra_profile.py -v`
Expected: all EVYTRA tests PASS

- [ ] **Step 6: Commit**

```bash
git add "workflows/po-parser/service/po_parser_service.py" "workflows/po-parser/tests/test_evytra_profile.py"
git commit -m "feat: add EVYTRA review validation rules"
```

### Task 6: Update Workflow Routing If Review Is Enabled Now

**Files:**
- Modify: `workflows/po-parser/workflow.json`
- Test: local workflow validation and manual n8n execution later

- [ ] **Step 1: Decide whether to enable `review` routing now or defer**

If deferred, skip this task and keep `review` only in parser output for now.

- [ ] **Step 2: Write the failing workflow expectation**

Document that workflow routing should branch on `success`, `review`, and `error` instead of only success/error.

- [ ] **Step 3: Modify workflow JSON minimally**

Add a review branch and route files to a `review` directory or output node.

- [ ] **Step 4: Validate workflow file**

Run the local validation command used in this repo for workflow files.
Expected: no structural validation errors from the workflow definition itself.

- [ ] **Step 5: Commit**

```bash
git add "workflows/po-parser/workflow.json"
git commit -m "feat: add review routing for PO parser"
```

### Task 7: Capture Knowledge And Verification

**Files:**
- Modify: `KNOWLEDGE.md`
- Modify: `workflows/po-parser/README.md`

- [ ] **Step 1: Update `KNOWLEDGE.md`**

Document the customer-profile parsing pattern and the rule-first approach for stable PDF layouts.

- [ ] **Step 2: Update product README**

Note that EVYTRA is the first explicit customer profile and that suspicious documents route to review.

- [ ] **Step 3: Run the narrowest meaningful verification**

Run:
- `pytest workflows/po-parser/tests/test_evytra_profile.py -v`
- any existing narrow parser tests that still apply

Record the actual results.

- [ ] **Step 4: Commit**

```bash
git add "KNOWLEDGE.md" "workflows/po-parser/README.md"
git commit -m "docs: record EVYTRA profile parsing pattern"
```

### Final Verification

**Run all relevant checks after implementation:**

- [ ] `pytest workflows/po-parser/tests/test_evytra_profile.py -v`
- [ ] `pytest workflows/po-parser/tests/test_po_parser_simple.py -v` or the narrowest applicable parser regression command
- [ ] validate `workflows/po-parser/workflow.json` if it was modified

Plan complete and saved to `docs/superpowers/plans/2026-04-03-evytra-po-implementation.md`. Ready to execute?
