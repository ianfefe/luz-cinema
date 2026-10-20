@echo off
setlocal
echo ============================================
echo   Compilando LuzCinema.exe com PyInstaller
echo ============================================

taskkill /F /IM LuzCinema.exe 2>nul

pyinstaller -y LuzCinema.spec

if %ERRORLEVEL% equ 0 (
    echo.
    echo [SUCESSO] LuzCinema.exe gerado com sucesso em dist\LuzCinema.exe
    echo.
) else (
    echo.
    echo [ERRO] Falha ao compilar o executavel.
    echo.
)
pause
