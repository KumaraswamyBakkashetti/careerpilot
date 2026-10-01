param([switch]$Integration)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Check([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Quality check failed: $Executable $Arguments" }
}

Push-Location (Join-Path $taskRoot 'backend')
try {
    $taskPython = if ($IsWindows -or $env:OS -eq 'Windows_NT') { '.venv/Scripts/python.exe' } else { '.venv/bin/python' }
    Invoke-Check $taskPython @('-m', 'ruff', 'format', '--check', 'app', 'tests')
    Invoke-Check $taskPython @('-m', 'ruff', 'check', 'app', 'tests')
    Invoke-Check $taskPython @('-m', 'mypy')
    Invoke-Check $taskPython @('-m', 'pytest', '-q', '-m', 'not integration')
    if ($Integration) {
        if ($env:CP_RUN_INTEGRATION -ne '1') { throw 'Set CP_RUN_INTEGRATION=1 for isolated integration tests.' }
        Invoke-Check $taskPython @('-m', 'pytest', '-q', '-m', 'integration')
    }
} finally { Pop-Location }
Push-Location (Join-Path $taskRoot 'frontend')
try {
    $taskNpm = if ($IsWindows -or $env:OS -eq 'Windows_NT') { 'npm.cmd' } else { 'npm' }
    Invoke-Check $taskNpm @('run', 'check')
} finally { Pop-Location }
Write-Host 'All requested quality checks passed.'
