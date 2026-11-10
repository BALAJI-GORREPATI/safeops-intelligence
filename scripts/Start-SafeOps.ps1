param([switch]$Production)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Run the README installation commands first.' }
New-Item -ItemType Directory -Force '.runtime' | Out-Null
if (Test-Path -LiteralPath '.runtime\pgdata') {
    & $pythonPath 'scripts\bootstrap_db.py'
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed.' }
}
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
& $pythonPath -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed; check .env and PostgreSQL.' }
foreach ($port in @(8000, 3000)) {
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try { $probe.Start() }
    catch { throw "Cannot bind local port $port. Stop the existing app or check Windows socket permissions." }
    finally { $probe.Stop() }
}
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','safeops.api:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput '.runtime\api.stdout.log' -RedirectStandardError '.runtime\api.stderr.log'
$nextPath = Join-Path $projectRoot 'frontend\node_modules\next\dist\bin\next'
$nextMode = if ($Production) { 'start' } else { 'dev' }
$webProcess = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @($nextPath,$nextMode,'--hostname','127.0.0.1','--port','3000') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot '.runtime\web.stdout.log') -RedirectStandardError (Join-Path $projectRoot '.runtime\web.stderr.log')
@{api=$apiProcess.Id;web=$webProcess.Id} | ConvertTo-Json | Set-Content -LiteralPath '.runtime\app-processes.json'
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $apiProcess.Refresh()
    $webProcess.Refresh()
    if ($apiProcess.HasExited -or $webProcess.HasExited) {
        if (!$apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
        if (!$webProcess.HasExited) { Stop-Process -Id $webProcess.Id }
        throw 'A SafeOps server exited during startup. Read .runtime\api.stderr.log and web.stderr.log.'
    }
    try {
        $health = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $homepageResponse = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000' -TimeoutSec 2
        if ($health.StatusCode -eq 200 -and $homepageResponse.StatusCode -eq 200) { $ready = $true; break }
    } catch { $lastReadinessError = $_.Exception.Message; Start-Sleep -Milliseconds 300 }
}
if (!$ready) { throw "Startup timed out: $lastReadinessError. Read .runtime logs; use Stop-SafeOps.ps1 before retrying." }
Write-Host 'SafeOps ready at http://127.0.0.1:3000'
Write-Host 'API documentation: http://127.0.0.1:8000/docs'
Write-Host 'Local demo password: SafeOps-local-demo (unless changed in .env)'
Write-Host 'Logs: .runtime\*.log. Stop with .\scripts\Stop-SafeOps.ps1'
