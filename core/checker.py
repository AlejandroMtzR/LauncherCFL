import os

def is_installed():
    appdata = os.getenv('APPDATA')
    mods = os.path.join(appdata, ".minecraft", "mods")
    return os.path.exists(mods) and len(os.listdir(mods)) > 0