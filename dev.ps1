# ============================================
# 银发守护 - 开发启动脚本
# ============================================
# 用法：
#   .\dev.ps1          启动全部（Docker 后端+基础设施 + 本地前端）
#   .\dev.ps1 docker   仅启动 Docker（后端+基础设施）
#   .\dev.ps1 frontend 仅启动前端
#   .\dev.ps1 stop     停止所有
# ============================================

param([string]$Action = "all")

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Docker Desktop CLI 不在 PATH 时，自动探测常见安装目录
$DockerCliPath = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $DockerCliPath "docker.exe"))) {
    $env:Path = "$DockerCliPath;$env:Path"
}

function Start-Docker {
    Write-Host "`n[1/2] 启动 Docker（后端 API + Worker + PostgreSQL + Redis + MinIO + Sandbox）..." -ForegroundColor Cyan
    cd $ProjectRoot
    docker compose up -d
    Write-Host "Docker 服务已启动" -ForegroundColor Green
    Write-Host "  后端 API: http://localhost:5050" -ForegroundColor White
}

function Start-Frontend {
    Write-Host "`n[2/2] 启动前端 (localhost:5173)..." -ForegroundColor Cyan
    cd "$ProjectRoot\web"
    # 统一走 Corepack 中由 web/package.json 锁定的 pnpm 版本（当前 10.11.0）
    Start-Process -NoNewWindow -FilePath "corepack" -ArgumentList "pnpm","run","dev" -WorkingDirectory "$ProjectRoot\web"
    Write-Host "前端已启动: http://localhost:5173" -ForegroundColor Green
}

function Stop-All {
    Write-Host "`n停止所有服务..." -ForegroundColor Yellow
    cd $ProjectRoot
    docker compose down 2>$null
    # 停前端（本地 pnpm dev 进程）
    $fe = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if ($fe) { Stop-Process -Id $fe.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Host "全部已停止" -ForegroundColor Green
}

switch ($Action) {
    "docker"   { Start-Docker }
    "frontend" { Start-Frontend }
    "stop"     { Stop-All }
    default {
        Start-Docker
        Start-Sleep -Seconds 2
        Start-Frontend
        Write-Host "`n========================================" -ForegroundColor Magenta
        Write-Host "  银发守护已启动" -ForegroundColor Magenta
        Write-Host "  前端: http://localhost:5173" -ForegroundColor White
        Write-Host "  后端: http://localhost:5050" -ForegroundColor White
        Write-Host "========================================`n" -ForegroundColor Magenta
    }
}
