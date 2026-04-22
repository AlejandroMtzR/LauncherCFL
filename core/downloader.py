"""
downloader.py — SOLO descarga el ZIP desde Drive.
⚠️  NO llama install_modpack ni update_modpack.
    El Worker es quien orquesta descarga → instalación.
"""
import requests
from config import MODPACK_LINK_URL, ZIP_NAME
import time
import re


# =========================
# 🔥 OBTENER LINK REAL
# =========================
def get_modpack_url(log_callback):
    log_callback("Conectando a servidor...")
    try:
        text  = requests.get(MODPACK_LINK_URL, timeout=10).text.strip()
        match = re.search(r'https?://\S+', text)
        if not match:
            raise Exception("No se encontró un link válido en el servidor")
        url = match.group(0)
        log_callback("✅ Link obtenido correctamente")
        return url
    except Exception as e:
        log_callback(f"❌ Error obteniendo link: {e}")
        raise


# =========================
# 🔥 DESCARGA DRIVE
# =========================
def get_drive_response(url, log_callback):
    session  = requests.Session()
    headers  = {"User-Agent": "Mozilla/5.0"}
    response = session.get(url, headers=headers, stream=True, timeout=30)

    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            log_callback("⚠️ Confirmando descarga de archivo grande...")
            response = session.get(
                url + "&confirm=" + value,
                headers=headers, stream=True, timeout=30
            )
            break
    return response


# =========================
# 🔥 VALIDAR ZIP
# =========================
def validate_zip(log_callback):
    try:
        with open(ZIP_NAME, "rb") as f:
            sig = f.read(4)
        if sig != b'PK\x03\x04':
            log_callback("❌ Archivo inválido (no es un ZIP real)")
            return False
        log_callback("✅ Archivo ZIP validado")
        return True
    except Exception as e:
        log_callback(f"❌ Error validando archivo: {e}")
        return False


