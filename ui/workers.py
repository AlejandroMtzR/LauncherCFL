# -*- coding: utf-8 -*-
import os

from PySide6.QtCore import QThread, Signal

from core.downloader import download_modpack
from core.installer import install_modpack
from core.installer_update import update_modpack
from core.updater import needs_update, save_local_version
from core.updater import get_local_version as get_local_modpack_version
from core.checker import is_installed, install_health, clear_stale_state
from core.launcherUpdate import check_launcher_update, download_new_exe, apply_update
from core import game_launcher
from core.repair import (
    stage_repair,
    restore_worlds,
    commit_repair,
    rollback_repair,
    find_pending_repair,
)
from config import MODPACK_FULL_LINK_URL, MODPACK_UPDATE_LINK_URL, ZIP_NAME


def _forget_verified():
    """Tras tocar .minecraft, el próximo Jugar verifica todo de nuevo."""
    try:
        game_launcher.forget_verified(game_launcher.paths.get_minecraft_dir())
    except Exception:
        pass


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
            # Con el juego abierto los .jar están bloqueados: la copia fallaría
            # a medias. Mejor avisar antes de descargar varios GB.
            if game_launcher.is_game_running():
                raise RuntimeError(
                    "Minecraft está abierto. Ciérralo antes de instalar o actualizar el modpack."
                )

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
                overlay_complete = True
                if MODPACK_UPDATE_LINK_URL:
                    try:
                        self.log.emit("🔄 Aplicando últimos cambios...")
                        download_modpack(self.progress.emit, self.log.emit, MODPACK_UPDATE_LINK_URL)
                        skipped = update_modpack(self.log.emit, self.progress.emit)
                        if skipped:
                            overlay_complete = False
                            self.log.emit(
                                f"⚠️ Overlay incompleto: {skipped} archivo(s) pendiente(s)"
                            )
                    except Exception as e:
                        overlay_complete = False
                        self.log.emit(f"⚠️ No se pudo aplicar el overlay (no crítico): {e}")

                if version and overlay_complete:
                    save_local_version(version)

                _forget_verified()
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
                    skipped = update_modpack(self.log.emit, self.progress.emit)
                    if skipped:
                        raise RuntimeError(
                            f"La actualización dejó {skipped} archivo(s) pendiente(s)"
                        )
                    if version:
                        save_local_version(version)
                    _forget_verified()
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


