@echo off
setlocal
cd /d "%~dp0.."
set "PORT=8877"
echo Iniciando Overdrive PC na porta %PORT%...
echo Se houver erro de porta ocupada, feche a aplicacao que usa essa porta.
where py >nul 2>&1
if not errorlevel 1 (
  start "" "http://127.0.0.1:%PORT%/web/"
  py -3 web\server.py --port %PORT%
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3 nao encontrado.
    pause
    exit /b 1
  )
  start "" "http://127.0.0.1:%PORT%/web/"
  python web\server.py --port %PORT%
)
echo.
echo O servidor foi encerrado ou falhou ao iniciar.
pause
