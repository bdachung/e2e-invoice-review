# Terraform setup for Invoice Review

This page explains the Terraform configuration in `infra/terraform/` from zero:
what Terraform is, what this setup manages, how secrets work, and how to work
with it safely. No prior Terraform experience is needed.

## What Terraform is

Terraform manages Azure resources by **declaring what you want** in text files
instead of clicking through the portal. You describe the target state (a
resource group here, a container app there), and Terraform figures out what
Azure needs to change to get there.

Three places matter:

1. **Configuration** - the `.tf` files. The desired state, checked into git.
2. **State** - a JSON file that remembers what Terraform already created or
   imported and what those resources currently look like. Not committed;
   stored remotely in Azure.
3. **Azure** - the actual resources.

`terraform plan` compares state against configuration and prints what it would
do. `terraform apply` makes those changes. This project uses a **remote state**
backend, so the state file lives in an Azure storage container instead of on
your laptop.

## Why this repo has Terraform

The Invoice Review app was deployed manually with scripts first. This migration
wraps that existing infrastructure in Terraform:

- The real Azure resources were **imported** (adopted, not recreated).
- The configuration was then adjusted until `terraform plan` reported
  "No changes" - meaning Terraform exactly matches what Azure already has.
- From now on, changes to that infrastructure go through Terraform so the
  configuration never drifts from reality.

Application image releases are **not** part of Terraform: CI pushes new image
tags with `az containerapp update`, and Terraform deliberately ignores the
image attribute.

## The layout

