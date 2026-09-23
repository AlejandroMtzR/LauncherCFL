# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# --- DATAS ---
# Empaqueta toda la carpeta assets/ manteniendo la ruta relativa
# "assets/..." que usa resource_path()/recurso().
datas = [('assets', 'assets')]
datas += collect_data_files('qtawesome')

# --- HIDDEN IMPORTS ---
hiddenimports = []
hiddenimports += collect_submodules('gdown')
hiddenimports += collect_submodules('minecraft_launcher_lib')
hiddenimports += collect_submodules('qtawesome')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CFL-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/logo.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CFL-Launcher-onedir',
)
