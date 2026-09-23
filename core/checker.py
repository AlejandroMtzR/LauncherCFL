import os

from config import INSTALLED_FILE, PACK_FILE, VERSION_FILE
from core.paths import get_minecraft_dir

# Mínimo de .jar para considerar que es el modpack y no una carpeta vacía/vanilla.
MIN_MODS = 10
# Tolerancia: si tenemos lista esperada, cuánto puede faltar y seguir contando
# como "instalado" (0.30 = puede faltar hasta el 30%).
MAX_MISSING_RATIO = 0.30


# =========================================================================
# LISTADO REAL DE MODS
# =========================================================================
def list_installed_mods(mc_dir=None):
    """Lista de nombres de .jar realmente presentes en <minecraft>/mods."""
    mc_dir = mc_dir or get_minecraft_dir()
    mods_dir = os.path.join(mc_dir, "mods")
    if not os.path.isdir(mods_dir):
        return []
    # Solo ARCHIVOS .jar: las carpetas que algunos mods crean dentro de mods/
    # no son mods y nunca deben contarse (ni como instaladas ni como faltantes).
    try:
        with os.scandir(mods_dir) as entries:
            return sorted(
                e.name for e in entries
                if e.name.lower().endswith(".jar") and e.is_file()
            )
    except OSError:
        return []


def read_text_lines(path):
    """
    Lee un archivo de texto tolerando la codificación: versiones anteriores
    guardaban pack_mods.txt con la codificación de Windows (cp1252) y aquí se
    leía como UTF-8, lo que rompía con nombres de mods con acentos.
    """
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def expected_mod_set():
    """
    Conjunto de .jar esperados según pack_mods.txt (vacío si no existe).
    Solo cuenta .jar: carpetas o archivos sueltos del pack nunca aparecen en
    list_installed_mods() y se reportaban como "faltantes" para siempre.
    """
    if not os.path.exists(PACK_FILE):
        return set()
    try:
        lines = read_text_lines(PACK_FILE)
    except OSError:
        return set()
    return {ln for ln in lines if ln.lower().endswith(".jar")}


# =========================================================================
# DIAGNÓSTICO COMPLETO
# =========================================================================
def install_health(mc_dir=None):
    """
    Devuelve un dict con el estado real en disco. Útil para loguear el listado.
    """
    mc_dir = mc_dir or get_minecraft_dir()
    have = set(list_installed_mods(mc_dir))
    want = expected_mod_set()
    # Windows no distingue mayúsculas en nombres de archivo.
    have_lower = {m.lower() for m in have}
    missing = {m for m in want if m.lower() not in have_lower}
    return {
        "mc_dir": mc_dir,
        "mods_dir_exists": os.path.isdir(os.path.join(mc_dir, "mods")),
        "have_count": len(have),
        "want_count": len(want),
        "missing_count": len(missing),
        "missing_sample": sorted(missing)[:10],
    }


# =========================================================================
# ¿ESTÁ INSTALADO DE VERDAD?
# =========================================================================
def is_installed(mc_dir=None):
    """
    True solo si <minecraft>/mods existe con .jar reales y coherentes.
    La bandera installed.flag YA NO se usa como fuente de verdad.
    """
    h = install_health(mc_dir)

    if not h["mods_dir_exists"]:
        return False
    if h["have_count"] < MIN_MODS:
        return False
    # Si tenemos una lista esperada, exigir que no falte demasiado.
    if h["want_count"] and h["missing_count"] > h["want_count"] * MAX_MISSING_RATIO:
        return False
    return True


# =========================================================================
# LIMPIEZA DE ESTADO HUÉRFANO
# =========================================================================
def clear_stale_state(log=None):
    """
    Si la bandera/versión dicen 'instalado' pero el disco dice que NO,
    borra bandera + versión + pack para forzar una instalación limpia.
    Devuelve True si limpió algo.
    """
    flag_says_installed = (
        os.path.exists(INSTALLED_FILE) or os.path.exists(VERSION_FILE)
    )
    if flag_says_installed and not is_installed():
        for p in (INSTALLED_FILE, VERSION_FILE, PACK_FILE):
            try:
                os.remove(p)
            except OSError:
                pass
        if log:
            log("🧹 Estado huérfano detectado (.minecraft ausente o vacío)")
            log("   → se reinicia a INSTALACIÓN LIMPIA")
        return True
    return False
