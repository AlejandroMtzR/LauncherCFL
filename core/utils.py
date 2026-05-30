import sys
import os


def resource_path(relative_path):

    if getattr(sys, "frozen", False):
        # Ejecutándose como .exe de PyInstaller: los recursos están en
        # la carpeta temporal _MEIPASS donde se descomprime el bundle.
        base_path = sys._MEIPASS
    else:
        # Ejecutándose como script: ruta del proyecto.
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)