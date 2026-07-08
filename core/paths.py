# -*- coding: utf-8 -*-

import os

APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "CFLLauncher")
os.makedirs(APP_DIR, exist_ok=True)

# Archivo donde guardamos una ruta de .minecraft elegida por el usuario
GAMEDIR_OVERRIDE_FILE = os.path.join(APP_DIR, "gamedir.txt")


# =========================================================================
# .MINECRAFT
# =========================================================================
def _default_minecraft_dir():
    base = os.getenv("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, ".minecraft")


def get_minecraft_dir():
    """
    Devuelve la carpeta .minecraft a usar.
    Prioridad: override del usuario (si existe y es válido) → default.
    """
    try:
        with open(GAMEDIR_OVERRIDE_FILE, encoding="utf-8") as f:
            p = f.read().strip()
        if p and os.path.isdir(os.path.dirname(p) or p):
            return p
    except OSError:
        pass
    return _default_minecraft_dir()


def set_minecraft_dir(path: str):
    """
    Fija una ruta personalizada de .minecraft (p. ej. F:\\Juegos\\.minecraft).
    Úsalo desde la página AJUSTES con un selector de carpeta.
    """
    os.makedirs(APP_DIR, exist_ok=True)
    with open(GAMEDIR_OVERRIDE_FILE, "w", encoding="utf-8") as f:
        f.write(path.strip())


def clear_minecraft_dir_override():
    try:
        os.remove(GAMEDIR_OVERRIDE_FILE)
    except OSError:
        pass


# =========================================================================
# UNIDADES DISPONIBLES
# =========================================================================
def available_drives():
    """Lista de raíces de unidad existentes: ['C:\\\\', 'D:\\\\', 'F:\\\\', ...]."""
    drives = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            drives.append(root)
    return drives


# =========================================================================
# LAUNCHER OFICIAL DE MINECRAFT
# =========================================================================
# Rutas relativas a la raíz de CUALQUIER unidad donde suele quedar el launcher.
_LAUNCHER_RELATIVE_PATHS = [
    r"Program Files (x86)\Minecraft Launcher\MinecraftLauncher.exe",
    r"Program Files\Minecraft Launcher\MinecraftLauncher.exe",
    r"XboxGames\Minecraft Launcher\Content\Minecraft.exe",
    r"Minecraft Launcher\MinecraftLauncher.exe",
    r"Games\Minecraft Launcher\MinecraftLauncher.exe",
]


def find_launcher_exe():
    """
    Devuelve la ruta del .exe del launcher oficial, o None si no se encuentra.
    Primero prueba variables de entorno; luego BARRE TODAS las unidades
    (así encuentra instalaciones en D:, F:, etc.).
    """
    # 1) Rutas por variables de entorno (instalación "normal" en C:)
    env_candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Minecraft Launcher\MinecraftLauncher.exe"),
        os.path.expandvars(r"%ProgramFiles%\Minecraft Launcher\MinecraftLauncher.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Minecraft Launcher\MinecraftLauncher.exe"),
    ]
    for p in env_candidates:
        if os.path.isfile(p):
            return p

    # 2) Barrido por todas las unidades (maneja F:, D: y letras cambiantes)
    for drive in available_drives():
        for rel in _LAUNCHER_RELATIVE_PATHS:
            p = os.path.join(drive, rel)
            if os.path.isfile(p):
                return p

    return None
