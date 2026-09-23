"""
installer_update.py — Actualización por capas (overlay).

Solo copia/reemplaza los archivos que vengan dentro del ZIP.
NO borra nada que no esté listado explícitamente en delete.txt.

Estructura esperada del ZIP (lo de dentro mapea a .minecraft):
    .minecraft/
        mods/mod_nuevo.jar      -> se añade/reemplaza
        config/archivo.toml     -> se añade/reemplaza
        delete.txt              -> (opcional) rutas a borrar

delete.txt (una ruta por línea, relativa a .minecraft):
    mods/mod_viejo.jar
    mods/jei-*.jar              <- acepta comodines (*, ?, [..])
    config/algo.toml
    # las líneas que empiezan con # se ignoran
"""
import os
import glob
import shutil
import zipfile
from config import ZIP_NAME
from core.paths import get_minecraft_dir


DELETE_MANIFEST = "delete.txt"


def find_folder(base, name):
    for root, dirs, _ in os.walk(base):
        if name in dirs:
            return os.path.join(root, name)
    return None


# =========================
# 🔍 DETECTAR SI MINECRAFT ESTÁ ABIERTO
# =========================
def is_minecraft_running():
    # Antes bastaba CUALQUIER javaw.exe (un IDE, otro programa Java...) para
    # bloquear la actualización. Ahora se busca Minecraft de verdad.
    try:
        from core import game_launcher
        return game_launcher.is_game_running()
    except Exception:
        return False


# =========================
# 🔥 ELIMINAR ENTRADA (archivo o carpeta)
# =========================
def remove_entry(path, log):
    try:
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
        return not os.path.lexists(path)
    except PermissionError:
        log(f"⚠️ Sin permisos para eliminar (saltando): {os.path.basename(path)}")
        return False
    except Exception as e:
        log(f"⚠️ Error eliminando {os.path.basename(path)}: {e}")
        return False


# =========================
# 📂 ENCONTRAR LA RAÍZ DEL OVERLAY
# =========================
def find_overlay_root(temp):
    # 1) Si el ZIP trae un .minecraft, usamos su interior
    mc = find_folder(temp, ".minecraft")
    if mc:
        return mc
    # 2) Si trae mods/ o config/ sueltos, usamos su carpeta padre
    for root, dirs, files in os.walk(temp):
        if "mods" in dirs or "config" in dirs or DELETE_MANIFEST in files:
            return root
    # 3) Último recurso: la raíz temporal
    return temp


# =========================
# 🗑  PROCESAR BORRADOS (con comodines)
# =========================
def process_deletions(src_root, mc_path, log):
    manifest = os.path.join(src_root, DELETE_MANIFEST)
    if not os.path.exists(manifest):
        return 0

    log("🗑  Procesando borrados (delete.txt)...")
    with open(manifest, encoding="utf-8") as f:
        lines = [
            ln.strip() for ln in f
            if ln.strip() and not ln.strip().startswith("#")
        ]

    base = os.path.realpath(os.path.abspath(mc_path))
    failures = 0

    for rel in lines:
        rel = rel.replace("/", os.sep).replace("\\", os.sep)
        drive, _tail = os.path.splitdrive(rel)
        normalized = os.path.normpath(rel)
        if (
            drive
            or os.path.isabs(rel)
            or normalized in ("", ".", "..")
            or normalized.startswith(".." + os.sep)
        ):
            raise ValueError(f"Ruta insegura en {DELETE_MANIFEST}: {rel}")

        pattern = os.path.abspath(os.path.join(base, normalized))
        try:
            if os.path.commonpath((base, pattern)) != base:
                raise ValueError(f"Ruta fuera de .minecraft en {DELETE_MANIFEST}: {rel}")
        except ValueError:
            raise ValueError(f"Ruta insegura en {DELETE_MANIFEST}: {rel}")

        matches = glob.glob(pattern)   # acepta comodines: *, ?, [..]

        if not matches:
            log(f"  (ya no existe): {rel}")
            continue

        for target in matches:
            target_abs = os.path.abspath(target)
            try:
                if os.path.commonpath((base, target_abs)) != base:
                    raise ValueError(
                        f"Coincidencia fuera de .minecraft en {DELETE_MANIFEST}: {rel}"
                    )
            except ValueError:
                raise ValueError(f"Coincidencia insegura en {DELETE_MANIFEST}: {rel}")

            # No seguir enlaces que apunten fuera de la instancia. El enlace
            # mismo se puede retirar con seguridad; cualquier otro destino
            # debe resolver dentro de .minecraft.
            if not os.path.islink(target):
                target_real = os.path.realpath(target)
                try:
                    if os.path.commonpath((base, target_real)) != base:
                        raise ValueError(
                            f"Destino enlazado fuera de .minecraft: {rel}"
                        )
                except ValueError:
                    raise ValueError(f"Destino inseguro en {DELETE_MANIFEST}: {rel}")

            if remove_entry(target, log):
                log(f"🗑  Eliminado: {os.path.relpath(target, mc_path)}")
            else:
                failures += 1

    return failures


