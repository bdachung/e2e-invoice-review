# Build-along guide

The complete guided build lives at <https://learn.datalumina.com/docs/invoice-review>.
This local guide records the working slices implemented in this workspace.

## Starter checkpoint

### Outcome

The repository uses a FastAPI backend, a React frontend, and fictional source
documents. The application starts locally before any provider request.

### Commands

```powershell
cd backend
uv sync --locked

cd ../frontend
pnpm install --frozen-lockfile

cd ..
./scripts/dev.ps1 -Check
./scripts/dev.ps1
```

### What you should observe

- `GET http://localhost:8000/health` returns `{"status":"ok"}`.
- `http://localhost:5173` loads Invoice Review.

## Document Intelligence schemas

### Outcome

`DocumentIntelligenceService` maps `prebuilt-invoice` and `prebuilt-receipt`
results into typed Pydantic models. Scalars retain content and confidence, and
the models retain addresses, taxes, payments, and line items.

### Command

```powershell
cd backend
uv run --locked --no-sync python ../playground/document_intelligence_mapping_experiment.py
```

## Maya's review workflow

### Outcome

Maya can upload one PDF, PNG, or JPEG up to 4 MB; view the original document,
prepared fields and line items; make corrections; select an account; and make
an explicit decision. Review history is local and deletable.

### Processing stages

1. Document Intelligence layout text, then Chat Completions classification.
2. `prebuilt-invoice` or `prebuilt-receipt` extraction.
3. Normalization with confidence, provenance, and line items.
4. Independent strict Chat Completions extraction.
5. Deterministic reconciliation: Document Intelligence remains primary and
   Chat values fill only missing values.
6. Pure invoice/receipt validation, then a fixed-catalog Chat GL suggestion.

### Policy behavior

- Invoice rules require supplier/customer identity and VAT IDs, document
  number/date, currency, and total; they validate supplier VAT locally,
  reconcile totals to EUR 0.01, detect duplicates, and warn for missing PO or
  low primary confidence.
- Receipt rules require merchant, transaction date, currency, positive total,
  and VAT total, without invoice-only customer, PO, or due-date requirements.
- Errors yield `needs_review`; warnings allow `ready`. Approval requires zero
  errors and a selected GL code from the local catalog.
- Saving a changed review field marks only that changed field human-supplied
  and re-runs the exact same policy.

### Review controls

- The review UI shows source confidence, line items, validation findings, GL
  selection, and an unsent supplier-correction draft where applicable.
- Approval is disabled until errors are resolved and a valid GL account is
  selected. The backend repeats this policy and returns `409 Conflict` for
  direct invalid requests.
- Progress streams to a local WebSocket and the browser also polls the
  persisted result.

## Azure single-container deployment

### Outcome

The Vite frontend is built into the FastAPI image and served from the same
Container App URL. The deployed demo uses a shared-password session gate,
PostgreSQL for review data, Azure Files for source-document uploads, and
exactly one replica. The backend virtual environment is built at its final
/app/.venv path, so its runtime scripts retain valid Python interpreter paths.
The image also ships the `mcp_server` package (added to the Dockerfile): the
chat bridge spawns it as a stdio child process inside the same container, and
the chat WebSocket is served by the FastAPI app itself.

Schema note: `create_all` only creates missing tables, so additive columns
(`document_review`, `decision_reason`) are applied at startup with an explicit
`ALTER TABLE` migration for both SQLite (`PRAGMA table_info`) and PostgreSQL
(`information_schema.columns`). An existing deployed PostgreSQL therefore
gains the new column automatically on the next revision — no manual SQL
needed.

### Commands

```powershell
az login
az account set --subscription "Azure subscription 1"
./scripts/deploy-azure.ps1
```

### What you should observe

- The script prints one HTTPS Container Apps URL.
- Each manual deployment uses a unique image tag and creates a new revision.
- PostgreSQL stores review data across revisions; Azure Files stores uploads
  only, so SQLite file locks do not affect startup. The deployment script
  URL-encodes the PostgreSQL password and requires TLS.
