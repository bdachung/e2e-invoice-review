<#
Deploy the single-container, password-protected Invoice Review demo to Azure.
Secrets are read from process environment variables or requested without echoing.
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-invoice-review',
    [string]$Location = 'southeastasia',
    [string]$AppName = 'invoice-review-web',
    [string]$EnvironmentName = 'cae-invoice-review',
    [string]$WorkspaceName = 'law-invoice-review',
    [string]$StorageShareName = 'reviewdata',
    [string]$PostgresAdminUser = 'invoiceadmin',
    [string]$PostgresDatabaseName = 'invoicereview'
)

$ErrorActionPreference = 'Stop'

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed. Check the command output above."
    }
}

function Get-DeploymentSecret([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ($value) { return $value }

    $secureValue = Read-Host -Prompt "Enter $Name" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Escape-YamlValue([string]$Value) {
    return $Value.Replace('\', '\\').Replace('"', '\"')
}

$subscriptionId = Invoke-Az -- account show --query id -o tsv
if (-not $subscriptionId) { throw 'Sign in with az login before deploying.' }
$unique = ($subscriptionId -replace '-', '').Substring(0, 8).ToLowerInvariant()
$registryName = "invoicereview$unique"
$storageName = "stinvoicereview$unique"
$postgresServerName = "pg-invoice-$unique"
$imageTag = "manual-$([DateTime]::UtcNow.ToString('yyyyMMddHHmmss'))"
$acrImage = "${registryName}.azurecr.io/$($AppName):$imageTag"
$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

$openAiKey = Get-DeploymentSecret 'AZURE_OPENAI_API_KEY'
$documentIntelligenceKey = Get-DeploymentSecret 'AZURE_DOCUMENT_INTELLIGENCE_KEY'
$appPassword = Get-DeploymentSecret 'APP_PASSWORD'
$sessionSecret = Get-DeploymentSecret 'SESSION_SECRET'
$openAiEndpoint = Get-DeploymentSecret 'AZURE_OPENAI_ENDPOINT'
$openAiDeployment = Get-DeploymentSecret 'AZURE_OPENAI_DEPLOYMENT'
$documentIntelligenceEndpoint = Get-DeploymentSecret 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
$postgresAdminPassword = Get-DeploymentSecret 'POSTGRES_ADMIN_PASSWORD'

Invoke-Az -- provider register --namespace Microsoft.App --wait
Invoke-Az -- provider register --namespace Microsoft.OperationalInsights --wait
Invoke-Az -- provider register --namespace Microsoft.ContainerRegistry --wait
Invoke-Az -- provider register --namespace Microsoft.DBforPostgreSQL --wait

Invoke-Az -- acr create --resource-group $ResourceGroup --name $registryName --sku Basic --location $Location --output none
Invoke-Az -- acr update --resource-group $ResourceGroup --name $registryName --admin-enabled true --output none
$registryCredentials = Invoke-Az -- acr credential show --name $registryName --query '{username:username,password:passwords[0].value}' -o json | ConvertFrom-Json

Invoke-Az -- monitor log-analytics workspace create --resource-group $ResourceGroup --workspace-name $WorkspaceName --location $Location --output none
$workspaceId = Invoke-Az -- monitor log-analytics workspace show --resource-group $ResourceGroup --workspace-name $WorkspaceName --query customerId -o tsv
$workspaceKey = Invoke-Az -- monitor log-analytics workspace get-shared-keys --resource-group $ResourceGroup --workspace-name $WorkspaceName --query primarySharedKey -o tsv
$existingEnvironment = Invoke-Az -- containerapp env list --resource-group $ResourceGroup --query "[?name=='$EnvironmentName'].name | [0]" -o tsv
if (-not $existingEnvironment) {
    Invoke-Az -- containerapp env create --name $EnvironmentName --resource-group $ResourceGroup --location $Location --logs-destination log-analytics --logs-workspace-id $workspaceId --logs-workspace-key $workspaceKey --output none
}

$existingPostgresServer = Invoke-Az -- postgres flexible-server list --resource-group $ResourceGroup --query "[?name=='$postgresServerName'].name | [0]" -o tsv
if (-not $existingPostgresServer) {
    Invoke-Az -- postgres flexible-server create --resource-group $ResourceGroup --name $postgresServerName --location $Location --admin-user $PostgresAdminUser --admin-password $postgresAdminPassword --sku-name Standard_B1ms --tier Burstable --storage-size 32 --version 16 --public-access 0.0.0.0 --yes --output none
}
$existingPostgresDatabase = Invoke-Az -- postgres flexible-server db list --resource-group $ResourceGroup --server-name $postgresServerName --query "[?name=='$PostgresDatabaseName'].name | [0]" -o tsv
if (-not $existingPostgresDatabase) {
    Invoke-Az -- postgres flexible-server db create --resource-group $ResourceGroup --server-name $postgresServerName --name $PostgresDatabaseName --output none
}
$encodedPostgresPassword = [Uri]::EscapeDataString($postgresAdminPassword)
$databaseUrl = "postgresql+psycopg://${PostgresAdminUser}:$encodedPostgresPassword@$postgresServerName.postgres.database.azure.com:5432/${PostgresDatabaseName}?sslmode=require"

Invoke-Az -- storage account create --resource-group $ResourceGroup --name $storageName --location $Location --kind StorageV2 --sku Standard_LRS --output none
Invoke-Az -- storage share-rm create --resource-group $ResourceGroup --storage-account $storageName --name $StorageShareName --quota 10 --enabled-protocols SMB --output none
$storageKey = Invoke-Az -- storage account keys list --resource-group $ResourceGroup --account-name $storageName --query '[0].value' -o tsv
Invoke-Az -- containerapp env storage set --name $EnvironmentName --resource-group $ResourceGroup --storage-name reviewdata --azure-file-account-name $storageName --azure-file-account-key $storageKey --azure-file-share-name $StorageShareName --access-mode ReadWrite --output none

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker Desktop must be running to build and push the deployment image.'
}
Invoke-Az -- acr login --name $registryName
& docker build --tag $acrImage $repositoryRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Docker image build failed.'
}
& docker push $acrImage
if ($LASTEXITCODE -ne 0) {
    throw 'Docker image push failed.'
}

$environmentId = Invoke-Az -- containerapp env show --name $EnvironmentName --resource-group $ResourceGroup --query id -o tsv
$template = Get-Content -Raw (Join-Path $PSScriptRoot '..\infra\containerapp.yaml')
$replacements = @{
    '__APP_NAME__' = $AppName
    '__LOCATION__' = $Location
    '__MANAGED_ENVIRONMENT_ID__' = $environmentId
    '__CONTAINER_IMAGE__' = $acrImage
    '__REGISTRY_SERVER__' = "$registryName.azurecr.io"
    '__REGISTRY_USERNAME__' = $registryCredentials.username
    '__ACR_PULL_PASSWORD__' = $registryCredentials.password
    '__AZURE_OPENAI_API_KEY__' = $openAiKey
    '__AZURE_DOCUMENT_INTELLIGENCE_KEY__' = $documentIntelligenceKey
    '__APP_PASSWORD__' = $appPassword
    '__SESSION_SECRET__' = $sessionSecret
    '__DATABASE_URL__' = $databaseUrl
    '__AZURE_OPENAI_ENDPOINT__' = $openAiEndpoint
    '__AZURE_OPENAI_DEPLOYMENT__' = $openAiDeployment
    '__AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT__' = $documentIntelligenceEndpoint
}
$resolvedYaml = $template
foreach ($entry in $replacements.GetEnumerator()) {
    $resolvedYaml = $resolvedYaml.Replace($entry.Key, (Escape-YamlValue $entry.Value))
}

$temporaryYaml = Join-Path ([IO.Path]::GetTempPath()) "$AppName-$([guid]::NewGuid()).yaml"
try {
    Set-Content -LiteralPath $temporaryYaml -Value $resolvedYaml -NoNewline
    $existingApp = Invoke-Az -- containerapp list --resource-group $ResourceGroup --query "[?name=='$AppName'].name | [0]" -o tsv
    if ($existingApp) {
        Invoke-Az -- containerapp update --name $AppName --resource-group $ResourceGroup --yaml $temporaryYaml --output none
    }
    else {
        Invoke-Az -- containerapp create --name $AppName --resource-group $ResourceGroup --yaml $temporaryYaml --output none
    }
}
finally {
    Remove-Item -LiteralPath $temporaryYaml -Force -ErrorAction SilentlyContinue
}

$fqdn = Invoke-Az -- containerapp show --name $AppName --resource-group $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv
Write-Host "Deployment completed: https://$fqdn"
Write-Host "Image: $acrImage"
Write-Host "Registry: $registryName"
Write-Host "PostgreSQL server: $postgresServerName"
Write-Host "Storage account: $storageName"
Write-Host "Logs: az containerapp logs show --name $AppName --resource-group $ResourceGroup --follow"
