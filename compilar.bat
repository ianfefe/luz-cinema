@echo off
setlocal
echo ========================================================
echo   Compilando Luz Cinema v2 (Multi-Lampadas e Cenarios)
echo ========================================================

taskkill /F /IM LuzCinema.exe 2>nul

pyinstaller -y LuzCinema.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCESSO] Luz Cinema v2 gerado com sucesso em dist\LuzCinema.exe
    echo.
) else (
    echo.
    echo [ERRO] Falha ao compilar o executavel.
    echo.
)
pause
