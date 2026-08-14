# Build-along guide

The complete guided build lives at <https://learn.datalumina.com/docs/invoice-review>. This local guide records the first checkpoint represented by the `main` branch.

## Starter outcome

The repository installs reproducibly, starts a minimal FastAPI service and React interface, and includes the business brief plus fictional source documents.

## Why this boundary exists

The starter removes the completed workflow while preserving every prerequisite needed to build it. You begin with the user, the source documents, and explicit service boundaries instead of reverse-engineering a finished application.

## Commands

```bash
cd backend
uv sync --locked

cd ../frontend
pnpm install --frozen-lockfile

cd ..
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
./scripts/dev.sh --check
./scripts/dev.sh
```

## Important locations

- `docs/client-brief.md`: the recurring finance problem and definition of done
- `docs/architecture.md`: the intended boundaries and data flow
- `samples/`: the fictional evaluation corpus and manifest
- `backend/app/main.py`: the initial API boundary
- `frontend/src/App.tsx`: the initial interface boundary

## What you should observe

- `GET http://localhost:8000/health` returns `{"status":"ok"}`.
- `http://localhost:5173` shows the Invoice Review starter screen.
- No Azure request occurs at this checkpoint.

## Checkpoint

- [ ] Locked backend and frontend installs succeed.
- [ ] Backend lint passes.
- [ ] Frontend type-check, lint, and production build pass.
- [ ] `./scripts/dev.sh --check` reports that Invoice Review is ready to start.
- [ ] The health endpoint and starter screen load locally.

Continue with the [online tutorial](https://learn.datalumina.com/docs/invoice-review).

## Document Intelligence schema exploration

### Outcome

`DocumentIntelligenceService` maps Azure's prebuilt invoice and receipt results
into Pydantic `InvoiceExtraction` and `ReceiptExtraction` models. Each extracted
value preserves its typed value, source content, and Azure confidence; the invoice
and receipt packages also retain provider-specific addresses, items, tax details,
and payment fields.

### Why

Document Intelligence field names and result shapes differ between invoices and
receipts. Dedicated mapping modules preserve Azure evidence at the extraction
boundary while `invoice_to_manifest_view` and `receipt_to_manifest_view` expose
the small normalized view needed by the fictional corpus and later policy layer.

### Commands

```bash
cd backend
uv run --locked --no-sync python ../playground/document_intelligence_mapping_experiment.py
```

### What you should observe

The command analyzes the fictional invoice and Dutch fuel receipt, prints their
Pydantic JSON models, and saves them as `playground/sample_invoice_model.json`
and `playground/sample_receipt_model.json`.

### Checkpoint

- [ ] Azure invoice fields map into the `Invoice` schema.
- [ ] Azure receipt fields map into the `Receipt` schema.
- [ ] Both saved playground results serialize as JSON.
## Azure OpenAI service exploration

### Outcome

`AzureOpenAIService` creates an OpenAI Responses API client from the local Azure
endpoint, API key, and `AZURE_OPENAI_DEPLOYMENT`. Its `generate_text()` method
returns the model's aggregated text output without exposing credentials.

### Why

Keeping the deployment selection and client construction in one class creates a
small, reusable boundary before the later structured document-review adapter is
introduced.

### Commands

```bash
cd backend
uv run --locked --no-sync python ../playground/azure_openai_sample.py
```

### What you should observe

The configured Azure OpenAI deployment answers the one-sentence prompt. The
same safe call is available through `python test.py` from `backend`.

### Checkpoint

- [ ] The Azure OpenAI deployment is loaded from `AZURE_OPENAI_DEPLOYMENT`.
- [ ] A Responses API call returns plain text through `AzureOpenAIService`.
## Azure OpenAI document-classification pipeline

### Outcome

`DocumentClassificationPipeline` uses Pydantic AI native structured output to
select either the `invoice` or `receipt` extraction route for a PDF, PNG, or JPEG.
It constructs an Azure Responses API model from the local endpoint, API key, and
`AZURE_OPENAI_DEPLOYMENT`; the result is a validated Pydantic model, not parsed
free-form text.

### Why

Document Intelligence uses separate prebuilt invoice and receipt models. This
small routing step determines which extraction model to invoke without adding a
custom Document Intelligence classifier or training dataset.

### Commands

```bash
cd backend
uv run --locked --no-sync python ../playground/document_classification_pipeline.py
```

### What you should observe

The fictional invoice prints `{"document_type": "invoice"}` and the Dutch fuel
receipt prints `{"document_type": "receipt"}`.

### Checkpoint

- [ ] Pydantic AI returns validated structured invoice/receipt routing output.
- [ ] The pipeline accepts local PDF, PNG, and JPEG financial documents.

## Python workspace imports

The root `pyrightconfig.json` and `.vscode/settings.json` declare `backend/` as
the import root and select its locked virtual environment. Pylance can therefore
resolve `from app...` in the playground without local `sys.path` changes. Reload
the VS Code window after pulling these workspace settings; integrated terminals
also receive `PYTHONPATH=backend` so **Run Python File** works for playground
scripts.
