import json
import os
import re
import subprocess
import threading
import time
import warnings

import minecraft_launcher_lib as mll

from core import paths

MODPACK_MC_VERSION = "1.20.1"

#    Déjalo en None SOLO para que use el Forge ya instalado más nuevo.
MODPACK_FORGE_VERSION = "1.20.1-47.4.10"

LAUNCHER_NAME = "CFL Launcher"

# Mismos flags que usa el launcher oficial: G1GC ajustado para Minecraft
# (menos tirones por el recolector de basura, sobre todo con muchos mods).
JVM_PERFORMANCE_FLAGS = [
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+UseG1GC",
    "-XX:G1NewSizePercent=20",
    "-XX:G1ReservePercent=20",
    "-XX:MaxGCPauseMillis=50",
    "-XX:G1HeapRegionSize=32M",
]

# Tras una verificación completa correcta, los siguientes "Jugar" se saltan
# el hash de miles de archivos (assets, librerías, Java) durante este tiempo.
VERIFY_TTL_SECONDS = 3 * 24 * 3600
VERIFIED_FILE = os.path.join(paths.APP_DIR, "verified_versions.json")

# Si el juego se cierra con error antes de este tiempo, se considera que no
# arrancó: se avisa al usuario y se fuerza verificación completa la próxima vez.
EARLY_CRASH_SECONDS = 90

LAUNCH_LOG_NAME = "cfl-ultimo-arranque.log"

_VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
_MANIFEST_TTL_SECONDS = 3600

# Componente de Java de Mojang -> versión mayor (solo para mostrarlo en la UI)
_JAVA_MAJOR = {
    "jre-legacy": "8",
    "java-runtime-alpha": "16",
    "java-runtime-beta": "17",
    "java-runtime-gamma": "17",
    "java-runtime-gamma-snapshot": "17",
    "java-runtime-delta": "21",
}

# Estado del último Minecraft lanzado por ESTE launcher.
_state_lock = threading.Lock()
_running = None     # dict con proc, started, version_id, game_dir, log_path, mc_dir
_last_exit = None   # igual que _running + code, seconds

_manifest_lock = threading.Lock()
_manifest_cache = {"at": 0.0, "versions": None}


def _mc_dir():
    return paths.get_minecraft_dir()


def modpack_version_id():
    """Id de la versión de Forge del modpack: '1.20.1-forge-47.4.10'."""
    if MODPACK_FORGE_VERSION:
        mc, forge = MODPACK_FORGE_VERSION.split("-", 1)
        return f"{mc}-forge-{forge}"
    installed = _installed_forge_ids(_mc_dir())
    return installed[-1] if installed else ""


# Traducción de los estados que reporta minecraft_launcher_lib.
_STATUS_ES = {
    "Download Libraries": "Descargando librerías...",
    "Download Assets": "Descargando recursos del juego...",
    "Install java runtime": "Instalando Java (automático)...",
    "Installation complete": "Archivos del juego listos",
    "Running installer": "Ejecutando instalador de Forge...",
}


def _callback(log, progress):
    state = {"max": 0, "downloads": 0, "last_log": 0.0}

    def set_status(text):
        text = str(text or "")
        # mll reporta CADA archivo ("Download xyz.png"): miles de líneas que
        # saturan el log y la UI. Se resumen como máximo una vez por segundo.
        if text.startswith("Download ") and text not in _STATUS_ES:
            state["downloads"] += 1
            now = time.monotonic()
            if now - state["last_log"] >= 1.2:
                state["last_log"] = now
                log(f"⬇️  Descargando archivos del juego... ({state['downloads']})")
            return
        if text.startswith("Running processor"):
            return
        log(f"⏳ {_STATUS_ES.get(text, text)}")

    def set_progress(value):
        if state["max"]:
            progress(max(0, min(100, int(value / state["max"] * 100))))

    def set_max(value):
        state["max"] = value or 1

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}


