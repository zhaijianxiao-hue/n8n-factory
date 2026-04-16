# Metal Price Sync Design

> Scope: add a new `workflows/metal-price-sync` product that runs daily in n8n, calls a dedicated local Python price service, validates normalized gold and copper prices, and writes the result to SAP through a customer-provided HTTP interface.

## Goal

Build a daily metal price synchronization flow that fetches one gold price and one copper price, normalizes them into a stable payload, and writes them to SAP only when both prices are present and valid.

## Current State

- The repository already supports product-specific workflow directories under `workflows/`.
- `workflows/po-parser` is the current primary product and already establishes the pattern of pairing n8n with a local Python service.
- `workflows/old-erp-sync` is a useful structural reference for a standalone sync-style workflow product.
- There is no existing `metal-price-sync` product, service, workflow, schema, or test set in the repository.
- The SAP write contract for this new flow is still unknown. Endpoint, method, authentication, headers, request body shape, and response examples have not been provided yet.

## Business Requirements

- Run automatically every day at `02:00`.
- Fetch prices from these fixed V1 sources:
  - Gold: `http://www.huangjinjiage.cn/quote/119023.html`
  - Copper: `https://www.jinritongjia.com/hutong/`
- Use a dedicated local Python service to fetch and normalize source data.
- Keep orchestration, validation branching, SAP mapping, SAP write, and failure handling in n8n.
- Do not merge this work into `po-parser`.
- Deploy the new service on the same machine as `po-parser`, but as a separate process on port `8766`.
- If either gold or copper is missing, the workflow must fail and must not write anything to SAP.
- V1 does not use browser automation for copper extraction.
- The workflow shape should remain:
  - `定时触发`
  - `获取金铜价格`
  - `检查抓取结果`
  - `转换 SAP 请求体`
  - `写入 SAP`
  - `检查 SAP 返回`
  - `失败处理`

## Data Source Findings

### Gold Source

- The gold page returns usable HTML content directly.
- The required price can be extracted with a normal HTTP request and HTML parsing.
- V1 should use a deterministic parser based on the stable page structure rather than browser execution.

### Copper Source

- The copper page does not expose the final price clearly in the initial HTML payload.
- The visible page content is populated by JavaScript.
- The observed page scripts include:
  - `https://www.jinritongjia.com/js/j.js`
  - `https://www.jinritongjia.com/js/hutong.js`
- V1 should identify and call the underlying HTTP data source directly if possible.
- V1 should not depend on Playwright, Selenium, or any other browser automation layer.

### AkShare Decision

- AkShare was evaluated and rejected as the primary V1 integration.
- Gold-related retrieval appeared usable, but copper-related retrieval was unstable in testing.
- Because the flow needs predictable daily production behavior, V1 should use direct website extraction instead of AkShare.

## Architecture

### 1. One workflow, one helper service

The product should be implemented as a new standalone workflow product under `workflows/metal-price-sync`. It should follow the same broad architectural style as `po-parser`, but without sharing runtime code or ports.

The design intentionally separates responsibilities:

- n8n handles schedule, branching, SAP mapping, SAP write, and operational error routing.
- The Python service handles source fetching, parsing, normalization, and service-level diagnostics.

### 2. Independent local service boundary

The Python service should run as its own process on the same host as `po-parser` using port `8766`. It must not write to SAP directly. Its only job is to return a normalized API response that n8n can validate and transform.

This keeps the service small and deterministic while leaving system integration logic in the workflow layer where retries, credentials, and branching are easier to manage.

### 3. Strict V1 completeness rule

V1 treats the daily payload as atomic. A run is only valid if both target metals are present and parse cleanly.

- If gold is missing, fail.
- If copper is missing, fail.
- If both are present but one is malformed, fail.
- If the Python service returns failure or partial status, n8n must route to `失败处理` and must not call SAP.

This avoids partial writes and keeps downstream SAP state consistent until a richer business rule is explicitly approved.

## Workflow Design

### n8n Node Responsibilities

