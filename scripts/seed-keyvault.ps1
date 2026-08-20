<#
Seed Azure Key Vault with the runtime secrets for Invoice Review.

Run this yourself in your own terminal (not through the assistant) after the
Key Vault exists. Every value is prompted with Read-Host -AsSecureString and
is never echoed, written to a file, or sent through chat.
#>
[CmdletBinding()]
param(
    [string]$VaultName = 'kv-invoice-547ea842',
    [string]$RegistryName = 'invoicereview547ea842'
)

$ErrorActionPreference = 'Stop'

$secretNames = @(
    'acr-pull-password',
    'app-password',
    'session-secret',
    'azure-openai-api-key',
    'document-intelligence-key',
    'postgres-admin-password',
    'database-url'
)

function Get-SecretValue([string]$Name) {
    $secure = Read-Host -Prompt "Enter value for $Name" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$vault = & az keyvault show --name $VaultName --query name -o tsv
if ($LASTEXITCODE -ne 0 -or -not $vault) {
    throw "Key Vault $VaultName not found. Run 'terraform apply -target=azurerm_key_vault.this' first."
}

$collected = @{}

foreach ($name in $secretNames) {
    $value = $null
    if ($name -eq 'acr-pull-password') {
        # Azure generates the ACR admin password when admin is enabled; fetch
        # it instead of prompting. The user confirms before it is written.
        $value = & az acr credential show --name $RegistryName --query passwords[0].value -o tsv
        if ($LASTEXITCODE -ne 0 -or -not $value) {
            throw "Could not read the ACR admin password for $RegistryName"
        }
        $confirm = Read-Host 'Use the ACR admin password? (y/n)'
        if ($confirm -notmatch '^[Yy]') {
            $value = Get-SecretValue $name
        }
    }
    elseif ($name -eq 'postgres-admin-password') {
        $value = Get-SecretValue $name
        $collected[$name] = $value
    }
    elseif ($name -eq 'database-url') {
        # Build the same URL deploy-azure.ps1 produces, using the password
        # entered one prompt earlier.
        if ($collected.ContainsKey('postgres-admin-password')) {
            $encoded = [Uri]::EscapeDataString($collected['postgres-admin-password'])
            $value = "postgresql+psycopg://invoiceadmin:${encoded}@pg-invoice-547ea842.postgres.database.azure.com:5432/invoicereview?sslmode=require"
            $confirm = Read-Host 'Build database-url from the PostgreSQL admin password? (y/n)'
            if ($confirm -notmatch '^[Yy]') {
                $value = Get-SecretValue $name
            }
        }
        else {
            $value = Get-SecretValue $name
        }
    }
    else {
        $value = Get-SecretValue $name
    }
    & az keyvault secret set --vault-name $VaultName --name $name --value $value
    if ($LASTEXITCODE -ne 0) {
        throw "az keyvault secret set failed for $name"
    }
    Write-Host "Seeded $name"
}

Write-Host 'All secrets seeded. Next: terraform apply (full), then terraform plan to confirm no changes.'
