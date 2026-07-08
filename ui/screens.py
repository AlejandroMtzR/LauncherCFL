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
from core import accounts
from core.game_launcher import MODPACK_FORGE_VERSION

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



class _HomeVersionLoader(QThread):
    loaded = Signal(list, list)

    def __init__(self, snapshots=False, old=False, parent=None):
        super().__init__(parent)
        self._snapshots = snapshots
        self._old = old

    def run(self):
        try:
            from core import game_launcher
            versions = game_launcher.list_versions(self._snapshots, self._old)
            forge_versions = game_launcher.list_installed_forge_versions()
            self.loaded.emit(versions, forge_versions)
        except Exception:
            self.loaded.emit([], [])


class CoverArt(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self._pix = QPixmap(image_path)
        self.setFixedSize(240, 138)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        p.setClipPath(path)

        if not self._pix.isNull():
            scaled = self._pix.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            p.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
        else:
            p.fillRect(self.rect(), QColor(T.CARD_HI))

        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor(0, 0, 0, 20))
        g.setColorAt(1, QColor(0, 0, 0, 150))
        p.fillRect(self.rect(), g)


#   MAIN SCREEN

class MainScreen(QWidget):
    request_action = Signal(str)   # "install" | "update" | "play"
    account_changed = Signal(object)

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
        self._account_mode = ""
        self._home_target = "modpack"
        self._home_snap = False
        self._home_old = False
        self._current_version = ""
        self._account = None
        self._settings = QSettings("CFL", "Launcher")
        self._ram_gb = int(self._settings.value("game/ram_gb", 6, int))
        self._syncing_combo = False
        self._pending_skin_path = ""
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
        self._nav_modpacks = NavItem("spark", "MODPACKS")
        self._nav_mods = NavItem("grid", "MODS")
        self._nav_cfg  = NavItem("gear", "AJUSTES")
        for b in [self._nav_home, self._nav_modpacks, self._nav_mods, self._nav_cfg]:
            sb.addWidget(b)
        sb.addStretch()

        footer = QLabel("© 2026 ChafaLand")
        footer.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px; color:{T.DIM};")
        footer.setContentsMargins(8, 0, 0, 0)
        sb.addWidget(footer)
        root.addWidget(sidebar)

        self._nav_home.clicked.connect(lambda: self._switch_page(0))
        self._nav_modpacks.clicked.connect(lambda: self._switch_page(1))
        self._nav_mods.clicked.connect(lambda: self._switch_page(2))
        self._nav_cfg.clicked.connect(lambda: self._switch_page(3))

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
        self._pages.addWidget(self._build_modpacks_page()) # 1
        self._mods_page = ModsPage()
        self._mods_page.open_image.connect(self._open_lightbox)
        self._pages.addWidget(self._mods_page)            # 2
        self._pages.addWidget(self._build_ajustes_page()) # 3
        cl.addWidget(self._pages)
        root.addWidget(content)

        # Visor (encima de todo)
        self._lightbox = Lightbox(self)

    # ── Página INICIO (hero + panel inferior) ─────────────────────
    def _build_home_page_legacy(self):
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
    def _build_home_page(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        ph = QVBoxLayout(page)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(0)

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hl = QVBoxLayout(body)
        hl.setContentsMargins(44, 16, 44, 12)
        hl.setSpacing(7)

        banner = HeroBanner(
            resource_path("assets/home_hero.png"),
            show_text=False
        )
        banner.setFixedHeight(165)
        hl.addWidget(banner)
        hl.addSpacing(8)

        eyebrow = QLabel("CFL LAUNCHER")
        eyebrow.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                              f" color:{T.ACCENT_HI}; letter-spacing:5px;")
        hl.addWidget(eyebrow)

        title = QLabel("¿Qué quieres jugar?")
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:28px; font-weight:900;"
                            f" color:{T.TEXT};")
        hl.addWidget(title)
        hl.addSpacing(4)

        self._home_notice = QLabel("")
        self._home_notice.setWordWrap(True)
        self._home_notice.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px;"
                                        f" color:{T.INFO}; background:transparent;")
        self._home_notice.hide()
        hl.addWidget(self._home_notice)

        self._home_modpack_card = QFrame()
        self._home_modpack_card.setCursor(Qt.PointingHandCursor)
        self._home_modpack_card.mousePressEvent = lambda e: self._select_home_modpack()
        mc = QHBoxLayout(self._home_modpack_card)
        mc.setContentsMargins(18, 14, 18, 14)
        mc.setSpacing(14)

        icon_box = QLabel("◆")
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setFixedSize(48, 48)
        icon_box.setStyleSheet(f"font-size:29px; color:{T.ACCENT};"
                               f" background:{T.rgba(T.ACCENT, 0.10)};"
                               f" border:1px solid {T.rgba(T.ACCENT, 0.45)};"
                               " border-radius:14px;")
        mc.addWidget(icon_box)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        name = QLabel("ChafaLand Modpack")
        name.setStyleSheet(f"font-family:'{T.FONT}'; font-size:17px; font-weight:900;"
                           f" color:{T.TEXT}; background:transparent;")
        meta = QLabel("Forge 1.20.1  ·  +340 mods")
        meta.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px;"
                           f" color:{T.TEXT2}; background:transparent;")
        txt.addWidget(name)
        txt.addWidget(meta)
        mc.addLayout(txt)
        mc.addStretch()

        self._home_badge = QLabel("RECOMENDADO")
        self._home_badge.setAlignment(Qt.AlignCenter)
        self._home_badge.setMinimumWidth(112)
        mc.addWidget(self._home_badge)
        hl.addWidget(self._home_modpack_card)
        hl.addSpacing(8)

        lab = QLabel("O juega otra versión (sin mods)")
        lab.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; font-weight:700;"
                          f" color:{T.TEXT2};")
        hl.addWidget(lab)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        chips.setAlignment(Qt.AlignLeft)
        releases = QLabel("Releases")
        releases.setStyleSheet(f"color:{T.MUTED}; font-size:11px; background:transparent;")
        self._home_chip_snap = self._make_home_chip("+ Snapshots", self._toggle_home_snap)
        self._home_chip_old = self._make_home_chip("+ Antiguas", self._toggle_home_old)
        chips.addWidget(releases)
        chips.addWidget(self._home_chip_snap)
        chips.addWidget(self._home_chip_old)
        chips.addStretch()
        hl.addLayout(chips)

        self._home_version_combo = QComboBox()
        self._home_version_combo.setFixedHeight(50)
        self._home_version_combo.setCursor(Qt.PointingHandCursor)
        self._home_version_combo.setStyleSheet(f"""
            QComboBox {{
                background:{T.CARD};
                border:1px solid {T.BORDER_HI};
                border-radius:8px;
                padding:8px 14px;
                color:{T.TEXT};
                font-family:'{T.FONT}';
                font-size:13px;
                font-weight:700;
            }}
            QComboBox:hover {{
                background:{T.CARD_HI};
                border-color:{T.rgba(T.ACCENT, 0.45)};
            }}
            QComboBox::drop-down {{
                width:34px;
                border:none;
            }}
            QComboBox QAbstractItemView {{
                background:{T.SURFACE};
                border:1px solid {T.BORDER_HI};
                selection-background-color:{T.rgba(T.ACCENT, 0.22)};
                selection-color:{T.TEXT};
                color:{T.TEXT2};
                outline:0;
                padding:6px;
            }}
        """)
        self._home_version_combo.currentIndexChanged.connect(self._select_home_combo)
        hl.addWidget(self._home_version_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setAlignment(Qt.AlignLeft)
        self._main_btn = PlayBtn()
        self._main_btn.setText("CARGANDO...")
        self._main_btn.setEnabled(False)
        self._main_btn.clicked.connect(self._on_home_play)
        self._sec_btn = SecBtn("...")
        self._sec_btn.hide()
        self._chk_spin = Spinner(size=20, color=T.ACCENT_HI)
        btn_row.addWidget(self._main_btn)
        btn_row.addWidget(self._sec_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(self._chk_spin)
        btn_row.addStretch()
        hl.addLayout(btn_row)
        self._reload_home_versions()

        bottom = QWidget()
        bottom.setFixedHeight(170)
        bottom.setStyleSheet(f"background:{T.rgba(T.SURFACE,0.70)};"
                             f" border-top:1px solid {T.BORDER};")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(52, 16, 52, 18)
        bl.setSpacing(8)
        sr = QHBoxLayout()
        self._st_lbl = QLabel("INICIANDO")
        self._st_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                                   f" color:{T.ACCENT_HI}; letter-spacing:3px;")
        self._pct_lbl = QLabel("")
        self._pct_lbl.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:9px; color:{T.MUTED};")
        sr.addWidget(self._st_lbl)
        sr.addStretch()
        sr.addWidget(self._pct_lbl)
        bl.addLayout(sr)
        self._bar = GlowBar(height=12)
        bl.addWidget(self._bar)
        bl.addSpacing(5)
        self._log = LogBox()
        bl.addWidget(self._log)

        ph.addWidget(body)
        ph.addWidget(bottom)
        return page

    def _make_home_chip(self, text, cb):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(cb)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {T.MUTED};
                border: 1px solid {T.BORDER_HI};
                border-radius: 12px;
                padding: 4px 12px;
                font-family:'{T.FONT}';
                font-size: 11px;
            }}
            QPushButton:checked {{
                background: {T.rgba(T.ACCENT,0.14)};
                color: {T.ACCENT_HI};
                border: 1px solid {T.rgba(T.ACCENT,0.4)};
            }}
        """)
        return b

    def _toggle_home_snap(self):
        self._home_snap = self._home_chip_snap.isChecked()
        self._reload_home_versions()

    def _toggle_home_old(self):
        self._home_old = self._home_chip_old.isChecked()
        self._reload_home_versions()

    def _reload_home_versions(self):
        self._syncing_combo = True
        self._home_version_combo.clear()
        self._home_version_combo.addItem("Cargando versiones...", None)
        self._home_version_combo.setEnabled(False)
        self._syncing_combo = False
        self._home_loader = _HomeVersionLoader(self._home_snap, self._home_old, self)
        self._home_loader.loaded.connect(self._on_home_versions)
        self._home_loader.start()

    def _on_home_versions(self, versions, forge_versions):
        self._syncing_combo = True
        self._home_version_combo.clear()
        self._home_version_combo.addItem(
            f"ChafaLand Modpack · Forge {MODPACK_FORGE_VERSION}",
            "modpack"
        )
        for forge_id in forge_versions:
            self._home_version_combo.addItem(f"Forge instalado · {forge_id}", ("installed", forge_id))
        for idx, version in enumerate(versions):
            prefix = "Ultima version" if idx == 0 else "Release"
            self._home_version_combo.addItem(f"{prefix} · {version}", ("vanilla", version))
        if self._home_version_combo.count() == 1:
            self._home_version_combo.addItem("No se pudieron cargar versiones vanilla", None)
        self._home_version_combo.setEnabled(True)
        self._set_combo_to_target()
        self._syncing_combo = False

    def _select_home_modpack(self):
        self._home_target = "modpack"
        self._set_combo_to_target()
        self._refresh_home_card_style()
        self._update_home_state()

    def _select_home_combo(self, _index):
        if self._syncing_combo:
            return
        data = self._home_version_combo.currentData()
        if data is None:
            return
        self._home_target = data
        self._refresh_home_card_style()
        self._update_home_state()

    def _set_combo_to_target(self):
        if not hasattr(self, "_home_version_combo"):
            return
        old = self._syncing_combo
        self._syncing_combo = True
        for i in range(self._home_version_combo.count()):
            if self._home_version_combo.itemData(i) == self._home_target:
                self._home_version_combo.setCurrentIndex(i)
                self._syncing_combo = old
                return
        if self._home_version_combo.count():
            self._home_version_combo.setCurrentIndex(0)
        self._syncing_combo = old

    def _refresh_home_card_style(self):
        on = self._home_target == "modpack"
        self._home_modpack_card.setStyleSheet(f"""
            QFrame {{
                background: {T.CARD_HI if on else T.CARD};
                border: 1.5px solid {T.ACCENT if on else T.BORDER};
                border-radius: 14px;
            }}
        """)

    def _badge_qss(self, color):
        return f"""
            QLabel {{
                font-family:'{T.FONT}';
                font-size:9px;
                font-weight:800;
                color:{color};
                background:{T.rgba(color, 0.10)};
                border:1px solid {T.rgba(color, 0.28)};
                border-radius:4px;
                padding:5px 10px;
            }}
        """

    def _home_modpack_label(self):
        if self._state == self.S_NONE:
            return "INSTALAR", T.INFO, "install"
        if self._state == self.S_UPDATE:
            return "ACTUALIZAR", T.INFO2, "update"
        if self._state == self.S_BUSY:
            return "PROCESANDO", T.INFO, "play"
        if self._state == self.S_ERROR:
            return "REINTENTAR", T.ERROR, "install"
        return "RECOMENDADO", T.ACCENT_HI, "play"

    def _update_home_state(self):
        if not hasattr(self, "_main_btn"):
            return

        badge, color, mode = self._home_modpack_label()
        self._home_badge.setText(badge)
        self._home_badge.setStyleSheet(self._badge_qss(color))
        if self._account_mode == "premium" and self._state == self.S_READY:
            self._home_notice.setText("Cuenta premium detectada: JUGAR abre el launcher oficial.")
            self._home_notice.show()
        else:
            self._home_notice.clear()
            self._home_notice.hide()
        self._sec_btn.hide()

        busy = self._state in (self.S_CHECKING, self.S_BUSY)
        if self._home_target == "modpack":
            if self._state == self.S_CHECKING:
                text = "VERIFICANDO..."
            elif self._state == self.S_BUSY:
                text = "PROCESANDO..."
            elif self._state == self.S_NONE:
                text = "INSTALAR"
            elif self._state == self.S_UPDATE:
                text = "ACTUALIZAR"
            elif self._state == self.S_ERROR:
                text = "REINTENTAR"
            else:
                text = "JUGAR"
            self._main_btn.setMode(mode)
            self._main_btn.setEnabled(not busy)
            self._main_btn.setText(text)
        else:
            self._main_btn.setMode("play")
            self._main_btn.setText("JUGAR")
            self._main_btn.setEnabled(not busy)

        if busy:
            self._chk_spin.start()
        else:
            self._chk_spin.stop()
        self._refresh_home_card_style()

    def home_target(self):
        return self._home_target

    def _on_home_play(self):
        self.request_action.emit("home_play")

    def _build_modpacks_page(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(44, 26, 44, 26)
        lay.setSpacing(16)

        title = QLabel("MIS MODPACKS")
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:26px; font-weight:900;"
                            f" color:{T.TEXT}; letter-spacing:2px;")
        lay.addWidget(title)

        sub = QLabel("Disponible para cuentas premium y no premium")
        sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};")
        lay.addWidget(sub)
        lay.addSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(18)
        row.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        card = QFrame()
        card.setFixedWidth(276)
        card.setStyleSheet(f"""
            QFrame {{
                background:{T.CARD};
                border:1px solid {T.BORDER};
                border-radius:8px;
            }}
        """)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(18, 18, 18, 18)
        cv.setSpacing(11)
        cv.addWidget(CoverArt(resource_path("assets/home_hero.png")), alignment=Qt.AlignCenter)

        self._modpack_card_badge = QLabel("VERIFICANDO")
        self._modpack_card_badge.setAlignment(Qt.AlignCenter)
        self._modpack_card_badge.setFixedWidth(116)
        cv.addWidget(self._modpack_card_badge, alignment=Qt.AlignLeft)

        name = QLabel("ChafaLand Modpack")
        name.setWordWrap(True)
        name.setStyleSheet(f"font-family:'{T.FONT}'; font-size:15px; font-weight:900;"
                           f" color:{T.TEXT}; background:transparent; border:none;")
        cv.addWidget(name)

        by = QLabel("Por ChafaLand")
        by.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; color:{T.TEXT2};"
                         " background:transparent; border:none;")
        cv.addWidget(by)

        meta = QLabel("Forge 1.20.1  ·  +340 mods")
        meta.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; color:{T.MUTED};"
                           " background:transparent; border:none;")
        cv.addWidget(meta)

        self._modpack_bar = GlowBar()
        cv.addWidget(self._modpack_bar)
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._modpack_status_lbl = QLabel("Verificando archivos")
        self._modpack_status_lbl.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:9px;"
                                               f" color:{T.MUTED}; background:transparent; border:none;")
        self._modpack_pct_lbl = QLabel("")
        self._modpack_pct_lbl.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:9px;"
                                            f" color:{T.MUTED}; background:transparent; border:none;")
        status_row.addWidget(self._modpack_status_lbl)
        status_row.addStretch()
        status_row.addWidget(self._modpack_pct_lbl)
        cv.addLayout(status_row)

        self._modpack_action_btn = PlayBtn()
        self._modpack_action_btn.clicked.connect(self._on_modpack_action)
        cv.addWidget(self._modpack_action_btn, alignment=Qt.AlignLeft)
        row.addWidget(card)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        self._update_modpack_page_state()
        return page

    def _update_modpack_page_state(self):
        if not hasattr(self, "_modpack_action_btn"):
            return

        if self._state == self.S_NONE:
            text, badge, color, mode, enabled = "INSTALAR", "NO INSTALADO", T.INFO, "install", True
            status = "Primera instalacion"
        elif self._state == self.S_UPDATE:
            text, badge, color, mode, enabled = "ACTUALIZAR", "UPDATE", T.INFO2, "update", True
            status = "Actualizacion disponible"
        elif self._state == self.S_READY:
            text, badge, color, mode, enabled = "JUGAR", "LISTO", T.ACCENT_HI, "play", True
            status = "Listo para jugar"
        elif self._state == self.S_BUSY:
            text, badge, color, mode, enabled = "PROCESANDO...", "PROCESANDO", T.INFO, "play", False
            status = "Procesando archivos"
        elif self._state == self.S_ERROR:
            text, badge, color, mode, enabled = "REINTENTAR", "ERROR", T.ERROR, "install", True
            status = "Error"
        else:
            text, badge, color, mode, enabled = "VERIFICANDO...", "VERIFICANDO", T.MUTED, "play", False
            status = "Verificando archivos"

        self._modpack_action_btn.setText(text)
        self._modpack_action_btn.setMode(mode)
        self._modpack_action_btn.setEnabled(enabled)
        self._modpack_card_badge.setText(badge)
        self._modpack_card_badge.setStyleSheet(self._badge_qss(color))
        self._modpack_status_lbl.setText(status)

    def _on_modpack_action(self):
        if self._state in (self.S_NONE, self.S_ERROR):
            self.request_action.emit("install")
        elif self._state == self.S_UPDATE:
            self.request_action.emit("update")
        elif self._state == self.S_READY:
            self.request_action.emit("play")

    def show_modpacks_page(self):
        self._switch_page(1)

    def set_account_mode(self, mode):
        self._account_mode = mode or ""
        self._update_home_state()

    def _build_ajustes_page_legacy(self):
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
    def _build_ajustes_page(self):
        page = QWidget(); page.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(page); lay.setContentsMargins(52, 22, 52, 22); lay.setSpacing(14)
        title = QLabel("AJUSTES")
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:26px; font-weight:900;"
                           f" color:{T.TEXT}; letter-spacing:2px;")
        lay.addWidget(title)
        sub = QLabel("Configuracion del launcher")
        sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};")
        lay.addWidget(sub); lay.addSpacing(6)

        ram_card = QFrame()
        ram_card.setStyleSheet(self._settings_card_qss())
        rv = QVBoxLayout(ram_card); rv.setContentsMargins(20, 18, 20, 18); rv.setSpacing(10)
        ram_title = QLabel("MEMORIA RAM")
        ram_title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
                                f" color:{T.TEXT}; background:transparent; border:none;")
        rv.addWidget(ram_title)
        ram_row = QHBoxLayout(); ram_row.setSpacing(12)
        ram_label = QLabel("RAM para Minecraft")
        ram_label.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.TEXT2};"
                                " background:transparent; border:none;")
        self._ram_spin = QSpinBox()
        self._ram_spin.setRange(2, 16)
        self._ram_spin.setSuffix(" GB")
        self._ram_spin.setValue(self._ram_gb)
        self._ram_spin.setFixedWidth(120)
        self._ram_spin.setStyleSheet(self._spin_qss())
        self._ram_spin.valueChanged.connect(self._on_ram_changed)
        ram_row.addWidget(ram_label)
        ram_row.addStretch()
        ram_row.addWidget(self._ram_spin)
        rv.addLayout(ram_row)
        lay.addWidget(ram_card)

        self._offline_card = QFrame()
        self._offline_card.setStyleSheet(self._settings_card_qss())
        ov = QVBoxLayout(self._offline_card); ov.setContentsMargins(20, 18, 20, 18); ov.setSpacing(12)
        offline_title = QLabel("PERFIL NO PREMIUM")
        offline_title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
                                    f" color:{T.TEXT}; background:transparent; border:none;")
        ov.addWidget(offline_title)

        profile_row = QHBoxLayout(); profile_row.setSpacing(18)
        self._settings_skin_preview = QLabel("?")
        self._settings_skin_preview.setAlignment(Qt.AlignCenter)
        self._settings_skin_preview.setFixedSize(86, 86)
        self._settings_skin_preview.setStyleSheet(f"background:{T.SURFACE}; border:1px solid {T.BORDER_HI};"
                                                  f" border-radius:10px; color:{T.MUTED};")
        profile_row.addWidget(self._settings_skin_preview)

        form = QVBoxLayout(); form.setSpacing(8)
        name_lab = QLabel("Nombre de jugador")
        name_lab.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; font-weight:700;"
                               f" color:{T.TEXT2}; background:transparent; border:none;")
        self._settings_name = QLineEdit()
        self._settings_name.setMaxLength(16)
        self._settings_name.setStyleSheet(self._input_qss())
        self._settings_uuid = QLabel("")
        self._settings_uuid.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:9px;"
                                          f" color:{T.MUTED}; background:transparent; border:none;")
        self._settings_skin_lbl = QLabel("Steve por defecto")
        self._settings_skin_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                                              f" color:{T.MUTED}; background:transparent; border:none;")
        form.addWidget(name_lab)
        form.addWidget(self._settings_name)
        form.addWidget(self._settings_uuid)
        form.addWidget(self._settings_skin_lbl)
        profile_row.addLayout(form, stretch=1)
        ov.addLayout(profile_row)

        btns = QHBoxLayout(); btns.setSpacing(10)
        self._skin_settings_btn = QPushButton("Cambiar skin")
        self._skin_settings_btn.setCursor(Qt.PointingHandCursor)
        self._skin_settings_btn.setStyleSheet(self._ghost_btn_qss())
        self._skin_settings_btn.clicked.connect(self._pick_settings_skin)
        self._save_profile_btn = QPushButton("Guardar perfil")
        self._save_profile_btn.setCursor(Qt.PointingHandCursor)
        self._save_profile_btn.setStyleSheet(self._primary_btn_qss())
        self._save_profile_btn.clicked.connect(self._save_offline_profile)
        btns.addWidget(self._skin_settings_btn)
        btns.addWidget(self._save_profile_btn)
        btns.addStretch()
        ov.addLayout(btns)
        lay.addWidget(self._offline_card)

        self._premium_hint = QLabel("La skin premium se gestiona desde el launcher oficial.")
        self._premium_hint.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};")
        lay.addWidget(self._premium_hint)
        lay.addStretch()
        self._refresh_account_settings()
        return page

    def _settings_card_qss(self):
        return f"QFrame {{ background:{T.rgba(T.CARD,0.65)}; border:1px solid {T.BORDER}; border-radius:10px; }}"

    def _input_qss(self):
        return f"""
            QLineEdit {{
                background:{T.SURFACE};
                border:1px solid {T.BORDER_HI};
                border-radius:8px;
                padding:9px 12px;
                color:{T.TEXT};
                font-family:'{T.FONT}';
                font-size:13px;
            }}
            QLineEdit:focus {{ border-color:{T.ACCENT}; }}
        """

    def _spin_qss(self):
        return f"""
            QSpinBox {{
                background:{T.SURFACE};
                border:1px solid {T.BORDER_HI};
                border-radius:8px;
                padding:8px 10px;
                color:{T.TEXT};
                font-family:'{T.FONT}';
                font-size:13px;
                font-weight:700;
            }}
        """

    def _primary_btn_qss(self):
        return f"""
            QPushButton {{
                background:{T.ACCENT};
                color:#1a1206;
                border:none;
                border-radius:8px;
                padding:10px 16px;
                font-family:'{T.FONT}';
                font-size:12px;
                font-weight:800;
            }}
            QPushButton:hover {{ background:{T.ACCENT_HI}; }}
        """

    def _ghost_btn_qss(self):
        return f"""
            QPushButton {{
                background:transparent;
                color:{T.TEXT2};
                border:1px solid {T.BORDER_HI};
                border-radius:8px;
                padding:10px 16px;
                font-family:'{T.FONT}';
                font-size:12px;
                font-weight:700;
            }}
            QPushButton:hover {{ background:{T.CARD_HI}; color:{T.TEXT}; }}
        """

    def _on_ram_changed(self, value):
        self._ram_gb = int(value)
        self._settings.setValue("game/ram_gb", self._ram_gb)

    def ram_gb(self):
        return max(2, min(16, int(self._ram_gb or 6)))

    def set_account(self, account):
        self._account = account
        self.set_account_mode(getattr(account, "mode", ""))
        self._refresh_account_settings()

    def _refresh_account_settings(self):
        if not hasattr(self, "_offline_card"):
            return
        acc = self._account
        is_offline = bool(acc and acc.mode == "offline")
        self._offline_card.setVisible(is_offline)
        self._premium_hint.setVisible(bool(acc and acc.mode == "premium"))
        if not is_offline:
            return
        self._settings_name.setText(acc.username)
        self._settings_uuid.setText(f"UUID offline: {acc.uuid}")
        self._pending_skin_path = ""
        self._set_settings_skin(acc.skin_path)

    def _set_settings_skin(self, path):
        if path and os.path.exists(path):
            img = QImage(path)
            if not img.isNull() and img.width() >= 64 and img.height() >= 32:
                face = img.copy(8, 8, 8, 8)
                hat = img.copy(40, 8, 8, 8)
                base = QImage(8, 8, QImage.Format_ARGB32)
                base.fill(Qt.transparent)
                p = QPainter(base)
                p.drawImage(0, 0, face)
                p.drawImage(0, 0, hat)
                p.end()
                px = QPixmap.fromImage(base).scaled(70, 70, Qt.KeepAspectRatio, Qt.FastTransformation)
                self._settings_skin_preview.setPixmap(px)
                self._settings_skin_lbl.setText(os.path.basename(path))
                return
        self._settings_skin_preview.setPixmap(QPixmap())
        self._settings_skin_preview.setText("?")
        self._settings_skin_lbl.setText("Steve por defecto")

    def _pick_settings_skin(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elige tu skin", "", "Skin de Minecraft (*.png)")
        if not path:
            return
        img = QImage(path)
        if img.isNull() or img.width() < 64 or img.height() < 32:
            QMessageBox.warning(self, "CFL Launcher", "PNG invalido. Usa una skin de 64x64 o 64x32.")
            return
        self._pending_skin_path = path
        self._set_settings_skin(path)

    def _save_offline_profile(self):
        acc = self._account
        if not acc or acc.mode != "offline":
            return
        name = self._settings_name.text().strip()
        if not accounts.is_valid_name(name):
            QMessageBox.warning(self, "CFL Launcher", "Usa 3-16 caracteres: letras, numeros o _")
            return
        if name != acc.username:
            ans = QMessageBox.question(
                self,
                "Cambiar nombre",
                "Cambiar el nombre puede separar tu progreso en servidores offline. Guardar de todos modos?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                self._settings_name.setText(acc.username)
                return
        skin_path = acc.skin_path
        if self._pending_skin_path:
            try:
                skin_path = accounts.save_skin(name, self._pending_skin_path)
            except Exception:
                skin_path = self._pending_skin_path
        updated = accounts.make_offline(name, skin_path=skin_path)
        accounts.save(updated)
        self._account = updated
        self.account_changed.emit(updated)
        self._refresh_account_settings()
        self.append_log("Perfil no premium guardado")

    def _open_lightbox(self, paths, idx):
        self._lightbox.open_at(paths, idx)

    # ── Cambio de página ──────────────────────────────────────────
    def _switch_page(self, idx):
        self._pages.setCurrentIndex(idx)
        self._nav_home.setActive(idx == 0)
        self._nav_modpacks.setActive(idx == 1)
        self._nav_mods.setActive(idx == 2)
        self._nav_cfg.setActive(idx == 3)
        name = {0: "INICIO", 1: "MODPACKS", 2: "MODS", 3: "AJUSTES"}[idx]
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

        self._update_home_state()
        self._update_modpack_page_state()

    def _set_st(self, text, color):
        self._st_lbl.setText(text)
        self._st_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                                  f" color:{color}; letter-spacing:3px;")

    def set_done_ok(self):
        self._bar.setValue(100); self._pct_lbl.setText("100%")
        version = getattr(self, "_current_version", "")
        self.set_state(self.S_READY, version)

    def set_status_text(self, text):
        self._st_lbl.setText(text.upper())
        if hasattr(self, "_modpack_status_lbl"):
            self._modpack_status_lbl.setText(text)

    def on_progress(self, v):
        self._bar.setValue(v)
        self._pct_lbl.setText(f"{v}%")
        if hasattr(self, "_modpack_bar"):
            self._modpack_bar.setValue(v)
            self._modpack_pct_lbl.setText(f"{v}%")
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