#### `定时触发`

- Runs daily at `02:00`.
- Uses the server timezone configured for the deployment host.
- Starts exactly one end-to-end sync attempt per schedule tick.

#### `获取金铜价格`

- Calls the local Python service endpoint for the latest normalized prices.
- Expects a JSON response that includes service status plus both metal records.
- Should fail fast on connection errors, timeouts, or non-2xx responses.

#### `检查抓取结果`

- Verifies that the service returned a success status.
- Verifies that both gold and copper records exist.
- Verifies that required normalized fields are populated.
- Blocks SAP write on any missing or invalid data.

#### `转换 SAP 请求体`

- Maps the normalized service payload to the final SAP request body.
- Applies SAP-specific field names only in the workflow layer.
- Must remain easy to adjust once the real SAP contract is provided.

#### `写入 SAP`

- Sends the mapped payload to the SAP HTTP interface.
- Uses n8n-managed credentials or headers rather than embedding secrets in code.
- Should remain isolated from scraping logic.

#### `检查 SAP 返回`

- Interprets SAP success and failure responses.
- Routes to success only when the response matches the agreed success contract.
- Routes all other cases to the failure path.

#### `失败处理`

- Records or emits enough error context for operators to diagnose the run.
- Should capture whether the failure came from service fetch, validation, payload mapping, transport, or SAP rejection.
- Should be written so future retry or alerting steps can be added without changing the upstream parsing contract.

## Service API Design

The helper service should expose a minimal HTTP API.

### `GET /health`

Purpose:
- Provide a lightweight health check for deployment and operations.

Response shape:

```json
{
  "status": "ok",
  "service": "metal-price-sync",
  "port": 8766
}
```

### `GET /prices/latest`

Purpose:
- Fetch, parse, and normalize the latest gold and copper prices in one call.

Response shape:

```json
{
  "status": "success",
  "fetched_at": "2026-04-15T02:00:00Z",
  "source_status": {
    "gold": "success",
    "copper": "success"
  },
  "prices": {
    "gold": {
      "metal_code": "gold",
      "source_url": "http://www.huangjinjiage.cn/quote/119023.html",
      "price": 761.23,
      "currency": "CNY",
      "unit": "g",
      "price_date": "2026-04-15",
      "raw_text": "optional source snippet"
    },
    "copper": {
      "metal_code": "copper",
      "source_url": "https://www.jinritongjia.com/hutong/",
      "price": 72850.0,
      "currency": "CNY",
      "unit": "t",
      "price_date": "2026-04-15",
      "raw_text": "optional source snippet"
    }
  },
  "warnings": []
}
```

Failure shape:

```json
{
  "status": "error",
  "fetched_at": "2026-04-15T02:00:00Z",
  "source_status": {
    "gold": "success",
    "copper": "missing"
  },
  "prices": {
    "gold": {
      "metal_code": "gold",
      "source_url": "http://www.huangjinjiage.cn/quote/119023.html",
      "price": 761.23,
      "currency": "CNY",
      "unit": "g",
      "price_date": "2026-04-15"
    },
    "copper": null
  },
  "warnings": [],
  "errors": [
    {
      "source": "copper",
      "code": "PRICE_NOT_FOUND",
      "message": "Copper price could not be extracted"
    }
  ]
}
```

## Normalization Rules

- Return one top-level record containing both metals for the run.
- Normalize metal identity as stable lowercase codes: `gold`, `copper`.
- Normalize `price` as a numeric field, not a formatted string.
- Normalize `currency` as an explicit code when the source or business context makes it unambiguous.
- Normalize `unit` into a stable business-facing unit per metal.
- Normalize `price_date` to `YYYY-MM-DD`.
- Keep `source_url` on each record for traceability.
- Allow `raw_text` or equivalent source evidence for debugging, but keep it optional in downstream SAP mapping.

## Parsing Strategy

### Gold Parsing

