@echo off
setlocal
cd /d "%~dp0.."
echo ========================================================
echo   Compilando Luz Cinema
echo ========================================================

taskkill /F /IM LuzCinema.exe 2>nul

pyinstaller -y ferramentas\LuzCinema.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCESSO] Gerado em dist\LuzCinema.exe
    echo.
) else (
    echo.
    echo [ERRO] Falha ao compilar.
    echo.
)
pause
