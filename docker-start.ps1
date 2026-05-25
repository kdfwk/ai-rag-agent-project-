# docker-start.ps1 - ZhiSaoTong Docker Startup Script

Write-Host "Starting ZhiSaoTong Docker Services..." -ForegroundColor Green
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check .env file
if (-Not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found" -ForegroundColor Yellow
    Write-Host "Creating from template..." -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
    Write-Host "Please edit .env file and add your API Key" -ForegroundColor Red
    notepad .env
    Write-Host "Press any key to continue..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Check data directory
$dataFiles = Get-ChildItem ".\data\" -Recurse -File -ErrorAction SilentlyContinue | Measure-Object
if ($dataFiles.Count -eq 0) {
    Write-Host "WARNING: data/ directory is empty" -ForegroundColor Yellow
    Write-Host "Supported formats: PDF, Word, TXT, Images" -ForegroundColor Gray
}

# Stop existing services
Write-Host "Stopping existing services..." -ForegroundColor Cyan
docker compose down 2>$null

# Build and start
Write-Host "Building Docker images (first time may be slow)..." -ForegroundColor Cyan
docker compose up -d --build

# Wait for services to start
Write-Host "Waiting for services to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# Check service status
Write-Host ""
Write-Host "Service Status:" -ForegroundColor Green
docker compose ps

# Check if services are healthy
$appStatus = docker compose ps app --format json 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS! Services started successfully" -ForegroundColor Green
    Write-Host ""
    Write-Host "Web Interface: http://localhost:8501" -ForegroundColor Blue
    Write-Host "MCP Server: http://localhost:8001" -ForegroundColor Blue
    Write-Host ""
    Write-Host "Common Commands:" -ForegroundColor Gray
    Write-Host "  View logs: docker compose logs -f" -ForegroundColor Gray
    Write-Host "  Stop services: docker compose down" -ForegroundColor Gray
    Write-Host "  Restart services: docker compose restart" -ForegroundColor Gray
    Write-Host ""
    
    # Ask if open browser
    $openBrowser = Read-Host "Open browser now? (Y/N)"
    if ($openBrowser -eq "Y" -or $openBrowser -eq "y") {
        Start-Process "http://localhost:8501"
    }
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to start services" -ForegroundColor Red
    Write-Host "Check logs: docker compose logs" -ForegroundColor Gray
}
