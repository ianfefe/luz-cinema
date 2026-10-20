Write-Host "Compilando LuzCinema.exe com PyInstaller..." -ForegroundColor Cyan
Stop-Process -Name "LuzCinema" -Force -ErrorAction SilentlyContinue

pyinstaller -y LuzCinema.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCESSO] Executavel gerado em dist/LuzCinema.exe`n" -ForegroundColor Green
} else {
    Write-Host "`n[ERRO] Falha na compilacao.`n" -ForegroundColor Red
}
