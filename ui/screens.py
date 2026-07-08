# -*- coding: utf-8 -*-
"""
Las dos pantallas del launcher: SplashScreen (carga inicial) y MainScreen
(barra lateral + topbar + páginas: Inicio / Mods / Ajustes).
"""
import os
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from . import theme as T
from .components import Spinner, GlowBar, LogBox, PlayBtn, SecBtn, WinBtn, NavItem
from .mods_page import ModsPage
from .gallery import Lightbox
from .mods_page import ModsPage, HeroBanner
from core.utils import resource_path
from core.launcherUpdate import LAUNCHER_VERSION as APP_VERSION

MODPACK_VERSION = "1.0.0"
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.ico")


def _read_launcher_version():
    path = os.path.join(os.getenv("APPDATA", ""), "CFLLauncher", "launcherVersion.txt")
    try:
        with open(path) as f:
            return f.read().strip() or APP_VERSION
    except FileNotFoundError:
        return APP_VERSION

LAUNCHER_VERSION = _read_launcher_version()


def get_logo(resource_fn=None):
    if resource_fn:
        return resource_fn("assets/logo.ico")
    return LOGO_PATH



#   SPLASH SCREEN

class SplashScreen(QWidget):
    def __init__(self, resource_fn=None, parent=None):
        super().__init__(parent)
        self._resource_fn = resource_fn
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter); lay.setSpacing(0)
        lay.addStretch(3)

        logo_lbl = QLabel(); logo_lbl.setAlignment(Qt.AlignCenter)
        px = QPixmap(get_logo(self._resource_fn))
        if not px.isNull():
            logo_lbl.setPixmap(px.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("⬡"); logo_lbl.setStyleSheet(f"font-size:72px; color:{T.ACCENT};")
        lay.addWidget(logo_lbl); lay.addSpacing(22)

        t = QLabel("CFL LAUNCHER"); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"font-family:'{T.FONT}'; font-size:46px; font-weight:900;"
                       f" color:{T.TEXT}; letter-spacing:10px;")
        lay.addWidget(t); lay.addSpacing(6)

        s = QLabel("CHAFALAND MODPACK"); s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; font-weight:500;"
                       f" color:{T.ACCENT_HI}; letter-spacing:8px;")
        lay.addWidget(s); lay.addSpacing(40)

        row = QHBoxLayout(); row.setAlignment(Qt.AlignCenter); row.setSpacing(12)
        self._spinner = Spinner(size=20, color=T.ACCENT); self._spinner.start()
        row.addWidget(self._spinner)
        self._lbl = QLabel("Verificando actualizaciones...")
        self._lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px;"
                               f" color:{T.TEXT2}; letter-spacing:1px;")
        row.addWidget(self._lbl)
        lay.addLayout(row); lay.addStretch(4)

        ver = QLabel(f"v{LAUNCHER_VERSION}"); ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:10px; color:{T.DIM};")
        lay.addWidget(ver); lay.addSpacing(20)

    def set_status(self, text): self._lbl.setText(text)

    def set_progress(self, v):
        if not hasattr(self, "_pbar"):
            self._pbar = QProgressBar(); self._pbar.setTextVisible(False)
            self._pbar.setFixedHeight(3)
            self._pbar.setStyleSheet(f"""
                QProgressBar {{ background: rgba(255,255,255,0.05); border-radius:1px; border:none; }}
                QProgressBar::chunk {{ background: {T.ACCENT}; border-radius:1px; }}
            """)
            lay = self.layout(); lay.insertWidget(lay.count() - 2, self._pbar)
        self._pbar.setValue(v); self._pbar.show()

    def hide_progress(self):
        if hasattr(self, "_pbar"): self._pbar.hide()

    def stop(self):
        self._spinner.stop(); self._lbl.setText("Listo")



#   MAIN SCREEN

