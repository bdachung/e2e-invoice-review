<#
Bootstrap the dedicated Terraform remote-state storage for Invoice Review.

Creates one resource group, one storage account, one blob container, enables
blob versioning and soft delete, and grants the current user Storage Blob Data
Contributor on the state container. No secrets are involved.

Run this yourself in your own terminal (not through the assistant), then run
`terraform init` from infra/terraform.
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-invoice-review-tfstate',
    [string]$StorageAccount = 'stinvoicereviewtfstate',
    [string]$Container = 'tfstate',
    [string]$Location = 'southeastasia',
    [string]$PrincipalId = ''
)

$ErrorActionPreference = 'Stop'

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
}

$subscriptionId = Invoke-Az -- account show --query id -o tsv
if (-not $subscriptionId) {
    throw 'Sign in with az login before bootstrapping remote state.'
}

Invoke-Az -- group create --name $ResourceGroup --location $Location --output none

Invoke-Az -- storage account create `
    --resource-group $ResourceGroup `
    --name $StorageAccount `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    --min-tls-version TLS1_2 `
    --allow-blob-public-access false `
    --output none

Invoke-Az -- storage account blob-service-properties update `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --enable-versioning true `
    --enable-delete-retention true `
    --delete-retention-days 7 `
    --enable-container-delete-retention true `
    --container-delete-retention-days 7 `
    --output none

Invoke-Az -- storage container create `
    --account-name $StorageAccount `
    --name $Container `
    --auth-mode login `
    --output none

if (-not $PrincipalId) {
    $PrincipalId = Invoke-Az -- ad signed-in-user show --query id -o tsv
}

$scope = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Storage/storageAccounts/$StorageAccount/blobServices/default/containers/$Container"
Invoke-Az -- role assignment create `
    --assignee $PrincipalId `
    --role 'Storage Blob Data Contributor' `
    --scope $scope `
    --output none

Write-Host "Remote state storage ready: $StorageAccount/$Container"
Write-Host 'Next: cd infra/terraform; terraform init'
