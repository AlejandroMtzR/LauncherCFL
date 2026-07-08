r"""
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


LAUNCHER_VERSION = "4.1.4"

API_URL      = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
HEADERS      = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

APP_DIR           = os.path.join(os.getenv("APPDATA", ""), "CFLLauncher")
LOCAL_VERSION_FILE = os.path.join(APP_DIR, "launcherVersion.txt")
os.makedirs(APP_DIR, exist_ok=True)



# 📄 VERSIÓN LOCAL

def get_local_version():
    try:
        with open(LOCAL_VERSION_FILE) as f:
            return f.read().strip() or LAUNCHER_VERSION
    except FileNotFoundError:
        return LAUNCHER_VERSION


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
    r"""
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

def apply_update(new_exe_path: str, version: str = "", log=None):
    """
    Escribe un .bat que espera a que cierre este proceso, reemplaza el .exe
    (con reintentos), marca la versión SOLO si la copia funcionó, y reinicia.
    """
    current_exe = sys.executable if getattr(sys, "frozen", False) else None

    if not current_exe:
        if log: log("⚠️ Modo desarrollo: el reemplazo automático solo funciona en el .exe compilado")
        if log: log(f"   Nuevo launcher en: {new_exe_path}")
        return

    bat_path = os.path.join(os.getenv("TEMP", APP_DIR), "cfl_update.bat")
    # En --onefile hay 2 procesos (bootloader + python); esperar por NOMBRE de
    # imagen los cubre a ambos. Esto evita copiar/relanzar antes de tiempo,
    # que es lo que provoca el error "Failed to load Python DLL" al reabrir.
    exe_name = os.path.basename(current_exe)

    bat_content = f"""@echo off
chcp 65001 >nul

rem ── 1) Esperar a que el launcher cierre POR COMPLETO (todos los procesos) ──
:wait
tasklist /FI "IMAGENAME eq {exe_name}" 2>nul | find /I "{exe_name}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)

rem    Margen para que Windows libere el candado del .exe.
timeout /t 2 /nobreak >nul

rem ── 2) Reemplazar el exe (con reintentos por si sigue bloqueado) ──
set _tries=0
:copyloop
copy /Y "{new_exe_path}" "{current_exe}" >nul
if not errorlevel 1 goto copyok
set /a _tries+=1
if %_tries% geq 15 goto copyfail
timeout /t 1 /nobreak >nul
goto copyloop

rem ── 3a) Copia OK ──────────────────────────────────────────────────────
rem    Dejar que el .exe recién escrito se asiente en disco y que el
rem    antivirus termine de escanearlo ANTES de relanzar. Sin esta pausa,
rem    el bootloader --onefile falla al descomprimir python311.dll (error 126).
:copyok
timeout /t 3 /nobreak >nul
>"{LOCAL_VERSION_FILE}" echo {version}
start "" "{current_exe}"
goto cleanup

rem ── 3b) Falló la copia: NO marcar versión, relanzar la actual ──
:copyfail
start "" "{current_exe}"

:cleanup
del "{new_exe_path}" >nul 2>&1
del "%~f0" >nul 2>&1
"""

    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    if log: log("🔄 Aplicando actualización y reiniciando...")

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True
    )

    # Cierre del PROCESO completo (no solo el hilo).
    os._exit(0)



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
        apply_update(new_exe, version, log=log)  # ← la versión se guarda dentro del .bat
    except Exception as e:
        if log: log(f"❌ No se pudo actualizar el launcher: {e}")
        if on_no_update:
            on_no_update()