# ── Lectura de versiones locales ─────────────────────────────────────────
def _read_version_json(mc_dir, version_id):
    path = os.path.join(mc_dir, "versions", version_id, f"{version_id}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _version_installed(mc_dir, version_id) -> bool:
    """comprueba por carpeta, sin depender de parsear cada JSON."""
    folder = os.path.join(mc_dir, "versions", version_id)
    return os.path.isdir(folder) and os.path.isfile(
        os.path.join(folder, f"{version_id}.json"))


def _version_chain(mc_dir, version_id):
    """[json de la versión, json padre, ...] o None si falta alguno."""
    chain, seen, current = [], set(), version_id
    while current:
        if current in seen or len(chain) > 8:
            return None
        seen.add(current)
        data = _read_version_json(mc_dir, current)
        if data is None:
            return None
        chain.append(data)
        current = data.get("inheritsFrom")
    return chain


def _library_rel_path(lib):
    artifact = (lib.get("downloads") or {}).get("artifact") or {}
    if artifact.get("path"):
        return artifact["path"]
    name = lib.get("name", "")
    ext = "jar"
    if "@" in name:
        name, ext = name.rsplit("@", 1)
    parts = name.split(":")
    if len(parts) < 3:
        return None
    group, artifact_id, version = parts[0], parts[1], parts[2]
    classifier = f"-{parts[3]}" if len(parts) > 3 else ""
    return os.path.join(*group.split("."), artifact_id, version,
                        f"{artifact_id}-{version}{classifier}.{ext}")


def _java_component(chain):
    for data in chain or []:
        jv = data.get("javaVersion")
        if isinstance(jv, dict) and jv.get("component"):
            return jv["component"]
    return None


def is_launchable(mc_dir, version_id) -> bool:
    """
    Chequeo RÁPIDO (sin hashes ni red) de lo mínimo para arrancar: JSONs de
    toda la cadena, jar base, índice de assets, librerías comunes y Java.
    """
    chain = _version_chain(mc_dir, version_id)
    if not chain:
        return False
    root = chain[-1]
    root_id = root.get("id", "")
    if not os.path.isfile(os.path.join(mc_dir, "versions", root_id, f"{root_id}.jar")):
        return False
    asset_index = (root.get("assetIndex") or {}).get("id") or root.get("assets")
    if asset_index and not os.path.isfile(
            os.path.join(mc_dir, "assets", "indexes", f"{asset_index}.json")):
        return False
    for data in chain:
        for lib in data.get("libraries", []):
            # Las que tienen reglas son específicas de un sistema operativo.
            if not isinstance(lib, dict) or "rules" in lib or "natives" in lib:
                continue
            rel = _library_rel_path(lib)
            if rel and not os.path.isfile(os.path.join(mc_dir, "libraries", rel)):
                return False
    component = _java_component(chain)
    if component and not mll.runtime.get_executable_path(component, mc_dir):
        return False
    return True


# ── Registro de verificaciones completas ─────────────────────────────────
def _verify_key(mc_dir, version_id):
    return f"{os.path.normcase(os.path.abspath(mc_dir))}|{version_id}"


def _load_verified():
    try:
        with open(VERIFIED_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_verified(data):
    try:
        tmp = VERIFIED_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, VERIFIED_FILE)
    except OSError:
        pass


def _mark_verified(mc_dir, version_id):
    data = _load_verified()
    data[_verify_key(mc_dir, version_id)] = time.time()
    _save_verified(data)


def _recently_verified(mc_dir, version_id):
    stamp = _load_verified().get(_verify_key(mc_dir, version_id))
    try:
        return 0 <= time.time() - float(stamp) < VERIFY_TTL_SECONDS
    except (TypeError, ValueError):
        return False


def forget_verified(mc_dir=None, version_id=None):
    """
    Olvida verificaciones: una versión concreta, todas las de un .minecraft,
    o todas (sin argumentos). Úsalo tras instalar/actualizar/reparar.
    """
    if mc_dir is None and version_id is None:
        _save_verified({})
        return
    data = _load_verified()
    if version_id is not None:
        data.pop(_verify_key(mc_dir or _mc_dir(), version_id), None)
    else:
        prefix = _verify_key(mc_dir, "")
        data = {k: v for k, v in data.items() if not k.startswith(prefix)}
    _save_verified(data)


def _short_error(exc):
    text = str(exc).strip() or exc.__class__.__name__
    return text if len(text) <= 160 else text[:157] + "..."


def _friendly_install_error(version, exc):
    name = exc.__class__.__name__
    if name == "VersionNotFound":
        return RuntimeError(
            f"La versión {version} no existe o no se pudo descargar la lista de "
            "versiones (revisa tu conexión a internet).")
    try:
        import requests
        if isinstance(exc, requests.RequestException):
            return RuntimeError(
                f"Sin conexión: no se pudo descargar Minecraft {version}. "
                "Revisa tu internet e inténtalo de nuevo.")
    except Exception:
        pass
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:
        return RuntimeError("No hay espacio suficiente en el disco para instalar la versión.")
    return RuntimeError(f"No se pudo instalar Minecraft {version}: {_short_error(exc)}")


# ── Instalación de versión / Forge ────────────────────────────────────────
def ensure_vanilla(version: str, log, progress, force_verify=False) -> None:
    mc_dir = _mc_dir()
    if (not force_verify and _recently_verified(mc_dir, version)
            and is_launchable(mc_dir, version)):
        log(f"✅ Minecraft {version} listo (verificado recientemente)")
        return

    log(f"📥 Verificando Minecraft {version}...")
    try:
        mll.install.install_minecraft_version(version, mc_dir, callback=_callback(log, progress))
    except Exception as exc:
        # Sin internet (o un fallo puntual de Mojang) no debe impedir jugar
        # si los archivos ya están en disco.
        if is_launchable(mc_dir, version):
            log(f"⚠️ No se pudo verificar en línea ({_short_error(exc)})")
            log("   → se usarán los archivos que ya tienes instalados")
            return
        raise _friendly_install_error(version, exc) from exc
    _mark_verified(mc_dir, version)
    log(f"✅ Minecraft {version} listo")


def _installed_forge_ids(mc_dir):
    """IDs '1.20.1-forge-XX.Y.Z' """
    vdir = os.path.join(mc_dir, "versions")
    prefix = f"{MODPACK_MC_VERSION}-forge-"
    if not os.path.isdir(vdir):
        return []
    out = []
    for name in os.listdir(vdir):
        if name.startswith(prefix) and _version_installed(mc_dir, name):
            out.append(name)
    return sorted(out)


def list_installed_forge_versions(exclude_modpack=True):
    """Forge instalados en .minecraft (sin el del modpack: ya tiene su tarjeta)."""
    mc_dir = _mc_dir()
    vdir = os.path.join(mc_dir, "versions")
    if not os.path.isdir(vdir):
        return []
    skip = modpack_version_id() if exclude_modpack else None
    out = []
    for name in os.listdir(vdir):
        if name == skip:
            continue
        if "-forge-" in name.lower() and _version_installed(mc_dir, name):
            out.append(name)
    return sorted(out)


def installed_vanilla_versions():
    """Versiones vanilla con JSON + jar en disco (se pueden jugar sin internet)."""
    mc_dir = _mc_dir()
    vdir = os.path.join(mc_dir, "versions")
    out = set()
    try:
        names = os.listdir(vdir)
    except OSError:
        return out
    for name in names:
        jar = os.path.join(vdir, name, f"{name}.jar")
        if not os.path.isfile(jar):
            continue
        data = _read_version_json(mc_dir, name)
        if data and "inheritsFrom" not in data:
            out.add(name)
    return out


def ensure_forge(log, progress) -> str:
    """Devuelve el id de Forge lanzable, instalándolo si hace falta."""
    mc_dir = _mc_dir()

    # 1) Versión FIJADA por el modpack (lo recomendado)
    if MODPACK_FORGE_VERSION:
        installed_id = modpack_version_id()
        if _version_installed(mc_dir, installed_id):
            log(f"✅ Forge del modpack ya instalado: {installed_id}")
            return installed_id
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        forge = mll.forge.find_forge_version(MODPACK_MC_VERSION)
        if not forge:
            raise RuntimeError(f"No encontré Forge para {MODPACK_MC_VERSION}")
        installed_id = mll.forge.forge_to_installed_version(forge)
        log(f"⚠️ Instalando Forge recomendado {forge} (revisa que tus mods lo acepten)")
        mll.forge.install_forge_version(forge, mc_dir, callback=_callback(log, progress))
    return installed_id


# ── Carpetas de juego ─────────────────────────────────────────────────────
def game_dir_for(target):
    """
    Carpeta de juego (saves, options, mods...) para un destino:
      "modpack"               -> .minecraft (la del pack)
      ("installed", forge_id) -> instancia propia de ese Forge
      ("vanilla", version)    -> instancia vanilla / snapshots / antiguas
    """
    if target == "modpack":
        return _mc_dir()
    kind, version = target
    if kind == "installed":
        return paths.instance_dir(version)
    vtype = version_type(version)
    if vtype == "snapshot":
        return paths.instance_dir("snapshots")
    if vtype.startswith("old"):
        return paths.instance_dir("antiguas")
    return paths.instance_dir("vanilla")


# ── Lanzar ────────────────────────────────────────────────────────────────
def _launcher_version():
    try:
        from core.launcherUpdate import get_local_version
        return get_local_version()
    except Exception:
        return "1.0"


def launch_version(version_id, account, log, ram_gb=6, extra_jvm=None, game_dir=None):
    global _running
    mc_dir = _mc_dir()
    game_dir = game_dir or mc_dir
    os.makedirs(game_dir, exist_ok=True)
    ram_gb = max(1, int(ram_gb))

    options = account.to_options()
    options["jvmArguments"] = (
        [f"-Xmx{ram_gb}G", f"-Xms{min(2, ram_gb)}G"]
        + JVM_PERFORMANCE_FLAGS + list(extra_jvm or [])
    )
    options["launcherName"] = LAUNCHER_NAME
    options["launcherVersion"] = _launcher_version()
    options["gameDirectory"] = game_dir

    log(f"🎮 Lanzando como {account.username} ({account.mode})...")
    command = mll.command.get_minecraft_command(version_id, mc_dir, options)

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    log_path = os.path.join(game_dir, LAUNCH_LOG_NAME)
    # La salida del juego va a un archivo: sirve para explicar un cierre
    # inesperado y evita heredar handles inválidos del launcher sin consola.
    with open(log_path, "wb") as out:
        proc = subprocess.Popen(
            command, cwd=game_dir, stdout=out, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, creationflags=creationflags)

    with _state_lock:
        _running = {
            "proc": proc,
            "started": time.monotonic(),
            "version_id": version_id,
            "game_dir": game_dir,
            "mc_dir": mc_dir,
            "log_path": log_path,
        }
    log("✅ Minecraft iniciado")
    return True


# ── ¿El juego ya está corriendo? ──────────────────────────────────────────
def is_tracked_game_running():
    """Rápido: ¿sigue vivo el proceso que ESTE launcher lanzó? (poll instantáneo)"""
    global _running, _last_exit
    with _state_lock:
        if _running is None:
            return False
        code = _running["proc"].poll()
        if code is None:
            return True
        info = dict(_running)
        info.pop("proc", None)
        info["code"] = code
        info["seconds"] = time.monotonic() - info["started"]
        _last_exit = info
        _running = None
    if info["code"] != 0 and info["seconds"] < EARLY_CRASH_SECONDS:
        # No arrancó bien: la próxima vez verificar todo en vez de confiar.
        # (El registro está en la versión base: 1.20.1 para el Forge del pack.)
        for data in _version_chain(info["mc_dir"], info["version_id"]) or []:
            forget_verified(info["mc_dir"], data.get("id"))
        forget_verified(info["mc_dir"], info["version_id"])
    return False


def pop_last_exit():
    """Info del último cierre del juego (una sola vez) o None."""
    global _last_exit
    with _state_lock:
        info, _last_exit = _last_exit, None
    return info


def is_early_crash(info):
    return bool(info) and info.get("code") not in (0, None) \
        and info.get("seconds", 1e9) < EARLY_CRASH_SECONDS


def crash_log_tail(info, max_lines=14):
    """Últimas líneas útiles de la salida del juego (para mostrar el error)."""
    path = (info or {}).get("log_path")
    if not path:
        return ""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 64 * 1024))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-max_lines:])


