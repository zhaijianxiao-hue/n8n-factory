# PO Profile Lab UI Design

> Scope: add a local/internal UI for `workflows/po-parser` Profile Lab so business users and admins can visually review, evaluate, approve, and publish customer PO parsing profiles. This is not a general platform.

## Goal

Build a high-end but practical PO parsing workbench around the existing `profile_lab` CLI and file outputs.

The UI should make one hard problem visible: whether a customer PO PDF was parsed correctly enough to become an online automation profile. It should show the PDF, text candidate, vision candidate, merged JSON, evaluation score, blocking errors, and publish gate in one coherent review surface.

## Non-Goals

- Do not build a multi-tenant platform.
- Do not add account management, complex permissions, billing, or cross-team workspace features.
- Do not replace the existing `profile_lab` core.
- Do not duplicate n8n as a workflow designer.
- Do not make per-customer n8n workflows. The current shared workflow model remains.

## Primary Users

### Business Assistant

The business assistant prepares a customer profile:

- uploads or selects customer PDF samples;
- runs draft generation;
- reviews text and vision candidate differences;
- corrects the merged JSON or expected output;
- runs evaluation;
- submits the run when they believe it is ready for automation.

### Administrator

The administrator is the release gate:

- receives a notification when a run is submitted;
- opens the same run in admin review mode;
- checks score, P0 blockers, sample evidence, prompt/profile changes, and publish gate;
- approves and publishes the profile, or rejects it with a change note.

## Visual Direction

Use the approved direction: precision console.

- Dark interface, crisp cyan accents, restrained glow, clear data density.
- The product should feel like an engineering-grade control room, not a marketing page.
- Motion is allowed but should be functional: page load reveal, active scan highlight, diff focus, run-status transitions, and subtle publish-gate state changes.
- Avoid decorative cards for page sections. Use full workbench panels, dense controls, and stable dimensions.

## Core Layout

The first screen is Review First.

The primary workbench has:

- top run bar: customer, run id, profile version, model names, run state, primary actions;
- score strip: overall score, P0 status, row count, P1 score, business-rule status, publish gate;
- left pane: rendered PDF page images with highlighted regions;
- middle pane: candidate comparison between deterministic/text extraction and vision extraction;
- right pane: standard JSON tree with field-level status;
- side panel: adjudication agent notes, suggested corrections, prompt patch suggestions, and admin gate.

Dashboard is a secondary page for customer coverage and progress:

- customers onboarded / in review / published;
- latest runs;
- blocked P0 issues;
- publishable profiles waiting for admin approval;
- recent publish history.

## Approval Workflow

The UI introduces a lightweight approval state machine stored with the run artifacts.

States:

- `draft`: run assets exist but have not been generated.
- `generated`: candidates and merged draft exist.
- `evaluated`: evaluation summary exists.
- `submitted`: business assistant submitted the evaluated run for approval.
- `changes_requested`: admin rejected the run with a note.
- `approved`: admin approved the run for publishing.
- `published`: profile was exported to `workflows/po-parser/profiles/`.

Publish rules:

- A run can be submitted only after evaluation exists.
- A run can be approved only if P0 passes and evaluation is publishable.
- A run can be published only after admin approval.
- The UI may show a disabled publish button before approval, but backend must enforce the gate.

Approval metadata is stored under the run directory, for example:

```text
profile-lab/customers/<customer>/runs/<run-id>/approval.json
```

Suggested shape:

```json
{
  "state": "submitted",
  "submitted_by": "business",
  "submitted_at": "2026-05-14T18:30:00+08:00",
  "admin_decision": null,
  "admin_by": null,
  "admin_at": null,
  "note": "EVYTRA sample set looks ready for automation."
}
```

## Notification

This is not a platform notification center. MVP notification is a simple outbound event when a run enters `submitted`.

Preferred MVP:

- backend calls a configured n8n webhook such as `PO_PROFILE_LAB_APPROVAL_WEBHOOK_URL`;
- n8n handles the real delivery channel, such as Feishu, email, or future internal message;
- if the webhook is not configured, the UI still records the submitted state and shows a visible warning that notification was skipped.

Notification payload:

