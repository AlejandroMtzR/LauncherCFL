# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# --- DATAS ---
# Empaqueta toda la carpeta assets/ (banner, hero, logo, mods_banner)
# manteniendo la misma ruta relativa "assets/..." que usa resource_path().
datas = [('assets', 'assets')]
# qtawesome trae sus propias fuentes .ttf/.otf con los glifos de los iconos;
# sin esto los iconos de Discord/Web/GitHub salen en blanco o crashean.
datas += collect_data_files('qtawesome')

# --- HIDDEN IMPORTS ---
# gdown y minecraft_launcher_lib se importan dentro de funciones (import "en
# caliente"), así que el análisis estático de PyInstaller no los detecta
# solo. collect_submodules jala también sus dependencias internas.
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
    a.binaries,
    a.datas,
    [],
    # Debe coincidir EXACTO con EXE_NAME en core/launcherUpdate.py
    # (ahí está puesto "CFL-Launcher.exe") para que el auto-update
    # encuentre el asset correcto en el release de GitHub.
    name='CFL-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX apagado: comprime/corrompe las DLL de Qt y hace que varios
    # antivirus pongan el .exe en cuarentena a medio extraer -> los
    # errores de "no se encontró la DLL" que están viendo tus amigos.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Apunta al ícono real del proyecto (icono.ico no existe).
    icon=['assets/logo.ico'],
)
