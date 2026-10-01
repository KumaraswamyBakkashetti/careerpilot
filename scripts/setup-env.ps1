$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskDestination = Join-Path $taskRoot '.env'
if (-not (Test-Path -LiteralPath $taskDestination)) {
    $taskBytes = New-Object byte[] 32
    $taskGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $taskGenerator.GetBytes($taskBytes) } finally { $taskGenerator.Dispose() }
    $taskPassword = -join ($taskBytes | ForEach-Object { $_.ToString('x2') })
    $taskText = (Get-Content -LiteralPath (Join-Path $taskRoot '.env.example') -Raw).
        Replace('CP_NEO4J_PASSWORD=', "CP_NEO4J_PASSWORD=$taskPassword").
        Replace('NEO4J_LOCAL_PASSWORD=', "NEO4J_LOCAL_PASSWORD=$taskPassword").
        Replace('CP_JWT_SECRET=', "CP_JWT_SECRET=$taskPassword")
    [System.IO.File]::WriteAllText($taskDestination, $taskText)
    Write-Host 'Created ignored root .env with generated local Neo4j credentials.'
} else {
    $taskExisting = Get-Content -LiteralPath $taskDestination -Raw
    if ($taskExisting -notmatch '(?m)^CP_JWT_SECRET=.{32,}$') {
        $taskBytes = New-Object byte[] 32
        $taskGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $taskGenerator.GetBytes($taskBytes) } finally { $taskGenerator.Dispose() }
        $taskSecret = -join ($taskBytes | ForEach-Object { $_.ToString('x2') })
        [System.IO.File]::AppendAllText($taskDestination, "`r`nCP_JWT_SECRET=$taskSecret`r`n")
        Write-Host 'Existing root .env preserved; missing local JWT secret added.'
    } else { Write-Host 'Existing root .env preserved.' }
}
$taskFrontendEnv = Join-Path $taskRoot 'frontend/.env'
if (-not (Test-Path -LiteralPath $taskFrontendEnv)) {
    Copy-Item -LiteralPath (Join-Path $taskRoot 'frontend/.env.example') -Destination $taskFrontendEnv
}
