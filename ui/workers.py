# -*- coding: utf-8 -*-
from PySide6.QtCore import QThread, Signal

from core.downloader import download_modpack
from core.installer import install_modpack
from core.installer_update import update_modpack
from core.updater import needs_update, save_local_version
from core.checker import is_installed
from core.launcherUpdate import check_launcher_update, download_new_exe, apply_update
from config import MODPACK_FULL_LINK_URL, MODPACK_UPDATE_LINK_URL


class Worker(QThread):
    progress = Signal(int)
    status   = Signal(str)
    log      = Signal(str)
    done     = Signal(bool)

    def __init__(self, force_update=False):
        super().__init__()
        self.force_update = force_update

    def run(self):
        try:
            update, version = needs_update(self.log.emit)

            if not is_installed():
                self.status.emit("Instalando modpack...")
                self.log.emit("🆕 Primera instalación detectada")
                self.log.emit("────────────────────────────")

                # 1) Pack completo (base)
                download_modpack(self.progress.emit, self.log.emit, MODPACK_FULL_LINK_URL)
                self.log.emit("📦 Iniciando instalación...")
                install_modpack(self.log.emit, self.progress.emit)

                # 2) Aplicar el overlay actual encima para quedar 100% al día
                if MODPACK_UPDATE_LINK_URL:
                    try:
                        self.log.emit("🔄 Aplicando últimos cambios...")
                        download_modpack(self.progress.emit, self.log.emit, MODPACK_UPDATE_LINK_URL)
                        update_modpack(self.log.emit, self.progress.emit)
                    except Exception as e:
                        self.log.emit(f"⚠️ No se pudo aplicar el overlay (no crítico): {e}")

                if version:
                    save_local_version(version)
                self.log.emit("🎉 ¡Listo para jugar!")
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


class LauncherUpdateWorker(QThread):
    status   = Signal(str)
    progress = Signal(int)
    done     = Signal(bool)

    def run(self):
        try:
            needs, version, url = check_launcher_update(log=self.status.emit)
            if not needs:
                self.done.emit(False)
                return
            self.status.emit(f"🆕 Nueva versión del launcher: v{version}")
            self.status.emit("⬇️  Descargando actualización...")
            new_exe = download_new_exe(url, log=self.status.emit, progress=self.progress.emit)
            self.status.emit("✅ Descarga completa, reiniciando...")
            self.done.emit(True)
            import time; time.sleep(1)
            apply_update(new_exe, version, log=self.status.emit)
        except Exception as e:
            self.status.emit(f"⚠️ Update del launcher falló: {e} — continuando...")
            self.done.emit(False)


class CheckWorker(QThread):
    result = Signal(str, str)

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