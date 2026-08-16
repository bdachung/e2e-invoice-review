# Azure deployment guide

This guide deploys Invoice Review as one password-protected Azure Container App.
The React frontend and FastAPI API run in the same container and use the same
HTTPS address. Existing Azure OpenAI and Azure Document Intelligence resources
in `rg-invoice-review` are reused.

## What Azure services this deployment uses

| Service | Why it exists | Main cost driver |
| --- | --- | --- |
| Azure Container Apps | Runs the single web/API container with HTTPS ingress. | Allocated vCPU and memory while the replica is idle or processing, plus requests. |
| Container Apps environment | Required network, revision, storage-mount, and logging boundary for the app. | It supports the app; compute is charged through the app's workload. |
| Azure Container Registry (Basic) | Stores the Docker image built by Azure. | Registry tier and stored image size. |
| Azure Database for PostgreSQL Flexible Server | Persists review records, validation, decisions, and selected GL accounts. | Provisioned compute tier, 32 GiB storage minimum, backups, and network egress. |
| Azure Storage + Azure Files | Persists uploaded PDFs/images at `/mnt/data/uploads`. | Stored data, SMB transactions, and transfer. |
| Log Analytics workspace | Stores Container App logs for troubleshooting. | Log ingestion and retention. |
| Azure OpenAI (existing) | Classification, independent review, GL suggestion, and optional correction draft. | Input and output tokens. |
| Azure Document Intelligence (existing) | Layout text and invoice/receipt extraction. | Pages analyzed. |

Current prices depend on subscription, currency, region, and the deployed
OpenAI model. Estimate before deploying with the official pricing pages:

- [Azure Container Apps pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
- [Azure Container Registry pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/)
- [Azure Database for PostgreSQL pricing](https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/)
- [Azure Files pricing](https://azure.microsoft.com/en-us/pricing/details/storage/files/)
- [Azure Monitor / Log Analytics pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/)
- [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Azure Document Intelligence pricing](https://azure.microsoft.com/en-us/pricing/details/document-intelligence/)

The app intentionally runs exactly one replica to keep in-memory WebSocket
progress simple. PostgreSQL, rather than SQLite on the Azure Files mount,
persists review records across revisions. The app does **not** scale to zero:
expect continuing idle Container Apps compute charges. Each processed
document calls Document Intelligence for layout plus one invoice/receipt model,
then Azure OpenAI for classification, independent review, and GL suggestion.
Drafting a supplier correction email makes one extra OpenAI call only when a
reviewer requests it.

## Before you start

1. Install Azure CLI, start Docker Desktop, and sign in:

   ```powershell
   docker version
   az login
   az account set --subscription "Azure subscription 1"
   az group show --name rg-invoice-review --output table
   ```

2. The existing group is in Southeast Asia. Do not remove its existing
   `di-invoice-review` or `invoice-review-foundry-hungbd` resources.

3. Start from the repository root. The deployment script prompts for secrets
   without echoing them, unless you already set the equivalent process
   environment variables. Do not create or commit a production `.env` file.

   The script needs:

   - `AZURE_OPENAI_API_KEY`
   - `AZURE_DOCUMENT_INTELLIGENCE_KEY`
   - `APP_PASSWORD` for the shared login
   - `SESSION_SECRET`, a long random value used to sign login sessions
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_DEPLOYMENT`
   - `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`
   - `POSTGRES_ADMIN_PASSWORD`, a new password for the managed PostgreSQL
     administrator; keep it to rerun the deployment script

## Deploy

Run the repository deployment script:

```powershell
Set-Location D:\projects\e2e-invoice-review
.\scripts\deploy-azure.ps1
```

The script registers required providers, creates supporting resources, builds
the Docker image locally with Docker Desktop, pushes it to ACR, creates or updates the Container App,
and prints the HTTPS URL.

The deployed app is public at its Container Apps HTTPS FQDN but protected by
one shared password. It uses PostgreSQL for review records and Azure Files only
at `/mnt/data/uploads` for source documents. The PostgreSQL connection URL,
AI keys, and login credentials become Container App secrets. The script permits
Azure-hosted resources to reach PostgreSQL; use private networking before a
production rollout with stricter network requirements.

The temporary resolved Container Apps YAML contains secrets only while the
script runs and is removed in its `finally` block. It is never written into
the repository.

## Verify

```powershell
$app = "invoice-review-web"
$group = "rg-invoice-review"
$fqdn = az containerapp show --name $app --resource-group $group --query properties.configuration.ingress.fqdn -o tsv
Invoke-WebRequest "https://$fqdn/health" | Select-Object -ExpandProperty Content
az containerapp logs show --name $app --resource-group $group --follow
```

In the browser, open `https://$fqdn`, confirm an incorrect password is
rejected, sign in, and run a fictional invoice/receipt through the full review
flow. Refresh to confirm the 12-hour session persists. Rerun the deployment
script, then confirm PostgreSQL preserved review history and Azure Files
preserved source files.

The unauthenticated `/health` endpoint remains available for platform probes.
All API routes and processing-progress WebSockets require the signed session.


## Pause and resume between development sessions

To pause without deleting records or uploads, run from the repository root:

```powershell
.\scripts\pause-azure.ps1
```

It deactivates every active Container App revision and stops PostgreSQL compute.
The public app URL is unavailable until you resume it. Azure Files uploads and
PostgreSQL data remain intact.

Resume the same provisioned revision the next day:

```powershell
.\scripts\resume-azure.ps1
```

PostgreSQL starts first; the script then activates the most recently provisioned
Container App revision. Allow a short time for the readiness probe before using
the app.

For the current transition from the failed SQLite deployment, start only
PostgreSQL tomorrow, deploy the corrected application revision, then use normal
resume behavior afterward:

```powershell
.\scripts\resume-azure.ps1 -DatabaseOnly
.\scripts\deploy-azure.ps1
```

This pause does not delete or fully stop Azure Container Registry, Azure Files,
Log Analytics retention, or existing Azure AI resources. Those services can
still incur storage, retention, or pay-per-use charges. Use the targeted cleanup
section only when you want to delete resources permanently.

## Updates, password rotation, and costs

Deploy a new image revision from current source with:

```powershell
.\scripts\deploy-azure.ps1
```

To rotate access, rerun it with a new `APP_PASSWORD` and
`SESSION_SECRET`; changing both invalidates current sessions.

Create a monthly Azure Cost Management budget before sharing the URL. Choose an
amount based on expected document pages, token use, storage, and logging, and
configure notification thresholds. A budget notifies; it does not stop use.
Review Container Apps, ACR, PostgreSQL, Storage, Log Analytics, Document
Intelligence, and OpenAI meters separately in Cost Management.

## Targeted cleanup

These commands remove only resources created by this guide. They deliberately
do **not** remove the existing Document Intelligence or Azure OpenAI resources.

```powershell
$group = "rg-invoice-review"
az containerapp delete --name invoice-review-web --resource-group $group --yes
az containerapp env delete --name cae-invoice-review --resource-group $group --yes
az acr delete --name "<registry-name-printed-by-the-script>" --resource-group $group --yes
az postgres flexible-server delete --name "<postgres-server-name-printed-by-the-script>" --resource-group $group --yes
az storage account delete --name "<storage-name-printed-by-the-script>" --resource-group $group --yes
az monitor log-analytics workspace delete --workspace-name law-invoice-review --resource-group $group --yes
```

Deleting the Storage account permanently removes uploaded files. Deleting the
PostgreSQL server permanently removes review history. Export anything needed
before cleanup.
