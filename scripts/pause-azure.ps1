<#
Pause the deployed Invoice Review demo without deleting data or infrastructure.
It deactivates Container App revisions and stops PostgreSQL compute.
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-invoice-review',
    [string]$AppName = 'invoice-review-web',
    [string]$PostgresServerName
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

$activeRevisions = @(
    Invoke-Az -- containerapp revision list --name $AppName --resource-group $ResourceGroup --query "[?properties.active].name" -o tsv
)
foreach ($revision in $activeRevisions | Where-Object { $_ }) {
    Invoke-Az -- containerapp revision deactivate --name $AppName --resource-group $ResourceGroup --revision $revision --output none
    Write-Host "Deactivated revision: $revision"
}

$serverExists = Invoke-Az -- postgres flexible-server list --resource-group $ResourceGroup --query "[?name=='$PostgresServerName'].name | [0]" -o tsv
if ($serverExists) {
    $state = Invoke-Az -- postgres flexible-server show --resource-group $ResourceGroup --name $PostgresServerName --query state -o tsv
    if ($state -ne 'Stopped') {
        Invoke-Az -- postgres flexible-server stop --resource-group $ResourceGroup --name $PostgresServerName --output none
        Write-Host "Stopped PostgreSQL server: $PostgresServerName"
    }
    else {
        Write-Host "PostgreSQL server is already stopped: $PostgresServerName"
    }
}
else {
    Write-Warning "PostgreSQL server was not found: $PostgresServerName"
}

Write-Host 'Paused. No database records or uploaded source documents were deleted.'
