# -*- mode: python ; coding: utf-8 -*-
# Gera as duas edições oficiais (rode a partir da raiz do repositório):
#   dist/LuzCinema.exe       -> edição Simples (uma lâmpada)
#   dist/LuzCinemaMulti.exe  -> edição Multi (várias lâmpadas por zona)
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(SPECPATH)
ICON = os.path.join(ROOT, 'luzcinema', 'assets', 'luzcinema.ico')

datas = [(ICON, os.path.join('luzcinema', 'assets'))]
binaries = []
hiddenimports = ['qrcode.image.pil', 'luzcinema.tuya_cloud', 'luzcinema.tuya_link']
for package in ('mss', 'tinytuya', 'tuya_sharing', 'pystray'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

EXCLUDES = ['numpy', 'pandas', 'scipy', 'matplotlib', 'IPython', 'pytest']


def build(script, name):
    analysis = Analysis([os.path.join(ROOT, script)], pathex=[ROOT], binaries=binaries, datas=datas,
                        hiddenimports=hiddenimports, excludes=EXCLUDES, noarchive=False, optimize=0)
    return EXE(PYZ(analysis.pure), analysis.scripts, analysis.binaries, analysis.datas, [],
               name=name, debug=False, strip=False, upx=True, console=False, icon=ICON)


build('luz_cinema.py', 'LuzCinema')
build('luz_cinema_multi.py', 'LuzCinemaMulti')
