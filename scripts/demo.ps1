<#
.SYNOPSIS
  Sobe a demo no Windows (equivalente ao scripts/demo.sh): API em :8000 + dashboard em :5173.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\demo.ps1            # instala, testa e sobe
  powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -SkipTests # sobe sem rodar os testes
  powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Check     # sobe, confere que respondem e encerra
#>
param([switch]$SkipTests, [switch]$Check)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Wait-Url($url) {
  for ($i = 0; $i -lt 90; $i++) {
    try { Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3 | Out-Null; return } catch { Start-Sleep -Seconds 1 }
  }
  throw "Não respondeu: $url"
}

Step "Dependências Python (uv sync)"
uv sync --all-extras
Step "Dependências do frontend (npm ci)"
Push-Location frontend
npm ci --no-fund --no-audit
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Pop-Location

if (-not $SkipTests) {
  Step "Testes do backend"
  uv run pytest
  if ($LASTEXITCODE -ne 0) { throw "pytest falhou" }
  Step "Testes, lint e build do frontend"
  Push-Location frontend
  npm run test; if ($LASTEXITCODE -ne 0) { throw "npm test falhou" }
  npm run lint; if ($LASTEXITCODE -ne 0) { throw "npm run lint falhou" }
  npm run build; if ($LASTEXITCODE -ne 0) { throw "npm run build falhou" }
  Pop-Location
}

Step "API em modo demo (cache em outputs/)"
$api = Start-Process -PassThru -NoNewWindow uv -ArgumentList "run", "uvicorn", "backend.api.main:app", "--port", "8000"
Step "Frontend"
$web = Start-Process -PassThru -NoNewWindow npm.cmd -ArgumentList "run", "dev", "--", "--port", "5173", "--strictPort" -WorkingDirectory "$Root\frontend"
try {
  Wait-Url "http://127.0.0.1:8000/documents"
  Wait-Url "http://localhost:5173/api/documents"
  if ($Check) { Step "OK: API e frontend responderam"; return }
  Step "Pronto: abra http://localhost:5173 (Ctrl+C encerra)"
  Start-Process "http://localhost:5173"
  Wait-Process -Id $api.Id
} finally {
  foreach ($p in @($web, $api)) { if ($p -and -not $p.HasExited) { taskkill /PID $p.Id /T /F | Out-Null } }
}