# =========================
# 📥 COPIAR EN MODO CAPA (overlay)
# =========================
def overlay_copy(src_root, mc_path, log, progress):
    files = []
    for root, _, filenames in os.walk(src_root):
        for name in filenames:
            files.append(os.path.join(root, name))

    total    = max(len(files), 1)
    last_pct = -1
    copied   = 0
    skipped  = 0

    for i, file in enumerate(files, 1):
        relative = os.path.relpath(file, src_root)

        # No copiar el manifiesto de borrado
        if relative == DELETE_MANIFEST:
            continue

        dst = os.path.join(mc_path, relative)
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(file, dst)
            copied += 1
            # Loguear cada archivo satura el log con overlays grandes.
            if copied <= 40 or relative.lower().startswith("mods"):
                log(f"  ✓ {relative}")
            elif copied == 41:
                log("  … (más archivos de configuración)")
        except PermissionError:
            skipped += 1
            log(f"⚠️ Sin permisos (saltando): {relative}")
        except Exception as e:
            skipped += 1
            log(f"⚠️ Error con {relative}: {e}")

        pct = 30 + int((i / total) * 70)
        if pct != last_pct:
            progress(pct)
            last_pct = pct

    log(f"📥 {copied} archivo(s) copiado(s)/reemplazado(s)")
    if skipped:
        log(f"⚠️ {skipped} saltado(s)")
    return skipped


# =========================
# 🚀 UPDATE PRINCIPAL
# =========================
def update_modpack(log, progress):
    # ── ⛔ Verificar que Minecraft esté cerrado ────────────────────
    if is_minecraft_running():
        raise Exception(
            "Minecraft está abierto. Ciérralo antes de actualizar para evitar conflictos."
        )

    log("🔄 Iniciando actualización...")

    if not os.path.exists(ZIP_NAME):
        raise Exception(f"No se encontró el archivo: {ZIP_NAME}")

    appdata = os.getenv("APPDATA")
    mc_path = get_minecraft_dir()
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
        shutil.rmtree(temp, ignore_errors=True)
        raise Exception("El ZIP está corrupto, descárgalo de nuevo")

    # ── Localizar raíz del overlay ─────────────────────────────────
    src_root = find_overlay_root(temp)

    # ── 1) Borrar lo indicado en delete.txt ────────────────────────
    deletion_failures = process_deletions(src_root, mc_path, log)

    # ── 2) Copiar/reemplazar solo lo que trae el ZIP ───────────────
    log("🔄 Aplicando archivos (modo capa)...")
    copy_failures = overlay_copy(src_root, mc_path, log, progress)

    # ── Limpieza ───────────────────────────────────────────────────
    shutil.rmtree(temp, ignore_errors=True)
    if os.path.exists(ZIP_NAME):
        os.remove(ZIP_NAME)
        log("🧹 Archivos temporales eliminados")

    progress(100)
    log("────────────────────────────")
    log("🎉 ¡Actualización finalizada!")
    return deletion_failures + copy_failures