```json
{
  "event": "po_profile_lab.approval_requested",
  "customer": "evytra",
  "run_id": "2026-05-14-153000",
  "overall_score": 0.924,
  "publishable": true,
  "review_url": "http://<host>/po-profile-lab/customers/evytra/runs/2026-05-14-153000"
}
```

This keeps delivery flexible without hardcoding one corporate channel in the app.

## Backend Design

Add a small FastAPI UI service beside the existing Profile Lab core.

Candidate location:

```text
workflows/po-parser/profile_lab_ui/
```

Responsibilities:

- serve the frontend app;
- list customers and runs from the existing `profile-lab/` directory;
- expose run artifacts: manifest, page images, candidates, adjudication, evaluation, approval state;
- run existing Profile Lab actions through Python functions or subprocess wrappers;
- update expected/merged JSON files after user correction;
- submit runs for admin review;
- send approval notifications through a webhook adapter;
- approve, reject, and publish profiles through existing publisher logic.

The first version remains file-backed. A database is unnecessary for MVP because Profile Lab already stores durable artifacts by customer and run id.

## API Sketch

Read APIs:

- `GET /api/customers`
- `GET /api/customers/{customer}/runs`
- `GET /api/customers/{customer}/runs/{run_id}`
- `GET /api/customers/{customer}/runs/{run_id}/evaluation`
- `GET /api/customers/{customer}/runs/{run_id}/approval`
- `GET /api/customers/{customer}/runs/{run_id}/pages/{sample}/{page}`

Action APIs:

- `POST /api/customers`
- `POST /api/customers/{customer}/runs/{run_id}/draft`
- `POST /api/customers/{customer}/runs/{run_id}/evaluate`
- `PUT /api/customers/{customer}/runs/{run_id}/merged/{sample}`
- `POST /api/customers/{customer}/runs/{run_id}/submit`
- `POST /api/customers/{customer}/runs/{run_id}/approve`
- `POST /api/customers/{customer}/runs/{run_id}/reject`
- `POST /api/customers/{customer}/runs/{run_id}/publish`

All action APIs return structured status, warnings, and artifact paths.

## Frontend Design

Use a focused frontend app rather than adding pages to n8n.

Recommended stack for MVP:

- Vite + React + TypeScript;
- CSS modules or plain CSS variables for the custom visual system;
- no heavy UI framework in the first version;
- optional lightweight icons via `lucide-react`.

Main routes:

- `/` dashboard summary;
- `/customers/:customer/runs/:runId` review workbench;
- `/admin/review` submitted runs waiting for approval.

Key components:

- `RunTopBar`
- `ScoreStrip`
- `PdfEvidencePane`
- `CandidateDiffPane`
- `StandardJsonPane`
- `AdjudicationPanel`
- `ApprovalGate`
- `RunTimeline`
- `CustomerDashboard`

## Editing Model

MVP editing should be deliberately narrow.

- The user edits merged/expected JSON through structured field controls or a JSON editor view.
- Every save writes the artifact file and creates a lightweight local revision entry.
- The workbench highlights fields changed by the user.
- Prompt patch suggestions are displayed as suggestions first; applying them can be a later task.

This avoids pretending the Agent can autonomously fix all profiles while still showing concrete guidance.

## Error Handling

- Missing run artifacts show empty-state panels with exact next action.
- CLI/model failures show command, stderr summary, and affected sample.
- Invalid JSON edits are blocked before saving.
- Failed notification does not roll back submission, but is shown as a warning and can be retried.
- Publish attempts without approval fail with a clear gate error.

## Verification

MVP should include:

- API tests for listing runs, reading evaluation, submit, approve, reject, and publish gate behavior;
- component-level checks for score/gate rendering if the chosen frontend test setup supports it;
- Playwright smoke test for loading dashboard and opening a run;
- existing Profile Lab tests must continue passing.

Manual verification:

- create or use a sample customer run;
- run draft/evaluate;
- submit as business assistant;
- confirm webhook payload or notification-skip warning;
- approve as admin;
- publish and confirm profile file appears in `workflows/po-parser/profiles/`.

## Success Criteria

- A business assistant can visually decide whether a run is ready without opening raw folders.
- An admin can approve or reject from the workbench using evidence and evaluation results.
- Published profiles still go through the existing publish gate.
- Notification is sent or explicitly reported as skipped.
- The UI feels like a precision control console and keeps the Review First layout.

