@echo off
setlocal
cd /d "%~dp0.."
echo ========================================================
echo   Compilando Luz Cinema (Simples) e Luz Cinema Multi
echo ========================================================

taskkill /F /IM LuzCinema.exe 2>nul
taskkill /F /IM LuzCinemaMulti.exe 2>nul

pyinstaller -y ferramentas\LuzCinema.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCESSO] Gerados em dist\LuzCinema.exe e dist\LuzCinemaMulti.exe
    echo.
) else (
    echo.
    echo [ERRO] Falha ao compilar.
    echo.
)
pause
