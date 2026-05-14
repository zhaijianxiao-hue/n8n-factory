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
