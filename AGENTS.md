# AGENTS.md

## ⚠️ Knowledge Base

**All agents MUST read `KNOWLEDGE.md` at the repository root before working on n8n-related tasks.**

This knowledge base contains:
- n8n API capabilities and usage patterns
- Expression syntax and common pitfalls
- Workflow development and debugging patterns
- Feishu API integration knowledge
- Execution data structures
- test006.json as golden reference for node structure

If you add new patterns or discoveries, **update KNOWLEDGE.md** to preserve institutional knowledge.

## 📦 Project Skills

### n8n Workflow Management (REQUIRED)

**For ALL n8n operations, use the `n8n` skill:**

```bash
# List workflows
python -m n8n list-workflows

# Get workflow details
python -m n8n get-workflow --id <workflow-id>

# Validate workflow
python -m n8n validate --id <workflow-id>

# Test workflow
python -m n8n dry-run --id <workflow-id> --data-file test.json

# Analyze performance
python -m n8n analyze --id <workflow-id>

# Activate/Deactivate
python -m n8n activate --id <workflow-id>
python -m n8n deactivate --id <workflow-id>
```

**Skill capabilities:**
- Workflow CRUD via n8n API
- Structure validation and testing
- Execution monitoring
- Performance optimization with scoring
- Test suite execution and reporting

**Documentation:** See skill docs at `~/.agents/skills/n8n/SKILL.md` or run `skill info n8n`

**⚠️ DO NOT:**
- Use manual curl commands for n8n API
- Hand-craft workflow JSON without validation
- Create workflows without testing

**Always use the skill for:**
- Workflow creation and updates
- Execution monitoring
- Performance analysis
- Validation before deployment

## Purpose

- This repository is an `n8n` workflow factory for building, testing, and deploying workflow-based automations.
- The current active product is `workflows/po-parser`, which parses purchase-order PDFs and exposes a small FastAPI service for n8n HTTP nodes.
- Agents should optimize for small, targeted edits and preserve existing repository structure.

## New Session Bootstrap

If you are starting fresh in this repository and need to become productive quickly, do this in order:

1. Read this `AGENTS.md` completely.
2. Read root `KNOWLEDGE.md` completely.
3. Read the specific product README before editing product files.
   - For the current primary product, read `workflows/po-parser/README.md`.
4. If the task is about workflow behavior, inspect both:
   - `workflows/po-parser/workflow.json`
   - `workflows/po-parser/service/po_parser_service.py`
5. If the task mentions EVYTRA or customer-specific parsing, also inspect:
   - `workflows/po-parser/tests/test_evytra_profile.py`
   - `workflows/po-parser/tests/fixtures/evytra/extracted-linux.txt`
   - `workflows/po-parser/profiles/evytra.json`
   - `workflows/po-parser/schemas/po-output.schema.json`

Do not start by guessing from old docs or only reading `workflow.json`. The parser service contains customer-profile routing logic and many production issues only make sense when workflow JSON and service code are read together.

## Repository Layout

- `workflows/`: product-specific workflow implementations.
- `workflows/po-parser/workflow.json`: main n8n workflow definition.
- `workflows/po-parser/service/po_parser_service.py`: FastAPI service used by the workflow.
- `workflows/po-parser/tests/`: Python-based test and diagnostic scripts.
- `workflows/po-parser/schemas/`: JSON schema contracts for workflow output.
- `workflows/po-parser/config/`: product metadata and environment-oriented config.
- `scripts/`: documentation for build/deploy scripts; actual JS scripts are not currently present.
- `docs/`: architecture, development, and deployment docs.
- `test-pdfs/`: sample PDF inputs and generated output JSON.

## Rule Files

- No root `AGENTS.md` existed when this file was written.
- No `.cursorrules` file was found.
- No `.cursor/rules/` directory was found.
- No `.github/copilot-instructions.md` file was found.
- If any of those files are added later, treat them as higher-priority repository instructions and update this file to reflect them.

