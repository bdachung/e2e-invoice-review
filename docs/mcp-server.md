# Northstar Finance MCP Server — Implementation Summary

This file summarizes the **implemented** MCP server (what was built and how it
behaves). The original requirements and decisions live in
[docs/mcp-design.md](mcp-design.md).

## 1. What it is

The **Northstar Finance MCP server** (`backend/mcp_server/`) is a thin adapter
layer that exposes the existing finance application to AI clients through the
**Model Context Protocol (MCP)**. It contains no finance policy of its own:
every domain decision — document classification, extraction, VAT validation,
totals reconciliation, duplicate/PO checks, GL suggestion, and review state —
is delegated to the existing FastAPI finance application through one
`FinanceAdapter`.

```text
MCP client / AI agent
        │  MCP (stdio or Streamable HTTP)
        ▼
Northstar Finance MCP server   (backend/mcp_server/)
        │  FinanceAdapter  →  DocumentService
        ▼
Existing finance application   (Azure Document Intelligence + Azure OpenAI + SQLite)
```

## 2. Tool surface — the four business-level tools

| Tool | Purpose | Human-gated? |
|---|---|---|
| `process_document(document_ref)` | Runs the full finance review for one already-uploaded document (classify → extract → normalize → independent review → validate VAT/totals/duplicates/PO → GL suggestion) and returns a structured `ReviewResult` with a stable `review_id`. Streams progress while it runs. | No |
| `approve_document(review_id, reviewer_id)` | Approves an existing review. | **Yes** — only after an explicit reviewer action; the LLM may only recommend |
| `reject_document(review_id, reviewer_id, reason)` | Rejects an existing review; the reason is persisted by the app. | **Yes** |
| `draft_supplier_email(review_id, reason?)` | Drafts an unsent supplier-correction email (subject/body); there is no send capability. | No |

`document_ref` is the finance app's document id (a UUID) — the chat host
uploads the file and supplies the reference; the MCP server never handles file
uploads. After processing, `review_id` (equal to `document_ref`) is the stable
handle for the three post-processing tools.

## 3. Design principles

- **No duplicated finance policy.** The MCP layer only translates arguments,
  results, and errors. Tool descriptions steer the model; approval/rejection
  stay behind explicit human actions.
- **Structured results, not free text.** `process_document` returns a typed
  `ReviewResult`: `review_id`, `document_type`, `status`, `fields`,
  `validation` summary, `gl_suggestion`, `conclusion`, and `allowed_actions`.
- **Idempotent processing.** Re-calling `process_document` on an already
  reviewed document returns the existing result without re-running Azure.
- **Coarse-grained surface.** No low-level tools (`extract_supplier`,
  `validate_vat`, …) — those remain inside the finance application.

## 4. Progress notifications

`process_document` can take tens of seconds (Document Intelligence + Azure
OpenAI), so the tool reports ordered MCP progress events through the
`Context` progress mechanism (13 events per run):

```text
1/6 Classifying invoice or receipt        → Document classified
2/6 Extracting document fields            → Fields extracted
3/6 Normalizing fields and provenance     → Fields normalized
4/6 Running independent document review   → Independent review complete
5/6 Validating VAT, totals, duplicates, PO → Validation complete
6/6 Suggesting GL account                 → GL account suggested
6/6 Review complete
```

The Streamable HTTP endpoint is **not** configured with `json_response=True`,
so in-flight progress notifications are preserved.

## 5. Human control and authorization

- Approve/Reject are **human-gated**: the tool descriptions state this, and
  the agent prompt forbids autonomous decisions.
- `reviewer_id` for human actions must be in the trusted list
  (`AppConfig.mcp_reviewer_ids`, default `("maya",)`); anything else returns
  `UNKNOWN_REVIEWER`. The identity is supplied by the trusted host (the app),
  never by the model.
- The finance application's own state transitions still apply (e.g. approval
  requires a clean validation report and a selected GL account).

## 6. Error handling

Domain errors are returned as structured tool results, not transport errors:

| Code | Meaning |
|---|---|
| `DOCUMENT_NOT_FOUND` | Unknown `document_ref` / `review_id` |
| `DOCUMENT_PROCESSING_FAILED` | The pipeline failed for this document |
| `INVALID_REVIEW_STATE` | Invalid transition (e.g. approving an approved review, approval without GL) |
| `UNKNOWN_REVIEWER` | Unauthorized `reviewer_id` |
| `INTERNAL_ERROR` | Unexpected failure (logged with traceback) |

Missing purchase order is a review warning (`po_match: not_available`), not an
error.

## 7. Observability

Every tool call is audit-logged (`invoice_review.mcp.audit`) with:

