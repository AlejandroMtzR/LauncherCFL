# -*- coding: utf-8 -*-
"""
Hilos en segundo plano (QThread) para descargar/instalar/actualizar el
modpack y para autoactualizar el launcher. No tocan la interfaz: solo
emiten señales que las pantallas conectan.
"""
from PySide6.QtCore import QThread, Signal

from core.downloader import download_modpack
from core.installer import install_modpack
from core.installer_update import update_modpack
from core.updater import needs_update, save_local_version
from core.checker import is_installed
from core.launcherUpdate import (
    check_launcher_update, download_new_exe, apply_update,
    save_local_version as save_launcher_version,
)


#   WORKER — descarga / instala / actualiza el modpack

class Worker(QThread):
    progress = Signal(int)
    status   = Signal(str)
    log      = Signal(str)
    done     = Signal(bool)

    def __init__(self, force_update=False):
        super().__init__()
        self.force_update = force_update
        self._running = False

    def run(self):
        if self._running:
            return
        self._running = True
        try:
            update, version = needs_update(self.log.emit)

            if not is_installed():
                self.status.emit("Instalando modpack...")
                self.log.emit("🆕 Primera instalación detectada")
                self.log.emit("────────────────────────────")
                download_modpack(self.progress.emit, self.log.emit)
                self.log.emit("📦 Iniciando instalación...")
                install_modpack(self.log.emit, self.progress.emit)
                if version:
                    save_local_version(version)
                self.log.emit("🎉 ¡Listo para jugar!")
                self.status.emit("LISTO PARA JUGAR")
                self.done.emit(True)
                return

            if update and self.force_update:
                self.status.emit("Actualizando modpack...")
                self.log.emit("🔄 Iniciando actualización...")
                self.log.emit("────────────────────────────")
                download_modpack(self.progress.emit, self.log.emit)
                self.log.emit("📦 Aplicando actualización...")
                update_modpack(self.log.emit, self.progress.emit)
                if version:
                    save_local_version(version)
                self.log.emit("🎉 ¡Actualización completada!")
                self.status.emit("LISTO PARA JUGAR")
                self.done.emit(True)
                return

            self.status.emit("LISTO PARA JUGAR")
            self.log.emit("✅ Modpack al día")
            self.done.emit(True)

        except Exception as e:
            self.log.emit(f"❌ Error: {e}")
            self.status.emit("Error — revisa el log")
            self.done.emit(False)
        finally:
            self._running = False


#   LAUNCHER UPDATE WORKER

class LauncherUpdateWorker(QThread):
    status   = Signal(str)
    progress = Signal(int)
    done     = Signal(bool)   # True si se aplicó update (el proceso cerrará)

    def run(self):
        try:
            needs, version, url = check_launcher_update(log=self.status.emit)
            if not needs:
                self.done.emit(False)
                return
            self.status.emit(f"🆕 Nueva versión del launcher: v{version}")
            self.status.emit("⬇️  Descargando actualización...")
            new_exe = download_new_exe(url, log=self.status.emit, progress=self.progress.emit)
            save_launcher_version(version)
            self.status.emit("✅ Descarga completa, reiniciando...")
            self.done.emit(True)
            import time; time.sleep(1)
            apply_update(new_exe, log=self.status.emit)
        except Exception as e:
            self.status.emit(f"⚠️ Update del launcher falló: {e} — continuando...")
            self.done.emit(False)


#   CHECK WORKER — solo verifica, sin descargar nada

class CheckWorker(QThread):
    result = Signal(str, str)   # estado, versión remota

    def run(self):
        try:
            installed = is_installed()
            update, version = needs_update(lambda _: None)
            if not installed:
                self.result.emit("not_installed", version or "")
            elif update:
                self.result.emit("update", version or "")
            else:
                self.result.emit("ready", version or "")
        except Exception:
            self.result.emit("ready", "")