- The browser shows a password screen before any review data.
- `/health` is available to the platform, while API and WebSocket routes
  require the signed session cookie.
- Documents remain available after a deployment revision because data is
  mounted from Azure Files.

See [deployment.md](deployment.md) for service purpose, cost drivers, current
pricing links, password rotation, updates, and targeted cleanup commands.

### Pause and resume

```powershell
.\scripts\pause-azure.ps1
.\scripts\resume-azure.ps1
```

Pause deactivates the app and stops PostgreSQL without deleting review records
or uploads. Resume includes inactive revisions when selecting the latest
provisioned revision. Use `resume-azure.ps1 -DatabaseOnly` before deploying a corrected
revision when the prior provisioned revision is known to be unhealthy.

## Northstar Finance MCP server

### Outcome

The backend now ships a thin MCP server (`backend/mcp_server/`) that exposes
four business-level tools to an AI chatbot: `process_document`,
`approve_document`, `reject_document`, and `draft_supplier_email`. The server
is an adapter layer only — every domain decision still runs in the existing
finance application (see `docs/mcp-design.md`). Local development uses the
`stdio` transport; remote deployment uses Streamable HTTP with stateless
sessions and in-flight progress notifications.

### Why

A chatbot should be able to run the finance review and let Maya approve,
reject, or request a supplier correction, without reimplementing any policy.
The MCP layer stays small: `FinanceAdapter` translates application results
into structured tool results and maps application errors to stable codes
(`DOCUMENT_NOT_FOUND`, `DOCUMENT_PROCESSING_FAILED`, `INVALID_REVIEW_STATE`,
`UNKNOWN_REVIEWER`). Approve and Reject are human-gated: the tool descriptions
say so, and the server rejects any `reviewer_id` outside the trusted list
(`AppConfig.mcp_reviewer_ids`, default `("maya",)`). Draft Email returns
editable text; there is no send capability. Every tool call is audit logged
with request id, tool, document reference, actor, latency, status, and error.

The design document sketches the MCP Python SDK v2 API; this project pins the
MCP SDK `mcp==1.29.0` (v1, already locked transitively), so the imports were
adapted to its `FastMCP` API as the design instructs.

### App extensions used by the adapter

- `DocumentRecord.decision_reason` column (additive SQLite migration in
  `app/main.py`) so a rejection reason is persisted by the app.
- `DocumentService.process_existing(record_id, progress_callback=None)`
  forwards pipeline progress to both the WebSocket broker and the MCP caller.
- `DocumentService.decide(record_id, decision, reason=None)` and
  `draft_correction_email(record_id, reason=None)` accept the reviewer's
  reason; the correction-email drafter includes it in the prompt.

### Commands

```powershell
cd backend
uv run --locked --no-sync ruff check app mcp_server
uv run --locked --no-sync python -m compileall -q app mcp_server

# stdio (local MCP clients, Inspector)
uv run --locked --no-sync python -m mcp_server.server --transport stdio

# Streamable HTTP (stateless, progress-friendly)
uv run --locked --no-sync python -m mcp_server.server --transport streamable-http --host 127.0.0.1 --port 9000
```

`document_ref` is the finance application's document id: upload a fictional
sample through the app first (`POST /api/documents` or the review UI), then
pass the returned id to `process_document`. Uploads that the app auto-processes
return their existing review; an unprocessed record is processed live by the
MCP call, which is when progress notifications stream.

### What you should observe

- An MCP client discovers exactly the four tools with their input schemas.
- `process_document` streams ordered progress (Classifying → Extracting →
  Normalizing → Independent review → Validating → GL suggestion → Review
  complete) and returns a structured `ReviewResult` with a stable `review_id`,
  fields, validation summary, GL suggestion, conclusion, and allowed actions.
- Calling `process_document` again returns the same review without reprocessing.
- Approve requires `reviewer_id` from the trusted list; it fails until a valid
  GL account is selected, and a decided document cannot be changed.
- Reject persists the reason; Draft Email returns subject/body with the
  optional reason and never sends anything.
- Unknown references return `{"error": "DOCUMENT_NOT_FOUND", ...}`.
- The server logs one `mcp_tool_call` audit line per call with latency.

