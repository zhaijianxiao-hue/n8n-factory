# n8n Workflow Factory Knowledge Base

> This file captures accumulated knowledge from developing, debugging, and operating n8n workflows. 
> **All agents working in this repository MUST read this file first** before touching n8n-related code.

---

## 1. n8n Architecture Overview

### Execution Model

```
Workflow (工作流) - Definition, static
  └── Execution (执行) - One runtime instance
        ├── Node A execution result
        ├── Node B execution result
        ├── Node C execution result
        └── ...
```

**Key insight**: An Execution represents the **entire workflow run**, not a single node. Each execution records all node inputs/outputs.

### Data Flow

- n8n uses **item-based** data flow
- Each node outputs an array of items: `{ "json": {...}, "pairedItem": [...] }`
- Downstream nodes process each item independently (unless in batch mode)
- Microsoft SQL node returns: `[{ "json": { "field1": "value1", ... } }]` directly, NOT `{ "Result": "[...]" }`

---

## 2. n8n Public API (v1.1.1)

### Base URL & Auth

```
Base: http://10.142.1.135:5678/api/v1
Auth: X-N8N-API-KEY header
```

Credentials stored in `.env.local`.

### Workflow Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/workflows` | GET | List workflows (filter: `active`, `tags`, `name`, `projectId`) |
| `/workflows` | POST | Create workflow |
| `/workflows/{id}` | GET | Get workflow definition |
| `/workflows/{id}` | PUT | Update workflow |
| `/workflows/{id}` | DELETE | Delete workflow |
| `/workflows/{id}/activate` | POST | Publish/activate workflow |
| `/workflows/{id}/deactivate` | POST | Deactivate workflow |
| `/workflows/{id}/{versionId}` | GET | Get specific version from history |
| `/workflows/{id}/transfer` | PUT | Transfer to another project |

### Execution Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/executions` | GET | List executions (filter: `status`, `workflowId`) |
| `/executions/{id}` | GET | Get execution details |
| `/executions/{id}?includeData=true` | GET | Get execution with full node data |
| `/executions/{id}` | DELETE | Delete execution record |
| `/executions/{id}/retry` | POST | Retry failed execution |
| `/executions/{id}/stop` | POST | Stop running execution |
| `/executions/stop` | POST | Batch stop executions |

### Critical Limitation

**n8n API does NOT provide workflow execution trigger**. To run a workflow:
1. Add a **Webhook Trigger node** and call its URL
2. Use **Schedule Trigger** for automatic runs
3. Manual trigger in n8n UI

### Workflow Update Payload

When updating workflow via API (`PUT /workflows/{id}`), the payload MUST contain ONLY:
```json
{
  "name": "Workflow Name",
  "nodes": [...],
  "connections": {...},
  "settings": {}
}
```

Including `versionId`, `staticData`, or other fields causes **validation errors**.

Important compatibility note from the PO-Parser EVYTRA rollout:
- The current n8n server in this repository accepts `PUT /workflows/{id}` for workflow updates. Using `PATCH /workflows/{id}` returns `405 PATCH method not allowed`.
- Environment files in this repository use `N8N_URL`, while some local tooling expects `N8N_BASE_URL`. When using the tooling, map `N8N_URL` to `N8N_BASE_URL` explicitly for the process.

---

## 3. n8n Expression Syntax

### Basic Syntax

```
={{ $json.field }}           // Access current item's field
={{ $node["NodeName"].json }}  // Access another node's output
={{ 'Bearer ' + $json.token }} // String concatenation
```

### JSON Serialization

```
={{ JSON.stringify($node["NodeName"].json) }}
```

**WRONG**: `={{ $node["NodeName"].json | JSON.stringify }}` - Pipe operators NOT supported.

### Common Patterns

| Expression | Purpose |
|------------|---------|
| `={{ $json.id }}` | Current item field |
| `={{ $node["SQL查询"].json[0].name }}` | First item from named node |
| `={{ Object.keys($json) }}` | Get all keys |
| `={{ $json.items.map(i => i.id) }}` | Array operations |

