"""
installer_update.py — Solo actualiza mods y config.
NO toca saves, journeymap, shaderpacks, resourcepacks.
"""
import os
import shutil
import zipfile
import subprocess
from config import PACK_FILE, ZIP_NAME


PROTECTED = {"saves", "journeymap", "shaderpacks", "resourcepacks", "logs", "screenshots"}


def load_old_pack():
    if not os.path.exists(PACK_FILE):
        return set()
    with open(PACK_FILE) as f:
        return set(f.read().splitlines())

def save_pack(mods):
    with open(PACK_FILE, "w") as f:
        for m in mods:
            f.write(m + "\n")

def find_folder(base, name):
    for root, dirs, _ in os.walk(base):
        if name in dirs:
            return os.path.join(root, name)
    return None


# =========================
# 🔍 DETECTAR SI MINECRAFT ESTÁ ABIERTO
# =========================
def is_minecraft_running():
    try:
        result = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq javaw.exe"],
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000  # sin ventana
        ).decode(errors="ignore")
        return "javaw.exe" in result
    except Exception:
        return False


# =========================
# 🔥 COPIAR ENTRADA (archivo o carpeta)
# =========================
def copy_entry(src, dst, log):
    try:
        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        return True
    except PermissionError:
        log(f"⚠️ Sin permisos (saltando): {os.path.basename(src)}")
        return False
    except Exception as e:
        log(f"⚠️ Error copiando {os.path.basename(src)}: {e}")
        return False


# =========================
# 🔥 ELIMINAR ENTRADA (archivo o carpeta)
# =========================
def remove_entry(path, log):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
        return True
    except PermissionError:
        log(f"⚠️ Sin permisos para eliminar (saltando): {os.path.basename(path)}")
        return False
    except Exception as e:
        log(f"⚠️ Error eliminando {os.path.basename(path)}: {e}")
        return False


# =========================
# 🚀 UPDATE PRINCIPAL
# =========================
def update_modpack(log, progress):
    import time

    # ── ⛔ Verificar que Minecraft esté cerrado ────────────────────
    if is_minecraft_running():
        raise Exception(
            "Minecraft está abierto. Ciérralo antes de actualizar para evitar conflictos."
        )

    log("🔄 Iniciando actualización...")

    if not os.path.exists(ZIP_NAME):
        raise Exception(f"No se encontró el archivo: {ZIP_NAME}")

    appdata = os.getenv("APPDATA")
    mc_path = os.path.join(appdata, ".minecraft")
    temp    = os.path.join(os.getenv("TEMP", appdata), "mc_update_temp")

    shutil.rmtree(temp, ignore_errors=True)
    os.makedirs(temp, exist_ok=True)

    # ── Extraer ZIP ────────────────────────────────────────────────
    log("📦 Extrayendo actualización...")
    progress(0)

    try:
        with zipfile.ZipFile(ZIP_NAME, "r") as z:
            members = z.namelist()
            total   = len(members)
            for i, m in enumerate(members, 1):
                z.extract(m, temp)
                if i % 200 == 0 or i == total:
                    progress(int((i / total) * 30))
    except zipfile.BadZipFile:
        raise Exception("El ZIP está corrupto, descárgalo de nuevo")

    src_mc   = find_folder(temp, ".minecraft")
    src_mods = find_folder(temp, "mods")

    # ── Actualización desde .minecraft completo ────────────────────
    if src_mc:
        log("🔄 Aplicando actualización (modo protegido)...")

        files = []
        for root, _, filenames in os.walk(src_mc):
            for name in filenames:
                files.append(os.path.join(root, name))

        total      = len(files)
        last_pct   = -1
        start_time = time.time()
        skipped    = 0

        for i, file in enumerate(files, 1):
            relative   = os.path.relpath(file, src_mc)
            top_folder = relative.split(os.sep)[0]

            if top_folder in PROTECTED:
                continue

            dst = os.path.join(mc_path, relative)
            if not copy_entry(file, dst, log):
                skipped += 1

            pct = 30 + int((i / total) * 70)
            if pct != last_pct:
                progress(pct)
                last_pct = pct

            if i % 200 == 0 or i == total:
                elapsed   = time.time() - start_time
                speed     = i / elapsed if elapsed > 0 else 0
                remaining = (total - i) / speed if speed > 0 else 0
                m, s      = int(remaining // 60), int(remaining % 60)
                eta       = f"{m}m {s}s" if m > 0 else f"{s}s"
                log(f"  {pct}% | {i}/{total} archivos | ETA: {eta}")

        if skipped > 0:
            log(f"⚠️ {skipped} archivos saltados (sin permisos)")

        mods_in_new = os.path.join(src_mc, "mods")
        if os.path.exists(mods_in_new):
            save_pack(set(os.listdir(mods_in_new)))

    # ── Actualización solo de mods ─────────────────────────────────
    elif src_mods:
        log("🔄 Actualizando solo mods...")
        mods_path = os.path.join(mc_path, "mods")
        os.makedirs(mods_path, exist_ok=True)

        new_pack = set(os.listdir(src_mods))
        old_pack = load_old_pack()
        total    = max(len(new_pack) + len(old_pack), 1)
        count    = 0
        last_pct = -1
        skipped  = 0

        for entry in old_pack:
            path = os.path.join(mods_path, entry)
            if os.path.exists(path) and entry not in new_pack:
                if remove_entry(path, log):
                    log(f"🗑  Eliminado: {entry}")
                else:
                    skipped += 1
            count += 1
            pct = 30 + int((count / total) * 70)
            if pct != last_pct:
                progress(pct)
                last_pct = pct

        for entry in new_pack:
            src = os.path.join(src_mods, entry)
            dst = os.path.join(mods_path, entry)
            if not copy_entry(src, dst, log):
                skipped += 1
            count += 1
            pct = 30 + int((count / total) * 70)
            if pct != last_pct:
                progress(pct)
                last_pct = pct

        if skipped > 0:
            log(f"⚠️ {skipped} entradas saltadas (sin permisos)")

        save_pack(new_pack)

    else:
        shutil.rmtree(temp, ignore_errors=True)
        raise Exception(
            "Estructura del ZIP inválida — no se encontró .minecraft ni mods/"
        )

    # ── Limpieza ───────────────────────────────────────────────────
    shutil.rmtree(temp, ignore_errors=True)
    if os.path.exists(ZIP_NAME):
        os.remove(ZIP_NAME)
        log("🧹 Archivos temporales eliminados")

    progress(100)
    log("────────────────────────────")
    log("🎉 ¡Actualización finalizada!")