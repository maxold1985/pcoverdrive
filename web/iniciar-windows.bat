@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>&1
if %errorlevel%==0 (
  start "" "http://127.0.0.1:8765/web/"
  py -3 -m http.server 8765 --bind 127.0.0.1
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3 nao encontrado. Instale Python 3 e tente novamente.
    pause
    exit /b 1
  )
  start "" "http://127.0.0.1:8765/web/"
  python -m http.server 8765 --bind 127.0.0.1
)
