Write-Host "Compilando LuzCinema.exe com PyInstaller..." -ForegroundColor Cyan
Push-Location (Join-Path $PSScriptRoot "..")
try {
    $py = "venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        Write-Host "Criando o ambiente virtual em venv\ ..."
        python -m venv venv
        if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel criar o venv (o Python esta instalado?)." }
    }
    Write-Host "Instalando dependencias e PyInstaller no venv..."
    & $py -m pip install -q -r requirements.txt pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependencias." }

    Stop-Process -Name "LuzCinema" -Force -ErrorAction SilentlyContinue
    & $py -m PyInstaller -y ferramentas\LuzCinema.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha na compilacao." }

    Write-Host "`n[SUCESSO] Gerado em dist/LuzCinema.exe" -ForegroundColor Green
    Write-Host "Copie-o para a pasta onde fica a sua pasta 'dados' (ex.: a da versao anterior).`n"
} catch {
    Write-Host "`n[ERRO] $_`n" -ForegroundColor Red
} finally {
    Pop-Location
}