### Error Patterns to Avoid

- ❌ `{{ $json | json }}` - No pipe operators
- ❌ `{{ $.json.field }}` - Missing `$` before node reference
- ❌ Unquoted node names with special characters

---

## 4. Workflow Development Patterns

### Customer Profile Parsing Pattern

- For purchase-order PDFs from multiple customers, keep one shared n8n workflow and move customer-specific logic into the parser service.
- Detect customer profile from stable document markers in extracted text before field extraction.
- Prefer deterministic rules first for stable layouts, and reserve LLM extraction for fallback or genuinely ambiguous free text.
- Return `review` instead of `success` when extraction is structurally complete but business anomalies remain, such as mismatched totals or suspicious amount outliers.
- EVYTRA is the first explicit profile in this repository and uses:
  - customer markers: `EVYTRA GmbH`, `Your supplier ID:`, `OrderConfirmation@evytra.com`
  - German number normalization: decimal `,`, thousands `.`
  - header-level normalization for delivery tolerance and long-form note blocks
  - deterministic item-block parsing instead of generic one-shot LLM extraction

### Node Naming Convention

Use **business action names** in Chinese:
- `获取老ERP数据` - not `SQL Query`
- `写入飞书多维表格` - not `HTTP Request`
- `转换数据格式` - not `Code Node`

### Connection Structure

```json
"connections": {
  "NodeA": {
    "main": [
      [{ "node": "NodeB", "type": "main", "index": 0 }]
    ]
  }
}
```

### HTTP Request Node Configuration

For Feishu API calls:
```json
{
  "method": "POST",
  "url": "={{ 'https://open.feishu.cn/open-apis/bitable/v1/apps/' + $json.app_token + '/tables/' + $json.table_id + '/records/batch_create' }}",
  "authentication": "genericCredentialType",
  "genericAuthType": "httpHeaderAuth",
  "headers": {
    "Authorization": "={{ 'Bearer ' + $node['获取飞书Token'].json.token }}"
  },
  "body": "={{ JSON.stringify({ records: $json.records }) }}"
}
```

### If / Set Node Compatibility Notes

- For `n8n-nodes-base.if` version 2 on the current server, string conditions should include `conditions.options.caseSensitive`. Omitting it can fail at runtime with:
  - `Cannot read properties of undefined (reading 'caseSensitive')`
- If you need to route `success`, `review`, and `error`, do not overload a single `If` node with ambiguous branches. Prefer a small two-step decision tree:
  - first `success?`
  - then `review?`
  - otherwise fall through to `error`
- In `n8n-nodes-base.set` version 3.4, arrays must be typed as `array`, not `object`. For PO-Parser outputs:
  - `warnings` should be `array`
  - `error_reason` should be `array` when it carries the parser warnings list
- If a `Set` field is typed incorrectly, n8n can still complete side effects in upstream nodes such as file moves, but the execution itself will end in error on the final output node.

### Scan Endpoint Notes

- `Path.glob('*.pdf')` can behave differently across environments. On Windows it may still match uppercase `.PDF`, while on Linux it will typically be case-sensitive.
- For the PO-Parser `/scan` endpoint, treat the default PDF scan as extension-based and case-insensitive so both `.pdf` and `.PDF` are picked up from `incoming`.
- If scanning appears broken in production, verify the real filename casing before debugging the workflow routing.

### Batch Processing Pattern

For batch operations (e.g., Feishu batch write):
1. Data preparation node: Transform data to batch format
2. Check batch size (Feishu max: 500 records)
3. Split if needed (Loop node or multiple HTTP calls)
4. Error handling per batch

---

## 5. Execution Data Structure

### Get Full Execution Data

```bash
curl -s "http://10.142.1.135:5678/api/v1/executions/{id}?includeData=true" \
  -H "X-N8N-API-KEY: {key}"
```