### Checkpoint

- [ ] `ruff check app mcp_server` is green.
- [ ] Tool discovery returns the four business-level tools.
- [ ] `process_document` streams progress and returns a structured review.
- [ ] Approve/Reject work only through their explicit tools with a trusted reviewer.
- [ ] Rejection reason is persisted; Draft Email never sends.
- [ ] Errors are structured and traceable in the audit log.
- [ ] The server runs over both stdio and Streamable HTTP.

### Playground scripts

Ready-to-run MCP demos live in `playground/` and run from `backend/`:

```powershell
cd backend
uv run --locked --no-sync python ../playground/mcp_tools_list.py      # tool surface, no Azure
uv run --locked --no-sync python ../playground/mcp_stdio_client.py    # full stdio demo (Azure)
uv run --locked --no-sync python ../playground/mcp_http_probe.py      # Streamable HTTP probe
```

`mcp_stdio_client.py` uploads two fictional samples, streams `process_document`
progress, approves after a host GL selection, rejects with a reason, and drafts
an unsent supplier email. `mcp_http_probe.py` starts the server itself and can
process a real document over HTTP with `--document-ref <id>`. Both document
their expected Azure calls in their headers; created records persist in the
local SQLite database for the review UI and can be removed with the
`_mcp_demo.delete_record` helper. If `mcp_http_probe.py` fails with
`426 Upgrade Required`, a stale process already holds the chosen port — use
`--port NNNN` or stop it (`netstat -ano | findstr :9010`, then
`taskkill /PID <pid> /F`).

## Chat box over the MCP server

### Outcome

The review UI now has a floating chat icon (bottom-right) that toggles a chat
panel on and off. The chat connects to the **Northstar Finance MCP server via
stdio, hosted by the FastAPI app**: the app spawns
`python -m mcp_server.server --transport stdio` as a persistent child process
(`app/chat/bridge.py`) and drives it with a pydantic-ai agent
(`app/chat/agent.py`) whose only tools are the four MCP tools. Browser, agent,
and human actions all flow through one WebSocket (`/api/chat/stream`), and the
MCP `process_document` progress notifications stream into the chat.

### Why stdio instead of browser-to-HTTP

The browser cannot speak stdio, so the FastAPI app acts as the MCP client
(stdio) and the browser only talks to the app: one port, existing password
gate, no new frontend dependency, no CORS, and the MCP child process isolates
the blocking Azure work from the FastAPI event loop. Streamable HTTP remains
for external MCP clients (Inspector, Claude Desktop).

### Human control

The agent prompt forbids autonomous approval/rejection. When `process_document`
returns, the backend emits a `review` event and the panel renders **Approve /
Reject / Draft email chips**. Clicking a chip sends an `action` message that
the route executes directly through the bridge with the trusted reviewer id
(`AppConfig.mcp_reviewer_ids`), never through the LLM; the finance app's own
state checks still apply (e.g. approval requires a clean report and a selected
GL account).

### Commands

```powershell
cd backend
uv run --locked --no-sync ruff check app mcp_server
uv run --locked --no-sync uvicorn app.main:app
```

Open http://127.0.0.1:8000, click the chat icon, and either upload an invoice
or receipt directly in the chat (paperclip button) or ask the assistant to
review the current document. Chat uploads use `auto_process=false` so the
agent's `process_document` call runs the pipeline live with progress. Backend
verification: `pyright backend/app/chat backend/mcp_server` reports zero
errors; frontend `tsc -b`, `eslint`, and `vite build` stay green.

### What you should observe

- The chat icon toggles the panel; the header shows "Connected to MCP server"
  and lists the four discovered tools.
- Asking for a review streams the six-stage progress into the chat, then the
  structured review event renders the action chips and the assistant summarizes.
- Approve/Reject/Draft email run as explicit actions; policy errors (e.g.
  "Resolve all validation errors before approval") come back as structured
  `action_result` events.
- Closing the panel cancels the in-flight turn; chat history is ephemeral.

### Checkpoint