def _java_processes_exist():
    """Chequeo barato (tasklist) antes de lanzar PowerShell, que tarda ~1 s."""
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout.lower()
        return '"java.exe"' in out or '"javaw.exe"' in out
    except Exception:
        return True  # ante la duda, que decida el escaneo completo


def _scan_minecraft_running():

    if os.name != "nt":
        return False
    if not _java_processes_exist():
        return False
    try:
        mc_dir = _mc_dir().lower()
        instances = paths.INSTANCES_DIR.lower()
        ps = ("Get-CimInstance Win32_Process -Filter "
              "\"Name='javaw.exe' or Name='java.exe'\" | "
              "Select-Object -ExpandProperty CommandLine")
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        blob = (out.stdout or "").lower()
        # Coincidir por la ruta del .minecraft o por marcadores claros de MC/Forge.
        return (mc_dir in blob) or (instances in blob) \
            or ("net.minecraft" in blob) or ("minecraftforge" in blob)
    except Exception:
        return False


def is_game_running():
    """Completo: proceso rastreado + escaneo. Úsalo al presionar Jugar."""
    if is_tracked_game_running():
        return True
    return _scan_minecraft_running()


def play_modpack(account, log, progress, ram_gb=6):
    ensure_vanilla(MODPACK_MC_VERSION, log, progress)
    version_id = ensure_forge(log, progress)
    progress(100)
    return launch_version(version_id, account, log, ram_gb=ram_gb,
                          game_dir=game_dir_for("modpack"))