### Response Structure

```json
{
  "id": "679",
  "status": "success",
  "startedAt": "2026-04-02T11:31:42.169Z",
  "stoppedAt": "2026-04-02T11:31:44.662Z",
  "workflowId": "LQ7ZKNlKz4KCIhv4",
  "data": {
    "resultData": {
      "runData": {
        "NodeName": [{
          "data": { "main": [[{ "json": {...} }]] },
          "executionTime": 1436,
          "source": [...]
        }]
      },
      "lastNodeExecuted": "FinalNodeName"
    }
  }
}
```

### Extract Specific Node Output

```bash
# Get node names
jq '.data.resultData.runData | keys'

# Get node execution time
jq '.data.resultData.runData["NodeName"][0].executionTime'

# Get node output data
jq '.data.resultData.runData["NodeName"][0].data.main[0]'
```

### Execution Status Values

| Status | Meaning |
|--------|---------|
| `success` | Completed successfully |
| `error` | Failed with error |
| `running` | Currently executing |
| `waiting` | Waiting for webhook/trigger |
| `crashed` | System crash |
| `canceled` | User canceled |

---

## 6. Feishu (飞书) Bitable API

### Authentication Flow

1. Get tenant_access_token:
```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
Body: { "app_id": "...", "app_secret": "..." }
Response: { "tenant_access_token": "..." }
```

2. Use in subsequent calls:
```
Header: Authorization: Bearer {tenant_access_token}
```

### Batch Create Records

```
POST https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create

Body: {
  "records": [
    { "fields": { "fieldName": "value" } },
    { "fields": { "fieldName": "value" } }
  ]
}

Max: 500 records per request
```

### Field Types Mapping

| Feishu Type | n8n/JSON Type |
|-------------|---------------|
| Text | string |
| Number | number (send as string works) |
| Date | number (Unix timestamp ms) or formatted string |
| SingleSelect | string (option name) |
| MultiSelect | array of strings |
| Checkbox | boolean |
| URL | { "link": "url", "text": "display" } |
| Attachment | [{ "file_token": "..." }] |

### Response Structure

```json
{
  "code": 0,
  "data": {
    "records": [
      { "id": "recvXXXXXX", "record_id": "recvXXXXXX", "fields": {...} }
    ]
  }
}
```

`code: 0` means success.

---

## 7. Debugging Patterns

### Workflow Not Running

1. Check execution history: `GET /executions?workflowId={id}`
2. Get latest execution details: `GET /executions/{id}?includeData=true`
3. Check `lastNodeExecuted` to find where it stopped
4. Examine node's `data.main` for actual output

### Expression Errors

1. Check syntax: no pipe operators, proper `$` references
2. Test in n8n expression editor (shows errors)
3. Use `JSON.stringify()` for complex objects

### HTTP Node Failures

1. Check execution data for response body
2. Verify authentication headers
3. Check URL construction (use `={{ }}` properly)
4. Test with curl directly

### SQL Node Issues

- SQL node returns **array of objects**, not JSON string
- Each row is a separate n8n item
- Use `$json.field` directly, no parsing needed

---

## 8. Common Gotchas

### Workflow JSON Fields

| Field | Can Update via API? |
|-------|---------------------|
| `name` | ✅ Yes |
| `nodes` | ✅ Yes |
| `connections` | ✅ Yes |
| `settings` | ✅ Yes (must be `{}`) |
| `versionId` | ❌ No - causes validation error |
| `staticData` | ❌ No - causes validation error |
| `id` | ❌ No - generated by n8n |
| `active` | ❌ No - use activate/deactivate endpoints |

### n8n Data Types

- `null` in JSON becomes `undefined` in expression
- Empty string `""` is valid, `null` may cause errors
- Numbers can be sent as strings to some APIs

### Pagination

n8n API uses **cursor-based pagination**:
```json
{
  "data": [...],
  "nextCursor": "MTIzZTQ1Njct..."
}
```

