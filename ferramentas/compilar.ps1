Write-Host "Compilando LuzCinema.exe com PyInstaller..." -ForegroundColor Cyan
Stop-Process -Name "LuzCinema" -Force -ErrorAction SilentlyContinue

Push-Location (Join-Path $PSScriptRoot "..")
pyinstaller -y ferramentas\LuzCinema.spec

$ok = $LASTEXITCODE -eq 0
if ($ok) {
    Write-Host "`n[SUCESSO] Gerado em dist/LuzCinema.exe`n" -ForegroundColor Green
} else {
    Write-Host "`n[ERRO] Falha na compilacao.`n" -ForegroundColor Red
}
Pop-Location
