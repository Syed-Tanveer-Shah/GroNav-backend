Write-Host "Starting Django Backend..." -ForegroundColor Cyan
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

if (Test-Path "venv\Scripts\Activate.ps1") {
    . venv\Scripts\Activate.ps1
} else {
    Write-Error "Virtual environment not found in Backend\venv"
    pause
    exit
}

python manage.py runserver
pause
