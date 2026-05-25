# check-docker.ps1 - Check Docker Desktop Installation Status

Write-Host "Checking Docker Desktop installation..." -ForegroundColor Cyan
Write-Host ""

# 1. Check if Docker Desktop is installed
$dockerPaths = @(
    "C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    "C:\Program Files\Docker\Docker\Docker Desktop.exe"
)

$dockerInstalled = $false
foreach ($path in $dockerPaths) {
    if (Test-Path $path) {
        Write-Host "Docker Desktop found at: $path" -ForegroundColor Green
        $dockerInstalled = $true
        break
    }
}

if (-not $dockerInstalled) {
    Write-Host "Docker Desktop not found!" -ForegroundColor Red
    Write-Host "Please download from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}

# 2. Check if docker command works
try {
    $dockerVersion = docker --version
    Write-Host "Docker command works: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "Docker command not available in PATH" -ForegroundColor Yellow
    
    # Try to add to PATH temporarily
    $dockerBinPath = "C:\Program Files\Docker\Docker\resources\bin"
    if (Test-Path $dockerBinPath) {
        Write-Host "Found Docker bin directory, adding to PATH..." -ForegroundColor Cyan
        $env:Path += ";$dockerBinPath"
        
        try {
            $dockerVersion = docker --version
            Write-Host "Docker now works: $dockerVersion" -ForegroundColor Green
        } catch {
            Write-Host "Still cannot use Docker" -ForegroundColor Red
            exit 1
        }
    }
}

# 3. Check if Docker Desktop is running
Write-Host ""
Write-Host "Checking if Docker Desktop is running..." -ForegroundColor Cyan
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if ($dockerProcess) {
    Write-Host "Docker Desktop is running" -ForegroundColor Green
    
    # 4. Test Docker connection
    try {
        docker info | Out-Null
        Write-Host "Docker service is responding" -ForegroundColor Green
        Write-Host ""
        Write-Host "Docker Desktop is ready!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Cyan
        Write-Host "1. Copy .env.example to .env" -ForegroundColor Gray
        Write-Host "2. Edit .env and add your API key" -ForegroundColor Gray
        Write-Host "3. Run: .\docker-start.ps1" -ForegroundColor Gray
    } catch {
        Write-Host "Docker Desktop running but not responding yet" -ForegroundColor Yellow
        Write-Host "Please wait a moment and try again" -ForegroundColor Gray
    }
} else {
    Write-Host "Docker Desktop is NOT running" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please start Docker Desktop application" -ForegroundColor Yellow
    Write-Host "Search for 'Docker Desktop' in Start Menu" -ForegroundColor Gray
    Write-Host ""
    
    $startDocker = Read-Host "Start Docker Desktop now? (Y/N)"
    if ($startDocker -eq "Y" -or $startDocker -eq "y") {
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        Write-Host "Starting Docker Desktop..." -ForegroundColor Cyan
        Write-Host "Please wait 1-2 minutes until tray icon turns green" -ForegroundColor Yellow
        Write-Host "Then run this script again" -ForegroundColor Yellow
    }
}