```text
request_id, tool_name, document_ref/review_id, actor,
started_at, finished_at, latency_ms, status, error_code
```

## 8. Transports

The same server runs over two transports:

```powershell
cd backend

# stdio (local MCP clients, Inspector, and the web chat)
uv run --locked --no-sync python -m mcp_server.server --transport stdio

# Streamable HTTP (stateless, progress-friendly, remote deployment)
uv run --locked --no-sync python -m mcp_server.server --transport streamable-http --host 127.0.0.1 --port 9000
```

The browser cannot speak stdio, so the web chat connects through the FastAPI
app, which hosts the MCP server as a persistent stdio child process (see §10).

## 9. Package layout

```text
backend/mcp_server/
├── __init__.py
├── server.py          # FastMCP construction, tool registration, transports
├── adapter.py         # FinanceAdapter: the only bridge to the finance app
├── audit.py           # structured per-call audit logging
├── schemas/
│   └── results.py     # ReviewResult, ValidationSummary, GlSuggestion, …
└── tools/
    ├── processing.py  # process_document with progress streaming
    ├── review.py      # approve_document, reject_document
    └── email.py       # draft_supplier_email
```

It uses the MCP Python SDK already pinned by the project (`mcp==1.29.0`,
`FastMCP` API) — no new dependency was added.

## 10. How the app uses it

### Minimal app extensions the adapter relies on

- `DocumentRecord.decision_reason` column (additive SQLite migration) so
  rejection reasons are persisted by the app.
- `DocumentService.process_existing(..., progress_callback=...)` forwards
  pipeline progress to both the WebSocket broker and MCP.
- `DocumentService.decide(..., reason=...)` and
  `draft_correction_email(..., reason=...)` accept the reviewer's reason.

### Web chat (frontend + backend)

- `backend/app/chat/bridge.py` spawns the MCP server as a persistent stdio
  child process and serializes MCP calls.
- `backend/app/chat/agent.py` is a pydantic-ai agent (Azure OpenAI, same
  wiring as the classification pipeline) whose only tools are the four MCP
  tools.
- `backend/app/chat/routes.py` exposes the auth-gated WebSocket
  `/api/chat/stream`: `message` events run the agent; `action` events call
  approve/reject/draft **directly** with the trusted reviewer id (never
  through the LLM).
- The React UI (`frontend/src/components/ChatPanel.tsx`) adds a floating chat
  icon that toggles a panel with live progress, an **in-chat upload button**
  (uploads with `auto_process=false` so `process_document` runs the pipeline
  live), and Approve/Reject/Draft-email chips rendered from the `review`
  event's `allowed_actions`.

### Playground scripts (`playground/`)

| Script | Purpose |
|---|---|
| `mcp_tools_list.py` | Inspect the tool surface in-process (no Azure) |
| `mcp_stdio_client.py` | Full stdio demo: process with progress, approve, reject, draft email (Azure) |
| `mcp_http_probe.py` | Starts the server, probes it over Streamable HTTP (Azure optional via `--document-ref`) |
| `_mcp_demo.py` | Shared helpers (sample upload, GL selection, deletion, server env) |

## 11. Verification

```powershell
cd backend
uv run --locked --no-sync ruff check app mcp_server
uv run --locked --no-sync python -m compileall -q app mcp_server

# type check the new modules (0 errors expected)
npx pyright backend/app/chat backend/mcp_server

cd ../frontend
pnpm exec tsc -b --pretty false
pnpm lint
pnpm build
```

End-to-end checks performed in this workspace: tool discovery over stdio and
Streamable HTTP; live `process_document` with 13 ordered progress events;
structured errors (`DOCUMENT_NOT_FOUND`, `UNKNOWN_REVIEWER`,
`INVALID_REVIEW_STATE`); approval after host GL selection; rejection with a
persisted reason; unsent email draft; audit log lines; and the full web-chat
flow (in-chat upload → agent → progress → review chips).

## 12. Acceptance criteria (from the design) — status

- [x] The MCP server starts independently (stdio and Streamable HTTP).
- [x] An MCP client can discover the four finance tools.
- [x] `process_document` accepts a document reference and reuses existing finance functionality.
- [x] Processing progress is observable by an MCP client.
- [x] The final result contains a stable `review_id`.
- [x] Approve/Reject occur only through their explicit tools, with reasons supported.
- [x] Draft Email returns editable text and cannot send an email.
- [x] The MCP layer contains no duplicated finance policy.
- [x] Errors are returned in a predictable form and tool calls are traceable in logs.
- [x] The server is testable locally (Inspector / playground clients).
- [x] The server runs over Streamable HTTP for remote deployment.