```
infra/terraform/
|-- versions.tf              Terraform + AzureRM provider version pins, remote backend
|-- provider.tf              AzureRM provider settings (subscription, CLI auth)
|-- variables.tf             Inputs with defaults + one required local variable
|-- locals.tf                Small local constants (app name)
|-- data.tf                  Read-only lookups (current user/tenant/subscription)
|-- main.tf                  Resource group, Log Analytics, Container Apps env, ACR
|-- storage.tf               Storage account, file share, Container Apps env storage
|-- postgres.tf              PostgreSQL server, database, firewall rule
|-- container_app.tf         The web app: identity, ingress, secrets, env, probes
|-- key_vault.tf             Key Vault + RBAC grants
|-- outputs.tf               Useful values printed after apply (app URL, IDs)
|-- terraform.tfvars.example Template for your local values (no secrets)
|-- terraform.tfvars         Your local copy - git-ignored, never committed
`-- .terraform.lock.hcl      Pinned provider checksums (committed)
```

File by file:

- `versions.tf` pins Terraform to exactly `1.15.9`, the AzureRM provider to
  exactly `4.80.0`, and points at the remote state backend.
- `provider.tf` tells the AzureRM provider which subscription to use and to
  authenticate with your logged-in Azure CLI (`az login`).
- `variables.tf` holds everything you might want to change without editing
  code. Most variables have safe defaults (region, endpoints, paths);
  `key_vault_secrets_officer_object_id` has no default because it is personal.
- `terraform.tfvars` is your personal override file. Copy it from
  `terraform.tfvars.example`. It is git-ignored.
- `main.tf`, `storage.tf`, `postgres.tf`, `container_app.tf`, and
  `key_vault.tf` each group related Azure resources. Every block is a
  `resource "<type>" "<name>"` that Terraform can create, read, update, or
  delete.
- `outputs.tf` prints useful values after an apply, like the app URL.

## What Terraform manages

| Resource | Azure name | Purpose |
| --- | --- | --- |
| Resource group | `rg-invoice-review` | Groups all resources |
| Log Analytics workspace | `law-invoice-review` | Container App logs |
| Container Apps environment | `cae-invoice-review` | Hosts the app (Consumption profile) |
| Container registry | `invoicereview547ea842` | Stores the app images |
| Storage account | `stinvoicereview547ea842` | Backing store for the file share |
| File share | `reviewdata` | Uploaded invoices/receipts (Azure Files) |
| Container App env storage | `reviewdata` | Mounts the share into the app |
| PostgreSQL server | `pg-invoice-547ea842` | Review database |
| PostgreSQL database | `invoicereview` | Schema and review data |
| Firewall rule | `AllowAllAzureServices...` | Azure services may connect (kept as-is) |
| Container App | `invoice-review-web` | The web app itself |
| Key Vault | `kv-invoice-547ea842` | Stores all secret values |
| Role assignments | - | App reads vault; operator writes secrets |

The Azure OpenAI (`invoice-review-foundry-hungbd`) and Document Intelligence
(`di-invoice-review`) resources are **referenced, not managed**: the app only
receives their public endpoints as plain environment variables. A later phase
can adopt those AI resources if desired.

## Secrets

The design rule: **secret values never enter Terraform files, state, git, or
chat.**

- The Key Vault is the single source of truth. It uses Azure RBAC, soft delete
  (7 days), and purge protection.
- Two role assignments:
  - the Container App's system-assigned identity -> `Key Vault Secrets User`
    (can read secrets);
  - you (via `key_vault_secrets_officer_object_id`) -> `Key Vault Secrets
    Officer` (can create and rotate).
- `scripts/seed-keyvault.ps1` prompts for each value with
  `Read-Host -AsSecureString` (nothing is echoed, logged, or written to disk).
  It fetches the ACR admin password automatically and builds `database-url`
  from the PostgreSQL password you enter.
- In `container_app.tf`, secrets are **references**, not values:
  `key_vault_secret_id = ".../secrets/app-password"` with `identity = "System"`.
  The app resolves them when a revision is created.
- The PostgreSQL administrator password is stored in the vault for safekeeping
  but is deliberately **out-of-band**: Terraform neither reads nor rotates it
  (`ignore_changes`), because it is embedded inside `database-url`.

Not secret: the AI endpoints and deployment name (`gpt-4.1-mini`). Knowing a
URL grants no access.

## Remote state

- State lives in `rg-invoice-review-tfstate` / `stinvoicereviewtfstate` /
  container `tfstate` / key `invoice-review.tfstate`.
- `scripts/bootstrap-remote-state.ps1` created that storage once.
- Remote state means everyone running Terraform shares one truth and gets a
  lock during `apply`, so two people cannot fight over Azure.
- Access uses Azure AD (`use_azuread_auth = true`) - no storage keys in the
  repository.

## Day-to-day commands

| Command | What it does |
| --- | --- |
| `az login` | Log into Azure (once per session) |
| `cd infra/terraform` | Enter the configuration |
| `terraform init` | One-time: download provider, connect backend |
| `terraform plan` | Show what would change (safe) |
| `terraform apply` | Apply the changes after reviewing them |
| `terraform plan -detailed-exitcode` | Exit code 0 means no changes |
| `terraform fmt` | Auto-format the files |
| `terraform validate` | Check syntax |
| `terraform import <addr> <id>` | Adopt an existing Azure resource |
| `terraform state list` | Show resources in state |
| `terraform state show <addr>` | Show one resource (may include sensitive values) |

Golden rules:

- **Always read the plan before applying.** `+ create` adds, `~ update`
  changes, `- destroy` deletes.
- Never use `-target` for routine work; it was only needed for bootstrap
  ordering during this migration.
- Never edit Azure by hand and expect Terraform to know. Terraform will detect
  the difference and revert it unless you import the change or `ignore_changes`
  deliberately.

## What happened so far

**Phase 1 - adoption.** Exported each existing resource with
`aztfexport --hcl-only`, wrote clean configuration, imported all 11 resources,
and reconciled details until the plan was empty. Known reconciliation spots:
probe fields (Azure stores 0, the provider requires 1+), PostgreSQL optional
defaults, Log Analytics `local_authentication_enabled`, and storage TLS stays
`TLS1_0` to match reality.

**Phase 2 - Key Vault secrets.** Created the vault, seeded the six secrets,
gave the app a system-assigned identity and read access to the vault, and
switched the app's secrets to Key Vault references. Lessons from the journey:

- Key Vault names are globally unique and limited to 3-24 characters.
- You cannot create a role assignment for a system-assigned identity in the
  same apply that creates the identity (chicken-and-egg), so it must be
  bootstrapped in order.
- `-target` applies pending changes on dependency resources too, which is how
  the app update once raced ahead of the role assignment.
- Key Vault RBAC can take a minute to propagate; re-run the apply if a
  revision fails to provision.

## Do / don't

- Do keep `terraform.tfvars` out of git (it is ignored).
- Do keep secret values only in Key Vault.
- Do review every plan.
- Don't commit `.tfstate` files, `.env`, uploads, or databases.
- Don't paste secrets into chat or issue trackers.
- Don't "clean up" the firewall rule or the storage TLS setting: the
  configuration deliberately preserves current behavior. Security posture
  changes should be deliberate and planned.