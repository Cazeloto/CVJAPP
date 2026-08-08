# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

# O .env fica externo, ao lado do executável, para permitir configuração
# em produção sem incorporar credenciais ao pacote interno.
datas = [
    ('.\\assets', 'assets'),
    ('.\\build_flags\\no_tkinter.flag', '.'),
    ('.\\db\\migrations', 'db\\migrations'),
]
binaries = []
hiddenimports = [
    'flet.fastapi',
    'flet_web.fastapi',
    'pkgutil',
    'importlib.resources',
    'anyio',
    'httpx',
    'msgpack',
    'oauthlib',
    'repath',
    'psycopg',
    'psycopg_binary',
    'reportlab',
    'requests',
]
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('starlette')
hiddenimports += collect_submodules('psycopg')
hiddenimports += collect_submodules('psycopg_binary')
tmp_ret = collect_all('flet')
datas += tmp_ret[0]; binaries += tmp_ret[1]
# O servidor nao usa a CLI nem os utilitarios opcionais de criptografia do Flet.
hiddenimports += [
    module for module in tmp_ret[2]
    if not module.startswith(('flet.cli', 'flet.security', 'flet.testing'))
]
tmp_ret = collect_all('flet_web')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'PIL.ImageTk',
        'flet_desktop',
        'cryptography',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CVJAPP_Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CVJAPP_Server',
)
