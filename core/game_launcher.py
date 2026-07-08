# -*- coding: utf-8 -*-
"""
core/game_launcher.py  (versión nueva)

Antes esto solo ABRÍA el launcher oficial de Microsoft. Eso obliga a ser
premium y a tener el perfil de Forge configurado a mano.

Ahora podemos lanzar Minecraft NOSOTROS con minecraft-launcher-lib:
  - Descarga cualquier versión de Minecraft (archivos públicos de Mojang,
    no requieren cuenta; Minecraft Java no tiene DRM en el cliente).
  - Instala Forge para el modpack.
  - Lanza en modo offline (no premium) o premium.

Requisitos:
  pip install minecraft-launcher-lib
  Java 17 instalado (para 1.20.1). La lib puede instalar el runtime de Mojang.
"""

import os
import subprocess
import minecraft_launcher_lib as mll

# El modpack de ChafaLand vive en el .minecraft estándar (tu installer ya
# copia ahí). Usamos ese mismo directorio para lanzar.
MC_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), ".minecraft")

# Versión del modpack
MODPACK_MC_VERSION = "1.20.1"
# Deja None para autodetectar el Forge recomendado, o fija el que usa tu pack,
# p. ej. "1.20.1-47.3.0"
MODPACK_FORGE_VERSION = None


def _callback(log, progress):
    """Adaptador entre los callbacks de la lib y tus signals log()/progress()."""
    state = {"max": 0}

    def set_status(text):
        log(f"⏳ {text}")

    def set_progress(value):
        if state["max"]:
            progress(int(value / state["max"] * 100))

    def set_max(value):
        state["max"] = value or 1

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}


# ── Instalación de versión / Forge ────────────────────────────────────────
def ensure_vanilla(version: str, log, progress) -> None:
    log(f"📥 Verificando Minecraft {version}...")
    mll.install.install_minecraft_version(version, MC_DIR, callback=_callback(log, progress))
    log(f"✅ Minecraft {version} listo")


def ensure_forge(log, progress) -> str:
    """Instala Forge para el modpack y devuelve el id lanzable."""
    forge = MODPACK_FORGE_VERSION or mll.forge.find_forge_version(MODPACK_MC_VERSION)
    if not forge:
        raise RuntimeError(f"No encontré Forge para {MODPACK_MC_VERSION}")

    installed_id = mll.forge.forge_to_installed_version(forge)
    already = mll.utils.get_installed_versions(MC_DIR)
    if any(v["id"] == installed_id for v in already):
        log(f"✅ Forge ya instalado: {installed_id}")
        return installed_id

    log(f"📥 Instalando Forge {forge}...")
    if not mll.forge.supports_automatic_install(forge):
        raise RuntimeError(f"Forge {forge} necesita instalación manual")
    mll.forge.install_forge_version(forge, MC_DIR, callback=_callback(log, progress))
    log(f"✅ Forge listo: {installed_id}")
    return installed_id


# ── Lanzar ────────────────────────────────────────────────────────────────
def launch_version(version_id, account, log, ram_gb=6, extra_jvm=None):
    """Lanza una versión ya instalada con la cuenta dada (offline o premium)."""
    options = account.to_options()
    options["jvmArguments"] = [f"-Xmx{ram_gb}G", "-Xms2G"] + (extra_jvm or [])
    options["launcherName"] = "CFL Launcher"
    options["gameDirectory"] = MC_DIR

    log(f"🎮 Lanzando como {account.username} ({account.mode})...")
    command = mll.command.get_minecraft_command(version_id, MC_DIR, options)

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # que no salga consola negra

    subprocess.Popen(command, cwd=MC_DIR, creationflags=creationflags)
    log("✅ Minecraft iniciado")
    return True


def play_modpack(account, log, progress, ram_gb=6):
    """
    Flujo completo para JUGAR el modpack ChafaLand:
      instala vanilla + Forge si falta, y lanza con la cuenta actual.
    Sirve igual para premium y para offline.
    """
    ensure_vanilla(MODPACK_MC_VERSION, log, progress)
    version_id = ensure_forge(log, progress)
    progress(100)
    return launch_version(version_id, account, log, ram_gb=ram_gb)


# ── "Cualquier versión" (para no premium que solo quiera vanilla) ─────────
def list_versions(include_snapshots=False, include_old=False):
    out = []
    for v in mll.utils.get_version_list():
        t = v["type"]
        if t == "release" or (include_snapshots and t == "snapshot") \
           or (include_old and t.startswith("old")):
            out.append(v["id"])
    return out


def play_vanilla(version, account, log, progress, ram_gb=4):
    ensure_vanilla(version, log, progress)
    progress(100)
    return launch_version(version, account, log, ram_gb=ram_gb)


# ── PREMIUM (opción A): abrir el launcher oficial, como antes ─────────────
# Se mantiene por compatibilidad: main_window.py la importa y el flujo
# premium la sigue usando.
def launch_minecraft(log):
    log("🎮 Intentando abrir Minecraft...")

    # 1. EXE clásico
    paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Minecraft Launcher\MinecraftLauncher.exe"),
        os.path.expandvars(r"%ProgramFiles%\Minecraft Launcher\MinecraftLauncher.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Minecraft Launcher\MinecraftLauncher.exe"),
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path])
                log(f"✅ Launcher abierto (exe)\n📂 {path}")
                return True
            except Exception as e:
                log(f"❌ Error exe: {e}")

    # 2. Microsoft Store
    try:
        subprocess.run(
            'start shell:AppsFolder\\Microsoft.4297127D64EC6_8wekyb3d8bbwe!Minecraft',
            shell=True,
        )
        log("✅ Launcher abierto")
        return True
    except Exception as e:
        log(f"❌ Error Store: {e}")

    # 3. fallback protocolo
    try:
        subprocess.run("start minecraft://", shell=True)
        log("⚠️ Intento con protocolo minecraft://")
        return True
    except Exception as e:
        log(f"❌ Fallback falló: {e}")

    log("❌ No se pudo abrir Minecraft")
    return False