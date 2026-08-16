<#
Resume the deployed Invoice Review demo after pause-azure.ps1.
It starts PostgreSQL before activating the latest provisioned Container App revision.
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-invoice-review',
    [string]$AppName = 'invoice-review-web',
    [string]$PostgresServerName,
    [switch]$DatabaseOnly
)

$ErrorActionPreference = 'Stop'

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'Azure CLI command failed. Check the command output above.'
    }
}

if (-not $PostgresServerName) {
    $subscriptionId = Invoke-Az -- account show --query id -o tsv
    $unique = ($subscriptionId -replace '-', '').Substring(0, 8).ToLowerInvariant()
    $PostgresServerName = "pg-invoice-$unique"
}

$serverExists = Invoke-Az -- postgres flexible-server list --resource-group $ResourceGroup --query "[?name=='$PostgresServerName'].name | [0]" -o tsv
if (-not $serverExists) {
    throw "PostgreSQL server was not found: $PostgresServerName"
}

$state = Invoke-Az -- postgres flexible-server show --resource-group $ResourceGroup --name $PostgresServerName --query state -o tsv
if ($state -eq 'Stopped') {
    Invoke-Az -- postgres flexible-server start --resource-group $ResourceGroup --name $PostgresServerName --output none
    Write-Host "Started PostgreSQL server: $PostgresServerName"
}
elseif ($state -ne 'Ready') {
    throw "PostgreSQL server is not ready to resume: $state"
}

if ($DatabaseOnly) {
    Write-Host 'PostgreSQL is ready. Container App revisions remain paused.'
    return
}

$revision = Invoke-Az -- containerapp revision list --name $AppName --resource-group $ResourceGroup --all --query "sort_by([?properties.provisioningState=='Provisioned'], &properties.createdTime)[-1].name" -o tsv
if (-not $revision) {
    throw "No provisioned revision is available for $AppName."
}

Invoke-Az -- containerapp revision activate --name $AppName --resource-group $ResourceGroup --revision $revision --output none
Write-Host "Activated revision: $revision"
Write-Host 'Resumed. Wait for the readiness probe before opening the app URL.'
