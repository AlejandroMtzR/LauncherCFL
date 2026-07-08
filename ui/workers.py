# -*- coding: utf-8 -*-
from PySide6.QtCore import QThread, Signal

from core.downloader import download_modpack
from core.installer import install_modpack
from core.installer_update import update_modpack
from core.updater import needs_update, save_local_version
from core.checker import is_installed, install_health, clear_stale_state
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
            # Si el estado quedó huérfano (.minecraft borrado pero bandera viva),
            # limpiarlo para que esto se trate como instalación limpia.
            clear_stale_state(self.log.emit)

            update, version = needs_update(self.log.emit)

            # ── INSTALACIÓN LIMPIA (no hay mods reales en disco) ──────────
            if not is_installed():
                self.status.emit("Instalando modpack...")
                self.log.emit("🆕 Primera instalación / reinstalación limpia")
                self.log.emit("────────────────────────────")

                # 1) Pack completo (base)
                download_modpack(self.progress.emit, self.log.emit, MODPACK_FULL_LINK_URL)
                self.log.emit("📦 Iniciando instalación...")
                install_modpack(self.log.emit, self.progress.emit)

                # 2) Overlay actual encima para quedar 100% al día
                if MODPACK_UPDATE_LINK_URL:
                    try:
                        self.log.emit("🔄 Aplicando últimos cambios...")
                        download_modpack(self.progress.emit, self.log.emit, MODPACK_UPDATE_LINK_URL)
                        update_modpack(self.log.emit, self.progress.emit)
                    except Exception as e:
                        self.log.emit(f"⚠️ No se pudo aplicar el overlay (no crítico): {e}")

                if version:
                    save_local_version(version)

                self._log_listing()
                self.log.emit("🎉 ¡Listo para jugar!")
                self.status.emit("LISTO PARA JUGAR")
                self.done.emit(True)
                return

            # ── YA INSTALADO ─────────────────────────────────────────────
            # Antes este caso NO hacía nada (el botón ACTUALIZAR no actualizaba).
            # Ahora, si se pidió actualizar o hay versión nueva, se aplica el overlay.
            if self.force_update or update:
                if MODPACK_UPDATE_LINK_URL:
                    self.status.emit("Actualizando modpack...")
                    self.log.emit("🔄 Descargando y aplicando actualización...")
                    download_modpack(self.progress.emit, self.log.emit, MODPACK_UPDATE_LINK_URL)
                    update_modpack(self.log.emit, self.progress.emit)
                    if version:
                        save_local_version(version)
                    self.log.emit("✅ Modpack actualizado")
                else:
                    self.log.emit("ℹ️ No hay URL de overlay configurada; nada que aplicar")
            else:
                self.log.emit("✅ Modpack al día")

            self._log_listing()
            self.status.emit("LISTO PARA JUGAR")
            self.done.emit(True)

        except Exception as e:
            self.log.emit(f"❌ Error: {e}")
            self.status.emit("Error — revisa el log")
            self.done.emit(False)

    def _log_listing(self):
        h = install_health()
        self.log.emit(f"📂 .minecraft: {h['mc_dir']}")
        self.log.emit(f"🧩 Mods instalados (.jar): {h['have_count']}")
        if h["want_count"]:
            self.log.emit(f"   esperados: {h['want_count']} | faltan: {h['missing_count']}")
            if h["missing_sample"]:
                self.log.emit("   faltan (muestra): " + ", ".join(h["missing_sample"]))


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
            # Limpiar estado huérfano ANTES de decidir el estado de la UI.
            clear_stale_state(lambda _msg: None)

            installed = is_installed()
            update, version = needs_update(lambda _msg: None)

            if not installed:
                self.result.emit("not_installed", version or "")
            elif update:
                self.result.emit("update", version or "")
            else:
                self.result.emit("ready", version or "")
        except Exception:
            # Ante la duda, NO mentir diciendo "ready": revalidar por disco.
            try:
                self.result.emit(
                    "ready" if is_installed() else "not_installed", ""
                )
            except Exception:
                self.result.emit("not_installed", "")