Pass `cursor={nextCursor}` to get next page.

---

## 9. Project-Specific Instances

### n8n Instance

- URL: `http://10.142.1.135:5678`
- API Key: in `.env.local`

### Known Workflow IDs

| Workflow | ID | Purpose |
|----------|-----|---------|
| old-erp-sync | `LQ7ZKNlKz4KCIhv4` | Sync ERP data to Feishu |

### Feishu Bitable

- App ID: in local env or n8n credentials
- App Secret: in `.env.local`
- Bitable App Token: in local env or n8n credentials
- Default Table ID: in local env or n8n credentials

---

## 10. Development Workflow

### Creating New Workflow

1. Design in n8n UI first
2. Export as JSON (download from UI)
3. Save to `workflows/{product}/workflow.json`
4. Create `config/product.json` with metadata
5. Document in `workflows/{product}/README.md`

### Updating Existing Workflow

1. Read current workflow JSON
2. Make targeted edits (preserve node IDs)
3. Push via API: `PUT /workflows/{id}`
4. Verify by fetching: `GET /workflows/{id}`
5. Test execution in UI or via webhook

### Debugging Failed Execution

1. Get execution ID from `GET /executions?workflowId={id}&status=error`
2. Get full data: `GET /executions/{id}?includeData=true`
3. Find failed node from `lastNodeExecuted` and runData
4. Examine error in node's execution data
5. Fix workflow and retry: `POST /executions/{id}/retry`

---

## 11. Workflow Development Best Practices

### Manual-First Development Pattern

When creating a new workflow or making significant changes:

1. **Create in n8n UI first**
   - Build nodes visually in the n8n editor
   - Test all connections and expressions manually
   - Verify the workflow runs successfully

2. **Export the working workflow**
   - Download as JSON from n8n UI (or use API: `GET /workflows/{id}`)
   - Save to `workflows/{product}/tests/testXXX.json` as backup

3. **Convert to API format**
   ```js
   const payload = {
     name: "Workflow Name",
     nodes: workflow.nodes,    // Keep exact structure from UI export
     connections: workflow.connections,  // Preserve all connections
     settings: {}  // API only accepts empty object
   };
   ```

4. **Push via API**
   ```bash
   curl -X PUT /workflows/{id} \
     -H "Content-Type: application/json" \
     -H "X-N8N-API-KEY: {key}" \
     -d '{name, nodes, connections, settings}'
   ```

5. **Preserve node metadata**
   - Keep `id` as UUID strings (generated by n8n)
   - Keep `typeVersion` exactly as exported (e.g., `1.1`, `4.4`, `3.4`)
   - Keep `position` coordinates for visual layout
   - Keep `credentials` references by their `id` and `name`

**Why this pattern?**
- n8n UI ensures correct node structure and field names
- Manual testing catches expression errors before automation
- API payload format is stricter than UI export format
- Avoids subtle bugs from hand-crafted JSON

---

### n8n Node Structure: UI Export vs Hand-Crafted

**Critical differences discovered when creating old-erp-sync workflow:**

| Field | n8n UI Export (CORRECT) | Hand-Crafted (WRONG) |
|-------|------------------------|---------------------|
| `id` | UUID: `"26118397-0c41-4ede-a324-65d9b465fb30"` | Short name: `"manual-trigger"` |
| `type` | Before parameters: `"type": "n8n-nodes-base.manualTrigger"` | After parameters |
| `typeVersion` | Exact version: `1.1`, `4.4`, `3.4` | Rounded: `1`, `4.2`, `3` |
| Field order | `parameters → type → typeVersion → position → id → name` | Random order |
| `credentials` | `{microsoftSql: {id: "...", name: "..."}}` | Sometimes omitted |
| `connections` | All nodes present, exact node names | Missing nodes, typos in names |