- [ ] The chat icon toggles the panel on/off in every view.
- [ ] The chat connects to the MCP server over stdio hosted by FastAPI.
- [ ] `process_document` progress and results stream into the chat.
- [ ] Approve/Reject/Draft email are human-click chips, never LLM-driven.
- [ ] Azure OpenAI chat replies and tool calls consume configured capacity;
      without OpenAI settings the chat reports a clear configuration error.

## Verification

```powershell
cd backend
uv run --locked --no-sync ruff check app
uv run --locked --no-sync python -m compileall -q app

cd ../frontend
pnpm exec tsc -b --pretty false
pnpm lint
pnpm build
```

### Checkpoint

- [ ] The configured API key can call Azure Chat Completions.
- [ ] PDF and image samples complete through layout text plus Chat routing.
- [ ] The review exposes field provenance, comparisons, items, policy findings,
  GL selection, and an unsent correction draft where applicable.
- [ ] A human edit revalidates and approval remains policy-gated.
- [ ] The deployed password gate protects API and WebSocket access.
- [ ] PostgreSQL retains review history across revisions.
- [ ] The Azure Files mount retains uploaded source documents across revisions.

## GitHub Actions image deployment

### Outcome

GitHub-hosted runners build the Docker image, push it to Azure Container
Registry, and update the existing Container App. OIDC grants short-lived Azure
access without copying AI keys or the shared app password to GitHub.

### Command

```powershell
./scripts/setup-github-actions.ps1
```

### What you should observe

- The script creates/reuses the Entra deployment identity, scoped Azure roles,
  federated GitHub credential, and GitHub `production` environment.
- A push to `main` runs the checked-in workflow and deploys a SHA-tagged
  image revision.
- Initial Container App provisioning remains `deploy-azure.ps1`; the GitHub
  workflow is used for future image deployments.

See [github-actions.md](github-actions.md) for the full flow.

## README architecture visuals

### Outcome

The repository README presents two separate visual overviews: the AI workflow
first, followed by the system architecture.

### Checkpoint

- [ ] The README renders `docs/ai_workflow.png` under **AI Workflow**.
- [ ] The README renders `docs/system_architecture.jpg` under **System Architecture**.

## Project-facing README

### Outcome

The README presents Invoice Review as a complete project rather than a learner
starter. It retains the tutorial link as build context while describing the
application's AI-assisted review workflow, deterministic policy controls, and
Azure deployment.

### Checkpoint

- [ ] The README has no learner-branch or starter-only instructions.
- [ ] The tutorial link remains available as a reference.

## README installation and verification

### Outcome

The README's installation section uses the lockfile-enforced backend and
frontend commands. Its verification section now states what each command
checks and includes backend compilation in addition to Ruff, TypeScript,
ESLint, and the production build.

### Checkpoint

- [ ] The README uses `uv sync --locked` and `pnpm install --frozen-lockfile`.
- [ ] The README verification commands match the project scripts and backend
  tooling.

## README local startup

### Outcome

The README documents one-command local startup scripts for PowerShell and Bash.
Each starts the FastAPI backend and Vite frontend together and stops both when
the user presses `Ctrl+C`. `dev.ps1 -Check` and `dev.sh -Check` run the
documented verification suite (backend Ruff + compile, frontend tsc + eslint +
build) and then exit; without the flag they start the servers. Both scripts
pre-check the ports and launch the frontend with pnpm when it is on PATH,
otherwise the already-installed Vite binary via Node, and finally Corepack, so
they run without a global pnpm installation.

### Commands

```powershell
.\scripts\dev.ps1
```

```bash
bash ./scripts/dev.sh
```

### Checkpoint

- [ ] The frontend is available at `http://127.0.0.1:5173`.
- [ ] The backend is available at `http://127.0.0.1:8000`.

## README library installation

### Outcome

The README explicitly instructs users to install both backend Python libraries
and frontend JavaScript libraries before starting the application.

### Checkpoint

- [ ] `uv sync --locked` installs backend libraries from `uv.lock`.
- [ ] `pnpm install --frozen-lockfile` installs frontend libraries from
  `pnpm-lock.yaml`.
