import sys
import os


def resource_path(relative_path):

    if getattr(sys, "frozen", False):
        # Ejecutándose como .exe de PyInstaller: los recursos están en
        # la carpeta temporal _MEIPASS donde se descomprime el bundle.
        base_path = sys._MEIPASS
    else:
        # Ejecutándose como script: ruta del proyecto (no la carpeta desde la
        # que se lanzó, que puede ser otra si se abre desde un acceso directo).
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)

def total_ram_gb():
    """RAM física total en GB (redondeada), o None si no se puede leer."""
    try:
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MemStatus()
        stat.dwLength = ctypes.sizeof(_MemStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        return max(1, round(stat.ullTotalPhys / (1024 ** 3)))
    except Exception:
        return None


def max_game_ram_gb(limit=16):
    """Máximo razonable para Minecraft: deja ~2-3 GB libres a Windows."""
    total = total_ram_gb()
    if not total:
        return limit
    return max(2, min(limit, total - (3 if total > 8 else 2)))