**Example: Correct Node Structure (from test006.json)**
```json
{
  "parameters": {
    "operation": "executeQuery",
    "query": "SELECT..."
  },
  "type": "n8n-nodes-base.microsoftSql",
  "typeVersion": 1.1,
  "position": [-256, -80],
  "id": "5b40ee84-0844-49f8-8190-77017ea234e8",
  "name": "Microsoft SQL",
  "credentials": {
    "microsoftSql": {
      "id": "b6fmBvUg9kek5amd",
      "name": "Microsoft SQL account"
    }
  }
}
```

**Common Mistakes to Avoid:**

1. **Node ID format** - Must be UUID, not short names like `"fetch-old-erp-data"`
2. **typeVersion precision** - Microsoft SQL: `1.1` not `1`, HTTP Request: `4.4` not `4.2`
3. **Node name in connections** - Must match exactly (e.g., `"转换数据格式"` not `"数据转换格式"`)
4. **Field ordering** - Follow: parameters, type, typeVersion, position, id, name
5. **Credentials structure** - Include both `id` and `name` references

**Why hand-crafted fails:**
- n8n validates node structure strictly on import
- Missing `typeVersion` or wrong version causes silent failures
- Wrong node name in `$node["..."]` reference causes runtime errors
- API is more strict than UI import

---

### API Payload Format

**What n8n API accepts (PUT /workflows/{id}):**
```json
{
  "name": "Workflow Name",
  "nodes": [...],
  "connections": {...},
  "settings": {}
}
```

**What causes validation errors:**
- ❌ `versionId`, `activeVersionId`, `versionCounter` - internal fields
- ❌ `staticData`, `updatedAt`, `createdAt` - read-only fields
- ❌ `settings` with properties - must be empty `{}`
- ❌ `shared`, `tags`, `activeVersion` - not allowed in payload

---

### Reference: test006.json Structure

**File location:** `workflows/old-erp-sync/tests/test006.json`

This is a manually-created, fully working workflow exported from n8n UI. Use it as the **gold standard** for node structure.

**Key nodes to reference:**

```json
{
  "nodes": [
    {
      "parameters": {},
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [-672, -80],
      "id": "26118397-0c41-4ede-a324-65d9b465fb30",
      "name": "When clicking 'Execute workflow'"
    },
    {
      "parameters": {
        "assignments": {
          "assignments": [
            {
              "id": "09eb3a3b-171c-4ab1-81a8-cb02b9314416",
              "name": "startDate",
              "value": "={{ $now.minus({ days: 1 }).toFormat(\"yyyy/MM/dd\") }}",
              "type": "string"
            }
          ]
        },
        "options": {}
      },
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.4,
      "position": [-464, -80],
      "id": "1895cc8e-42c3-41f1-861f-23ea47d75917",
      "name": "Edit Fields"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "DECLARE @StartDate varchar(20) = '{{ $json.startDate }}'..."
      },
      "type": "n8n-nodes-base.microsoftSql",
      "typeVersion": 1.1,
      "position": [-256, -80],
      "id": "5b40ee84-0844-49f8-8190-77017ea234e8",
      "name": "Microsoft SQL",
      "credentials": {
        "microsoftSql": {
          "id": "b6fmBvUg9kek5amd",
          "name": "Microsoft SQL account"
        }
      }
    },
    {
      "parameters": {
        "jsCode": "const dataDate = $now.minus({ days: 1 }).toFormat('yyyy/MM/dd');..."
      },
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [-48, -80],
      "id": "523f53a0-f7a9-4cb8-a066-840ec84374d1",
      "name": "数据转换格式"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "{...}",
        "options": {}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.4,
      "position": [160, -80],
      "id": "9c259d3f-cb16-427f-b369-2153eebe0a99",
      "name": "HTTP Request"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://open.feishu.cn/open-apis/bitable/v1/apps/.../records/batch_create",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [{
            "name": "Authorization",
            "value": "={{ 'Bearer ' + $json.tenant_access_token }}"
          }]
        },
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($node[\"数据转换格式\"].json) }}",
        "options": {}
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.4,
      "position": [368, -80],
      "id": "62b98715-0df4-4ddf-8917-fc0f7672584a",
      "name": "HTTP Request1"
    }
  ],
  "connections": {
    "When clicking 'Execute workflow'": {
      "main": [[{ "node": "Edit Fields", "type": "main", "index": 0 }]]
    },
    "Edit Fields": {
      "main": [[{ "node": "Microsoft SQL", "type": "main", "index": 0 }]]
    },
    "Microsoft SQL": {
      "main": [[{ "node": "数据转换格式", "type": "main", "index": 0 }]]
    },
    "数据转换格式": {
      "main": [[{ "node": "HTTP Request", "type": "main", "index": 0 }]]
    },
    "HTTP Request": {
      "main": [[{ "node": "HTTP Request1", "type": "main", "index": 0 }]]
    }
  }
}
```

