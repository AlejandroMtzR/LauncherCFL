# -*- coding: utf-8 -*-
"""
MainWindow: el "cascarón" de la ventana. Solo se encarga de la ventana sin
bordes (arrastrar, redimensionar, persistencia de tamaño/posición) y de
orquestar splash → verificación → pantalla principal. Toda la UI vive en
las pantallas (screens.py) y los hilos en workers.py.
"""
from PySide6.QtWidgets import QWidget, QStackedWidget, QSizeGrip, QApplication
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QPainter, QColor

from . import theme as T
from .components import BgPainter
from .screens import SplashScreen, MainScreen
from .workers import Worker, LauncherUpdateWorker, CheckWorker
from core.game_launcher import launch_minecraft

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
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

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

        self._splash = SplashScreen(resource_fn=self._resource_fn)
        self._main   = MainScreen(resource_fn=self._resource_fn)
        self._stack.addWidget(self._splash)
        self._stack.addWidget(self._main)
        self._stack.setCurrentIndex(0)

        self._main.request_action.connect(self._on_action)
        self._main._min_btn.clicked.connect(self.showMinimized)
        self._main._close_btn.clicked.connect(self.close)

        self._border = QWidget(self)
        self._border.setGeometry(0, 0, w, h)
        self._border.setStyleSheet(
            f"background:transparent; border:1px solid {T.BORDER}; border-radius:14px;"
        )
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
            # El launcher se va a reemplazar y reiniciar solo; no seguimos.
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
        QTimer.singleShot(500, self._show_main)

    def _show_main(self):
        self._splash.stop()
        self._stack.setCurrentIndex(1)
        state = getattr(self, "_check_state", "ready")
        version = getattr(self, "_check_version", "")
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
        if   action == "play":    self._do_play()
        elif action == "install": self._start_worker(False)
        elif action == "update":  self._start_worker(True)

    def _start_worker(self, force_update):
        if self._busy:
            return
        self._busy = True
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
            self._main.set_done_ok()
        else:
            self._main.set_state(MainScreen.S_ERROR)

    def _do_play(self):
        self._main.append_log("🎮 Abriendo Minecraft Launcher...")
        launch_minecraft(self._main.append_log)
