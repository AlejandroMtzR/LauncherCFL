import os

# =========================
# 📁 CARPETA PERSISTENTE
# %APPDATA%\CFLLauncher\ — nunca se borra
# =========================
APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "CFLLauncher")
os.makedirs(APP_DIR, exist_ok=True)

# =========================
# 🌐 URLs DE DRIVE
# =========================
VERSION_URL      = "https://drive.google.com/uc?export=download&id=1oXrV3xaCtD106nNH7iVujnVDPRZfCIEU"
MODPACK_LINK_URL = "https://drive.google.com/uc?export=download&id=13KFXY61-Fqm_HoSL6vyb110Y7pGyuS6-"

# =========================
# 📄 ARCHIVOS LOCALES
# Todos en %APPDATA%\CFLLauncher\
# =========================
VERSION_FILE   = os.path.join(APP_DIR, "version_local.txt")
PACK_FILE      = os.path.join(APP_DIR, "pack_mods.txt")
INSTALLED_FILE = os.path.join(APP_DIR, "installed.flag")

# ZIP en %TEMP% — no necesita ser permanente
ZIP_NAME = os.path.join(os.getenv("TEMP", APP_DIR), "modpack.zip")