## Environment Expectations

- Node.js: `>=18` per `package.json`.
- Python: docs mention `>=3.9`; `workflows/po-parser/config/product.json` expects `>=3.10`.
- n8n: docs expect a local or reachable `n8n` instance for workflow import and manual testing.
- Optional local services include Ollama and PDF parsing dependencies.

## Server Access

- The n8n server is reachable from this workspace via SSH alias `n8n`.
- Use `ssh n8n` for interactive login from PowerShell.
- SSH key authentication is configured, so normal login does not require a password.
- Verified connectivity command:
  - `ssh n8n "hostname"` -> `prdn8n-virtual-machine`
- Current production parser service path:
  - `/opt/po-parser/po_parser_service.py`
- Current production systemd unit:
  - `po-parser.service`
- Current SMB workflow directories:
  - `/mnt/smb/po_pdfs/incoming`
  - `/mnt/smb/po_pdfs/review`
  - `/mnt/smb/po_pdfs/done`
  - `/mnt/smb/po_pdfs/error`
  - `/mnt/smb/po_pdfs/output`

## Current Production Targets

- Current main workflow ID:
  - `BCPYC0kDhe8s9fVJ`
- Current workflow name:
  - `PO-Parser - 采购订单PDF解析`
- Current parser base URL used by the workflow:
  - `http://10.142.1.135:8765`
- Current n8n base URL:
  - `http://10.142.1.135:5678`

These values are intentionally repeated here so a new session can immediately inspect, validate, or update the production workflow without rediscovering IDs and endpoints.

## Practical Rules For New n8n Work

- For all real n8n operations, use the `n8n` skill first.
- Root `.env.local` stores the live local-only credentials for this workspace.
- Important environment naming mismatch:
  - the repository env file uses `N8N_URL`
  - some local tooling expects `N8N_BASE_URL`
  - map `N8N_URL` to `N8N_BASE_URL` for commands that require it
- Never commit `.env.local` or secrets.
- When updating workflows through the API, send only:
  - `name`
  - `nodes`
  - `connections`
  - `settings`
- On the current server, workflow updates use `PUT /workflows/{id}`, not `PATCH`.

## Production Debugging Shortcuts

- To inspect parser service health:
  - `ssh n8n "systemctl status po-parser --no-pager -n 30"`
  - `ssh n8n "journalctl -u po-parser --no-pager -n 80"`
  - `ssh n8n "curl -sS http://localhost:8765/health"`
- To inspect live workflow executions, use the n8n API and request `includeData=true` when you need node-level evidence.
- For PO-Parser specifically, many failures are only visible in execution node data, not in the top-level execution status.
- If the parser service works but the workflow still fails, inspect the last failed execution before editing code.

## Known Workflow Pitfalls

- `n8n-nodes-base.if` version 2 on the current n8n server can fail unless string conditions include `conditions.options.caseSensitive`.
- Do not force a single `If` node to route `success`, `review`, and `error` in one ambiguous split. Use a small decision tree instead.
- `n8n-nodes-base.set` version 3.4 is strict about value types:
  - arrays such as `warnings` must use type `array`
  - if typed as `object`, upstream side effects may still happen, but the execution can still end in error on the final node
- For PO-Parser, successful `/parse` does not guarantee successful workflow completion. Always verify file movement and the final output node.

## PO-Parser Working Model

- Keep one shared workflow for all customers.
- Put customer-specific parsing logic in `po_parser_service.py`.
- Detect customer profile from extracted text before extraction.
- Prefer deterministic parsing rules for stable layouts.
- Use `review` when extraction is structurally complete but contains business anomalies.
- EVYTRA is the current reference implementation for customer-profile parsing.

## Primary Commands

- Install Node dependencies: `npm install`
- Run configured linter: `npm run lint`
- Run configured Node test command: `npm test`

**n8n operations** — See 📦 Project Skills section above.

