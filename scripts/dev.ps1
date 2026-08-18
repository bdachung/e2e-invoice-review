<#
Start the FastAPI backend and Vite frontend from one PowerShell terminal.

Run from the repository root:
    .\scripts\dev.ps1             # start both development servers
    .\scripts\dev.ps1 -Check      # run the documented verification suite first

The frontend is launched with pnpm when it is on PATH, otherwise directly with
the already-installed Vite binary via Node, and finally through Corepack. The
script therefore runs even when pnpm is not installed globally.
#>

[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$rootDirectory = Split-Path -Parent $PSScriptRoot
$backendDirectory = Join-Path $rootDirectory "backend"
$frontendDirectory = Join-Path $rootDirectory "frontend"
$localBin = Join-Path $frontendDirectory "node_modules"

function Wait-ForPort {
    param(
        [int]$Port,
        [System.Diagnostics.Process]$Process,
        [string]$ServiceName
    )

    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        if ($Process.HasExited) {
            throw "$ServiceName stopped before becoming ready."
        }
        try {
            $client = [System.Net.Sockets.TcpClient]::new()
            $client.Connect("127.0.0.1", $Port)
            $client.Dispose()
            return
        }
        catch {
            Start-Sleep -Milliseconds 200
        }
    }
    throw "$ServiceName did not become ready on port $Port."
}

function Test-PortFree {
    param([int]$Port)

    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $client.Connect("127.0.0.1", $Port)
        $client.Dispose()
        return $false
    }
    catch {
        return $true
    }
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($null -ne $Process -and -not $Process.HasExited) {
        & taskkill /PID $Process.Id /T /F 2>$null | Out-Null
    }
}

function Assert-Exit {
    param([string]$Label)

    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Get-FrontendDevCommand {
    # Return the executable and arguments that start the Vite dev server.
    $pnpm = Get-Command pnpm,pnpm.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pnpm) {
        return @{ Mode = "pnpm"; FilePath = $pnpm.Source; Arguments = @("dev", "--host", "127.0.0.1", "--port", "5173") }
    }
    $node = Get-Command node,node.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($node -and (Test-Path (Join-Path $localBin "vite\bin\vite.js"))) {
        return @{ Mode = "local Vite via Node"; FilePath = $node.Source; Arguments = @((Join-Path $localBin "vite\bin\vite.js"), "dev", "--host", "127.0.0.1", "--port", "5173") }
    }
    $corepack = Get-Command corepack,corepack.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($corepack) {
        return @{ Mode = "Corepack pnpm"; FilePath = $corepack.Source; Arguments = @("pnpm", "dev", "--host", "127.0.0.1", "--port", "5173") }
    }
    throw "pnpm and Corepack are unavailable and the local Vite install is missing. Install pnpm or run 'pnpm install --frozen-lockfile' in frontend/ first."
}

function Invoke-FrontendChecks {
    # Run the documented frontend verification: type-check, lint, production build.
    $pnpm = Get-Command pnpm,pnpm.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
    $node = Get-Command node,node.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    $corepack = Get-Command corepack,corepack.cmd -ErrorAction SilentlyContinue | Select-Object -First 1

    if ($pnpm) {
        Write-Host "  pnpm exec tsc -b --pretty false"
        & $pnpm.Source "exec" "tsc" "-b" "--pretty" "false"; Assert-Exit "tsc"
        Write-Host "  pnpm lint"
        & $pnpm.Source "lint"; Assert-Exit "pnpm lint"
        Write-Host "  pnpm build"
        & $pnpm.Source "build"; Assert-Exit "pnpm build"
        return
    }
    if ($node -and (Test-Path (Join-Path $localBin "typescript\bin\tsc")) -and (Test-Path (Join-Path $localBin "eslint\bin\eslint.js")) -and (Test-Path (Join-Path $localBin "vite\bin\vite.js"))) {
        Write-Host "  node tsc -b --pretty false"
        & $node.Source (Join-Path $localBin "typescript\bin\tsc") "-b" "--pretty" "false"; Assert-Exit "tsc"
        Write-Host "  node eslint ."
        & $node.Source (Join-Path $localBin "eslint\bin\eslint.js") "."; Assert-Exit "eslint"
        Write-Host "  node vite build"
        & $node.Source (Join-Path $localBin "vite\bin\vite.js") "build"; Assert-Exit "vite build"
        return
    }
    if ($corepack) {
        Write-Host "  corepack pnpm exec tsc -b --pretty false"
        & $corepack.Source "pnpm" "exec" "tsc" "-b" "--pretty" "false"; Assert-Exit "tsc"
        Write-Host "  corepack pnpm lint"
        & $corepack.Source "pnpm" "lint"; Assert-Exit "pnpm lint"
        Write-Host "  corepack pnpm build"
        & $corepack.Source "pnpm" "build"; Assert-Exit "pnpm build"
        return
    }
    throw "pnpm and Corepack are unavailable and the local frontend install is missing."
}

$uvCommand = (Get-Command uv -ErrorAction Stop).Source

if ($Check) {
    Write-Host "Backend verification (ruff + compileall)..."
    Push-Location $backendDirectory
    try {
        & $uvCommand "run" "--locked" "--no-sync" "ruff" "check" "app" "mcp_server"; Assert-Exit "ruff check"
        & $uvCommand "run" "--locked" "--no-sync" "python" "-m" "compileall" "-q" "app" "mcp_server"; Assert-Exit "compileall"
    }
    finally {
        Pop-Location
    }

    Write-Host "Frontend verification (tsc + eslint + build)..."
    Push-Location $frontendDirectory
    try {
        Invoke-FrontendChecks
    }
    finally {
        Pop-Location
    }

    Write-Host "Verification passed."
    Write-Host "Start the development servers with: .\scripts\dev.ps1"
    exit 0
}

foreach ($entry in @(@{ Port = 8000; Name = "Backend" }, @{ Port = 5173; Name = "Frontend" })) {
    if (-not (Test-PortFree -Port $entry.Port)) {
        throw "Port $($entry.Port) is already in use by another process. Stop it before starting the $($entry.Name) dev server."
    }
}

$frontendCommand = Get-FrontendDevCommand
Write-Host "Frontend launcher: $($frontendCommand.Mode)"

$backendProcess = Start-Process `
    -FilePath $uvCommand `
    -ArgumentList "run", "--locked", "--no-sync", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backendDirectory `
    -NoNewWindow `
    -PassThru

$frontendProcess = Start-Process `
    -FilePath $frontendCommand.FilePath `
    -ArgumentList $frontendCommand.Arguments `
    -WorkingDirectory $frontendDirectory `
    -NoNewWindow `
    -PassThru

try {
    Wait-ForPort -Port 8000 -Process $backendProcess -ServiceName "Backend"
    Wait-ForPort -Port 5173 -Process $frontendProcess -ServiceName "Frontend"

    Write-Host "Backend:  http://127.0.0.1:8000"
    Write-Host "Frontend: http://127.0.0.1:5173"
    Write-Host "Press Ctrl+C to stop both services."

    while (-not $backendProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Milliseconds 250
    }

    throw "The backend or frontend development server stopped unexpectedly."
}
finally {
    Stop-ProcessTree $backendProcess
    Stop-ProcessTree $frontendProcess
}