# ── "Cualquier versión" (independiente del modpack) ───────────────────────
def version_manifest(force=False):
    """
    Lista [{id, type}] de Mojang, cacheada en memoria. Una sola descarga
    sirve para Releases / Snapshots / Antiguas (antes se bajaba en cada clic).
    """
    with _manifest_lock:
        cached = _manifest_cache["versions"]
        fresh = cached is not None and \
            time.time() - _manifest_cache["at"] < _MANIFEST_TTL_SECONDS
        if fresh and not force:
            return cached
    try:
        import requests
        r = requests.get(_VERSION_MANIFEST_URL, timeout=15,
                         headers={"User-Agent": LAUNCHER_NAME})
        r.raise_for_status()
        versions = [
            {"id": v["id"], "type": v.get("type", "release")}
            for v in r.json().get("versions", []) if v.get("id")
        ]
    except Exception:
        if cached is not None:
            return cached
        raise
    with _manifest_lock:
        _manifest_cache.update(at=time.time(), versions=versions)
    return versions


def version_type_map():
    """{id: tipo} de la lista ya descargada (vacío si aún no se descargó)."""
    with _manifest_lock:
        cached = _manifest_cache["versions"] or []
    return {v["id"]: v["type"] for v in cached}


def version_type(version_id):
    vtype = version_type_map().get(version_id)
    if vtype:
        return vtype
    data = _read_version_json(_mc_dir(), version_id) or {}
    return str(data.get("type") or "release")