## Python Style

- Follow existing Python conventions in `workflows/po-parser/service/` and `workflows/po-parser/tests/`.
- Use `snake_case` for functions, variables, and module filenames.
- Use `PascalCase` for classes and Pydantic models.
- Prefer explicit type hints on function signatures, especially service-layer functions.
- Keep functions focused; split only when logic becomes hard to read.
- Prefer `Path` from `pathlib` for path composition, while tolerating existing `os.path` usage in touched files.
- Preserve UTF-8 behavior where files already contain Chinese text.

## Imports

- Group imports in this order: standard library, third-party, local modules.
- Keep one import per line unless the imported names are tightly related.
- Prefer direct imports over wildcard imports.
- Avoid introducing unused imports; this repository already has a few, so clean up only when touching the file.
- For typing imports, prefer explicit names such as `Optional` and `List` to match current style.

## Formatting

- Use 4 spaces for Python indentation.
- Use 2 spaces for JSON indentation.
- Keep line lengths readable; there is no enforced formatter config, so match surrounding style.
- Preserve existing docstring style when editing an existing file.
- Avoid reformatting entire files unless required for correctness or clarity.

## Naming

- Name workflow nodes by business action, not implementation detail.
- Name schema properties to match business payloads and workflow JSON keys.
- Prefer descriptive names such as `output_dir`, `source_file`, `customer_name`, `scan_directory`.
- Avoid abbreviations unless they are established domain terms like `PDF`, `PO`, `SAP`, `RFC`, or `LLM`.

## Types And Data Contracts

- Preserve schema compatibility with `workflows/po-parser/schemas/po-output.schema.json` unless the task explicitly changes the contract.
- When changing payload shape, update workflow JSON, service code, and schema together.
- In FastAPI code, prefer Pydantic models for request and response contracts.
- When returning JSON-like dicts, keep keys stable and predictable for n8n downstream nodes.

## Error Handling

- Fail fast for missing files, missing directories, and empty PDF content.
- In API code, prefer `HTTPException` with an appropriate status code for request failures.
- In scripts, it is acceptable to print diagnostics and exit early.
- When catching broad exceptions, include enough context for debugging and avoid silently swallowing errors.
- Prefer returning structured error details when a downstream n8n node needs to branch on status.
- Keep warnings separate from hard errors when partial extraction is acceptable.

## External Services

- `OLLAMA_URL` and `OLLAMA_MODEL` are environment-sensitive and should not be hardcoded in new code unless matching an existing local-only script pattern.
- Treat network calls to Ollama, SAP, SMB-backed paths, and n8n as integration points that may be unavailable during local verification.
- If a change depends on external connectivity, state clearly what could not be verified.

## File Safety

- Do not commit secrets, tokens, or private URLs into tracked files unless the user explicitly requests it.
- Prefer environment variables or n8n credentials for sensitive values.
- Sample outputs under `test-pdfs/output/` may contain business data; avoid rewriting them unless needed.

## Documentation Expectations

- Update docs when behavior, commands, or workflow structure materially changes.
- Correct mismatches between docs and code when they are in the area you are touching.
- If you discover a documented script that does not exist, call that out explicitly in your summary.

## Verification Expectations

- Verify the smallest meaningful scope first.
- For workflow-only edits, validate JSON structure and inspect node connections carefully.
- For service edits, run the narrowest relevant Python script or service startup command available.
- For schema-related edits, ensure keys and required fields remain aligned across JSON examples, schema, and code.
- Never claim lint/test/build success unless you actually ran the relevant command.

## Agent Working Style

- Start by reading the specific product directory you are changing.
- Prefer minimal diffs over speculative refactors.
- Preserve unrelated user changes in a dirty worktree.
- If repository instructions and runtime reality conflict, follow runtime reality and mention the discrepancy.
- When in doubt, leave a concise note in your final summary describing assumptions and verification gaps.
