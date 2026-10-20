from pathlib import Path
import importlib.metadata as metadata
import shutil
import sys

base = Path(__file__).resolve().parents[1]
target = base/'outputs'/'LuzCinema'/'licencas'
target.mkdir(exist_ok=True)
names = ['tinytuya','mss','Pillow','cryptography','cffi','pycparser','requests',
         'urllib3','certifi','charset-normalizer','idna','colorama','PyInstaller','setuptools',
         'tuya-device-sharing-sdk','qrcode','paho-mqtt']
versions=[]
for name in names:
    package=metadata.distribution(name)
    versions.append(f'{name} {package.version}')
    for item in package.files or []:
        parts=[p.lower() for p in item.parts]
        if any(p.startswith(('license','licence','copying','notice')) for p in parts):
            source=Path(package.locate_file(item))
            if source.is_file():
                dest=target/name/Path(*item.parts)
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,dest)
runtime=Path(sys.base_prefix)
if (runtime/'LICENSE.txt').exists():
    shutil.copyfile(runtime/'LICENSE.txt',target/'Python-LICENSE.txt')
for folder in ('tcl','Lib/tcl8.6','Lib/tk8.6'):
    if (runtime/folder).exists():
        for source in (runtime/folder).rglob('license.terms'):
            dest=target/'TclTk'/source.relative_to(runtime)
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest)
(target/'COMPONENTES.txt').write_text('Luz Cinema inclui software de terceiros. As licenças estão nas subpastas.\n'
    'PyInstaller utiliza a exceção de distribuição para seu bootloader.\n\n'+'\n'.join(versions),encoding='utf-8')
print('Licenças incluídas:',len(list(target.rglob('*'))),'arquivos e pastas.')
