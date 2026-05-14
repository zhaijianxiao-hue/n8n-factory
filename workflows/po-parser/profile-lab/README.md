# PO Profile Lab

Local-first training, evaluation, and tuning assets for onboarding customer PO PDF formats.

## Workflow

```bash
cd workflows/po-parser
python -m profile_lab init-customer --customer evytra --display-name "EVYTRA GmbH"
python -m profile_lab draft --customer evytra --run-id 2026-05-14-153000
python -m profile_lab evaluate --customer evytra --run-id 2026-05-14-153000
```

## CLI Options

Global options must be placed before the subcommand. For example, use
`python -m profile_lab --lab-root ./profile-lab draft ...`, not
`python -m profile_lab draft --lab-root ./profile-lab ...`.

The `draft` command supports `--text-model` and `--vision-model` for
OpenAI-compatible model-backed candidate generation.

Environment variables:
- `PO_PROFILE_LAB_OPENAI_API_KEY` is required when using model-backed candidates.
- `PO_PROFILE_LAB_OPENAI_BASE_URL` is optional for OpenAI-compatible endpoints.
- `PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL` is optional; when set, approval
  submissions send a notification webhook.

## UI

Build the frontend and run the FastAPI service:

```bash
cd workflows/po-parser/profile_lab_ui/frontend
npm install
npm run build
cd workflows/po-parser
python -m profile_lab_ui
```

The UI runs at `http://localhost:8768`.

## Human Approval

The draft command creates `adjudication/*.merged_draft.json`.
Copy and correct the approved result into `expected/*.json` before running evaluation.

## Publishing

Publishing is blocked unless evaluation summary says `publishable: true` and
the run has `approval.json` with admin approval. The normal path is:

1. Business user submits the evaluated run in the UI.
2. Admin opens Admin Review, checks the evidence, approves the run, then publishes.

The CLI publish command uses the same gate, so it cannot publish a run before
admin approval:

```bash
python -m profile_lab publish --customer evytra --run-id 2026-05-14-153000
```

Published profiles are exported to `workflows/po-parser/profiles/`.
