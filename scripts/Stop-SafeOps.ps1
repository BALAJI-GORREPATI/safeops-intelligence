$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$processFile = Join-Path $projectRoot '.runtime\app-processes.json'
if (Test-Path -LiteralPath $processFile) {
    $ownedProcesses = Get-Content -Raw -LiteralPath $processFile | ConvertFrom-Json
    foreach ($processId in @($ownedProcesses.api, $ownedProcesses.web)) {
        $candidate = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
        if ($candidate -and ($candidate.CommandLine -like '*uvicorn safeops.api:app*' -or $candidate.CommandLine -like '*next\dist\bin\next*')) {
            Stop-Process -Id $processId
        }
    }
}
Write-Host 'Owned SafeOps application processes stopped. PostgreSQL data is preserved.'