class MainScreen(QWidget):
    request_action = Signal(str)   # "install" | "update" | "play"

    S_CHECKING = "checking"
    S_NONE     = "not_installed"
    S_UPDATE   = "update"
    S_READY    = "ready"
    S_BUSY     = "busy"
    S_ERROR    = "error"

    def __init__(self, resource_fn=None, parent=None):
        super().__init__(parent)
        self._resource_fn = resource_fn
        self._state = self.S_CHECKING
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── SIDEBAR ───────────────────────────────────────────────
        sidebar = QWidget(); sidebar.setFixedWidth(196)
        sidebar.setStyleSheet(f"background: {T.rgba(T.SURFACE, 0.92)};")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 20, 14, 16); sb.setSpacing(4); sb.setAlignment(Qt.AlignTop)

        logo_row = QHBoxLayout(); logo_row.setContentsMargins(6, 0, 0, 0); logo_row.setSpacing(11)
        logo = QLabel(); logo.setFixedSize(42, 42); logo.setAlignment(Qt.AlignCenter)
        px = QPixmap(get_logo(self._resource_fn))
        if not px.isNull():
            logo.setPixmap(px.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("CFL")
            logo.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
                              f" color:{T.ACCENT}; background:{T.rgba(T.ACCENT,0.10)}; border-radius:10px;")
        logo_row.addWidget(logo)
        wordmark = QLabel(f"<span style='font-size:17px;font-weight:900;color:{T.TEXT};'>CFL</span>"
                          f"<br><span style='font-size:9px;font-weight:800;color:{T.ACCENT_HI};"
                          "letter-spacing:3px;'>LAUNCHER</span>")
        wordmark.setTextFormat(Qt.RichText); wordmark.setStyleSheet("background:transparent;")
        logo_row.addWidget(wordmark); logo_row.addStretch()
        sb.addLayout(logo_row); sb.addSpacing(22)

        self._nav_home = NavItem("home", "INICIO", active=True)
        self._nav_mods = NavItem("grid", "MODS")
        self._nav_cfg  = NavItem("gear", "AJUSTES")
        for b in [self._nav_home, self._nav_mods, self._nav_cfg]:
            sb.addWidget(b)
        sb.addStretch()

        footer = QLabel("© 2026 ChafaLand")
        footer.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px; color:{T.DIM};")
        footer.setContentsMargins(8, 0, 0, 0)
        sb.addWidget(footer)
        root.addWidget(sidebar)

        self._nav_home.clicked.connect(lambda: self._switch_page(0))
        self._nav_mods.clicked.connect(lambda: self._switch_page(1))
        self._nav_cfg.clicked.connect(lambda: self._switch_page(2))

        # ── CONTENIDO ─────────────────────────────────────────────
        content = QWidget(); content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(content); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # Topbar
        topbar = QWidget(); topbar.setFixedHeight(48)
        topbar.setStyleSheet(f"background:{T.rgba(T.SURFACE, 0.75)};")
        tb = QHBoxLayout(topbar); tb.setContentsMargins(24, 0, 0, 0); tb.setSpacing(0)
        self._bread = QLabel("CFL LAUNCHER  /  INICIO")
        self._bread.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                                 f" color:{T.MUTED}; letter-spacing:2px;")
        tb.addWidget(self._bread); tb.addStretch()
        self._ver_badge = QLabel(f"Modpack v{MODPACK_VERSION}")
        self._ver_badge.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:10px;"
            f" color:{T.ACCENT_HI}; background:{T.rgba(T.ACCENT,0.09)};"
            f" border:1px solid {T.rgba(T.ACCENT,0.22)}; border-radius:4px; padding:3px 10px;")
        tb.addWidget(self._ver_badge); tb.addSpacing(8)
        sep = QFrame(); sep.setFrameShape(QFrame.VLine); sep.setFixedHeight(20)
        sep.setStyleSheet(f"color:{T.BORDER};")
        tb.addWidget(sep)
        self._min_btn   = WinBtn("─", hover_bg="#1b2230", hover_fg=T.TEXT)
        self._close_btn = WinBtn("✕", hover_bg="#7f1d1d", hover_fg="#ffffff")
        tb.addWidget(self._min_btn); tb.addWidget(self._close_btn)
        cl.addWidget(topbar)

        # Páginas
        self._pages = QStackedWidget(); self._pages.setStyleSheet("background:transparent;")
        self._pages.addWidget(self._build_home_page())   # 0
        self._mods_page = ModsPage()
        self._mods_page.open_image.connect(self._open_lightbox)
        self._pages.addWidget(self._mods_page)            # 1
        self._pages.addWidget(self._build_ajustes_page()) # 2
        cl.addWidget(self._pages)
        root.addWidget(content)

        # Visor (encima de todo)
        self._lightbox = Lightbox(self)

    # ── Página INICIO (hero + panel inferior) ─────────────────────
    def _build_home_page(self):
        page = QWidget();
        page.setStyleSheet("background:transparent;")
        ph = QVBoxLayout(page);
        ph.setContentsMargins(0, 0, 0, 0);
        ph.setSpacing(0)
        banner = HeroBanner(
            resource_path("assets/home_banner.png"),
            show_text=False
        )
        banner.setFixedHeight(340)

        hero = QWidget()
        hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hero.setStyleSheet("background:transparent;")
        hl = QVBoxLayout(hero); hl.setContentsMargins(52, 0, 52, 0); hl.setSpacing(0)
        hl.addWidget(banner)
        hl.addSpacing(30)


        self._tag = QLabel("MODPACK  ·  MINECRAFT 1.20.1")
        self._tag.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; font-weight:600;"
                               f" color:{T.ACCENT_HI}; letter-spacing:5px;")
        hl.addWidget(self._tag); hl.addSpacing(8)
        self._title = QLabel("CFL LAUNCHER")
        self._title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:52px; font-weight:900;"
                                 f" color:{T.TEXT}; letter-spacing:3px;")
        hl.addWidget(self._title); hl.addSpacing(10)
        self._desc = QLabel("ChafaLand Modpack Oficial  ·  +340 Mods activos")
        self._desc.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; font-weight:400; color:{T.MUTED};")
        hl.addWidget(self._desc); hl.addSpacing(28)

        btn_row = QHBoxLayout(); btn_row.setSpacing(12); btn_row.setAlignment(Qt.AlignLeft)
        self._main_btn = PlayBtn(); self._main_btn.setText("CARGANDO..."); self._main_btn.setEnabled(False)
        self._main_btn.clicked.connect(self._on_main)
        self._sec_btn = SecBtn("..."); self._sec_btn.setEnabled(False)
        self._sec_btn.clicked.connect(self._on_sec)
        self._chk_spin = Spinner(size=20, color=T.ACCENT_HI)
        btn_row.addWidget(self._main_btn); btn_row.addWidget(self._sec_btn)
        btn_row.addSpacing(6); btn_row.addWidget(self._chk_spin)
        hl.addLayout(btn_row)

        hl.addSpacing(28)

        stats = QHBoxLayout()
        stats.setSpacing(12)

        for txt in (

        ):
            card = QLabel(txt)
            card.setAlignment(Qt.AlignCenter)
            card.setFixedSize(170, 54)

            card.setStyleSheet(f"""
                background:{T.rgba(T.CARD, 0.70)};
                border:1px solid {T.BORDER};
                border-radius:14px;
                color:{T.TEXT};
                font-size:13px;
                font-weight:700;
            """)

            stats.addWidget(card)

        stats.addStretch()

        hl.addLayout(stats)

        bottom = QWidget(); bottom.setFixedHeight(140)
        bottom.setStyleSheet(f"background:{T.rgba(T.SURFACE,0.70)};"
                            f" border-top:1px solid {T.BORDER};")
        bl = QVBoxLayout(bottom); bl.setContentsMargins(52, 14, 52, 16); bl.setSpacing(6)
        sr = QHBoxLayout()
        self._st_lbl = QLabel("INICIANDO")
        self._st_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                                  f" color:{T.ACCENT_HI}; letter-spacing:3px;")
        self._pct_lbl = QLabel("")
        self._pct_lbl.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:9px; color:{T.MUTED};")
        sr.addWidget(self._st_lbl); sr.addStretch(); sr.addWidget(self._pct_lbl)
        bl.addLayout(sr)
        self._bar = GlowBar(); bl.addWidget(self._bar); bl.addSpacing(5)
        self._log = LogBox(); bl.addWidget(self._log)

        ph.addWidget(hero); ph.addWidget(bottom)
        return page

    # ── Página AJUSTES (placeholder, listo para extender) ─────────
    def _build_ajustes_page(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(52, 22, 52, 22); lay.setSpacing(0)
        title = QLabel("AJUSTES")
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:26px; font-weight:900;"
                           f" color:{T.TEXT}; letter-spacing:2px;")
        lay.addWidget(title)
        sub = QLabel("Configuración del launcher")
        sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};")
        lay.addWidget(sub); lay.addSpacing(20)

        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background:{T.rgba(T.CARD,0.65)};"
                          f" border:1px solid {T.BORDER}; border-radius:14px; }}")
        cv = QVBoxLayout(card); cv.setContentsMargins(20, 24, 20, 24)
        msg = QLabel("⚙  Próximamente —  opciones del launcher.")
        msg.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; color:{T.TEXT2};")
        cv.addWidget(msg)
        lay.addWidget(card); lay.addStretch()
        return page

    # ── Visor ─────────────────────────────────────────────────────
    def _open_lightbox(self, paths, idx):
        self._lightbox.open_at(paths, idx)

    # ── Cambio de página ──────────────────────────────────────────
    def _switch_page(self, idx):
        self._pages.setCurrentIndex(idx)
        self._nav_home.setActive(idx == 0)
        self._nav_mods.setActive(idx == 1)
        self._nav_cfg.setActive(idx == 2)
        name = {0: "INICIO", 1: "MODS", 2: "AJUSTES"}[idx]
        self._bread.setText("CFL LAUNCHER  /  " + name)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_lightbox") and self._lightbox.isVisible():
            self._lightbox.setGeometry(self.rect())

    # ── Máquina de estados ────────────────────────────────────────
    def set_state(self, state, remote_version=""):
        self._state = state
        if remote_version:
            self._current_version = remote_version

        if state == self.S_CHECKING:

            self._main_btn.setText("VERIFICANDO...")
            self._main_btn.setMode("play")
            self._main_btn.setEnabled(False)

            self._sec_btn.setText("...")
            self._sec_btn.setEnabled(False)

            self._chk_spin.start()
            self._set_st("VERIFICANDO ARCHIVOS", T.ACCENT_HI)

        elif state == self.S_NONE:

            self._main_btn.setText("INSTALAR MODPACK")
            self._main_btn.setMode("install")
            self._main_btn.setEnabled(True)

            self._sec_btn.hide()

            self._chk_spin.stop()

            self._set_st("PRIMERA INSTALACIÓN", T.INFO)

            self._log.append_log(
                "🆕 Modpack no instalado — pulsa INSTALAR MODPACK para comenzar"
            )

        elif state == self.S_UPDATE:

            self._main_btn.setText("ACTUALIZAR MODPACK")
            self._main_btn.setMode("update")
            self._main_btn.setEnabled(True)

            self._sec_btn.setText("JUGAR IGUAL")
            self._sec_btn.show()
            self._sec_btn.setEnabled(True)

            self._chk_spin.stop()

            self._set_st(
                "ACTUALIZACIÓN DISPONIBLE",
                T.INFO2
            )

            if remote_version:
                self._ver_badge.setText(
                    f"Versión disponible v{remote_version}"
                )

                self._ver_badge.setStyleSheet(
                    f"""
                    font-family:'{T.FONT_MONO}';
                    font-size:10px;
                    color:{T.INFO2};
                    background:{T.rgba(T.INFO2, 0.09)};
                    border:1px solid {T.rgba(T.INFO2, 0.25)};
                    border-radius:4px;
                    padding:3px 10px;
                    """
                )

            self._log.append_log(
                "⬆️ Hay una actualización disponible. Se recomienda actualizar antes de iniciar."
            )

        elif state == self.S_READY:

            self._main_btn.setText("JUGAR")
            self._main_btn.setMode("play")
            self._main_btn.setEnabled(True)

            self._sec_btn.setText("✅AL DÍA")
            self._sec_btn.show()
            self._sec_btn.setEnabled(False)

            self._chk_spin.stop()

            self._set_st(
                "LISTO PARA JUGAR",
                T.ACCENT_HI
            )

            self._log.append_log(
                "✅ Todo actualizado. Listo para iniciar."
            )

            # Volver la insignia al estilo normal "Modpack v..."
            version = remote_version or getattr(self, "_current_version", "")
            if version:
                self.update_version_badge(version)

        elif state == self.S_BUSY:

            self._main_btn.setText("PROCESANDO...")
            self._main_btn.setEnabled(False)

            self._sec_btn.setEnabled(False)

            self._chk_spin.stop()

        elif state == self.S_ERROR:

            self._main_btn.setText("REINTENTAR")
            self._main_btn.setMode("install")
            self._main_btn.setEnabled(True)

            self._sec_btn.setEnabled(False)

            self._chk_spin.stop()

            self._set_st(
                "ERROR",
                T.ERROR
            )

            self._bar.setValue(0)
            self._pct_lbl.setText("")

    def _set_st(self, text, color):
        self._st_lbl.setText(text)
        self._st_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                                  f" color:{color}; letter-spacing:3px;")

    def set_done_ok(self):
        self._bar.setValue(100); self._pct_lbl.setText("100%")
        version = getattr(self, "_current_version", "")
        self.set_state(self.S_READY, version)

    def set_status_text(self, text): self._st_lbl.setText(text.upper())
    def on_progress(self, v): self._bar.setValue(v); self._pct_lbl.setText(f"{v}%")
    def append_log(self, text): self._log.append_log(text)

    def update_version_badge(self, version):
        self._ver_badge.setText(f"Modpack v{version}")
        self._ver_badge.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:10px; color:{T.ACCENT_HI};"
            f" background:{T.rgba(T.ACCENT,0.09)}; border:1px solid {T.rgba(T.ACCENT,0.22)};"
            " border-radius:4px; padding:3px 10px;")

    def _on_main(self):
        if self._state in (self.S_NONE, self.S_ERROR):
            self.request_action.emit("install")
        elif self._state == self.S_UPDATE:
            self.request_action.emit("update")
        elif self._state == self.S_READY:
            self.request_action.emit("play")    # ← JUGAR ahora SÍ abre Minecraft

    def _on_sec(self):
        if self._state == self.S_UPDATE:
            self.request_action.emit("play")
