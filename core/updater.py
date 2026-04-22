import requests
from config import VERSION_URL, VERSION_FILE


def get_remote_version(log=None):
    try:
        if log:
            log("🌐 Consultando versión en servidor...")

        r = requests.get(VERSION_URL, headers={"Cache-Control": "no-cache"})
        version = r.text.strip()

        if log:
            log(f"🌍 Versión remota: {version}")

        return version

    except Exception as e:
        if log:
            log(f"❌ Error obteniendo versión: {e}")
        return None


def get_local_version(log=None):
    try:
        with open(VERSION_FILE, "r") as f:
            version = f.read().strip()

            if log:
                log(f"💾 Versión local: {version}")

            return version

    except:
        if log:
            log("⚠️ No hay versión local")
        return None


def save_local_version(version):
    with open(VERSION_FILE, "w") as f:
        f.write(version)


def needs_update(log=None):
    remote = get_remote_version(log)
    local = get_local_version(log)

    if remote is None:
        return False, None

    if local is None:
        return True, remote

    if remote != local:
        if log:
            log("🔄 Nueva versión detectada")
        return True, remote

    if log:
        log("✅ Ya tienes la última versión")

    return False, remote