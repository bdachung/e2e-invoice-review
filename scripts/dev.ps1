<#
Start the FastAPI backend and Vite frontend from one PowerShell terminal.

Run from the repository root:
    .\scripts\dev.ps1
#>

$ErrorActionPreference = "Stop"
$rootDirectory = Split-Path -Parent $PSScriptRoot

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

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if ($null -ne $Process -and -not $Process.HasExited) {
        & taskkill /PID $Process.Id /T /F 2>$null | Out-Null
    }
}

$uvCommand = (Get-Command uv -ErrorAction Stop).Source
$pnpm = Get-Command pnpm,pnpm.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pnpm) {
    $frontendCommand = $pnpm.Source
    $frontendArguments = @("dev", "--host", "127.0.0.1", "--port", "5173")
}
else {
    $corepack = Get-Command corepack,corepack.cmd -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $corepack) {
        throw "pnpm is unavailable and Corepack was not found. Install pnpm or enable Corepack."
    }
    $frontendCommand = $corepack.Source
    $frontendArguments = @("pnpm", "dev", "--host", "127.0.0.1", "--port", "5173")
}

$backendProcess = Start-Process `
    -FilePath $uvCommand `
    -ArgumentList "run", "--locked", "--no-sync", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory "$rootDirectory\backend" `
    -NoNewWindow `
    -PassThru

$frontendProcess = Start-Process `
    -FilePath $frontendCommand `
    -ArgumentList $frontendArguments `
    -WorkingDirectory "$rootDirectory\frontend" `
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
