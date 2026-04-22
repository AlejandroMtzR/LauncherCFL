import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow



# RECURSOS — funciona tanto en desarrollo como en .exe compilado

def recurso(path):
    """
    En desarrollo:  busca relativo al proyecto
    En .exe:        busca en la carpeta temporal _MEIPASS de PyInstaller
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, path)
    return os.path.join(os.path.abspath("."), path)



# APP USER MODEL ID
# Hace que Windows muestre el ícono correcto en:
#   Barra de tareas
#   Alt+Tab
#   Notificaciones
#   Menú inicio (si se fija)

ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("cfl.launcher.v2")



# MUTEX — evitar que se abra dos veces

MUTEX_NAME = "CFL_LAUNCHER_MUTEX_V2"

mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)

if ctypes.windll.kernel32.GetLastError() == 183:
    ctypes.windll.user32.MessageBoxW(
        0,
        "CFL Launcher ya está abierto.",
        "CFL Launcher",
        0x40  # MB_ICONINFORMATION
    )
    sys.exit(0)



# ARRANQUE

app = QApplication(sys.argv)
app.setApplicationName("CFL Launcher")
app.setOrganizationName("CFL")

# Ícono global de la app (barra de tareas + ventana)
icon_path = recurso("assets/logo.ico")
app.setWindowIcon(QIcon(icon_path))

# Pasar la función recurso() a MainWindow para que cargue
# assets correctamente dentro del .exe
window = MainWindow(resource_fn=recurso)
window.show()

sys.exit(app.exec())