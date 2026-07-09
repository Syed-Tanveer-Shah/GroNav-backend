@echo off
echo Starting Django Backend...
cd /d "%~dp0"
if exist venv\Scripts\activate (
    call venv\Scripts\activate
) else (
    echo Virtual environment not found in Backend\venv
    pause
    exit /b
)
python manage.py runserver
pause
