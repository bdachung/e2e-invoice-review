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
