import os
import shutil
import zipfile
from config import PACK_FILE, ZIP_NAME, INSTALLED_FILE
from core.paths import get_minecraft_dir


# =========================
# 🔥 ESTADO INSTALACIÓN
# =========================
def is_first_install():
    return not os.path.exists(INSTALLED_FILE)

def mark_installed():
    with open(INSTALLED_FILE, "w") as f:
        f.write("installed")


# =========================
# 🔥 MODS
# =========================
def load_old_pack():
    if not os.path.exists(PACK_FILE):
        return set()
    with open(PACK_FILE, "r") as f:
        return set(f.read().splitlines())

def save_pack(mods):
    with open(PACK_FILE, "w") as f:
        for m in mods:
            f.write(m + "\n")


# =========================
# 🔍 DETECTAR ESTRUCTURA
# =========================
def find_minecraft_folder(base_path):
    for root, dirs, _ in os.walk(base_path):
        if ".minecraft" in dirs:
            return os.path.join(root, ".minecraft")
    return None

def find_mods_folder(base_path):
    for root, dirs, _ in os.walk(base_path):
        if "mods" in dirs:
            return os.path.join(root, "mods")
    return None


# =========================
# 🚀 INSTALLER PRINCIPAL
# =========================
def install_modpack(log, progress):
    import time

    log("🔥 Iniciando instalación...")

    # ── Verificar que el ZIP existe ───────────────────────────────
    if not os.path.exists(ZIP_NAME):
        raise Exception(f"No se encontró el archivo: {ZIP_NAME}")

    appdata = os.getenv("APPDATA")
    mc_path = get_minecraft_dir()   # ← antes: os.path.join(appdata, ".minecraft")

    # ── Carpeta temporal en %TEMP% (nunca relativa) ───────────────
    temp = os.path.join(os.getenv("TEMP", appdata), "mc_modpack_temp")
    shutil.rmtree(temp, ignore_errors=True)
    os.makedirs(temp, exist_ok=True)

    # ── Extraer ZIP ───────────────────────────────────────────────
    log("📦 Extrayendo modpack...")
    progress(0)

    try:
        with zipfile.ZipFile(ZIP_NAME, "r") as zip_ref:
            members = zip_ref.namelist()
            total_zip = len(members)
            for i, member in enumerate(members, 1):
                zip_ref.extract(member, temp)
                if i % 200 == 0 or i == total_zip:
                    percent = int((i / total_zip) * 30)  # extracción = 0-30%
                    progress(percent)
                    log(f"  Extrayendo... {i}/{total_zip} archivos")
    except zipfile.BadZipFile:
        raise Exception("El ZIP está corrupto, descárgalo de nuevo")

    # ── Detectar estructura del ZIP ───────────────────────────────
    contents = os.listdir(temp)
    log(f"📂 Estructura detectada: {len(contents)} elemento(s) en raíz")

    src_mc   = find_minecraft_folder(temp)
    src_mods = find_mods_folder(temp)

    # =========================
    # 🟢 INSTALACIÓN COMPLETA (.minecraft encontrado)
    # =========================
    if src_mc:
        first_install = is_first_install()

        if first_install:
            log("🆕 Primera instalación — copiando todo")
        else:
            log("🔄 Actualización — modo protegido activo")

        PROTECTED_FOLDERS = {"saves", "journeymap", "shaderpacks", "resourcepacks", "logs"}

        files = []
        for root, _, filenames in os.walk(src_mc):
            for name in filenames:
                files.append(os.path.join(root, name))

        total = len(files)
        last_percent = -1
        start_time = time.time()

        log(f"📁 {total} archivos a copiar...")

        for i, file in enumerate(files, 1):
            relative   = os.path.relpath(file, src_mc)
            top_folder = relative.split(os.sep)[0]

            # En actualizaciones, no pisar carpetas protegidas
            if not first_install and top_folder in PROTECTED_FOLDERS:
                continue

            dst = os.path.join(mc_path, relative)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(file, dst)  # copy2 preserva metadata

            # Progreso: extracción fue 0-30%, copia es 30-100%
            percent = 30 + int((i / total) * 70)
            if percent != last_percent:
                progress(percent)
                last_percent = percent

            if i % 100 == 0 or i == total:
                elapsed = time.time() - start_time
                speed = i / elapsed if elapsed > 0 else 0
                remaining = (total - i) / speed if speed > 0 else 0
                mins, secs = int(remaining // 60), int(remaining % 60)
                eta = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                log(f"  {percent}% | {i}/{total} archivos | ETA: {eta}")

        mods_folder = os.path.join(src_mc, "mods")
        if os.path.exists(mods_folder):
            save_pack(set(os.listdir(mods_folder)))

        log("✅ Instalación completa terminada")

    # =========================
    # 🟡 SOLO MODS (carpeta mods encontrada)
    # =========================
    elif src_mods:
        log("🔄 Actualización de mods detectada")

        mods_path = os.path.join(mc_path, "mods")
        os.makedirs(mods_path, exist_ok=True)

        new_pack = set(os.listdir(src_mods))
        old_pack = load_old_pack()

        total = len(new_pack) + len(old_pack)
        count = 0
        last_percent = -1

        # 🔥 Eliminar mods viejos (con protección)
        for file in old_pack:
            path = os.path.join(mods_path, file)

            if os.path.exists(path) and file not in new_pack:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)

                    log(f"🗑 Eliminado: {file}")

                except PermissionError:
                    log(f"⚠️ En uso (omitido): {file}")

            count += 1
            percent = 30 + int((count / total) * 70)
            if percent != last_percent:
                progress(percent)
                last_percent = percent

        # 🔥 Copiar nuevos mods (con protección)
        for file in new_pack:
            src = os.path.join(src_mods, file)
            dst = os.path.join(mods_path, file)

            try:
                shutil.copy2(src, dst)
                log(f"📦 Instalado: {file}")

            except PermissionError:
                log(f"⚠️ No se pudo copiar (en uso): {file}")

            count += 1
            percent = 30 + int((count / total) * 70)
            if percent != last_percent:
                progress(percent)
                last_percent = percent

        save_pack(new_pack)
        log("✅ Mods actualizados")
    # =========================
    # ❌ ESTRUCTURA NO RECONOCIDA
    # =========================
    else:
        shutil.rmtree(temp, ignore_errors=True)
        raise Exception(
            "No se encontró carpeta .minecraft ni mods en el ZIP. "
            "Verifica que el ZIP tenga la estructura correcta."
        )

    # ── Limpieza ──────────────────────────────────────────────────
    # 🔥 LIMPIEZA FINAL
    shutil.rmtree(temp, ignore_errors=True)

    try:
        if os.path.exists(ZIP_NAME):
            os.remove(ZIP_NAME)
            log("🧹 ZIP eliminado")
    except PermissionError:
        log("⚠️ No se pudo eliminar ZIP (en uso)")

    log("🧹 Archivos temporales eliminados")

    # 🔥 FINALIZACIÓN
    progress(100)

    log("────────────────────────────")
    log("🎉 ¡Instalación finalizada!")
    log("🚀 Listo para jugar")

    # 🔥 MARCAR COMO INSTALADO
    mark_installed()