- Use a simple HTTP client such as `requests` or `httpx`.
- Parse the returned HTML with a deterministic selector or text rule.
- Keep the extraction logic explicit and easy to adjust if the page structure changes.
- Treat multiple conflicting candidates as a parsing error rather than silently choosing one.

### Copper Parsing

- Start from normal HTTP inspection of the page and referenced scripts.
- Identify the underlying data endpoint or embedded payload used to populate the visible price.
- Call that endpoint directly from the Python service if it is stable enough for server-side use.
- If the endpoint cannot be derived reliably, stop short of browser automation in V1 and return a controlled extraction error instead of adding a headless browser dependency.

## Failure Handling

### Service-level failures

- Network timeout to source site.
- HTML or payload structure drift.
- Missing price field.
- Conflicting candidate values.
- Unexpected response encoding or content type.

These should produce `status = error` from the service with source-specific error details.

### Workflow-level failures

- Service unavailable.
- Invalid service response shape.
- Missing required normalized fields.
- SAP mapping failure.
- SAP transport error.
- SAP business rejection.

These should route to `失败处理` and should not produce a partial SAP write.

## Deployment And Configuration

- Create a new product directory at `workflows/metal-price-sync/`.
- Run the service as a separate local process from `po-parser`.
- Bind the service to port `8766`.
- Keep environment-driven configuration for:
  - service host and port
  - request timeouts
  - user agent if needed
  - optional source-specific tuning values
  - SAP target settings on the n8n side
- Keep secrets out of tracked files.
- Use n8n credentials or environment variables for SAP authentication.

## Security And Operational Notes

- The Python service should not own SAP credentials.
- The Python service should expose only the minimal endpoints needed for operations.
- Source fetching should use explicit timeouts so the scheduled workflow cannot hang indefinitely.
- Logs should distinguish source-site extraction problems from SAP integration problems.
- Because this flow runs on the same host as `po-parser`, deployment docs should make the separate port and process boundary explicit.

## File Structure Proposal

### New product files

- `workflows/metal-price-sync/README.md`
  - product overview, local run steps, deployment notes
- `workflows/metal-price-sync/workflow.json`
  - n8n workflow definition
- `workflows/metal-price-sync/config/product.json`
  - product metadata and runtime expectations
- `workflows/metal-price-sync/config/env.example`
  - non-secret configuration example
- `workflows/metal-price-sync/service/metal_price_service.py`
  - FastAPI service exposing `/health` and `/prices/latest`
- `workflows/metal-price-sync/tests/`
  - service parser and normalization tests

### Supporting documentation updates

- `KNOWLEDGE.md`
  - add any durable n8n or source-extraction discoveries made during implementation

## Testing Strategy

### Service tests

- Unit test gold HTML parsing against saved sample input.
- Unit test copper payload parsing against saved sample input.
- Unit test normalization rules for both metals.
- Unit test the strict failure case when one metal is missing.
- Unit test service response shapes for success and error payloads.

### Workflow checks

- Validate workflow JSON structure before import or deployment.
- Verify the decision path blocks SAP writes when the service returns partial or error results.
- Verify the SAP mapping node can be updated without changing service output.
- Once SAP details exist, test success and rejection response handling explicitly.

### Integration limits

- Source websites may change or block requests, so local tests should use saved fixtures where possible.
- SAP integration cannot be fully verified until the SAP contract and reachable endpoint are provided.

## Open Inputs Required From SAP Side

Implementation can start on the scraper service and workflow skeleton, but production-ready SAP write behavior still depends on these missing inputs:

- SAP endpoint URL.
- HTTP method.
- Authentication scheme.
- Required headers.
- Request body example.
- Success response example.
- Failure response example.
- Final field mapping from normalized metal payload to SAP table fields.

## Decisions Locked For V1

- Separate `metal-price-sync` product.
- Separate local Python service.
- Same machine as `po-parser`.
- Different process and port.
- Port `8766`.
- n8n owns SAP integration.
- Python service does not write SAP.
- Both metals required for a valid run.
- No browser automation for copper in V1.