# =========================
# 🔥 FALLBACK GDOWN
# =========================
def download_with_gdown(url, log_callback, progress_callback):
    import gdown, threading, os

    log_callback("⚠️ Activando descarga alternativa (gdown)...")
    start     = time.time()
    stop_flag = [False]
    possible  = [ZIP_NAME, ZIP_NAME + ".part", ZIP_NAME + ".tmp"]

    def get_size():
        for f in possible:
            if os.path.exists(f):
                return os.path.getsize(f)
        return 0

    def monitor():
        last_size     = 0
        last_log_time = 0
        history       = []

        # Esperar hasta 15s a que el archivo aparezca
        for _ in range(30):
            if stop_flag[0]: return
            if get_size() > 0: break
            time.sleep(0.5)

        log_callback("⬇️  Descarga iniciada (modo gdown)...")
        progress_callback(1)

        while not stop_flag[0]:
            try:
                size = get_size()
                mb   = size / (1024 * 1024)
                now  = time.time()

                history.append((now, size))
                if len(history) > 5:
                    history.pop(0)

                if len(history) >= 2:
                    dt       = history[-1][0] - history[0][0]
                    ds       = history[-1][1] - history[0][1]
                    speed    = (ds / dt) if dt > 0 else 0
                    mb_speed = speed / (1024 * 1024)
                else:
                    speed = mb_speed = 0

                TOTAL   = 3 * 1024 * 1024 * 1024
                percent = min(int((size / TOTAL) * 100), 98)
                progress_callback(percent)

                if size > last_size and now - last_log_time >= 2:
                    if mb_speed > 0:
                        eta_s = (TOTAL - size) / speed
                        m, s  = int(eta_s // 60), int(eta_s % 60)
                        eta   = f"{m}m {s}s" if m > 0 else f"{s}s"
                        log_callback(
                            f"  {percent:>2}% | {mb:,.1f} MB | "
                            f"{mb_speed:.2f} MB/s | ETA: {eta}"
                        )
                    else:
                        log_callback(f"  {mb:,.1f} MB descargados...")
                    last_size     = size
                    last_log_time = now

                time.sleep(1)
            except Exception:
                break

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()

    try:
        try:
            gdown.download(url, ZIP_NAME, quiet=True, fuzzy=True)
        except TypeError:
            log_callback("⚠️ gdown antiguo detectado, modo compatible...")
            gdown.download(url, ZIP_NAME, quiet=True)

        stop_flag[0] = True
        thread.join(timeout=2)

        elapsed  = time.time() - start
        m, s     = int(elapsed // 60), int(elapsed % 60)
        final_mb = os.path.getsize(ZIP_NAME) / (1024 * 1024) if os.path.exists(ZIP_NAME) else 0
        progress_callback(100)
        log_callback(f"✅ Descarga completada: {final_mb:,.1f} MB en {m}m {s}s")

    except Exception as e:
        stop_flag[0] = True
        log_callback(f"❌ Error en gdown: {e}")
        raise


# =========================
# 🔥 DESCARGA PRINCIPAL
# =========================
def download_modpack(progress_callback, log_callback):
    url = get_modpack_url(log_callback)
    log_callback("────────────────────────────")
    log_callback("Conectando con Drive...")

    try:
        response     = get_drive_response(url, log_callback)
        content_type = response.headers.get("Content-Type", "")

        if "text/html" in content_type:
            raise Exception("Drive devolvió HTML — verifica que el archivo sea público")

        total    = int(response.headers.get("content-length", 0))
        total_mb = total / (1024 * 1024)

        if total > 0:
            log_callback(f"Tamaño del modpack: {total_mb:,.1f} MB")
        else:
            log_callback("⚠️ Tamaño desconocido (Drive no reportó content-length)")

        downloaded    = 0
        start_time    = time.time()
        last_log_time = 0
        last_progress = -1

        log_callback("⬇️  Iniciando descarga...")
        progress_callback(0)

        with open(ZIP_NAME, "wb") as f:
            for chunk in response.iter_content(1024 * 256):
                if not chunk:
                    continue

                f.write(chunk)
                downloaded += len(chunk)

                elapsed       = time.time() - start_time
                speed         = downloaded / elapsed if elapsed > 0 else 0
                mb_downloaded = downloaded / (1024 * 1024)
                mb_speed      = speed / (1024 * 1024)
                now           = time.time()

                if total > 0:
                    percent = int((downloaded / total) * 100)
                    if percent != last_progress:
                        progress_callback(percent)
                        last_progress = percent
                    if now - last_log_time >= 2:
                        remaining = (total - downloaded) / speed if speed > 0 else 0
                        m, s      = int(remaining // 60), int(remaining % 60)
                        eta       = f"{m}m {s}s" if m > 0 else f"{s}s"
                        log_callback(
                            f"  {percent:>3}% | "
                            f"{mb_downloaded:,.1f}/{total_mb:,.1f} MB | "
                            f"{mb_speed:.2f} MB/s | ETA: {eta}"
                        )
                        last_log_time = now
                else:
                    if now - last_log_time >= 2:
                        fake = min(int((mb_downloaded / 3000) * 100), 99)
                        progress_callback(fake)
                        log_callback(f"  {mb_downloaded:,.1f} MB | {mb_speed:.2f} MB/s")
                        last_log_time = now

        if not validate_zip(log_callback):
            raise Exception("El archivo descargado está corrupto o incompleto")

        elapsed_total = time.time() - start_time
        m, s          = int(elapsed_total // 60), int(elapsed_total % 60)
        log_callback("────────────────────────────")
        log_callback(f"✅ Descarga completada en {m}m {s}s")
        # ✅ FIN — el Worker llamará al instalador correspondiente

    except Exception as e:
        log_callback(f"⚠️ Método principal falló: {e}")
        log_callback("🔄 Intentando método alternativo...")
        try:
            download_with_gdown(url, log_callback, progress_callback)
            if not validate_zip(log_callback):
                raise Exception("Archivo inválido tras descarga alternativa")
            log_callback("────────────────────────────")
            log_callback("✅ Descarga completada (método alternativo)")
            # ✅ FIN — el Worker llamará al instalador correspondiente
        except Exception as e2:
            progress_callback(0)
            log_callback("────────────────────────────")
            log_callback(f"❌ ERROR FINAL: {e2}")
            log_callback("👉 Verifica tu conexión o que el link sea público")
            raise