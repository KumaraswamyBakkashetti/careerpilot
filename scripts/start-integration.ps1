$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) { throw 'Create root .env first; see README.' }
    $taskConfig = Get-Content -LiteralPath '.env' -Raw
    $taskMatch = [regex]::Match($taskConfig, '(?m)^NEO4J_LOCAL_PASSWORD=(.+)$')
    if (-not $taskMatch.Success) { throw 'NEO4J_LOCAL_PASSWORD must be set in root .env.' }
    docker compose -p careerpilot-integration -f compose.yaml -f compose.test.yaml up -d --wait --wait-timeout 240
    if ($LASTEXITCODE -ne 0) { throw 'Isolated database startup failed.' }
    $env:CP_RUN_INTEGRATION = '1'
    $env:TEST_NEO4J_PASSWORD = $taskMatch.Groups[1].Value.Trim()
    Push-Location backend
    try {
        & '.venv/Scripts/python.exe' -m pytest -q -m integration
        if ($LASTEXITCODE -ne 0) { throw 'Real database integration tests failed.' }
    } finally { Pop-Location }
} finally { Pop-Location }
# Containers remain running for inspection. README documents scoped teardown.
