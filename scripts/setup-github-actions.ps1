<#
Configure passwordless GitHub Actions deployment through Azure OIDC.
This script creates or reuses one Entra application, limits its Azure roles,
creates a GitHub environment, and stores only OIDC identifiers in GitHub.
#>
[CmdletBinding()]
param(
    [string]$Repository = 'bdachung/e2e-invoice-review',
    [string]$Branch = 'main',
    [string]$GitHubEnvironment = 'production',
    [string]$ResourceGroup = 'rg-invoice-review',
    [string]$ContainerAppName = 'invoice-review-web',
    [string]$ApplicationDisplayName = 'github-invoice-review-deploy'
)

$ErrorActionPreference = 'Stop'

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
}

function Invoke-Gh {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & gh @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI command failed: gh $($Arguments -join ' ')"
    }
}

Invoke-Gh -- auth status

$subscriptionId = Invoke-Az -- account show --query id -o tsv
$tenantId = Invoke-Az -- account show --query tenantId -o tsv
$unique = ($subscriptionId -replace '-', '').Substring(0, 8).ToLowerInvariant()
$registryName = "invoicereview$unique"
$registryId = Invoke-Az -- acr show --name $registryName --resource-group $ResourceGroup --query id -o tsv
$resourceGroupScope = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup"

$appId = Invoke-Az -- ad app list --display-name $ApplicationDisplayName --query '[0].appId' -o tsv
if (-not $appId) {
    $appId = Invoke-Az -- ad app create --display-name $ApplicationDisplayName --query appId -o tsv
}

$servicePrincipalId = Invoke-Az -- ad sp list --filter "appId eq '$appId'" --query '[0].id' -o tsv
if (-not $servicePrincipalId) {
    Invoke-Az -- ad sp create --id $appId --output none
    Start-Sleep -Seconds 5
    $servicePrincipalId = Invoke-Az -- ad sp list --filter "appId eq '$appId'" --query '[0].id' -o tsv
}
if (-not $servicePrincipalId) {
    throw 'The Azure service principal was not available after creation. Run the script again.'
}

function Ensure-RoleAssignment([string]$Role, [string]$Scope) {
    $existing = Invoke-Az -- role assignment list --assignee-object-id $servicePrincipalId --scope $Scope --query "[?roleDefinitionName=='$Role'].id | [0]" -o tsv
    if (-not $existing) {
        Invoke-Az -- role assignment create --assignee-object-id $servicePrincipalId --assignee-principal-type ServicePrincipal --role $Role --scope $Scope --output none
    }
}

Ensure-RoleAssignment 'Contributor' $resourceGroupScope
Ensure-RoleAssignment 'AcrPush' $registryId

$federatedCredentialName = "github-$GitHubEnvironment"
$existingCredential = Invoke-Az -- ad app federated-credential list --id $appId --query "[?name=='$federatedCredentialName'].name | [0]" -o tsv
if (-not $existingCredential) {
    $credential = @{
        name = $federatedCredentialName
        issuer = 'https://token.actions.githubusercontent.com'
        subject = "repo:${Repository}:environment:${GitHubEnvironment}"
        audiences = @('api://AzureADTokenExchange')
    } | ConvertTo-Json -Compress
    $credentialPath = Join-Path ([IO.Path]::GetTempPath()) "github-oidc-$([guid]::NewGuid()).json"
    try {
        [IO.File]::WriteAllText($credentialPath, $credential, [Text.UTF8Encoding]::new($false))
        Invoke-Az -- ad app federated-credential create --id $appId --parameters "@$credentialPath" --output none
    }
    finally {
        Remove-Item -LiteralPath $credentialPath -Force -ErrorAction SilentlyContinue
    }
}

Invoke-Gh -- api --method PUT "repos/$Repository/environments/$GitHubEnvironment" | Out-Null
Invoke-Gh -- secret set AZURE_CLIENT_ID --repo $Repository --env $GitHubEnvironment --body $appId
Invoke-Gh -- secret set AZURE_TENANT_ID --repo $Repository --env $GitHubEnvironment --body $tenantId
Invoke-Gh -- secret set AZURE_SUBSCRIPTION_ID --repo $Repository --env $GitHubEnvironment --body $subscriptionId

$existingApp = Invoke-Az -- containerapp list --resource-group $ResourceGroup --query "[?name=='$ContainerAppName'].name | [0]" -o tsv
Write-Host "GitHub Actions OIDC is configured for $Repository."
if (-not $existingApp) {
    Write-Warning "The Container App does not exist yet. Run scripts\deploy-azure.ps1 once before the workflow deploys an image."
}
Write-Host "Push the checked-in workflow to $Branch to enable automatic deployments."
