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
from .components import (
    Spinner, GlowBar, LogBox, PlayBtn, SecBtn, WinBtn, NavItem,
    IconLabel, make_icon,
)
from .gallery import Lightbox
from .mods_page import ModsPage, HeroBanner
from .version_dialog import VersionDialog
from .version_list import VersionList
from core.utils import resource_path, max_game_ram_gb, total_ram_gb
from core.launcherUpdate import get_local_version as get_launcher_version
from core.updater import get_local_version as get_local_modpack_version
from core import accounts, checker, paths, game_launcher
from core.game_launcher import MODPACK_FORGE_VERSION
import config as cfg

try:
    import qtawesome as qta
except Exception:  # qtawesome opcional; si falla usamos texto
    qta = None

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "assets", "logo.ico")
SIDEBAR_W = 196

LAUNCHER_VERSION = get_launcher_version()


def _installed_modpack_version():
    """Versión del modpack guardada en disco ('' si no hay)."""
    try:
        return get_local_modpack_version() or ""
    except Exception:
        return ""


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
        self._spinner = Spinner(size=20, color=T.ACCENT, parent=self)
        row.addWidget(self._spinner)
        self._spinner.start()
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



class CoverArt(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 138)
        # Tamaño fijo: se escala UNA vez en lugar de en cada repintado.
        pix = QPixmap(image_path)
        self._pix = pix.scaled(self.size() * 2, Qt.KeepAspectRatioByExpanding,
                               Qt.SmoothTransformation) if not pix.isNull() else pix

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        p.setClipPath(path)

        if not self._pix.isNull():
            src = self._pix
            ratio = max(self.width() / src.width(), self.height() / src.height())
            sw, sh = self.width() / ratio, self.height() / ratio
            p.drawPixmap(QRectF(self.rect()), src,
                         QRectF((src.width() - sw) / 2, (src.height() - sh) / 2, sw, sh))
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
        self._current_version = _installed_modpack_version()
        self._account = None
        self._settings = QSettings("CFL", "Launcher")
        self._max_ram = max_game_ram_gb()
        self._ram_gb = max(2, min(self._max_ram, int(self._settings.value("game/ram_gb", 6, int))))
        self._game_running = False
        self._pending_skin_path = ""
        self._last_repair_backup = ""
        self._recovery_required = False
        self._health_cache = None          # (instante, dict) de checker.install_health
        self._overlay_wanted = False       # el usuario quiere ver el progreso
        self._busy_text = ""               # último estado de la tarea en curso
        self._checked_at = QDateTime.currentDateTime()
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── SIDEBAR ───────────────────────────────────────────────
        sidebar = QWidget(); sidebar.setFixedWidth(SIDEBAR_W)
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
        self._nav_modpacks = NavItem("cube", "MODPACKS")
        self._nav_mods = NavItem("puzzle", "MODS")
        self._nav_cfg  = NavItem("gear", "AJUSTES")
        for b in [self._nav_home, self._nav_modpacks, self._nav_mods, self._nav_cfg]:
            sb.addWidget(b)
        sb.addStretch()

        # ── Pill de estado (punto + textos) ───────────────────────
        self._sb_status = QFrame()
        self._sb_status.setObjectName("sbStatus")
        self._sb_status.setStyleSheet(
            f"QFrame#sbStatus {{ background:{T.rgba(T.OK,0.08)};"
            f" border:1px solid {T.rgba(T.OK,0.22)}; border-radius:10px; }}")
        ss = QHBoxLayout(self._sb_status)
        ss.setContentsMargins(11, 9, 11, 9); ss.setSpacing(9)
        self._sb_status_dot = QLabel("●")
        self._sb_status_dot.setStyleSheet(f"color:{T.OK}; font-size:11px; background:transparent; border:none;")
        ss.addWidget(self._sb_status_dot, alignment=Qt.AlignVCenter)
        st_col = QVBoxLayout(); st_col.setSpacing(0)
        self._sb_status_title = QLabel("Verificando…")
        self._sb_status_title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; font-weight:800;"
                                            f" color:{T.TEXT}; background:transparent; border:none;")
        self._sb_status_sub = QLabel("Un momento")
        self._sb_status_sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px;"
                                          f" color:{T.MUTED}; background:transparent; border:none;")
        st_col.addWidget(self._sb_status_title); st_col.addWidget(self._sb_status_sub)
        ss.addLayout(st_col); ss.addStretch()
        # Clic en la pastilla: ir a Inicio y ver el progreso/registro desde
        # cualquier página (el usuario puede navegar libre mientras instala).
        self._sb_status.setCursor(Qt.PointingHandCursor)
        self._sb_status.setToolTip("Ver progreso y registro")
        self._sb_status.mousePressEvent = lambda e: self._show_activity()
        sb.addWidget(self._sb_status)
        sb.addSpacing(12)

        # ── Redes sociales ────────────────────────────────────────
        social = QHBoxLayout(); social.setSpacing(8); social.setContentsMargins(4, 0, 4, 0)
        social.addWidget(self._make_social_btn("fa5b.discord", "Discord", getattr(cfg, "DISCORD_URL", "")))
        social.addWidget(self._make_social_btn("fa5s.globe",   "Sitio web", getattr(cfg, "WEB_URL", "")))
        social.addWidget(self._make_social_btn("fa5b.github",  "GitHub", getattr(cfg, "GITHUB_URL", "")))
        social.addStretch()
        sb.addLayout(social)
        sb.addSpacing(6)

        footer = QLabel("© 2026 ChafaLand")
        footer.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px; color:{T.DIM};")
        footer.setContentsMargins(4, 0, 0, 0)
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
        self._ver_badge = QLabel()
        # Alto fijo: sin él la etiqueta se estiraba a toda la barra (48 px)
        # y se veía como un recuadro naranja gigante.
        self._ver_badge.setFixedHeight(22)
        self._ver_badge.setAlignment(Qt.AlignCenter)
        self.update_version_badge(self._current_version)
        tb.addWidget(self._ver_badge, alignment=Qt.AlignVCenter); tb.addSpacing(10)
        sep = QFrame(); sep.setFrameShape(QFrame.VLine); sep.setFixedHeight(20)
        sep.setStyleSheet(f"color:{T.BORDER};")
        tb.addWidget(sep, alignment=Qt.AlignVCenter)
        self._min_btn   = WinBtn("─", hover_bg="#1b2230", hover_fg=T.TEXT)
        self._max_btn   = WinBtn("□", hover_bg="#1b2230", hover_fg=T.TEXT)
        self._close_btn = WinBtn("✕", hover_bg="#7f1d1d", hover_fg="#ffffff")
        self._min_btn.setToolTip("Minimizar")
        self._max_btn.setToolTip("Maximizar")
        self._close_btn.setToolTip("Cerrar")
        tb.addWidget(self._min_btn); tb.addWidget(self._max_btn); tb.addWidget(self._close_btn)
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

    # ── Botón de red social (barra lateral) ───────────────────────
    def _make_social_btn(self, icon_name, tooltip, url):
        b = QPushButton()
        b.setFixedSize(34, 34)
        b.setCursor(Qt.PointingHandCursor)
        has_url = bool(url)
        b.setToolTip(tooltip if has_url else f"{tooltip} — Próximamente")
        used_icon = False
        if qta is not None:
            try:
                b.setIcon(qta.icon(icon_name, color=T.MUTED, color_active=T.ACCENT_HI))
                b.setIconSize(QSize(16, 16))
                used_icon = True
            except Exception:
                used_icon = False
        if not used_icon:
            b.setText(tooltip[:1])
        b.setStyleSheet(f"""
            QPushButton {{
                background:{T.rgba(T.CARD_HI, 0.7)};
                border:1px solid {T.BORDER};
                border-radius:9px;
                color:{T.MUTED};
                font-family:'{T.FONT}'; font-size:13px; font-weight:800;
            }}
            QPushButton:hover {{
                border-color:{T.rgba(T.ACCENT, 0.5)};
                background:{T.CARD_HI};
                color:{T.TEXT};
            }}
            QPushButton:disabled {{ color:{T.DIM}; }}
        """)
        if has_url:
            b.clicked.connect(lambda: self._open_url(url))
        else:
            b.setEnabled(False)
        return b

    # ── Página INICIO (hero + tarjeta + versiones/estado) ─────────
    def _build_home_page(self):
        page = QWidget()
        page.setStyleSheet(f"background:{T.BG};")
        ph = QVBoxLayout(page)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(0)

        # El cuerpo va en un scroll: en ventanas bajas ya no se enciman la
        # tarjeta, el banner y los paneles (se desplaza en lugar de romperse).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(self._scroll_qss())

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        hl = QVBoxLayout(body)
        hl.setContentsMargins(26, 14, 26, 12)
        hl.setSpacing(12)

        # ── HERO con texto encima (alto adaptable, ver resizeEvent) ───
        self._home_banner = HeroBanner(resource_path("assets/home_banner.png"), show_text=False)
        self._home_banner.setFixedHeight(150)
        bl_ = self._home_banner.layout()
        bl_.setContentsMargins(30, 14, 30, 16)
        bl_.addStretch()
        hero_eyebrow = QLabel("BIENVENIDO")
        hero_eyebrow.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:800;"
                                   f" color:{T.ACCENT_HI}; letter-spacing:4px; background:transparent;")
        self._hero_title = QLabel("¿Qué quieres jugar hoy?")
        self._hero_title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:28px; font-weight:900;"
                                       " color:#ffffff; background:transparent;")
        self._hero_sub = QLabel("Elige el modpack o cualquier versión de Minecraft.")
        self._hero_sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px;"
                                     f" color:{T.TEXT2}; background:transparent;")
        bl_.addWidget(hero_eyebrow)
        bl_.addWidget(self._hero_title)
        bl_.addSpacing(2)
        bl_.addWidget(self._hero_sub)
        hl.addWidget(self._home_banner)

        # Aviso (solo se muestra en premium)
        self._home_notice = QLabel("")
        self._home_notice.setWordWrap(True)
        self._home_notice.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px;"
                                        f" color:{T.INFO}; background:{T.rgba(T.INFO,0.08)};"
                                        f" border:1px solid {T.rgba(T.INFO,0.20)};"
                                        " border-radius:8px; padding:8px 10px;")
        self._home_notice.hide()
        hl.addWidget(self._home_notice)

        hl.addWidget(self._build_target_card())

        # ── DOS COLUMNAS: VERSIONES + ESTADO ──────────────────────
        columns = QHBoxLayout()
        columns.setSpacing(14)
        columns.addWidget(self._build_releases_panel(), 3)
        columns.addWidget(self._build_news_panel(), 2)
        hl.addLayout(columns, 1)

        scroll.setWidget(body)
        ph.addWidget(scroll, 1)

        # ── BARRA INFERIOR DE INFO ────────────────────────────────
        ph.addWidget(self._build_info_bar())

        # ── OVERLAY DE PROGRESO (oculto; aparece al instalar) ─────
        self._build_progress_overlay()

        # Auxiliar que otros métodos esperan que exista
        self._sec_btn = SecBtn("...", page)
        self._sec_btn.hide()
        return page

    def _build_target_card(self):
        """Tarjeta del destino elegido: modpack o la versión seleccionada."""
        self._home_modpack_card = QFrame()
        self._home_modpack_card.setObjectName("homeModpackCard")
        self._home_modpack_card.setCursor(Qt.PointingHandCursor)
        self._home_modpack_card.setToolTip("Seleccionar el modpack")
        self._home_modpack_card.mousePressEvent = lambda e: self._select_home_modpack()
        card_v = QVBoxLayout(self._home_modpack_card)
        card_v.setContentsMargins(18, 15, 18, 14)
        card_v.setSpacing(12)

        mc = QHBoxLayout()
        mc.setSpacing(16)

        self._home_icon_box = QLabel("CFL")
        self._home_icon_box.setAlignment(Qt.AlignCenter)
        self._home_icon_box.setFixedSize(74, 74)
        self._home_icon_box.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:17px; font-weight:900; color:{T.ACCENT};"
            f" background:{T.rgba(T.ACCENT, 0.10)}; border:1px solid {T.rgba(T.ACCENT, 0.70)};"
            " border-radius:10px;")
        px = QPixmap(get_logo(self._resource_fn))
        if not px.isNull():
            self._home_icon_box.setPixmap(px.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        mc.addWidget(self._home_icon_box, alignment=Qt.AlignVCenter)

        txt = QVBoxLayout()
        txt.setSpacing(5)
        title_line = QHBoxLayout()
        title_line.setSpacing(10)
        self._home_title_lbl = QLabel("ChafaLand Modpack")
        self._home_title_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:22px; font-weight:900;"
                                           f" color:{T.TEXT}; background:transparent;")
        self._home_badge = QLabel("ACTUAL")
        self._home_badge.setAlignment(Qt.AlignCenter)
        self._home_badge.setMinimumWidth(72)
        title_line.addWidget(self._home_title_lbl)
        title_line.addWidget(self._home_badge, alignment=Qt.AlignVCenter)
        # Spinner de "verificando/procesando": va DENTRO del layout (con padre),
        # si no, al hacer .show() se abre como ventana flotante aparte.
        self._chk_spin = Spinner(size=18, color=T.ACCENT_HI, parent=self._home_modpack_card)
        title_line.addWidget(self._chk_spin, alignment=Qt.AlignVCenter)
        title_line.addStretch()

        self._home_meta_line = QWidget()
        self._home_meta_line.setStyleSheet("background:transparent;")
        meta = QHBoxLayout(self._home_meta_line)
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(7)
        self._home_meta_forge_icon = IconLabel("anvil", 15, T.MUTED)
        self._home_meta_forge_text = self._make_meta_text("Forge 1.20.1")
        self._home_meta_mods_icon = IconLabel("puzzle", 15, T.MUTED)
        self._home_meta_mods_text = self._make_meta_text("+340 mods")
        self._home_meta_ready_icon = IconLabel("check-circle", 15, T.OK)
        self._home_meta_ready_text = self._make_meta_text("Listo para jugar")
        for icon, label in (
            (self._home_meta_forge_icon, self._home_meta_forge_text),
            (self._home_meta_mods_icon, self._home_meta_mods_text),
            (self._home_meta_ready_icon, self._home_meta_ready_text),
        ):
            meta.addWidget(icon, alignment=Qt.AlignVCenter)
            meta.addWidget(label, alignment=Qt.AlignVCenter)
            if label is not self._home_meta_ready_text:
                dot = QLabel("·")
                dot.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};"
                                  " background:transparent;")
                meta.addWidget(dot, alignment=Qt.AlignVCenter)
        meta.addStretch()
        self._home_action_hint = QLabel("")
        self._home_action_hint.setWordWrap(True)
        self._home_action_hint.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px;"
                                             f" color:{T.MUTED}; background:transparent;")
        txt.addLayout(title_line)
        txt.addWidget(self._home_meta_line)
        txt.addWidget(self._home_action_hint)
        mc.addLayout(txt, 1)

        play_wrap = QHBoxLayout()
        play_wrap.setSpacing(0)
        self._main_btn = PlayBtn()
        self._main_btn.setRoundSide("left")   # split-button: solo izquierda redondeada
        self._main_btn.setText("CARGANDO...")
        self._main_btn.setEnabled(False)
        self._main_btn.clicked.connect(self._on_home_play)
        self._versions_toggle = QPushButton()
        self._versions_toggle.setCursor(Qt.PointingHandCursor)
        self._versions_toggle.setToolTip("Elegir otra versión")
        self._versions_toggle.setFixedSize(46, 52)
        self._versions_toggle.setIcon(make_icon("chevron-down", 16, "#ffffff"))
        self._versions_toggle.setIconSize(QSize(16, 16))
        self._versions_toggle.setStyleSheet(self._split_arrow_qss())
        self._versions_toggle.clicked.connect(self._open_all_versions)
        play_wrap.addWidget(self._main_btn)
        play_wrap.addWidget(self._versions_toggle)
        mc.addLayout(play_wrap)
        card_v.addLayout(mc)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._home_stat_profile = self._make_home_stat("layers", "PERFIL", "Modpack")
        self._home_stat_version = self._make_home_stat("anvil", "VERSIÓN", "Forge 1.20.1")
        self._home_stat_mods = self._make_home_stat("puzzle", "MODS INSTALADOS", "+340")
        self._home_stat_session = self._make_home_stat("clock", "ÚLTIMA SESIÓN", "Nunca")
        for stat in (
            self._home_stat_profile,
            self._home_stat_version,
            self._home_stat_mods,
            self._home_stat_session,
        ):
            stats_row.addWidget(stat, 1)
        card_v.addLayout(stats_row)
        return self._home_modpack_card

    def _panel_title(self, text):
        title = QLabel(text)
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:900;"
                            f" color:{T.ACCENT_HI}; letter-spacing:2px; background:transparent; border:none;")
        return title

    def _link_btn(self, text, cb):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; color:{T.MUTED};
                           font-family:'{T.FONT}'; font-size:11px; font-weight:700; padding:2px 4px; }}
            QPushButton:hover {{ color:{T.ACCENT_HI}; }}
        """)
        b.clicked.connect(cb)
        return b

    # ── Panel VERSIONES ───────────────────────────────────────────
    def _build_releases_panel(self):
        panel = QFrame()
        panel.setObjectName("homePanel")
        panel.setStyleSheet(self._home_panel_qss())
        panel.setMinimumHeight(250)
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 12, 14, 12)
        v.setSpacing(8)

        head = QHBoxLayout()
        head.addWidget(self._panel_title("VERSIONES"))
        head.addStretch()
        head.addWidget(self._link_btn("Ver en grande  ›", self._open_all_versions))
        v.addLayout(head)

        self._version_list = VersionList(panel)
        self._version_list.target_changed.connect(self._set_home_target)
        v.addWidget(self._version_list, 1)

        note = QLabel("Las versiones sin el modpack juegan en su propia carpeta: "
                      "no tocan tus mods ni tus mundos del modpack.")
        note.setWordWrap(True)
        note.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; color:{T.DIM};"
                           " background:transparent; border:none;")
        v.addWidget(note)
        return panel

    def _open_all_versions(self):
        try:
            dlg = VersionDialog(self.window(), current=self._home_target,
                                modpack_badge=self._modpack_list_badge())
            if dlg.exec():
                self._set_home_target(dlg.selected)
        except Exception as ex:
            self.append_log(f"⚠️ No se pudo abrir el selector de versiones: {ex}")

    # ── Panel ESTADO / NOVEDADES ──────────────────────────────────
    def _build_news_panel(self):
        panel = QFrame()
        panel.setObjectName("homePanel")
        panel.setStyleSheet(self._home_panel_qss())
        panel.setMinimumHeight(250)
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 12, 14, 12)
        v.setSpacing(6)

        head = QHBoxLayout()
        head.addWidget(self._panel_title("ESTADO"))
        head.addStretch()
        github = getattr(cfg, "GITHUB_URL", "")
        if github:
            head.addWidget(self._link_btn("Novedades  ›",
                                          lambda: self._open_url(github + "/releases")))
        v.addLayout(head)

        holder = QWidget()
        holder.setStyleSheet("background:transparent;")
        self._news_lay = QVBoxLayout(holder)
        self._news_lay.setContentsMargins(0, 2, 0, 0)
        self._news_lay.setSpacing(4)
        self._news_lay.setAlignment(Qt.AlignTop)
        v.addWidget(holder, 1)

        self._refresh_news()
        return panel

    def _make_news_item(self, icon_kind, color, title, sub):
        row = QFrame()
        row.setStyleSheet("QFrame { background:transparent; border:none; }")
        row.setMinimumHeight(48)
        h = QHBoxLayout(row)
        h.setContentsMargins(2, 4, 2, 4)
        h.setSpacing(12)
        h.addWidget(IconLabel(icon_kind, 24, color), alignment=Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; font-weight:700;"
                        f" color:{T.TEXT}; background:transparent; border:none;")
        s = QLabel(sub)
        s.setWordWrap(True)
        s.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                        f" color:{T.MUTED}; background:transparent; border:none;")
        col.addWidget(t)
        col.addWidget(s)
        h.addLayout(col, 1)
        return row

    def _refresh_news(self):
        if not hasattr(self, "_news_lay"):
            return
        while self._news_lay.count():
            it = self._news_lay.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        health_text, health_color = self._modpack_health_status()
        ok = health_color == T.OK
        mods_title = {
            self.S_NONE: "Modpack sin instalar",
            self.S_UPDATE: "Actualización disponible",
            self.S_BUSY: "Procesando archivos…",
            self.S_ERROR: "El último proceso falló",
            self.S_CHECKING: "Verificando…",
        }.get(self._state, "Todos tus mods están instalados" if ok else health_text)
        checked = self._checked_at.toString("HH:mm")

        forge_installed = os.path.isdir(os.path.join(
            paths.get_minecraft_dir(), "versions", game_launcher.modpack_version_id()))
        items = [
            ("check-circle" if ok else "warning", health_color, mods_title,
             f"Última verificación: hoy a las {checked}"),
            ("anvil", T.ACCENT_HI, f"Forge {self._forge_short()}",
             "Instalado" if forge_installed else "Se instala automáticamente al jugar"),
            ("download", T.INFO, f"CFL Launcher v{LAUNCHER_VERSION}",
             "Se actualiza solo al abrirlo"),
        ]
        for icon_kind, color, t, s in items:
            self._news_lay.addWidget(self._make_news_item(icon_kind, color, t, s))

    # ── Barra inferior de info (RAM / Java + utilidades) ──────────
    def _build_info_bar(self):
        bar = QWidget()
        bar.setFixedHeight(46)
        bar.setStyleSheet(f"background:{T.rgba(T.SURFACE,0.75)}; border-top:1px solid {T.BORDER};")
        l = QHBoxLayout(bar)
        l.setContentsMargins(26, 0, 18, 0)
        l.setSpacing(12)

        ram_item, self._info_ram = self._make_info_item("monitor", self._ram_text())
        l.addWidget(ram_item)
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(16)
        sep.setStyleSheet(f"color:{T.BORDER};")
        l.addWidget(sep)
        java_item, self._info_java = self._make_info_item("java", "Java:  …")
        l.addWidget(java_item)
        l.addStretch()

        self._open_folder_btn = QPushButton("Carpeta del modpack")
        self._open_folder_btn.setCursor(Qt.PointingHandCursor)
        self._open_folder_btn.setIcon(make_icon("folder", 16, T.TEXT2))
        self._open_folder_btn.setIconSize(QSize(16, 16))
        self._open_folder_btn.setStyleSheet(self._utility_btn_qss())
        self._open_folder_btn.clicked.connect(self._open_modpack_folder)
        java_btn = QPushButton("Memoria y Java")
        java_btn.setCursor(Qt.PointingHandCursor)
        java_btn.setIcon(make_icon("java", 16, T.TEXT2))
        java_btn.setIconSize(QSize(16, 16))
        java_btn.setStyleSheet(self._utility_btn_qss())
        java_btn.clicked.connect(self._open_java_options)
        more_btn = QPushButton()
        more_btn.setCursor(Qt.PointingHandCursor)
        more_btn.setToolTip("Más opciones")
        more_btn.setFixedWidth(44)
        more_btn.setIcon(make_icon("dots", 18, T.TEXT2))
        more_btn.setIconSize(QSize(18, 18))
        more_btn.setStyleSheet(self._utility_btn_qss())
        more_btn.clicked.connect(self._more_menu)
        l.addWidget(self._open_folder_btn)
        l.addWidget(java_btn)
        l.addWidget(more_btn)
        return bar

    def _make_info_item(self, icon_kind, text):
        item = QWidget()
        item.setStyleSheet("background:transparent; border:none;")
        h = QHBoxLayout(item)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(IconLabel(icon_kind, 17, T.MUTED), alignment=Qt.AlignVCenter)
        label = QLabel(text)
        label.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; color:{T.TEXT2};"
                            " background:transparent; border:none;")
        h.addWidget(label, alignment=Qt.AlignVCenter)
        return item, label

    def _refresh_java_label(self):
        # Java de Mojang que usará el destino (el del sistema no se usa), leído
        # del disco sin lanzar procesos: antes "java -version" congelaba la UI.
        if not hasattr(self, "_info_java"):
            return
        try:
            label = game_launcher.java_label(self._home_target)
        except Exception:
            label = "automático"
        self._info_java.setText(f"Java:  {label}")

    def _more_menu(self):
        m = QMenu(self)
        m.setStyleSheet(f"""
            QMenu {{
                background:{T.SURFACE}; color:{T.TEXT2};
                border:1px solid {T.BORDER_HI}; border-radius:8px; padding:6px;
                font-family:'{T.FONT}'; font-size:12px;
            }}
            QMenu::item {{ padding:7px 16px; border-radius:6px; }}
            QMenu::item:selected {{ background:{T.rgba(T.ACCENT,0.18)}; color:{T.TEXT}; }}
            QMenu::item:disabled {{ color:{T.DIM}; }}
        """)
        a_folder = m.addAction("Abrir carpeta del modpack (.minecraft)")
        a_instances = m.addAction("Abrir carpeta de versiones independientes")
        a_log = m.addAction("Ver progreso y registro")
        m.addSeparator()
        a_recheck = m.addAction("Volver a verificar el modpack")
        a_recheck.setEnabled(self._state not in (self.S_BUSY, self.S_CHECKING))
        a_reload = m.addAction("Recargar lista de versiones")
        m.addSeparator()
        a_github = m.addAction("GitHub del launcher")
        a_folder.triggered.connect(lambda: self._open_folder(paths.get_minecraft_dir()))
        a_instances.triggered.connect(lambda: self._open_folder(paths.INSTANCES_DIR))
        a_log.triggered.connect(self._show_activity)
        a_recheck.triggered.connect(lambda: self.request_action.emit("recheck"))
        a_reload.triggered.connect(self._version_list.reload)
        a_github.triggered.connect(lambda: self._open_url(getattr(cfg, "GITHUB_URL", "")))
        m.exec(QCursor.pos())

    def _ram_text(self):
        return f"RAM:  {self._ram_gb} GB"

    def _open_java_options(self):
        self._switch_page(3)

    def _open_url(self, url):
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _open_folder(self, folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _scroll_qss(self):
        return f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
            QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
            QScrollBar::handle:vertical {{
                background:{T.BORDER_HI}; border-radius:4px; min-height:24px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height:0; }}
        """

    def _show_activity(self):
        """Ir a Inicio y mostrar el progreso/registro."""
        self._switch_page(0)
        self._overlay_wanted = True
        self._show_progress_overlay()

    # ── Destino seleccionado (modpack o versión suelta) ───────────
    def _set_home_target(self, target):
        if target is None:
            return
        self._home_target = target
        if hasattr(self, "_version_list"):
            self._version_list.set_target(target)
        self._update_home_state()

    def _select_home_modpack(self):
        self._set_home_target("modpack")

    def _modpack_list_badge(self):
        """Insignia de la fila 'ChafaLand Modpack' según el estado."""
        if getattr(self, "_recovery_required", False):
            return "RECUPERACIÓN", T.ERROR
        return {
            self.S_NONE: ("NO INSTALADO", T.INFO),
            self.S_UPDATE: ("ACTUALIZAR", T.WARN),
            self.S_ERROR: ("ERROR", T.ERROR),
            self.S_BUSY: ("PROCESANDO", T.INFO),
            self.S_CHECKING: ("VERIFICANDO", T.MUTED),
        }.get(self._state, ("ACTUAL", T.OK))

    # ── Overlay de progreso (log + barra), oculto por defecto ─────
    def _build_progress_overlay(self):
        ov = QFrame(self)
        ov.setObjectName("progressOverlay")
        ov.setStyleSheet(f"""
            QFrame#progressOverlay {{
                background:{T.rgba(T.SURFACE, 0.98)};
                border-top:2px solid {T.rgba(T.ACCENT, 0.55)};
            }}
        """)
        lay = QVBoxLayout(ov)
        lay.setContentsMargins(28, 13, 28, 16)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self._st_lbl = QLabel("INICIANDO")
        self._st_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                                   f" color:{T.ACCENT_HI}; letter-spacing:3px;")
        self._pct_lbl = QLabel("")
        self._pct_lbl.setStyleSheet(f"font-family:'{T.FONT_MONO}'; font-size:9px; color:{T.MUTED};")
        close = QPushButton("✕")
        close.setCursor(Qt.PointingHandCursor)
        close.setFixedSize(24, 24)
        close.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{T.MUTED}; border:none;
                           font-size:13px; font-weight:800; border-radius:6px; }}
            QPushButton:hover {{ background:{T.rgba('#ffffff',0.08)}; color:{T.TEXT}; }}
        """)
        close.clicked.connect(self._hide_progress_overlay)
        head.addWidget(self._st_lbl)
        head.addStretch()
        head.addWidget(self._pct_lbl)
        head.addSpacing(8)
        head.addWidget(close)
        lay.addLayout(head)

        self._bar = GlowBar(height=12)
        lay.addWidget(self._bar)
        lay.addSpacing(4)
        self._log = LogBox()
        lay.addWidget(self._log)

        ov.hide()
        self._progress_overlay = ov

    def _position_progress_overlay(self):
        if not hasattr(self, "_progress_overlay"):
            return
        W, H = self.width(), self.height()
        ov_h = max(150, min(232, H - 130))
        self._progress_overlay.setGeometry(SIDEBAR_W, H - ov_h, max(1, W - SIDEBAR_W), ov_h)

    def _show_progress_overlay(self):
        # Solo sobre Inicio: en Mods/Ajustes tapaba botones y no dejaba usar
        # la página. Allí el progreso se ve en la pastilla de la barra lateral.
        if not hasattr(self, "_progress_overlay") or not self._overlay_wanted:
            return
        if self._pages.currentIndex() != 0:
            self._progress_overlay.hide()
            return
        self._position_progress_overlay()
        self._progress_overlay.show()
        self._progress_overlay.raise_()

    def _hide_progress_overlay(self):
        self._overlay_wanted = False
        if hasattr(self, "_progress_overlay"):
            self._progress_overlay.hide()

    # ── Pill de estado de la barra lateral ────────────────────────
    def _sidebar_status_update(self):
        if not hasattr(self, "_sb_status_title"):
            return
        st = self._state
        if getattr(self, "_recovery_required", False):
            color, title, sub = T.ERROR, "Recuperación", "Revisa el respaldo"
        elif st == self.S_CHECKING:
            color, title, sub = T.ACCENT_HI, "Verificando…", "Un momento"
        elif st == self.S_BUSY:
            pct = self._bar._val if hasattr(self, "_bar") else 0
            color, title, sub = T.INFO, f"Procesando… {pct}%", self._busy_text or "Ver progreso"
        elif st == self.S_NONE:
            color, title, sub = T.INFO, "Sin instalar", "Pulsa Instalar"
        elif st == self.S_UPDATE:
            color, title, sub = T.WARN, "Actualización lista", "Se recomienda actualizar"
        elif st == self.S_ERROR:
            color, title, sub = T.ERROR, "Error", "Revisa el registro"
        else:
            ht, hc = self._modpack_health_status()
            if hc == T.WARN:
                color, title, sub = T.WARN, "Falta actualizar", ht
            else:
                color, title, sub = T.OK, "Todo actualizado", "Listo para jugar"
        self._sb_status.setStyleSheet(
            f"QFrame#sbStatus {{ background:{T.rgba(color,0.08)};"
            f" border:1px solid {T.rgba(color,0.22)}; border-radius:10px; }}")
        self._sb_status_dot.setStyleSheet(f"color:{color}; font-size:11px; background:transparent; border:none;")
        self._sb_status_title.setText(title)
        fm = self._sb_status_sub.fontMetrics()
        self._sb_status_sub.setText(fm.elidedText(sub, Qt.ElideRight, 128))
        self._sb_status_sub.setToolTip(sub)


    def _home_panel_qss(self):
        return f"""
            QFrame#homePanel {{
                background:{T.rgba(T.CARD, 0.66)};
                border:1px solid {T.BORDER};
                border-radius:8px;
            }}
        """

    def _make_meta_text(self, text):
        label = QLabel(text)
        label.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px;"
                            f" color:{T.TEXT2}; background:transparent;")
        return label

    def _make_home_stat(self, icon_kind, label, value):
        box = QFrame()
        box.setObjectName("homeStat")
        box.setStyleSheet(f"""
            QFrame#homeStat {{
                background:{T.rgba(T.SURFACE, 0.72)};
                border:1px solid {T.BORDER};
                border-radius:8px;
            }}
        """)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)
        lay.addWidget(IconLabel(icon_kind, 19, T.MUTED), alignment=Qt.AlignVCenter)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        top = QLabel(label)
        top.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px; font-weight:900;"
                          f" color:{T.MUTED}; background:transparent; border:none;")
        val = QLabel(value)
        val.setObjectName("value")
        val.setWordWrap(True)
        val.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; font-weight:700;"
                          f" color:{T.TEXT}; background:transparent; border:none;")
        text_col.addWidget(top)
        text_col.addWidget(val)
        lay.addLayout(text_col, 1)
        return box

    def _split_arrow_qss(self):
        # Mismo gradiente vertical que PlayBtn (#f97316 → #ea580c) para que
        # botón y flecha se vean como UNA sola pieza.
        return f"""
            QPushButton {{
                background:qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #f97316, stop:1 #ea580c);
                color:#ffffff;
                border:none;
                border-left:1px solid {T.rgba("#ffffff", 0.22)};
                border-top-right-radius:8px;
                border-bottom-right-radius:8px;
                font-family:'{T.FONT}';
                font-size:13px;
                font-weight:900;
            }}
            QPushButton:hover {{
                background:qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #fb923c, stop:1 #f97316);
            }}
            QPushButton:pressed {{
                background:qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #ea580c, stop:1 #c2410c);
            }}
        """

    def _utility_btn_qss(self):
        return f"""
            QPushButton {{
                background:{T.rgba(T.CARD_HI, 0.86)};
                color:{T.TEXT2};
                border:1px solid {T.BORDER_HI};
                border-radius:8px;
                padding:9px 16px;
                font-family:'{T.FONT}';
                font-size:12px;
                font-weight:700;
            }}
            QPushButton:hover {{
                color:{T.TEXT};
                border-color:{T.rgba(T.ACCENT, 0.45)};
                background:{T.rgba(T.CARD_HI, 1.0)};
            }}
        """

    def _set_metric_value(self, box, value):
        if not box:
            return
        label = box.findChild(QLabel, "value")
        if label:
            label.setText(str(value))

    def _forge_short(self):
        return MODPACK_FORGE_VERSION.replace("1.20.1-", "")

    def _modpack_version_label(self):
        version = getattr(self, "_current_version", "")
        return f"Modpack v{version}" if version else "Modpack"

    def _target_info(self):
        target = self._home_target
        if target == "modpack":
            return {
                "title": "ChafaLand Modpack",
                "profile": self._modpack_version_label(),
                "version": "Forge 1.20.1",
                "mods": self._installed_mod_count_label(),
                "forge": self._forge_short(),
            }
        if isinstance(target, tuple) and len(target) == 2:
            kind, version = target
            if kind == "installed":
                return {
                    "title": f"Forge {version.split('-forge-', 1)[-1]}",
                    "profile": "Forge (sin el pack)",
                    "version": f"Minecraft {version.split('-forge-', 1)[0]}",
                    "mods": "Carpeta propia",
                    "forge": version.split("-forge-", 1)[-1] if "-forge-" in version else version,
                }
            vtype = game_launcher.version_type(version)
            profile = {"snapshot": "Snapshot"}.get(vtype, "Antigua" if vtype.startswith("old") else "Vanilla")
            return {
                "title": f"Minecraft {version}",
                "profile": profile,
                "version": version,
                "mods": "Sin mods",
                "forge": "No aplica",
            }
        return {
            "title": "Versión no disponible",
            "profile": "Sin selección",
            "version": "-",
            "mods": "-",
            "forge": "-",
        }

    def _health(self):
        """
        checker.install_health() cacheado unos segundos: la UI lo consultaba
        5-6 veces por cada cambio de estado (cada vez listando la carpeta mods).
        """
        now = QDateTime.currentMSecsSinceEpoch()
        if self._health_cache and now - self._health_cache[0] < 3000:
            return self._health_cache[1]
        try:
            h = checker.install_health()
        except Exception:
            h = None
        self._health_cache = (now, h)
        return h

    def _invalidate_health(self):
        self._health_cache = None

    def _installed_mod_count_label(self):
        h = self._health()
        count = h["have_count"] if h else 0
        return str(count) if count else "+340"

    def _modpack_health_status(self):
        if self._state == self.S_NONE:
            return "Sin instalar", T.INFO
        if self._state == self.S_UPDATE:
            return "Falta actualizar", T.WARN
        if self._state == self.S_BUSY:
            return "Procesando archivos", T.INFO
        if self._state == self.S_ERROR:
            return "Requiere atención", T.ERROR
        if self._state == self.S_CHECKING:
            return "Verificando…", T.MUTED
        h = self._health()
        if h and h["want_count"] and h["missing_count"]:
            return f"Faltan {h['missing_count']} mods", T.WARN
        return "Mods actualizados", T.OK

    def _last_session_text(self):
        raw = self._settings.value("game/last_session", "", str)
        if not raw:
            return "Nunca"
        dt = QDateTime.fromString(raw, Qt.ISODate)
        if not dt.isValid():
            return "Nunca"
        secs = max(0, dt.secsTo(QDateTime.currentDateTimeUtc()))
        if secs < 60:
            return "Hace un momento"
        mins = secs // 60
        if mins < 60:
            return f"Hace {mins} min"
        hours = mins // 60
        if hours < 24:
            return f"Hace {hours} h"
        days = hours // 24
        return "Hace 1 día" if days == 1 else f"Hace {days} días"

    def mark_session_started(self, target="modpack"):
        self._settings.setValue("game/last_session", QDateTime.currentDateTimeUtc().toString(Qt.ISODate))
        self._settings.setValue("game/last_target", str(target))
        self._settings.sync()
        self._refresh_home_metrics()

    def _open_modpack_folder(self):
        # Abre la carpeta de juego del destino elegido (modpack o versión).
        try:
            folder = game_launcher.game_dir_for(self._home_target)
        except Exception:
            folder = paths.get_minecraft_dir()
        self._open_folder(folder)

    def _refresh_home_metrics(self):
        info = self._target_info()
        if hasattr(self, "_home_title_lbl"):
            self._home_title_lbl.setText(info["title"])
        # Stats de la tarjeta (visibles)
        for attr, val in (
            ("_home_stat_profile", info["profile"]),
            ("_home_stat_version", info["version"]),
            ("_home_stat_mods", info["mods"]),
            ("_home_stat_session", self._last_session_text()),
        ):
            if hasattr(self, attr):
                self._set_metric_value(getattr(self, attr), val)
        if hasattr(self, "_info_ram"):
            self._info_ram.setText(self._ram_text())

    def _refresh_home_card_style(self):
        on = self._home_target == "modpack"
        style = (on, self._home_target)
        if getattr(self, "_card_style_key", None) == style:
            return
        self._card_style_key = style
        accent = T.ACCENT if on else T.INFO
        self._home_modpack_card.setStyleSheet(f"""
            QFrame#homeModpackCard {{
                background: {T.rgba(T.CARD_HI, 0.92)};
                border: 1px solid {T.rgba(accent, 0.70)};
                border-radius: 8px;
            }}
        """)
        # Ícono: logo del pack, o un bloque para versiones sueltas.
        if hasattr(self, "_home_icon_box"):
            if on:
                px = QPixmap(get_logo(self._resource_fn))
                if not px.isNull():
                    self._home_icon_box.setPixmap(
                        px.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self._home_icon_box.setPixmap(make_icon("cube", 44, T.INFO).pixmap(44, 44))
            self._home_icon_box.setStyleSheet(
                f"font-family:'{T.FONT}'; font-size:17px; font-weight:900; color:{accent};"
                f" background:{T.rgba(accent, 0.10)}; border:1px solid {T.rgba(accent, 0.70)};"
                " border-radius:10px;")
        self._home_modpack_card.setToolTip("" if on else "Clic para volver al ChafaLand Modpack")
        self._home_modpack_card.setCursor(Qt.ArrowCursor if on else Qt.PointingHandCursor)
        if hasattr(self, "_open_folder_btn"):
            self._open_folder_btn.setText("Carpeta del modpack" if on else "Carpeta de la versión")
            try:
                self._open_folder_btn.setToolTip(game_launcher.game_dir_for(self._home_target))
            except Exception:
                pass

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
            return "FALTA ACTUALIZAR", T.WARN, "update"
        if self._state == self.S_BUSY:
            return "PROCESANDO", T.INFO, "play"
        if self._state == self.S_ERROR:
            return "REINTENTAR", T.ERROR, "install"
        return "ACTUAL", T.OK, "play"

    def _target_installed(self):
        """¿La versión suelta elegida ya está descargada?"""
        target = self._home_target
        if not isinstance(target, tuple):
            return True
        vid = target[1]
        return os.path.isfile(os.path.join(paths.get_minecraft_dir(), "versions", vid, f"{vid}.json"))

    def _set_label_color(self, label, color, size=12):
        label.setStyleSheet(f"font-family:'{T.FONT}'; font-size:{size}px; color:{color};"
                            " background:transparent;")

    def _update_home_state(self):
        if not hasattr(self, "_main_btn"):
            return

        on_modpack = self._home_target == "modpack"
        badge, color, mode = self._home_modpack_label()
        health_text, health_color = self._modpack_health_status()
        installed = self._target_installed()
        if not on_modpack:
            badge, color = ("INSTALADA", T.INFO) if installed else ("SE DESCARGARÁ", T.ACCENT_HI)
        elif health_color == T.WARN and self._state == self.S_READY:
            badge, color = "FALTA ACTUALIZAR", T.WARN
        self._home_badge.setText(badge)
        self._home_badge.setStyleSheet(self._badge_qss(color))

        ready_line = (
            "Listo para jugar"
            if self._state == self.S_READY and health_text == "Mods actualizados"
            else health_text
        )
        info = self._target_info()
        if on_modpack:
            self._home_meta_forge_icon.setIcon("anvil", T.MUTED)
            self._home_meta_forge_text.setText("Forge 1.20.1")
            self._home_meta_mods_icon.setIcon("puzzle", T.MUTED)
            self._home_meta_mods_text.setText(f"{self._installed_mod_count_label()} mods")
            self._home_meta_ready_icon.setIcon(
                "check-circle" if health_color not in (T.WARN, T.ERROR) else "warning",
                health_color,
            )
            self._home_meta_ready_text.setText(ready_line)
            self._set_label_color(self._home_meta_ready_text, health_color)
        else:
            self._home_meta_forge_icon.setIcon("cube", T.MUTED)
            self._home_meta_forge_text.setText(info["profile"])
            self._home_meta_mods_icon.setIcon("folder", T.MUTED)
            self._home_meta_mods_text.setText("Carpeta independiente")
            self._home_meta_ready_icon.setIcon("check-circle" if installed else "download", T.INFO)
            self._home_meta_ready_text.setText("Lista para jugar" if installed else "Se instala al jugar")
            self._set_label_color(self._home_meta_ready_text, T.INFO)

        premium = self._account_mode == "premium"
        if not on_modpack:
            if premium:
                hint = "Con cuenta premium esta versión se juega desde el launcher oficial."
            elif installed:
                hint = "Se juega en su propia carpeta: no usa los mods ni los mundos del modpack."
            else:
                hint = "Se descarga la primera vez (unos minutos) y usa su propia carpeta, sin el modpack."
        elif self._state == self.S_NONE:
            hint = "Instala el modpack oficial antes de iniciar Minecraft."
        elif self._state == self.S_UPDATE:
            hint = "Hay una actualización disponible. Se recomienda actualizar antes de jugar."
        elif self._state == self.S_BUSY:
            hint = "El launcher está preparando los archivos necesarios."
        elif self._state == self.S_ERROR:
            hint = "Algo falló. Revisa el registro (⋯ → Ver progreso) y pulsa REINTENTAR."
        elif self._state == self.S_CHECKING:
            hint = "Comprobando la instalación del modpack…"
        elif premium:
            hint = "Perfil premium: JUGAR abre el launcher oficial de Minecraft."
        elif health_color == T.WARN:
            hint = f"{health_text}. Usa ACTUALIZAR o Ajustes → Reparar para completarlo."
        else:
            hint = "Todo actualizado. ¡A jugar!"
        self._home_action_hint.setText(hint)

        if premium and self._state == self.S_READY and on_modpack:
            self._home_notice.setText("Cuenta premium detectada: JUGAR abre el launcher oficial.")
            self._home_notice.show()
        else:
            self._home_notice.clear()
            self._home_notice.hide()
        self._sec_btn.hide()

        busy = self._state in (self.S_CHECKING, self.S_BUSY)
        if on_modpack:
            text = {
                self.S_CHECKING: "VERIFICANDO...",
                self.S_BUSY: "PROCESANDO...",
                self.S_NONE: "INSTALAR",
                self.S_UPDATE: "ACTUALIZAR",
                self.S_ERROR: "REINTENTAR",
            }.get(self._state, "JUGAR")
            self._main_btn.setMode(mode)
            self._main_btn.setEnabled(not busy)
            self._main_btn.setText(text)
        else:
            self._main_btn.setMode("play")
            self._main_btn.setText("PROCESANDO..." if self._state == self.S_BUSY else "JUGAR")
            self._main_btn.setEnabled(not busy)

        # Si Minecraft ya está corriendo, no dejar relanzar.
        if getattr(self, "_game_running", False) and not busy:
            self._main_btn.setMode("play")
            self._main_btn.setText("EN EJECUCIÓN")
            self._main_btn.setEnabled(False)

        if getattr(self, "_recovery_required", False):
            self._home_badge.setText("RECUPERACIÓN")
            self._home_badge.setStyleSheet(self._badge_qss(T.ERROR))
            self._main_btn.setMode("install")
            self._main_btn.setText("REVISAR RESPALDO")
            self._main_btn.setEnabled(False)
            self._home_action_hint.setText(
                "No inicies ni reinstales hasta revisar el respaldo indicado en Ajustes."
            )

        if busy:
            self._chk_spin.start()
        else:
            self._chk_spin.stop()
        if hasattr(self, "_version_list"):
            self._version_list.set_modpack_badge(*self._modpack_list_badge())
        self._refresh_home_card_style()
        self._refresh_account_badge()
        self._refresh_home_metrics()
        self._refresh_java_label()

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
        self._modpack_status_lbl.setWordWrap(True)
        self._modpack_status_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
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
            status = "Primera instalación"
        elif self._state == self.S_UPDATE:
            text, badge, color, mode, enabled = "ACTUALIZAR", "ACTUALIZAR", T.INFO2, "update", True
            status = "Actualización disponible"
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

        if getattr(self, "_game_running", False) and self._state == self.S_READY:
            self._modpack_action_btn.setText("EN EJECUCIÓN")
            self._modpack_action_btn.setEnabled(False)
            self._modpack_status_lbl.setText("Minecraft en ejecución")

        if getattr(self, "_recovery_required", False):
            self._modpack_action_btn.setText("REVISAR RESPALDO")
            self._modpack_action_btn.setEnabled(False)
            self._modpack_card_badge.setText("RECUPERACIÓN")
            self._modpack_card_badge.setStyleSheet(self._badge_qss(T.ERROR))
            self._modpack_status_lbl.setText("Recuperación manual necesaria")

    def set_game_running(self, running):
        """Llamado desde MainWindow: bloquea/desbloquea Jugar según si el
        juego sigue vivo."""
        self._game_running = bool(running)
        self._update_home_state()
        self._update_modpack_page_state()
        self._refresh_repair_button()
        if self._game_running:
            self.append_log("🎮 Minecraft en ejecución — Jugar bloqueado hasta que cierres el juego.")
        else:
            self.append_log("✅ Minecraft cerrado — ya puedes volver a jugar.")

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

    def _refresh_account_badge(self):
        if not hasattr(self, "_account_summary"):
            return
        acc = self._account
        if not acc:
            text = "Sin cuenta configurada."
        elif getattr(acc, "mode", "") == "premium":
            text = "Cuenta premium: JUGAR abre el launcher oficial de Minecraft."
        else:
            text = f"Jugando como <b>{acc.username}</b> · modo offline (no premium)."
        self._account_summary.setText(text)

    # ── Página AJUSTES ────────────────────────────────────────────
    def _build_ajustes_page(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
            QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
            QScrollBar::handle:vertical {{
                background:{T.BORDER_HI}; border-radius:4px; min-height:24px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height:0; }}
        """)

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(52, 22, 52, 22)
        lay.setSpacing(14)

        title = QLabel("AJUSTES")
        title.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:26px; font-weight:900;"
            f" color:{T.TEXT}; letter-spacing:2px;"
        )
        lay.addWidget(title)

        sub = QLabel("Configuración del launcher")
        sub.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};"
        )
        lay.addWidget(sub)
        lay.addSpacing(6)

        # ── CARD RAM ───────────────────────────────────────────────
        ram_card = QFrame()
        ram_card.setStyleSheet(self._settings_card_qss())

        rv = QVBoxLayout(ram_card)
        rv.setContentsMargins(20, 18, 20, 18)
        rv.setSpacing(10)

        ram_title = QLabel("MEMORIA RAM")
        ram_title.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
            f" color:{T.TEXT}; background:transparent; border:none;"
        )
        rv.addWidget(ram_title)

        ram_row = QHBoxLayout()
        ram_row.setSpacing(12)

        ram_label = QLabel("RAM para Minecraft")
        ram_label.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:12px; color:{T.TEXT2};"
            " background:transparent; border:none;"
        )

        self._ram_selector = self._make_ram_selector()

        ram_row.addWidget(ram_label)
        ram_row.addStretch()
        ram_row.addWidget(self._ram_selector)

        rv.addLayout(ram_row)
        total = total_ram_gb()
        ram_hint = QLabel(
            (f"Tu PC tiene {total} GB. " if total else "")
            + "Recomendado: 6–8 GB para el modpack, 2–4 GB para vanilla. "
            "Asignar de más no acelera el juego y puede trabar Windows."
        )
        ram_hint.setWordWrap(True)
        ram_hint.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:10px; color:{T.MUTED};"
            " background:transparent; border:none;"
        )
        rv.addWidget(ram_hint)
        lay.addWidget(ram_card)

        # ── CARD CUENTA ───────────────────────────────────────────
        account_card = QFrame()
        account_card.setStyleSheet(self._settings_card_qss())
        av = QVBoxLayout(account_card)
        av.setContentsMargins(20, 18, 20, 18)
        av.setSpacing(10)
        account_title = QLabel("CUENTA")
        account_title.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
            f" color:{T.TEXT}; background:transparent; border:none;"
        )
        av.addWidget(account_title)
        account_row = QHBoxLayout()
        account_row.setSpacing(12)
        self._account_summary = QLabel("")
        self._account_summary.setWordWrap(True)
        self._account_summary.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:12px; color:{T.TEXT2};"
            " background:transparent; border:none;"
        )
        account_row.addWidget(self._account_summary, 1)
        self._switch_account_btn = QPushButton("Cambiar cuenta")
        self._switch_account_btn.setCursor(Qt.PointingHandCursor)
        self._switch_account_btn.setStyleSheet(self._ghost_btn_qss())
        self._switch_account_btn.clicked.connect(lambda: self.request_action.emit("switch_account"))
        account_row.addWidget(self._switch_account_btn)
        av.addLayout(account_row)
        lay.addWidget(account_card)

        # ── CARD MANTENIMIENTO ────────────────────────────────────
        self._repair_card = QFrame()
        self._repair_card.setStyleSheet(self._settings_card_qss())

        maintenance = QVBoxLayout(self._repair_card)
        maintenance.setContentsMargins(20, 18, 20, 18)
        maintenance.setSpacing(10)

        repair_title = QLabel("MANTENIMIENTO")
        repair_title.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
            f" color:{T.TEXT}; background:transparent; border:none;"
        )
        maintenance.addWidget(repair_title)

        repair_desc = QLabel(
            "Reinstala el modpack desde cero para corregir archivos dañados "
            "o conflictos entre mods."
        )
        repair_desc.setWordWrap(True)
        repair_desc.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:12px; color:{T.TEXT2};"
            " background:transparent; border:none;"
        )
        maintenance.addWidget(repair_desc)

        repair_safety = QLabel(
            "Primero se descarga y valida el paquete. Tus mundos y tu perfil "
            "se conservan, y la instalación anterior queda respaldada."
        )
        repair_safety.setWordWrap(True)
        repair_safety.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:10px; color:{T.MUTED};"
            f" background:{T.rgba(T.INFO, 0.07)};"
            f" border:1px solid {T.rgba(T.INFO, 0.18)}; border-radius:7px;"
            " padding:8px 10px;"
        )
        maintenance.addWidget(repair_safety)

        self._repair_backup_lbl = QLabel("")
        self._repair_backup_lbl.setWordWrap(True)
        self._repair_backup_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._repair_backup_lbl.setStyleSheet(
            f"font-family:'{T.FONT_MONO}'; font-size:9px; color:{T.MUTED};"
            " background:transparent; border:none;"
        )
        self._repair_backup_lbl.hide()
        maintenance.addWidget(self._repair_backup_lbl)

        repair_actions = QHBoxLayout()
        repair_actions.setSpacing(10)

        self._repair_btn = QPushButton("REPARAR INSTALACIÓN")
        self._repair_btn.setCursor(Qt.PointingHandCursor)
        self._repair_btn.setStyleSheet(self._repair_btn_qss())
        self._repair_btn.clicked.connect(self._on_repair_clicked)

        self._repair_backup_btn = QPushButton("ABRIR ÚLTIMO RESPALDO")
        self._repair_backup_btn.setCursor(Qt.PointingHandCursor)
        self._repair_backup_btn.setStyleSheet(self._ghost_btn_qss())
        self._repair_backup_btn.clicked.connect(self._open_last_repair_backup)
        self._repair_backup_btn.hide()

        repair_actions.addWidget(self._repair_btn)
        repair_actions.addWidget(self._repair_backup_btn)
        repair_actions.addStretch()
        maintenance.addLayout(repair_actions)

        lay.addWidget(self._repair_card)

        # ── CARD PERFIL NO PREMIUM ─────────────────────────────────
        self._offline_card = QFrame()
        self._offline_card.setStyleSheet(self._settings_card_qss())

        ov = QVBoxLayout(self._offline_card)
        ov.setContentsMargins(20, 18, 20, 18)
        ov.setSpacing(12)

        offline_title = QLabel("PERFIL NO PREMIUM")
        offline_title.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:13px; font-weight:900;"
            f" color:{T.TEXT}; background:transparent; border:none;"
        )
        ov.addWidget(offline_title)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(18)

        self._settings_skin_preview = QLabel("?")
        self._settings_skin_preview.setAlignment(Qt.AlignCenter)
        self._settings_skin_preview.setFixedSize(86, 86)
        self._settings_skin_preview.setStyleSheet(
            f"background:{T.SURFACE}; border:1px solid {T.BORDER_HI};"
            f" border-radius:10px; color:{T.MUTED};"
        )
        profile_row.addWidget(self._settings_skin_preview)

        form = QVBoxLayout()
        form.setSpacing(8)

        name_lab = QLabel("Nombre de jugador")
        name_lab.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:11px; font-weight:700;"
            f" color:{T.TEXT2}; background:transparent; border:none;"
        )

        self._settings_name = QLineEdit()
        self._settings_name.setMaxLength(16)
        self._settings_name.setStyleSheet(self._input_qss())

        self._settings_uuid = QLabel("")
        self._settings_uuid.setStyleSheet(
            f"font-family:'{T.FONT_MONO}'; font-size:9px;"
            f" color:{T.MUTED}; background:transparent; border:none;"
        )

        self._settings_skin_lbl = QLabel("Steve por defecto")
        self._settings_skin_lbl.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:10px;"
            f" color:{T.MUTED}; background:transparent; border:none;"
        )

        form.addWidget(name_lab)
        form.addWidget(self._settings_name)
        form.addWidget(self._settings_uuid)
        form.addWidget(self._settings_skin_lbl)

        profile_row.addLayout(form, stretch=1)
        ov.addLayout(profile_row)

        profiles_lab = QLabel("Perfiles guardados")
        profiles_lab.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:11px; font-weight:700;"
            f" color:{T.TEXT2}; background:transparent; border:none;"
        )
        ov.addWidget(profiles_lab)

        profiles_row = QHBoxLayout()
        profiles_row.setSpacing(10)

        self._profiles_combo = QComboBox()
        self._profiles_combo.setFixedHeight(40)
        self._profiles_combo.setStyleSheet(self._combo_qss())

        self._restore_profile_btn = QPushButton("Restaurar")
        self._restore_profile_btn.setCursor(Qt.PointingHandCursor)
        self._restore_profile_btn.setStyleSheet(self._ghost_btn_qss())
        self._restore_profile_btn.clicked.connect(self._restore_selected_profile)

        profiles_row.addWidget(self._profiles_combo, stretch=1)
        profiles_row.addWidget(self._restore_profile_btn)
        ov.addLayout(profiles_row)

        btns = QHBoxLayout()
        btns.setSpacing(10)

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

        # ── HINT PREMIUM ────────────────────────────────────────────
        self._premium_hint = QLabel("La skin premium se gestiona desde el launcher oficial.")
        self._premium_hint.setStyleSheet(
            f"font-family:'{T.FONT}'; font-size:12px; color:{T.MUTED};"
        )
        lay.addWidget(self._premium_hint)

        lay.addStretch()

        self._refresh_account_settings()
        self._refresh_repair_button()

        scroll.setWidget(content)
        outer.addWidget(scroll)

        return page

    def _make_ram_selector(self):
        box = QFrame()
        box.setObjectName("ramSelector")
        box.setFixedSize(174, 42)
        box.setStyleSheet(self._ram_selector_qss())

        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self._ram_minus_btn = QPushButton("−")
        self._ram_minus_btn.setObjectName("ramMinus")
        self._ram_minus_btn.setFixedSize(42, 42)
        self._ram_minus_btn.setCursor(Qt.PointingHandCursor)
        self._ram_minus_btn.clicked.connect(self._ram_dec)

        self._ram_value_lbl = QLabel(f"{self.ram_gb()} GB")
        self._ram_value_lbl.setObjectName("ramValue")
        self._ram_value_lbl.setAlignment(Qt.AlignCenter)
        self._ram_value_lbl.setFixedHeight(42)

        self._ram_plus_btn = QPushButton("+")
        self._ram_plus_btn.setObjectName("ramPlus")
        self._ram_plus_btn.setFixedSize(42, 42)
        self._ram_plus_btn.setCursor(Qt.PointingHandCursor)
        self._ram_plus_btn.clicked.connect(self._ram_inc)

        h.addWidget(self._ram_minus_btn)
        h.addWidget(self._ram_value_lbl, stretch=1)
        h.addWidget(self._ram_plus_btn)

        self._refresh_ram_selector()

        return box

    def _ram_dec(self):
        self._set_ram_value(self.ram_gb() - 1)

    def _ram_inc(self):
        self._set_ram_value(self.ram_gb() + 1)

    def _set_ram_value(self, value):
        value = max(2, min(self._max_ram, int(value)))
        self._on_ram_changed(value)

    def _refresh_ram_selector(self):
        value = self.ram_gb()

        if hasattr(self, "_ram_value_lbl"):
            self._ram_value_lbl.setText(f"{value} GB")

        if hasattr(self, "_ram_minus_btn"):
            self._ram_minus_btn.setEnabled(value > 2)

        if hasattr(self, "_ram_plus_btn"):
            self._ram_plus_btn.setEnabled(value < self._max_ram)
            self._ram_plus_btn.setToolTip(
                "" if value < self._max_ram else
                f"Máximo recomendado para tu PC: {self._max_ram} GB")

    def _ram_selector_qss(self):
        return f"""
        QFrame#ramSelector {{
            background-color: #090E14;
            border: 1px solid #2A3442;
            border-radius: 9px;
        }}

        QFrame#ramSelector:hover {{
            border: 1px solid #3A4656;
        }}

        QPushButton#ramMinus,
        QPushButton#ramPlus {{
            background-color: #101722;
            color: {T.TEXT};
            border: none;
            font-family: '{T.FONT}';
            font-size: 17px;
            font-weight: 900;
        }}

        QPushButton#ramMinus {{
            border-top-left-radius: 8px;
            border-bottom-left-radius: 8px;
            border-right: 1px solid #2A3442;
        }}

        QPushButton#ramPlus {{
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
            border-left: 1px solid #2A3442;
        }}

        QPushButton#ramMinus:hover,
        QPushButton#ramPlus:hover {{
            background-color: #FF7A1A;
            color: #1A1206;
        }}

        QPushButton#ramMinus:pressed,
        QPushButton#ramPlus:pressed {{
            background-color: #D96100;
        }}

        QPushButton#ramMinus:disabled,
        QPushButton#ramPlus:disabled {{
            background-color: #0B111A;
            color: #45505E;
        }}

        QLabel#ramValue {{
            background-color: transparent;
            color: {T.TEXT};
            border: none;
            font-family: '{T.FONT}';
            font-size: 12px;
            font-weight: 900;
        }}
        """
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

    def _combo_qss(self):
        return f"""
            QComboBox {{
                background:{T.SURFACE};
                border:1px solid {T.BORDER_HI};
                border-radius:8px;
                padding:7px 12px;
                color:{T.TEXT};
                font-family:'{T.FONT}';
                font-size:12px;
            }}
            QComboBox::drop-down {{ width:30px; border:none; }}
            QComboBox QAbstractItemView {{
                background:{T.SURFACE};
                border:1px solid {T.BORDER_HI};
                color:{T.TEXT2};
                selection-background-color:{T.rgba(T.ACCENT, 0.22)};
                selection-color:{T.TEXT};
                outline:0;
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

    def _repair_btn_qss(self):
        return f"""
            QPushButton {{
                background:{T.rgba(T.ERROR, 0.10)};
                color:{T.ERROR};
                border:1px solid {T.rgba(T.ERROR, 0.45)};
                border-radius:8px;
                padding:10px 16px;
                font-family:'{T.FONT}';
                font-size:12px;
                font-weight:800;
            }}
            QPushButton:hover {{
                background:{T.rgba(T.ERROR, 0.18)};
                border-color:{T.ERROR};
            }}
            QPushButton:disabled {{
                background:{T.rgba(T.ERROR, 0.04)};
                color:{T.DIM};
                border-color:{T.BORDER};
            }}
        """

    def _refresh_repair_button(self):
        if not hasattr(self, "_repair_btn"):
            return
        checking_or_busy = self._state in (
            self.S_CHECKING, self.S_BUSY, self.S_NONE
        )
        game_running = bool(getattr(self, "_game_running", False))
        recovery_required = bool(getattr(self, "_recovery_required", False))
        self._repair_btn.setEnabled(
            not checking_or_busy and not game_running and not recovery_required
        )

        if recovery_required:
            hint = "Revisa y recupera manualmente el respaldo antes de continuar."
        elif self._state == self.S_BUSY:
            hint = "Espera a que termine la operación actual."
        elif self._state == self.S_CHECKING:
            hint = "Disponible cuando termine la verificación."
        elif self._state == self.S_NONE:
            hint = "Primero instala el modpack; todavía no hay una instalación que reparar."
        elif game_running:
            hint = "Cierra Minecraft antes de reparar la instalación."
        else:
            hint = "Reinstala el modpack conservando mundos, perfil y un respaldo."
        self._repair_btn.setToolTip(hint)

    def _on_repair_clicked(self):
        if self._state in (self.S_CHECKING, self.S_BUSY, self.S_NONE):
            return
        if getattr(self, "_recovery_required", False):
            return
        if getattr(self, "_game_running", False):
            QMessageBox.information(
                self,
                "Reparar instalación",
                "Cierra Minecraft antes de reparar la instalación.",
            )
            return

        mc_dir = os.path.abspath(paths.get_minecraft_dir())
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Reparar instalación")
        dialog.setText("¿Quieres reinstalar completamente el modpack?")
        dialog.setInformativeText(
            "Carpeta que se reemplazará:\n"
            f"{mc_dir}\n\n"
            "Primero se descargará y validará el paquete. Se conservarán tus "
            "mundos, tu perfil y tus skins, y la instalación anterior quedará "
            "disponible como respaldo.\n\n"
            "Necesitarás espacio para la descarga y las dos instalaciones; "
            "el respaldo puede ocupar varios GB."
        )
        repair_button = dialog.addButton(
            "REPARAR INSTALACIÓN", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = dialog.addButton(
            "Cancelar", QMessageBox.ButtonRole.RejectRole
        )
        dialog.setDefaultButton(cancel_button)
        dialog.setEscapeButton(cancel_button)
        dialog.exec()

        if dialog.clickedButton() is repair_button:
            self.request_action.emit("repair")

    def set_last_repair_backup(self, backup_path):
        """Muestra el respaldo creado y habilita abrirlo desde Ajustes."""
        raw = str(backup_path or "").strip()
        self._last_repair_backup = os.path.abspath(raw) if raw else ""

        if not hasattr(self, "_repair_backup_btn"):
            return
        visible = bool(self._last_repair_backup)
        self._repair_backup_btn.setVisible(visible)
        self._repair_backup_lbl.setVisible(visible)
        if visible:
            self._repair_backup_lbl.setText(
                f"Último respaldo: {self._last_repair_backup}"
            )
        else:
            self._repair_backup_lbl.clear()

    def set_recovery_required(self, backup_path=""):
        """Bloquea acciones que podrían sobrescribir una recuperación fallida."""
        self._recovery_required = True
        self.set_last_repair_backup(backup_path)
        self._update_home_state()
        self._update_modpack_page_state()
        self._refresh_repair_button()
        self.set_status_text("Recuperación manual necesaria")
        self.append_log(
            "⛔ Acciones bloqueadas: revisa el respaldo antes de continuar."
        )

    def _open_last_repair_backup(self):
        path = getattr(self, "_last_repair_backup", "")
        if not path or not os.path.isdir(path):
            QMessageBox.warning(
                self,
                "Respaldo no disponible",
                "La carpeta del último respaldo ya no existe.",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_ram_changed(self, value):
        self._ram_gb = max(2, min(self._max_ram, int(value)))
        self._settings.setValue("game/ram_gb", self._ram_gb)
        self._settings.sync()

        if hasattr(self, "_ram_value_lbl"):
            self._refresh_ram_selector()

        self._refresh_home_metrics()

    def ram_gb(self):
        return max(2, min(self._max_ram, int(self._ram_gb or 6)))

    def set_account(self, account):
        self._account = account
        self.set_account_mode(getattr(account, "mode", ""))
        self._refresh_account_badge()
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
        self._refresh_profiles()

    def _refresh_profiles(self):
        if not hasattr(self, "_profiles_combo"):
            return
        current_uuid = getattr(self._account, "uuid", "")
        self._profiles_combo.clear()
        profiles = accounts.list_profiles()
        if not profiles:
            self._profiles_combo.addItem("Sin perfiles guardados", None)
            self._restore_profile_btn.setEnabled(False)
            return
        self._restore_profile_btn.setEnabled(True)
        for profile in profiles:
            label = profile.username
            if profile.uuid == current_uuid:
                label += "  (actual)"
            self._profiles_combo.addItem(label, profile)
        for i in range(self._profiles_combo.count()):
            profile = self._profiles_combo.itemData(i)
            if profile and profile.uuid == current_uuid:
                self._profiles_combo.setCurrentIndex(i)
                break

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
            QMessageBox.warning(self, "CFL Launcher", "PNG inválido. Usa una skin de 64x64 o 64x32.")
            return
        self._pending_skin_path = path
        self._set_settings_skin(path)

    def _save_offline_profile(self):
        acc = self._account
        if not acc or acc.mode != "offline":
            return
        name = self._settings_name.text().strip()
        if not accounts.is_valid_name(name):
            QMessageBox.warning(self, "CFL Launcher", "Usa 3-16 caracteres: letras, números o _")
            return
        if name != acc.username:
            ans = QMessageBox.question(
                self,
                "Cambiar nombre",
                "Cambiar el nombre puede separar tu progreso en servidores offline. ¿Guardar de todos modos?",
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
        accounts.remember_profile(acc)
        updated = accounts.make_offline(name, skin_path=skin_path)
        accounts.save(updated)
        self._account = updated
        self.account_changed.emit(updated)
        self._refresh_account_settings()
        self.append_log("Perfil no premium guardado")

    def _restore_selected_profile(self):
        profile = self._profiles_combo.currentData()
        if not profile:
            return
        ans = QMessageBox.question(
            self,
            "Restaurar perfil",
            f"¿Restaurar el perfil '{profile.username}' con su UUID offline anterior?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        accounts.save(profile)
        self._account = profile
        self.account_changed.emit(profile)
        self._refresh_account_settings()
        self.append_log(f"Perfil restaurado: {profile.username}")

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
        # El panel de progreso solo vive en Inicio; en otras páginas no tapa nada.
        if idx == 0:
            self._show_progress_overlay()
        elif hasattr(self, "_progress_overlay"):
            self._progress_overlay.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_lightbox") and self._lightbox.isVisible():
            self._lightbox.setGeometry(self.rect())
        self._position_progress_overlay()
        # Banner de Inicio adaptable: en ventanas bajas cede espacio a la lista.
        if hasattr(self, "_home_banner"):
            h = self.height()
            banner_h = 170 if h >= 860 else 140 if h >= 720 else 104
            self._home_banner.setFixedHeight(banner_h)
            self._hero_sub.setVisible(banner_h >= 130)
            size = 28 if banner_h >= 130 else 22
            self._hero_title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:{size}px;"
                                           " font-weight:900; color:#ffffff; background:transparent;")

    # ── Máquina de estados ────────────────────────────────────────
    def set_state(self, state, remote_version=""):
        changed = state != self._state
        self._state = state
        self._invalidate_health()
        if state != self.S_BUSY:
            self._busy_text = ""

        if state == self.S_CHECKING:
            self._set_st("VERIFICANDO ARCHIVOS", T.ACCENT_HI)

        elif state == self.S_NONE:
            self._set_st("PRIMERA INSTALACIÓN", T.INFO)
            if changed:
                self._log.append_log(
                    "🆕 Modpack no instalado — pulsa INSTALAR para comenzar"
                )

        elif state == self.S_UPDATE:
            self._set_st("ACTUALIZACIÓN DISPONIBLE", T.INFO2)
            if remote_version:
                self._ver_badge.setText(f"Nueva versión v{remote_version}")
                self._ver_badge.setStyleSheet(self._ver_badge_qss(T.INFO2))
            if changed:
                self._log.append_log(
                    "⬆️ Hay una actualización disponible. Se recomienda actualizar antes de iniciar."
                )

        elif state == self.S_READY:
            if remote_version:
                self._current_version = remote_version
            health_text, health_color = self._modpack_health_status()
            if health_color == T.WARN:
                self._set_st("FALTA ACTUALIZAR", T.WARN)
                if changed:
                    self._log.append_log(f"⚠️ {health_text}. Se recomienda actualizar.")
            else:
                self._set_st("LISTO PARA JUGAR", T.ACCENT_HI)
                if changed:
                    self._log.append_log("✅ Todo actualizado. Listo para iniciar.")
            self.update_version_badge(self._current_version)

        elif state == self.S_BUSY:
            self._overlay_wanted = True

        elif state == self.S_ERROR:
            self._set_st("ERROR", T.ERROR)
            self._bar.setValue(0)
            self._pct_lbl.setText("")
            # Mostrar el registro para que se vea qué falló.
            self._overlay_wanted = True

        if state in (self.S_READY, self.S_NONE, self.S_UPDATE, self.S_CHECKING):
            self._checked_at = QDateTime.currentDateTime()

        self._update_home_state()
        self._update_modpack_page_state()
        self._sidebar_status_update()
        self._refresh_repair_button()
        self._refresh_news()

        if self._overlay_wanted and state in (self.S_BUSY, self.S_ERROR):
            self._show_progress_overlay()

    def _set_st(self, text, color):
        self._st_lbl.setText(text)
        self._st_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:700;"
                                  f" color:{color}; letter-spacing:3px;")

    def set_done_ok(self):
        self._bar.setValue(100); self._pct_lbl.setText("100%")
        # Tras instalar/actualizar, la versión instalada es la que quedó en disco.
        self._current_version = _installed_modpack_version() or self._current_version
        self.set_state(self.S_READY)
        # Dejar ver el final del registro un momento antes de ocultarlo.
        self.schedule_overlay_hide()

    def _auto_hide_overlay(self):
        if self._state not in (self.S_BUSY, self.S_ERROR, self.S_CHECKING):
            self._hide_progress_overlay()

    def schedule_overlay_hide(self, ms=3500):
        QTimer.singleShot(ms, self._auto_hide_overlay)

    def mark_version_installed(self, version):
        if hasattr(self, "_version_list"):
            self._version_list.mark_installed(version)
        self._update_home_state()

    def set_status_text(self, text):
        self._st_lbl.setText(text.upper())
        if self._state == self.S_BUSY:
            self._busy_text = text
            self._sidebar_status_update()
        if hasattr(self, "_modpack_status_lbl"):
            self._modpack_status_lbl.setText(text)

    def on_progress(self, v):
        v = max(0, min(100, int(v)))
        self._bar.setValue(v)
        self._pct_lbl.setText(f"{v}%")
        if hasattr(self, "_modpack_bar"):
            self._modpack_bar.setValue(v)
            self._modpack_pct_lbl.setText(f"{v}%")
        if self._state == self.S_BUSY:
            self._sidebar_status_update()

    def append_log(self, text): self._log.append_log(text)

    def _ver_badge_qss(self, color):
        return (f"font-family:'{T.FONT_MONO}'; font-size:10px; color:{color};"
                f" background:{T.rgba(color, 0.09)}; border:1px solid {T.rgba(color, 0.25)};"
                " border-radius:4px; padding:0px 10px;")

    def update_version_badge(self, version=None):
        version = version or self._current_version
        self._ver_badge.setText(f"Modpack v{version}" if version else "Modpack")
        self._ver_badge.setStyleSheet(self._ver_badge_qss(T.ACCENT_HI))

    def set_maximized(self, maximized):
        """MainWindow avisa para cambiar el ícono del botón maximizar."""
        self._max_btn.setSymbol("❐" if maximized else "□")
        self._max_btn.setToolTip("Restaurar" if maximized else "Maximizar")
