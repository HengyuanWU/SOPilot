# Requires: PowerShell 7+
param(
    [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info([string]$msg) { Write-Host "[info] $msg" -ForegroundColor Cyan }
function Write-Warn([string]$msg) { Write-Host "[warn] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "[error] $msg" -ForegroundColor Red }

Push-Location (Split-Path -Parent $PSCommandPath) | Out-Null
Set-Location ..

if (-not $SkipInstall) {
    try {
        Write-Info "安装后端依赖（优先使用 uv）..."
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            uv pip install -r backend/requirements.txt
        } else {
            Write-Warn "未检测到 uv，改用 pip"
            pip install -r backend/requirements.txt
        }
    } catch {
        Write-Err "安装后端依赖失败: $($_.Exception.Message)"
    }

    try {
        Write-Info "安装前端依赖..."
        if (-not (Test-Path frontend/node_modules)) {
            Push-Location frontend
            npm install
            Pop-Location
        } else {
            Write-Info "跳过前端依赖安装（已存在 node_modules）"
        }
    } catch {
        Write-Err "安装前端依赖失败: $($_.Exception.Message)"
    }
}

Write-Info "启动后端（http://127.0.0.1:8000）..."
$backendCmd = 'pwsh -NoExit -Command "$env:PYTHONPATH=\"backend/src\"; python -m uvicorn app.asgi:app --reload --app-dir backend/src --port 8000"'
Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCmd | Out-Null

Start-Sleep -Seconds 1
Write-Info "启动前端（http://127.0.0.1:5173）..."
$frontendCmd = 'pwsh -NoExit -Command "Set-Location frontend; npm run dev -- --host"'
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontendCmd | Out-Null

Write-Host "" 
Write-Info "已启动："
Write-Host "  - 后端: http://127.0.0.1:8000/api/v1/runs/health"
Write-Host "  - 前端: http://127.0.0.1:5173"

Pop-Location | Out-Null
