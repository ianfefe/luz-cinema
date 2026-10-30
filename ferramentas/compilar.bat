@echo off
setlocal
cd /d "%~dp0.."
echo ========================================================
echo   Compilando Luz Cinema
echo ========================================================

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Criando o ambiente virtual em venv\ ...
    python -m venv venv || goto :erro
)
echo Instalando dependencias e PyInstaller no venv...
"%PY%" -m pip install -q -r requirements.txt pyinstaller || goto :erro

taskkill /F /IM LuzCinema.exe 2>nul

"%PY%" -m PyInstaller -y ferramentas\LuzCinema.spec || goto :erro

echo.
echo [SUCESSO] Gerado em dist\LuzCinema.exe
echo Copie-o para a pasta onde fica a sua pasta "dados" (ex.: a da versao anterior).
echo.
pause
exit /b 0

:erro
echo.
echo [ERRO] Falha ao compilar. Veja a mensagem acima.
echo.
pause
exit /b 1
