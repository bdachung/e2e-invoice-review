# GitHub Actions deployment

GitHub Actions builds the Docker image on GitHub's hosted runner, pushes it to
Azure Container Registry, then updates the existing Container App. It does not
use ACR Tasks, which this Azure subscription does not permit.

## One-time setup

From the repository root, run:

```powershell
.\scripts\setup-github-actions.ps1
```

The script uses your signed-in Azure CLI and GitHub CLI to:

1. Create or reuse an Entra application and service principal.
2. Grant it `Contributor` on `rg-invoice-review` and `AcrPush` only on
   the project registry.
3. Create the `production` GitHub environment.
4. Configure a federated OIDC credential restricted to the
   `bdachung/e2e-invoice-review` repository and its `production`
   environment.
5. Store `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and
   `AZURE_SUBSCRIPTION_ID` as GitHub environment secrets.

It never uploads Azure AI keys, the application password, or the session
secret to GitHub. Those remain Container App secrets from the initial
`deploy-azure.ps1` deployment.

## First deploy and future deployments

Run `scripts\deploy-azure.ps1` once to create the Container App, Azure Files
mount, and runtime secrets. Docker Desktop must be running for that initial
deployment.

Commit and push [deploy-container-app.yml](../.github/workflows/deploy-container-app.yml)
to `main`. Later changes to `Dockerfile`, `backend/`, or `frontend/`
automatically build a SHA-tagged image and deploy a new revision. Use
**Actions â†’ Deploy Container App â†’ Run workflow** for a manual deployment.

The workflow uses OIDC and short-lived Azure tokens, not a long-lived Azure
client secret. See [GitHub OIDC for Azure](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)
and [Azure Container Apps GitHub Actions](https://learn.microsoft.com/en-us/azure/container-apps/github-actions).

## Troubleshooting setup

The setup script writes the federated-credential payload to a temporary JSON
file before calling Azure CLI. This avoids PowerShell altering JSON quotes.
If a prior run stopped at that step, rerun the script; it reuses the existing
Entra application and only creates the missing federated credential.