**How to use as template:**
1. Copy entire `nodes` array from test006.json
2. Rename nodes to match your workflow (change `name` field only)
3. Update `parameters` for your use case (keep structure)
4. Rebuild `connections` to match your node names
5. Keep all `id`, `type`, `typeVersion`, `position` unchanged
6. Remove fields not allowed in API payload: `versionId`, `activeVersionId`, etc.

**Critical details to preserve:**
- `typeVersion` for each node type (Set=3.4, MSSQL=1.1, HTTP=4.4, Code=2)
- UUID format for `id` field (don't use short names)
- Exact field order in each node object
- `credentials` structure with both `id` and `name`

---

## 12. Common Pitfalls

### Node Reference Naming in Expressions

When a node uses `$node["NodeName"]` to reference another node's output, the name **must match exactly**.

**Example Bug:**
```json
{
  "name": "写入飞书多维表格",
  "parameters": {
    "jsonBody": "={{ JSON.stringify($node[\"数据转换格式\"].json) }}"
  }
}
```

If the actual node name is `转换数据格式` but the expression references `数据转换格式`, the workflow will fail at runtime with "node not found" error.

**Fix:** Ensure all `$node["..."]` references use the exact current node name:
```json
"jsonBody": "={{ JSON.stringify($node[\"转换数据格式\"].json) }}"
```

**Common when:** Renaming nodes or copying workflows between instances.

---

## 13. Skills & Tools

### n8n Skills Available

- `n8n-code-javascript` - Writing Code node JavaScript
- `n8n-expression-syntax` - Expression syntax validation
- `n8n-node-configuration` - Node configuration guidance
- `n8n-validation-expert` - Workflow validation errors
- `n8n-workflow-patterns` - Architectural patterns

Invoke these skills when working on n8n-specific tasks.

### Project n8n Skill

**Location:** `skills/n8n/`

This project includes a complete n8n skill with:
- Python API wrapper (`scripts/n8n_api.py`)
- Workflow tester (`scripts/n8n_tester.py`)
- Performance optimizer (`scripts/n8n_optimizer.py`)
- API reference (`references/api.md`)

**Usage:**
```bash
python skills/n8n/scripts/n8n_api.py list-workflows
python skills/n8n/scripts/n8n_tester.py test-workflow <id>
```

### API Reference File

Full OpenAPI spec at: `docs/api-1.json`

Contains all endpoints, schemas, and examples.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-02 | Created initial knowledge base from old-erp-sync development |
| 2026-04-02 | Added: Node reference naming must match exactly |
| 2026-04-02 | Added: Manual-First Development Pattern for workflow creation |
| 2026-04-02 | Added: Detailed n8n Node Structure comparison table (UI Export vs Hand-Crafted) |
| 2026-04-02 | Added: API Payload Format validation rules |
| 2026-04-02 | Added: test006.json as golden reference template with full node structure |
| 2026-04-03 | Added: Project n8n skill (skills/n8n/) with Python API wrapper, tester, and optimizer |
