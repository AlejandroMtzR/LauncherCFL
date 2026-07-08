
import os
import subprocess
import minecraft_launcher_lib as mll

from core import paths

MODPACK_MC_VERSION = "1.20.1"

# 👇 FIJA AQUÍ la versión de Forge de tu modpack (sin la palabra "forge").
#    Debe ser >= la que piden tus mods. La tuya es 47.4.10.
#    Déjalo en None SOLO si quieres que use el Forge ya instalado más nuevo.
MODPACK_FORGE_VERSION = "1.20.1-47.4.10"


def _mc_dir():
    return paths.get_minecraft_dir()


def _callback(log, progress):
    state = {"max": 0}

    def set_status(text):
        log(f"⏳ {text}")

    def set_progress(value):
        if state["max"]:
            progress(int(value / state["max"] * 100))

    def set_max(value):
        state["max"] = value or 1

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}


def _version_installed(mc_dir, version_id) -> bool:
    """Robusto: comprueba por carpeta, sin depender de parsear cada JSON."""
    folder = os.path.join(mc_dir, "versions", version_id)
    return os.path.isdir(folder) and os.path.isfile(
        os.path.join(folder, f"{version_id}.json"))


def _installed_forge_ids(mc_dir):
    """IDs '1.20.1-forge-XX.Y.Z' presentes en /versions (por nombre de carpeta)."""
    vdir = os.path.join(mc_dir, "versions")
    prefix = f"{MODPACK_MC_VERSION}-forge-"
    if not os.path.isdir(vdir):
        return []
    out = []
    for name in os.listdir(vdir):
        if name.startswith(prefix) and _version_installed(mc_dir, name):
            out.append(name)
    return sorted(out)


# ── Instalación de versión / Forge ────────────────────────────────────────
def ensure_vanilla(version: str, log, progress) -> None:
    mc_dir = _mc_dir()
    log(f"📥 Verificando Minecraft {version}...")
    mll.install.install_minecraft_version(version, mc_dir, callback=_callback(log, progress))
    log(f"✅ Minecraft {version} listo")


def ensure_forge(log, progress) -> str:
    """Devuelve el id de Forge lanzable, instalándolo si hace falta."""
    mc_dir = _mc_dir()

    # 1) Versión FIJADA por el modpack (lo recomendado)
    if MODPACK_FORGE_VERSION:
        installed_id = mll.forge.forge_to_installed_version(MODPACK_FORGE_VERSION)
        if _version_installed(mc_dir, installed_id):
            log(f"✅ Forge del modpack ya instalado: {installed_id}")
            return installed_id
        if not mll.forge.is_forge_version_valid(MODPACK_FORGE_VERSION):
            raise RuntimeError(f"Forge {MODPACK_FORGE_VERSION} no existe")
        if not mll.forge.supports_automatic_install(MODPACK_FORGE_VERSION):
            raise RuntimeError(f"Forge {MODPACK_FORGE_VERSION} requiere instalación manual")
        log(f"📥 Instalando Forge {MODPACK_FORGE_VERSION}...")
        mll.forge.install_forge_version(
            MODPACK_FORGE_VERSION, mc_dir, callback=_callback(log, progress))
        log(f"✅ Forge listo: {installed_id}")
        return installed_id

    # 2) Sin fijar: usa el Forge ya instalado MÁS NUEVO (evita el recomendado viejo)
    installed = _installed_forge_ids(mc_dir)
    if installed:
        chosen = installed[-1]
        log(f"✅ Usando Forge ya instalado: {chosen}")
        return chosen

    # 3) Último recurso: el recomendado de Mojang (puede quedar corto)
    forge = mll.forge.find_forge_version(MODPACK_MC_VERSION)
    if not forge:
        raise RuntimeError(f"No encontré Forge para {MODPACK_MC_VERSION}")
    installed_id = mll.forge.forge_to_installed_version(forge)
    log(f"⚠️ Instalando Forge recomendado {forge} (revisa que tus mods lo acepten)")
    mll.forge.install_forge_version(forge, mc_dir, callback=_callback(log, progress))
    return installed_id


# ── Lanzar ────────────────────────────────────────────────────────────────
def launch_version(version_id, account, log, ram_gb=6, extra_jvm=None):
    mc_dir = _mc_dir()
    options = account.to_options()
    options["jvmArguments"] = [f"-Xmx{ram_gb}G", "-Xms2G"] + (extra_jvm or [])
    options["launcherName"] = "CFL Launcher"
    options["gameDirectory"] = mc_dir

    log(f"🎮 Lanzando como {account.username} ({account.mode})...")
    command = mll.command.get_minecraft_command(version_id, mc_dir, options)

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW

    subprocess.Popen(command, cwd=mc_dir, creationflags=creationflags)
    log("✅ Minecraft iniciado")
    return True


def play_modpack(account, log, progress, ram_gb=6):
    ensure_vanilla(MODPACK_MC_VERSION, log, progress)
    version_id = ensure_forge(log, progress)
    progress(100)
    return launch_version(version_id, account, log, ram_gb=ram_gb)


# ── "Cualquier versión" (vanilla) ─────────────────────────────────────────
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


# ── PREMIUM (opción A): abrir el launcher oficial ─────────────────────────
def launch_minecraft(log):
    log("🎮 Intentando abrir Minecraft...")
    exe = paths.find_launcher_exe()
    if exe:
        try:
            subprocess.Popen([exe])
            log(f"✅ Launcher abierto\n📂 {exe}")
            return True
        except Exception as e:
            log(f"❌ Error exe: {e}")
    try:
        subprocess.run(
            'start shell:AppsFolder\\Microsoft.4297127D64EC6_8wekyb3d8bbwe!Minecraft',
            shell=True)
        log("✅ Launcher abierto (Store)")
        return True
    except Exception as e:
        log(f"❌ Error Store: {e}")
    try:
        subprocess.run("start minecraft://", shell=True)
        log("⚠️ Intento con protocolo minecraft://")
        return True
    except Exception as e:
        log(f"❌ Fallback falló: {e}")
    log("❌ No se pudo abrir Minecraft")
    return False