def _accept_type(vtype, include_snapshots, include_old):
    return vtype == "release" or (include_snapshots and vtype == "snapshot") \
        or (include_old and vtype.startswith("old"))


def list_versions(include_snapshots=False, include_old=False):
    try:
        manifest = version_manifest()
    except Exception:
        # Sin internet: al menos las versiones que ya están en disco.
        local = installed_vanilla_versions()
        if not local:
            raise
        mc_dir = _mc_dir()
        out = []
        for vid in local:
            data = _read_version_json(mc_dir, vid) or {}
            if _accept_type(str(data.get("type") or "release"), include_snapshots, include_old):
                out.append((str(data.get("releaseTime") or ""), vid))
        return [vid for _t, vid in sorted(out, reverse=True)]
    return [v["id"] for v in manifest
            if _accept_type(v["type"], include_snapshots, include_old)]


def play_vanilla(version, account, log, progress, ram_gb=4):
    ensure_vanilla(version, log, progress)
    progress(100)
    game_dir = game_dir_for(("vanilla", version))
    log(f"📂 Carpeta independiente del modpack: {game_dir}")
    return launch_version(version, account, log, ram_gb=ram_gb, game_dir=game_dir)


def play_installed(version_id, account, log, progress, ram_gb=4):
    mc_dir = _mc_dir()
    if not _version_installed(mc_dir, version_id):
        raise RuntimeError(f"La versión {version_id} no está instalada")
    parent = (_read_version_json(mc_dir, version_id) or {}).get("inheritsFrom")
    if parent:
        ensure_vanilla(parent, log, progress)
    progress(100)
    game_dir = game_dir_for(("installed", version_id))
    log(f"📂 Carpeta independiente del modpack: {game_dir}")
    return launch_version(version_id, account, log, ram_gb=ram_gb, game_dir=game_dir)


# ── Java que se usará (sin lanzar procesos) ───────────────────────────────
def java_label(target="modpack"):
    """Texto corto con el Java que usará el destino: 'Java 17.0.8'."""
    mc_dir = _mc_dir()
    if target == "modpack":
        version_id = modpack_version_id() or MODPACK_MC_VERSION
    else:
        version_id = target[1]
    chain = _version_chain(mc_dir, version_id)
    if chain is None and target == "modpack":
        chain = _version_chain(mc_dir, MODPACK_MC_VERSION)
    component = _java_component(chain) or ("java-runtime-gamma" if target == "modpack" else None)
    if not component:
        return "automático"
    major = _JAVA_MAJOR.get(component, "")
    exe = mll.runtime.get_executable_path(component, mc_dir)
    if not exe:
        return f"{major} (automático)" if major else "automático"
    release = os.path.join(os.path.dirname(os.path.dirname(exe)), "release")
    try:
        with open(release, encoding="utf-8", errors="replace") as f:
            m = re.search(r'JAVA_VERSION="([^"]+)"', f.read())
        if m:
            return m.group(1)
    except OSError:
        pass
    return major or "instalado"


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
