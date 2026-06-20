import os
from config import INSTALLED_FILE

def is_installed():
    # Fuente de verdad: la bandera que escribe el instalador.
    if os.path.exists(INSTALLED_FILE):
        return True
    # Compatibilidad: instalaciones viejas sin bandera pero con mods.
    appdata = os.getenv("APPDATA", "")
    mods = os.path.join(appdata, ".minecraft", "mods")
    return os.path.isdir(mods) and len(os.listdir(mods)) > 0