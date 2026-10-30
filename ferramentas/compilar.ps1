Write-Host "Compilando LuzCinema.exe (Simples) e LuzCinemaMulti.exe com PyInstaller..." -ForegroundColor Cyan
Stop-Process -Name "LuzCinema", "LuzCinemaMulti" -Force -ErrorAction SilentlyContinue

Push-Location (Join-Path $PSScriptRoot "..")
pyinstaller -y ferramentas\LuzCinema.spec

$ok = $LASTEXITCODE -eq 0
if ($ok) {
    Write-Host "`n[SUCESSO] Gerados em dist/LuzCinema.exe e dist/LuzCinemaMulti.exe`n" -ForegroundColor Green
} else {
    Write-Host "`n[ERRO] Falha na compilacao.`n" -ForegroundColor Red
}
Pop-Location