class RepairWorker(QThread):
    """Reinstalación limpia con predescarga, respaldo y rollback."""

    progress = Signal(int)
    status   = Signal(str)
    log      = Signal(str)
    # ok, ruta del respaldo, instalación anterior intacta/restaurada, al día
    done     = Signal(bool, str, bool, bool)

    def __init__(self, account=None, parent=None):
        super().__init__(parent)
        self.account = account
        self._last_progress = 0

    def _emit_progress(self, value):
        value = max(self._last_progress, min(100, int(value)))
        self._last_progress = value
        self.progress.emit(value)

    def _phase_progress(self, start, end):
        span = max(0, end - start)

        def emit(value):
            value = max(0, min(100, int(value)))
            self._emit_progress(start + int((value / 100) * span))

        return emit

    @staticmethod
    def _backup_location(session):
        if session is None:
            return ""
        for attr in ("backup_dir", "record_dir"):
            value = getattr(session, attr, "")
            if value:
                return str(value)
        return ""

    def run(self):
        session = None
        backup_path = ""
        try:
            self.status.emit("Comprobando que Minecraft esté cerrado...")
            if game_launcher.is_game_running():
                raise RuntimeError(
                    "Minecraft está abierto. Ciérralo antes de reparar la instalación."
                )

            self.log.emit("🛡️ Reparación segura: primero se descargará y validará el modpack.")
            self.log.emit("   La instalación actual no se tocará si falla la descarga.")
            _update, version = needs_update(self.log.emit)

            self.status.emit("Descargando instalación limpia...")
            download_modpack(
                self._phase_progress(0, 40),
                self.log.emit,
                MODPACK_FULL_LINK_URL,
            )

            # La descarga puede tardar bastante; comprobar otra vez justo antes
            # de mover la instalación actual.
            if game_launcher.is_game_running():
                raise RuntimeError(
                    "Minecraft se abrió durante la descarga. Ciérralo y vuelve a intentar."
                )

            self.status.emit("Respaldando mundos e instalación anterior...")
            session = stage_repair(
                account=self.account,
                log=self.log.emit,
                progress=self._phase_progress(40, 50),
            )
            backup_path = self._backup_location(session)

            self.status.emit("Instalando una copia limpia...")
            install_modpack(self.log.emit, self._phase_progress(50, 84))

            fully_updated = True
            if MODPACK_UPDATE_LINK_URL:
                try:
                    self.status.emit("Aplicando los últimos cambios...")
                    download_modpack(
                        self._phase_progress(84, 91),
                        self.log.emit,
                        MODPACK_UPDATE_LINK_URL,
                    )
                    skipped = update_modpack(
                        self.log.emit, self._phase_progress(91, 96)
                    )
                    if skipped:
                        fully_updated = False
                        self.log.emit(
                            f"⚠️ El overlay dejó {skipped} archivo(s) pendiente(s)."
                        )
                except Exception as exc:
                    # El pack completo ya es utilizable; igual que en la
                    # instalación normal, el overlay se considera no crítico.
                    fully_updated = False
                    self.log.emit(f"⚠️ No se pudo aplicar el overlay (no crítico): {exc}")

            self.status.emit("Restaurando mundos guardados...")
            restore_worlds(
                session,
                log=self.log.emit,
                progress=self._phase_progress(96, 99),
            )

            if not is_installed(getattr(session, "minecraft_dir", None)):
                raise RuntimeError(
                    "La verificación final no encontró una instalación completa."
                )

            if version and fully_updated:
                save_local_version(version)

            commit_repair(session, log=self.log.emit)
            _forget_verified()
            self._emit_progress(100)
            h = install_health(getattr(session, "minecraft_dir", None))
            self.log.emit(f"🧩 Mods instalados (.jar): {h['have_count']}")
            self.log.emit("✅ Reparación terminada; el respaldo anterior se conservó.")
            if fully_updated:
                self.status.emit("REPARACIÓN TERMINADA")
            else:
                self.status.emit("REPARADA — ACTUALIZACIÓN PENDIENTE")
            self.done.emit(True, backup_path, True, fully_updated)

        except Exception as exc:
            stage_recovery_ok = bool(getattr(exc, "recovery_ok", True))
            if session is None:
                session = getattr(exc, "session", None)
                backup_path = self._backup_location(session)

            rollback_error = None
            if session is not None and getattr(session, "status", "") == "staged":
                try:
                    self.status.emit("Restaurando la instalación anterior...")
                    rollback_repair(session, log=self.log.emit)
                except Exception as rollback_exc:
                    rollback_error = rollback_exc
            elif not stage_recovery_ok:
                rollback_error = getattr(exc, "rollback_error", exc)

            if session is None:
                self.log.emit("🛡️ La instalación actual no fue modificada.")
            elif stage_recovery_ok and rollback_error is None:
                self.log.emit("↩️ La instalación anterior fue restaurada.")
            else:
                self.log.emit(f"❌ No se pudo completar el rollback: {rollback_error}")
                self.log.emit(f"   Respaldo disponible en: {backup_path}")

            self.log.emit(f"❌ Reparación cancelada: {exc}")
            self.status.emit("Error en la reparación — revisa el registro")
            recovery_ok = stage_recovery_ok and (
                session is None or rollback_error is None
            )
            self.done.emit(False, backup_path, recovery_ok, False)

        finally:
            # install_modpack/update_modpack suelen limpiarlo; cubrir también
            # los fallos entre fases para no dejar un ZIP de varios GB.
            try:
                if os.path.isfile(ZIP_NAME):
                    os.remove(ZIP_NAME)
            except OSError:
                pass


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
            pending = find_pending_repair()
            if pending is not None:
                self.result.emit("recovery", str(pending.backup_dir))
                return

            # Limpiar estado huérfano ANTES de decidir el estado de la UI.
            clear_stale_state(lambda _msg: None)

            installed = is_installed()
            update, version = needs_update(lambda _msg: None)
            if not version and installed:
                # Sin conexión: mostrar la versión instalada en vez de un
                # "Modpack v1.0.0" inventado.
                version = get_local_modpack_version()

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
