import ctypes
import os
import sys
import time

from PySide6.QtWidgets import QWidget, QStackedWidget, QSizeGrip, QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer, QSettings, QRect, QPoint, QUrl
from PySide6.QtGui import QPainter, QColor, QGuiApplication, QDesktopServices

from . import theme as T
from .components import BgPainter
from .screens import SplashScreen, MainScreen
from .account_screen import AccountScreen
from .workers import Worker, RepairWorker, LauncherUpdateWorker, CheckWorker
from .play_worker import PlayWorker
from core.game_launcher import launch_minecraft
from core import game_launcher
from core import accounts

WIN_DEFAULT_W = 1180
WIN_DEFAULT_H = 740
# Por debajo de esto la tarjeta de Inicio y los paneles se enciman.
WIN_MIN_W     = 940
WIN_MIN_H     = 600
TOPBAR_H      = 48
EDGE          = 6      # grosor de las franjas para redimensionar
SETTINGS_ORG  = "CFL"
SETTINGS_APP  = "Launcher"


class _EdgeHandle(QWidget):
    """Franja invisible en un borde: arrastrarla redimensiona la ventana
    con el mecanismo nativo de Windows (la ventana no tiene marco propio)."""

    def __init__(self, parent, edges, cursor):
        super().__init__(parent)
        self._edges = edges
        self.setCursor(cursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemResize(self._edges)
            e.accept()


class MainWindow(QWidget):
    def __init__(self, resource_fn=None):
        super().__init__()
        self._resource_fn = resource_fn
        self.setWindowTitle("CFL Launcher")
        self.setMinimumSize(WIN_MIN_W, WIN_MIN_H)
        # Sin WA_TranslucentBackground: una ventana translúcida obliga a
        # componer la ventana entera en cada repintado (más lento) y sus
        # esquinas "redondeadas" quedaban tapadas por el contenido cuadrado.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self._drag_pos = None
        self._busy = False
        self._account = None
        self._launch_lock = False
        self._repair_in_progress = False
        self._main_shown = False
        self._maximized = False
        self._normal_geo = None
        self._last_press = (0.0, QPoint())
        self._chrome_applied = False
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self._lock_timer = QTimer(self)
        self._lock_timer.setSingleShot(True)
        self._lock_timer.timeout.connect(self._release_lock)

        # Vigilancia: mientras Minecraft esté vivo, bloquea el botón Jugar.
        self._game_running = False
        self._game_timer = QTimer(self)
        self._game_timer.setInterval(2000)
        self._game_timer.timeout.connect(self._poll_game_running)
        self._game_timer.start()

        self._build()
        self._restore_geometry()
        QTimer.singleShot(100, self._start_check)

    # ── Persistencia de tamaño/posición ───────────────────────────
    def _restore_geometry(self):
        screen = QApplication.primaryScreen().availableGeometry()
        def_w = min(WIN_DEFAULT_W, int(screen.width() * 0.88))
        def_h = min(WIN_DEFAULT_H, int(screen.height() * 0.86))
        s = self._settings
        w = max(int(s.value("win/w", def_w, int)), WIN_MIN_W)
        h = max(int(s.value("win/h", def_h, int)), WIN_MIN_H)
        self.resize(w, h)

        placed = False
        if s.contains("win/x"):
            x, y = int(s.value("win/x", 0, int)), int(s.value("win/y", 0, int))
            # La barra superior debe quedar visible en ALGÚN monitor. Antes se
            # recortaba siempre al monitor principal: si el usuario dejaba el
            # launcher en su segunda pantalla, al reabrir volvía a la primera.
            title_strip = QRect(x + 60, y, max(1, w - 180), TOPBAR_H)
            for sc in QGuiApplication.screens():
                if sc.availableGeometry().intersects(title_strip):
                    self.move(x, y)
                    placed = True
                    break
        if not placed:
            self.move(screen.x() + (screen.width() - w) // 2,
                      screen.y() + (screen.height() - h) // 2)
        if s.value("win/max", False, bool):
            QTimer.singleShot(0, self._maximize)

    def _save_geo(self):
        geo = self._normal_geo if self._maximized and self._normal_geo else self.geometry()
        self._settings.setValue("win/w", geo.width())
        self._settings.setValue("win/h", geo.height())
        self._settings.setValue("win/x", geo.x())
        self._settings.setValue("win/y", geo.y())
        self._settings.setValue("win/max", self._maximized)
        self._settings.sync()

    def closeEvent(self, e):
        if self._repair_in_progress:
            QMessageBox.warning(
                self,
                "Reparación en curso",
                "Espera a que termine la reparación antes de cerrar el launcher.\n\n"
                "La instalación anterior está protegida por un respaldo, pero "
                "interrumpir este paso puede dejar la instalación nueva incompleta.",
            )
            e.ignore()
            return
        if self._busy:
            ans = QMessageBox.question(
                self,
                "Hay una tarea en curso",
                "El launcher está descargando o instalando archivos.\n\n"
                "Si cierras ahora se cancelará y la próxima vez empezará de nuevo.\n"
                "¿Cerrar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
        self._save_geo()
        super().closeEvent(e)

    # ── Mover / maximizar (ventana sin marco) ─────────────────────
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pos = e.position().toPoint()
        now = time.monotonic()
        last_t, last_pos = self._last_press
        self._last_press = (now, pos)
        in_title = pos.y() <= TOPBAR_H
        # Doble clic en la barra superior: maximizar / restaurar.
        if in_title and now - last_t <= QApplication.doubleClickInterval() / 1000 \
                and (pos - last_pos).manhattanLength() < 8:
            self._last_press = (0.0, QPoint())
            self._toggle_maximize()
            return
        if self._maximized:
            # Arrastrar una ventana maximizada la restaura bajo el cursor.
            ratio = pos.x() / max(1, self.width())
            self._restore()
            gp = e.globalPosition().toPoint()
            self.move(gp.x() - int(self.width() * ratio), gp.y() - min(pos.y(), TOPBAR_H // 2))
        handle = self.windowHandle()
        # Movimiento nativo: suave, multi-monitor y con Aero Snap.
        if handle is not None and handle.startSystemMove():
            self._drag_pos = None
            return
        self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def _toggle_maximize(self):
        if self._maximized:
            self._restore()
        else:
            self._maximize()

    def _maximize(self):
        if self._maximized:
            return
        self._normal_geo = self.geometry()
        screen = self.screen() or QApplication.primaryScreen()
        # Maximizado "manual" al área de trabajo: una ventana sin marco
        # maximizada por el sistema puede tapar la barra de tareas.
        self._maximized = True
        self.setGeometry(screen.availableGeometry())
        self._update_chrome()

    def _restore(self):
        if not self._maximized:
            return
        self._maximized = False
        if self._normal_geo is not None:
            self.setGeometry(self._normal_geo)
        self._update_chrome()

    def _update_chrome(self):
        for w in self._edges + [self._grip, self._border]:
            w.setVisible(not self._maximized)
        self._main.set_maximized(self._maximized)
        self._place_chrome()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._chrome_applied:
            self._chrome_applied = True
            self._apply_windows_corners()

    def _apply_windows_corners(self):
        """Windows 11: esquinas redondeadas nativas (en Windows 10 no hace nada)."""
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))  # DWMWA_WINDOW_CORNER_PREFERENCE
        except Exception:
            pass

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T.BG))

    # ── Build ─────────────────────────────────────────────────────
    def _build(self):
        self._bg = BgPainter(self)

        self._stack = QStackedWidget(self)
        self._stack.setStyleSheet("background:transparent;")

        self._splash  = SplashScreen(resource_fn=self._resource_fn)
        self._account_screen = AccountScreen(resource_fn=self._resource_fn)
        self._main    = MainScreen(resource_fn=self._resource_fn)
        self._stack.addWidget(self._splash)
        self._stack.addWidget(self._account_screen)
        self._stack.addWidget(self._main)
        self._stack.setCurrentWidget(self._splash)

        self._account_screen.account_ready.connect(self._on_account_ready)
        self._account_screen.cancelled.connect(self._on_account_cancel)
        self._main.request_action.connect(self._on_action)
        self._main.account_changed.connect(self._on_main_account_changed)
        self._main._min_btn.clicked.connect(self.showMinimized)
        self._main._max_btn.clicked.connect(self._toggle_maximize)
        self._main._close_btn.clicked.connect(self.close)

        self._border = QWidget(self)
        self._border.setStyleSheet(f"background:transparent; border:1px solid {T.BORDER_HI};")
        self._border.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(18, 18)

        C = Qt
        self._edges = [
            _EdgeHandle(self, C.TopEdge, C.SizeVerCursor),
            _EdgeHandle(self, C.BottomEdge, C.SizeVerCursor),
            _EdgeHandle(self, C.LeftEdge, C.SizeHorCursor),
            _EdgeHandle(self, C.RightEdge, C.SizeHorCursor),
            _EdgeHandle(self, C.TopEdge | C.LeftEdge, C.SizeFDiagCursor),
            _EdgeHandle(self, C.TopEdge | C.RightEdge, C.SizeBDiagCursor),
            _EdgeHandle(self, C.BottomEdge | C.LeftEdge, C.SizeBDiagCursor),
            _EdgeHandle(self, C.BottomEdge | C.RightEdge, C.SizeFDiagCursor),
        ]
        self._place_chrome()

    def _place_chrome(self):
        w, h = self.width(), self.height()
        self._bg.setGeometry(0, 0, w, h)
        self._stack.setGeometry(0, 0, w, h)
        self._border.setGeometry(0, 0, w, h)
        self._grip.move(w - 20, h - 20)
        e, c = EDGE, EDGE * 2
        geos = [
            (c, 0, w - 2 * c, e), (c, h - e, w - 2 * c, e),
            (0, c, e, h - 2 * c), (w - e, c, e, h - 2 * c),
            (0, 0, c, c), (w - c, 0, c, c), (0, h - c, c, c), (w - c, h - c, c, c),
        ]
        for handle, (x, y, gw, gh) in zip(self._edges, geos):
            handle.setGeometry(x, y, max(1, gw), max(1, gh))
            handle.raise_()
        self._border.raise_()
        self._grip.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_edges"):
            self._place_chrome()

    # ── Verificación inicial ──────────────────────────────────────
    def _start_check(self):
        self._splash.set_status("Verificando launcher...")
        self._launcher_update_thread = LauncherUpdateWorker()
        self._launcher_update_thread.status.connect(self._splash.set_status)
        self._launcher_update_thread.progress.connect(self._splash.set_progress)
        self._launcher_update_thread.done.connect(self._on_launcher_check_done)
        self._launcher_update_thread.start()

    def _on_launcher_check_done(self, updated):
        if updated:
            self._splash.set_status("Actualizando launcher, reiniciando...")
            return
        self._splash.set_status("Verificando modpack...")
        self._splash.hide_progress()
        self._run_check_worker()

    def _run_check_worker(self):
        self._checker = CheckWorker()
        self._checker.result.connect(self._on_check_result)
        self._checker.start()

    def _on_check_result(self, state, version):
        self._check_state = state
        if state == "recovery":
            self._recovery_backup = version
            self._check_version = ""
        else:
            self._check_version = version
        if self._main_shown:
            # Re-verificación pedida desde el menú: solo refrescar el estado.
            self._apply_check_state()
            self._main.append_log("🔍 Verificación terminada")
            return
        self._splash.set_status("Listo")
        QTimer.singleShot(400, self._gate_account)

    def _start_recheck(self):
        if self._busy:
            return
        self._main.set_state(MainScreen.S_CHECKING)
        self._main.append_log("🔍 Verificando la instalación del modpack...")
        self._run_check_worker()

    # ── Puerta de cuenta ──────────────────────────────────────────
    def _gate_account(self):
        saved = accounts.load()
        if saved:
            self._account = saved
            self._show_main()
        else:
            self._splash.stop()
            self._account_screen.reset()
            self._account_screen.set_can_cancel(False)
            self._stack.setCurrentWidget(self._account_screen)

    def _on_account_ready(self, account):
        self._account = account
        if account:
            accounts.save(account)
        self._show_main()

    def _on_account_cancel(self):
        if self._account is not None:
            self._stack.setCurrentWidget(self._main)

    def _switch_account(self):
        if self._busy:
            QMessageBox.information(
                self, "CFL Launcher",
                "Espera a que termine la tarea en curso para cambiar de cuenta.")
            return
        self._account_screen.reset()
        self._account_screen.set_can_cancel(self._account is not None)
        self._stack.setCurrentWidget(self._account_screen)

    def _show_main(self):
        self._splash.stop()
        self._stack.setCurrentWidget(self._main)
        self._main_shown = True
        self._main.set_account(self._account)
        self._apply_check_state()

    def _apply_check_state(self):
        state = getattr(self, "_check_state", "ready")
        version = getattr(self, "_check_version", "")
        if state == "not_installed":
            self._main.set_state(MainScreen.S_NONE, version)
        elif state == "update":
            self._main.set_state(MainScreen.S_UPDATE, version)
        elif state == "recovery":
            self._busy = True
            self._main.set_state(MainScreen.S_ERROR)
            self._main.set_recovery_required(
                getattr(self, "_recovery_backup", "")
            )
        elif state == "error":
            self._main.set_state(MainScreen.S_ERROR)
        else:
            self._main.set_state(MainScreen.S_READY, version)

    # ── Acciones ──────────────────────────────────────────────────
    def _on_action(self, action):
        if   action == "play":      self._do_play("modpack")
        elif action == "home_play": self._on_home_play()
        elif action == "install":   self._start_worker(False)
        elif action == "update":    self._start_worker(True)
        elif action == "repair":    self._start_repair()
        elif action == "recheck":   self._start_recheck()
        elif action == "switch_account": self._switch_account()

    def _on_main_account_changed(self, account):
        self._account = account

    def _on_home_play(self):
        acc = self._account
        if acc is None:
            self._switch_account()
            return

        target = self._main.home_target()
        state = getattr(self, "_check_state", "ready")

        if acc.mode == "premium":
            if target == "modpack" and state in ("not_installed", "error"):
                self._start_worker(False)
            elif target == "modpack" and state == "update":
                self._start_worker(True)
            else:
                if target != "modpack":
                    QMessageBox.information(
                        self,
                        "CFL Launcher",
                        "Con cuenta premium las versiones se eligen y se juegan desde "
                        "el launcher oficial de Minecraft. Se abrirá ahora.",
                    )
                self._do_play("modpack")
            return

        if target == "modpack":
            if state in ("not_installed", "error"):
                self._start_worker(False)
            elif state == "update":
                self._start_worker(True)
            else:
                self._do_play("modpack")
        else:
            self._do_play(target)

    def _start_worker(self, force_update):
        if self._busy:
            return
        self._busy = True
        self._pre_worker_state = getattr(self, "_check_state", "ready")
        self._main.set_state(MainScreen.S_BUSY)
        self._main.set_status_text("Actualizando modpack..." if force_update else "Preparando instalación...")
        self._worker = Worker(force_update=force_update)
        self._worker.progress.connect(self._main.on_progress)
        self._worker.status.connect(self._main.set_status_text)
        self._worker.log.connect(self._main.append_log)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok):
        self._busy = False
        if ok:
            self._check_state = "ready"
            self._main.set_done_ok()
        else:
            self._check_state = getattr(self, "_pre_worker_state", "not_installed")
            self._main.set_state(MainScreen.S_ERROR)

    def _start_repair(self):
        if self._busy:
            return

        if game_launcher.is_tracked_game_running():
            self._notify_game_running()
            return

        # El perfil offline vive fuera de .minecraft. Guardarlo una vez más
        # antes de iniciar deja persistidos nombre, UUID y skin actuales.
        if self._account and getattr(self._account, "mode", "") == "offline":
            try:
                accounts.save(self._account)
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "No se pudo iniciar la reparación",
                    f"No fue posible guardar el perfil no premium:\n\n{exc}",
                )
                return

        self._busy = True
        self._repair_in_progress = True
        self._pre_repair_state = getattr(self, "_check_state", "ready")
        self._main.set_state(MainScreen.S_BUSY)
        self._main.set_status_text("Preparando reparación segura...")

        # RepairWorker comprueba (en su hilo) que Minecraft esté cerrado.
        self._repair_worker = RepairWorker(account=self._account)
        self._repair_worker.progress.connect(self._main.on_progress)
        self._repair_worker.status.connect(self._main.set_status_text)
        self._repair_worker.log.connect(self._main.append_log)
        self._repair_worker.done.connect(self._on_repair_done)
        self._repair_worker.start()

    def _on_repair_done(self, ok, backup_path, recovery_ok, fully_updated):
        self._busy = not recovery_ok
        self._repair_in_progress = False

        if ok:
            self._check_state = "ready" if fully_updated else "update"
            if fully_updated:
                self._main.set_done_ok()
            else:
                self._main.on_progress(100)
                self._main.set_state(
                    MainScreen.S_UPDATE, getattr(self, "_check_version", "")
                )
            if hasattr(self._main, "set_last_repair_backup"):
                self._main.set_last_repair_backup(backup_path)
            detail = (
                f"\n\nRespaldo de la instalación anterior:\n{backup_path}"
                if backup_path else ""
            )
            result_text = (
                "La instalación limpia terminó correctamente y tus mundos "
                "fueron restaurados."
                if fully_updated else
                "La instalación limpia y tus mundos quedaron listos, pero no "
                "se pudieron aplicar todos los cambios más recientes. Usa "
                "ACTUALIZAR cuando el servidor esté disponible."
            )
            QMessageBox.information(
                self,
                "Reparación terminada",
                f"{result_text}{detail}",
            )
            return

        previous = getattr(self, "_pre_repair_state", "ready")
        if not recovery_ok:
            self._check_state = "error"
            self._main.set_state(MainScreen.S_ERROR)
            if hasattr(self._main, "set_recovery_required"):
                self._main.set_recovery_required(backup_path)
        else:
            self._check_state = previous
            self._apply_check_state()

        detail = (
            f"\n\nEl respaldo recuperable está en:\n{backup_path}"
            if backup_path else ""
        )
        message = (
            "La instalación anterior quedó intacta o fue restaurada."
            if recovery_ok else
            "No fue posible restaurar automáticamente la instalación anterior. "
            "No intentes jugar hasta revisar el respaldo."
        )
        dialog = QMessageBox.warning if recovery_ok else QMessageBox.critical
        dialog(
            self,
            "No se pudo completar la reparación",
            f"{message}{detail}\n\nRevisa el registro para ver la causa.",
        )

    # ── Candado anti-doble-clic ───────────────────────────────────
    def _lock_play(self, cooldown_ms):
        self._launch_lock = True
        try:
            self._main._main_btn.setEnabled(False)
            if hasattr(self._main, "_modpack_action_btn"):
                self._main._modpack_action_btn.setEnabled(False)
        except Exception:
            pass
        if cooldown_ms > 0:
            self._lock_timer.start(cooldown_ms)

    def _release_lock(self):
        self._launch_lock = False
        try:
            if not self._busy:
                self._main._update_home_state()
                self._main._update_modpack_page_state()
        except Exception:
            pass

    # ── Vigilancia de "juego en ejecución" ───────────────────────
    def _poll_game_running(self):
        # Barato: solo revisa el proceso que lanzamos (poll instantáneo).
        try:
            running = game_launcher.is_tracked_game_running()
        except Exception:
            running = False
        if running != self._game_running:
            self._game_running = running
            try:
                self._main.set_game_running(running)
            except Exception:
                pass
        info = game_launcher.pop_last_exit()
        if info and game_launcher.is_early_crash(info):
            self._report_early_crash(info)

    def _report_early_crash(self, info):
        code, secs = info.get("code"), int(info.get("seconds", 0))
        self._main.append_log(
            f"❌ Minecraft se cerró con un error (código {code}) a los {secs} s de abrirse.")
        game_dir = info.get("game_dir") or ""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Minecraft se cerró inesperadamente")
        box.setText("Minecraft se cerró con un error poco después de abrirse.")
        box.setInformativeText(
            "Causas comunes: poca RAM asignada, un mod incompatible o archivos "
            "dañados. La próxima vez el launcher verificará todos los archivos "
            "antes de jugar.\n\nEn 'Mostrar detalles' están las últimas líneas del juego."
        )
        tail = game_launcher.crash_log_tail(info)
        if tail:
            box.setDetailedText(tail)
        open_btn = box.addButton("Abrir registros", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is open_btn:
            for sub in ("crash-reports", "logs", ""):
                folder = os.path.join(game_dir, sub) if sub else game_dir
                if folder and os.path.isdir(folder):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
                    break

    def _notify_game_running(self):
        QMessageBox.information(
            self,
            "CFL Launcher",
            "Minecraft ya se está ejecutando.\n\n"
            "Cierra el juego antes de volver a darle Jugar.",
        )

    # ── Jugar ─────────────────────────────────────────────────────
    def _do_play(self, target="modpack"):
        # Evita abrir dos veces por doble clic o por instalación instantánea.
        if self._launch_lock or self._busy:
            return

        acc = self._account
        if acc is None:
            self._switch_account()
            return

        if acc.mode == "premium":
            self._lock_play(6000)  # enfriamiento
            self._main.append_log("🎮 Abriendo Minecraft Launcher...")
            if launch_minecraft(self._main.append_log):
                self._main.mark_session_started(target)
            return

        # No premium: chequeo rápido aquí; el escaneo completo (lento) corre
        # dentro de PlayWorker para no congelar la ventana.
        if game_launcher.is_tracked_game_running():
            self._game_running = True
            self._main.set_game_running(True)
            self._notify_game_running()
            return

        self._busy = True
        self._play_target = target
        self._lock_play(0)  # bloquear; se libera con enfriamiento en _on_play_done
        self._main.set_state(MainScreen.S_BUSY)
        self._main.set_status_text("Preparando Minecraft...")
        self._play_worker = PlayWorker(acc, target=target, ram_gb=self._main.ram_gb())
        self._play_worker.progress.connect(self._main.on_progress)
        self._play_worker.log.connect(self._main.append_log)
        self._play_worker.done.connect(self._on_play_done)
        self._play_worker.already_running.connect(self._on_play_already_running)
        self._play_worker.start()

    def _on_play_already_running(self):
        self._busy = False
        self._release_lock()
        self._apply_check_state()
        self._game_running = True
        self._main.set_game_running(True)
        self._main.append_log("⚠️ Minecraft ya se está ejecutando.")
        self._notify_game_running()

    def _on_play_done(self, ok, error=""):
        self._busy = False
        target = getattr(self, "_play_target", "modpack")
        if ok:
            self._main.mark_session_started(target)
            if target == "modpack":
                self._check_state = "ready"
            elif target[0] == "vanilla":
                self._main.mark_version_installed(target[1])
            self._apply_check_state()
            self._main.on_progress(100)
            self._main.schedule_overlay_hide()
            self._main.append_log("⏳ Iniciando Minecraft, espera unos segundos...")
            self._lock_play(12000)  # enfriamiento: evita relanzar por doble clic
        else:
            # Un fallo al LANZAR no es un fallo de instalación: se conserva el
            # estado del modpack (antes pasaba a "REINTENTAR" = reinstalar).
            self._release_lock()
            self._apply_check_state()
            QMessageBox.warning(
                self,
                "No se pudo iniciar Minecraft",
                f"{error or 'Error desconocido.'}\n\nRevisa el registro para más detalles.",
            )
