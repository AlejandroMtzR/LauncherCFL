"""
launcherUpdate.py
Auto-actualización del launcher desde GitHub Releases.

Flujo:
  1. Lee versión local  (launcherVersion.txt en %APPDATA%\CFLLauncher\)
  2. Consulta GitHub    (API releases/latest)
  3. Compara versiones
  4. Si hay nueva:
       → descarga el .exe nuevo a %TEMP%
       → escribe update.bat que reemplaza y reinicia
       → ejecuta el .bat y cierra el launcher actual
"""

import os
import sys
import time
import requests
import subprocess

# ── Config ────────────────────────────────────────────────────────
GITHUB_USER  = "AlejandroMtzR"
GITHUB_REPO  = "LauncherCFL"
EXE_NAME     = "CFL-Launcher.exe"

API_URL      = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
HEADERS      = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

APP_DIR           = os.path.join(os.getenv("APPDATA", ""), "CFLLauncher")
LOCAL_VERSION_FILE = os.path.join(APP_DIR, "launcherVersion.txt")
os.makedirs(APP_DIR, exist_ok=True)



# 📄 VERSIÓN LOCAL

def get_local_version():
    try:
        with open(LOCAL_VERSION_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"


def save_local_version(version: str):
    with open(LOCAL_VERSION_FILE, "w") as f:
        f.write(version.strip())


# VERSIÓN REMOTA (GitHub)

def get_remote_release(log=None):
    """
    Retorna (tag_name, download_url) del último release,
    o (None, None) si falla.
    """
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        tag     = data.get("tag_name", "").lstrip("v")
        assets  = data.get("assets", [])

        # Buscar el .exe en los assets del release
        url = None
        for asset in assets:
            if asset.get("name", "").lower() == EXE_NAME.lower():
                url = asset.get("browser_download_url")
                break

        if not url:
            if log: log("⚠️ No se encontró el .exe en el release de GitHub")
            return None, None

        return tag, url

    except requests.ConnectionError:
        if log: log("⚠️ Sin conexión — no se pudo verificar actualizaciones del launcher")
        return None, None
    except Exception as e:
        if log: log(f"⚠️ Error consultando GitHub: {e}")
        return None, None


# ¿HAY ACTUALIZACIÓN?

def _parse_version(v: str):
    """'1.2.3' → (1, 2, 3)"""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def check_launcher_update(log=None):
    """
    Retorna (needs_update: bool, remote_version: str, download_url: str)
    """
    local   = get_local_version()
    remote, url = get_remote_release(log)

    if not remote:
        return False, local, None

    if log:
        log(f"🖥️  Launcher local:  v{local}")
        log(f"🌐 Launcher remoto: v{remote}")

    if _parse_version(remote) > _parse_version(local):
        return True, remote, url

    return False, local, None



# DESCARGAR NUEVO .EXE

def download_new_exe(url: str, log=None, progress=None):
    """
    Descarga el nuevo .exe a %TEMP%\CFL-Launcher-new.exe
    Retorna la ruta del archivo descargado.
    """
    dest = os.path.join(os.getenv("TEMP", APP_DIR), "CFL-Launcher-new.exe")

    if log: log(f"⬇️  Descargando nueva versión del launcher...")
    if progress: progress(0)

    try:
        r         = requests.get(url, stream=True, timeout=60)
        total     = int(r.headers.get("content-length", 0))
        total_mb  = total / (1024 * 1024)
        downloaded = 0
        start      = time.time()

        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 256):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)

                if total > 0 and progress:
                    pct = int((downloaded / total) * 100)
                    progress(pct)

                if log and total > 0:
                    elapsed  = time.time() - start
                    speed    = downloaded / elapsed if elapsed > 0 else 0
                    mb_dl    = downloaded / (1024 * 1024)
                    mb_speed = speed / (1024 * 1024)
                    remaining = (total - downloaded) / speed if speed > 0 else 0
                    m, s     = int(remaining // 60), int(remaining % 60)
                    # Solo loguear cada ~10% para no saturar
                    if pct % 10 == 0 and pct != getattr(download_new_exe, "_last_pct", -1):
                        download_new_exe._last_pct = pct
                        log(f"  {pct}% | {mb_dl:.1f}/{total_mb:.1f} MB | {mb_speed:.2f} MB/s | ETA: {m}m {s}s")

        if progress: progress(100)
        if log: log(f"✅ Launcher descargado correctamente")
        return dest

    except Exception as e:
        if log: log(f"❌ Error descargando launcher: {e}")
        raise



# REEMPLAZAR Y REINICIAR

def apply_update(new_exe_path: str, log=None):
    """
    Escribe un .bat que:
      1. Espera a que este proceso cierre
      2. Reemplaza el .exe actual por el nuevo
      3. Inicia el nuevo launcher
      4. Se borra a sí mismo

    Luego lanza el .bat y cierra el launcher actual.
    """
    current_exe = sys.executable if getattr(sys, "frozen", False) else None

    if not current_exe:
        # En desarrollo (no compilado) — solo avisar
        if log: log("⚠️ Modo desarrollo: el reemplazo automático solo funciona en el .exe compilado")
        if log: log(f"   Nuevo launcher en: {new_exe_path}")
        return

    bat_path = os.path.join(os.getenv("TEMP", APP_DIR), "cfl_update.bat")

    bat_content = f"""@echo off
:: Esperar a que el launcher actual cierre
:wait
tasklist /FI "PID eq {os.getpid()}" 2>nul | find /I "CFL" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)

:: Reemplazar el exe
copy /Y "{new_exe_path}" "{current_exe}"

:: Iniciar el nuevo launcher
start "" "{current_exe}"

:: Limpiar temp
del "{new_exe_path}"
del "%~f0"
"""

    with open(bat_path, "w") as f:
        f.write(bat_content)

    if log: log("🔄 Aplicando actualización y reiniciando...")

    # Lanzar el bat en background y cerrar el launcher
    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True
    )

    # Salir del launcher actual
    sys.exit(0)



#  FUNCIÓN PRINCIPAL — llamar desde main.py

def run_launcher_update(log=None, progress=None, on_no_update=None):
    """
    Verifica y aplica actualización del launcher si existe.
    Si no hay update, llama on_no_update() para continuar el flujo normal.
    """
    needs, version, url = check_launcher_update(log)

    if not needs:
        if log: log("✅ Launcher actualizado")
        save_local_version(version)   # asegura que el archivo exista
        if on_no_update:
            on_no_update()
        return

    if log: log(f"🆕 Nueva versión del launcher disponible: v{version}")

    try:
        new_exe = download_new_exe(url, log=log, progress=progress)
        save_local_version(version)
        apply_update(new_exe, log=log)
    except Exception as e:
        if log: log(f"❌ No se pudo actualizar el launcher: {e}")
        if on_no_update:
            on_no_update()   # continuar aunque falle el update