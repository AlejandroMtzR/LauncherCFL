
from PySide6.QtWidgets import QWidget, QStackedWidget, QSizeGrip, QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QPainter, QColor

from . import theme as T
from .components import BgPainter
from .screens import SplashScreen, MainScreen
from .account_screen import AccountScreen
from .workers import Worker, LauncherUpdateWorker, CheckWorker
from .play_worker import PlayWorker
from core.game_launcher import launch_minecraft
from core import accounts

WIN_DEFAULT_W = 1100
WIN_DEFAULT_H = 660
WIN_MIN_W     = 820
WIN_MIN_H     = 520
SETTINGS_ORG  = "CFL"
SETTINGS_APP  = "Launcher"


class MainWindow(QWidget):
    def __init__(self, resource_fn=None):
        super().__init__()
        self._resource_fn = resource_fn
        self.setWindowTitle("CFL Launcher")
        self.setMinimumSize(WIN_MIN_W, WIN_MIN_H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        self._busy = False
        self._account = None
        self._launch_lock = False
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self._lock_timer = QTimer(self)
        self._lock_timer.setSingleShot(True)
        self._lock_timer.timeout.connect(self._release_lock)

        screen = QApplication.primaryScreen().availableGeometry()
        def_w = min(WIN_DEFAULT_W, int(screen.width() * 0.85))
        def_h = min(WIN_DEFAULT_H, int(screen.height() * 0.82))
        w = max(self._settings.value("win/w", def_w, int), WIN_MIN_W)
        h = max(self._settings.value("win/h", def_h, int), WIN_MIN_H)
        self.resize(w, h)

        self._build()
        self._restore_pos()
        QTimer.singleShot(100, self._start_check)

    # ── Persistencia ──────────────────────────────────────────────
    def _restore_pos(self):
        screen = QApplication.primaryScreen().availableGeometry()
        if self._settings.contains("win/x"):
            x = max(0, min(self._settings.value("win/x", 0, int), screen.width() - self.width()))
            y = max(0, min(self._settings.value("win/y", 0, int), screen.height() - self.height()))
            self.move(x, y)
        else:
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _save_geo(self):
        self._settings.setValue("win/w", self.width())
        self._settings.setValue("win/h", self.height())
        self._settings.setValue("win/x", self.x())
        self._settings.setValue("win/y", self.y())

    def closeEvent(self, e):
        self._save_geo()
        super().closeEvent(e)

    # ── Arrastrar ─────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.BG))
        p.drawRoundedRect(self.rect(), 14, 14)

    # ── Build ─────────────────────────────────────────────────────
    def _build(self):
        w, h = self.width(), self.height()

        self._bg = BgPainter(self)
        self._bg.setGeometry(0, 0, w, h)

        self._stack = QStackedWidget(self)
        self._stack.setGeometry(0, 0, w, h)
        self._stack.setStyleSheet("background:transparent;")

        self._splash  = SplashScreen(resource_fn=self._resource_fn)
        self._account_screen = AccountScreen(resource_fn=self._resource_fn)
        self._main    = MainScreen(resource_fn=self._resource_fn)
        self._stack.addWidget(self._splash)
        self._stack.addWidget(self._account_screen)
        self._stack.addWidget(self._main)
        self._stack.setCurrentWidget(self._splash)

        self._account_screen.account_ready.connect(self._on_account_ready)
        self._main.request_action.connect(self._on_action)
        self._main.account_changed.connect(self._on_main_account_changed)
        self._main._min_btn.clicked.connect(self.showMinimized)
        self._main._close_btn.clicked.connect(self.close)

        self._border = QWidget(self)
        self._border.setGeometry(0, 0, w, h)
        self._border.setStyleSheet(
            f"background:transparent; border:1px solid {T.BORDER}; border-radius:14px;")
        self._border.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(18, 18)
        self._grip.move(w - 20, h - 20)
        self._grip.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        w, h = self.width(), self.height()
        if hasattr(self, "_bg"):
            self._bg.setGeometry(0, 0, w, h)
            self._stack.setGeometry(0, 0, w, h)
            self._border.setGeometry(0, 0, w, h)
            self._grip.move(w - 20, h - 20)

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
        self._checker = CheckWorker()
        self._checker.result.connect(self._on_check_result)
        self._checker.start()

    def _on_check_result(self, state, version):
        self._check_state = state
        self._check_version = version
        self._splash.set_status("Listo")
        QTimer.singleShot(400, self._gate_account)

    # ── Puerta de cuenta ──────────────────────────────────────────
    def _gate_account(self):
        saved = accounts.load()
        if saved:
            self._account = saved
            self._show_main()
        else:
            self._splash.stop()
            self._account_screen.reset()
            self._stack.setCurrentWidget(self._account_screen)

    def _on_account_ready(self, account):
        self._account = account
        self._show_main()

    def _show_main(self):
        self._splash.stop()
        self._stack.setCurrentWidget(self._main)
        state = getattr(self, "_check_state", "ready")
        version = getattr(self, "_check_version", "")
        self._main.set_account_mode(getattr(self._account, "mode", ""))
        self._main.set_account(self._account)
        if state == "not_installed":
            self._main.set_state(MainScreen.S_NONE, version)
        elif state == "update":
            self._main.set_state(MainScreen.S_UPDATE, version)
        else:
            self._main.set_state(MainScreen.S_READY, version)
            if version:
                self._main.update_version_badge(version)

    # ── Acciones ──────────────────────────────────────────────────
    def _on_action(self, action):
        if   action == "play":      self._do_play("modpack")
        elif action == "home_play": self._on_home_play()
        elif action == "install":   self._start_worker(False)
        elif action == "update":    self._start_worker(True)

    def _on_main_account_changed(self, account):
        self._account = account

    def _on_home_play(self):
        acc = self._account
        if acc is None:
            self._account_screen.reset()
            self._stack.setCurrentWidget(self._account_screen)
            return

        target = self._main.home_target()
        state = getattr(self, "_check_state", "ready")

        if acc.mode == "premium":
            if target == "modpack" and state in ("not_installed", "error"):
                self._start_worker(False)
            elif target == "modpack" and state == "update":
                self._start_worker(True)
            else:
                QMessageBox.information(
                    self,
                    "CFL Launcher",
                    "Esta parte es para NO PREMIUM. Continuando al launcher premium.",
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

    # ── Jugar ─────────────────────────────────────────────────────
    def _do_play(self, target="modpack"):
        # Evita abrir dos veces por doble clic o por instalación instantánea.
        if self._launch_lock or self._busy:
            return

        acc = self._account
        if acc is None:
            self._account_screen.reset()
            self._stack.setCurrentWidget(self._account_screen)
            return

        if acc.mode == "premium":
            self._lock_play(6000)  # enfriamiento
            self._main.append_log("🎮 Abriendo Minecraft Launcher...")
            if launch_minecraft(self._main.append_log):
                self._main.mark_session_started(target)
            return

        self._busy = True
        self._pre_play_state = getattr(self, "_check_state", "ready")
        self._play_target = target
        self._lock_play(0)  # bloquear; se libera con enfriamiento en _on_play_done
        self._main.set_state(MainScreen.S_BUSY)
        self._play_worker = PlayWorker(acc, target=target, ram_gb=self._main.ram_gb())
        self._play_worker.progress.connect(self._main.on_progress)
        self._play_worker.log.connect(self._main.append_log)
        self._play_worker.done.connect(self._on_play_done)
        self._play_worker.start()

    def _on_play_done(self, ok):
        self._busy = False
        if ok:
            target = getattr(self, "_play_target", "modpack")
            self._main.mark_session_started(target)
            if target == "modpack":
                self._check_state = "ready"
                self._main.set_state(MainScreen.S_READY, getattr(self, "_check_version", ""))
            else:
                state = getattr(self, "_pre_play_state", "ready")
                if state == "not_installed":
                    self._main.set_state(MainScreen.S_NONE, getattr(self, "_check_version", ""))
                elif state == "update":
                    self._main.set_state(MainScreen.S_UPDATE, getattr(self, "_check_version", ""))
                else:
                    self._main.set_state(MainScreen.S_READY, getattr(self, "_check_version", ""))
            self._main.append_log("⏳ Iniciando Minecraft, espera unos segundos...")
            self._lock_play(12000)  # enfriamiento: evita relanzar por doble clic
        else:
            self._release_lock()
            target = getattr(self, "_play_target", "modpack")
            state = getattr(self, "_pre_play_state", "not_installed")
            if target == "modpack":
                self._check_state = "error"
                self._main.set_state(MainScreen.S_ERROR)
            else:
                if state == "update":
                    self._main.set_state(MainScreen.S_UPDATE, getattr(self, "_check_version", ""))
                elif state == "ready":
                    self._main.set_state(MainScreen.S_READY, getattr(self, "_check_version", ""))
                else:
                    self._main.set_state(MainScreen.S_NONE, getattr(self, "_check_version", ""))
