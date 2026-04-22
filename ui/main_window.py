from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from core.downloader import download_modpack
from core.installer import install_modpack
from core.installer_update import update_modpack
from core.updater import needs_update, save_local_version
from core.checker import is_installed
from core.game_launcher import launch_minecraft
from core.launcherUpdate import check_launcher_update, download_new_exe, apply_update, save_local_version as save_launcher_version
import math
import os

MODPACK_VERSION  = "1.0.0"
LAUNCHER_VERSION = "1.0.0"

WIN_DEFAULT_W = 1100
WIN_DEFAULT_H = 660
WIN_MIN_W     = 820
WIN_MIN_H     = 520

SETTINGS_ORG = "CFL"
SETTINGS_APP = "Launcher"
# LOGO_PATH se resuelve dinámicamente via resource_fn pasado desde main.py
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.ico")

def _get_logo(resource_fn=None):
    if resource_fn:
        return resource_fn("assets/logo.ico")
    return LOGO_PATH



#   WORKER — descarga / instala / actualiza

class Worker(QThread):
    progress = Signal(int)
    status   = Signal(str)
    log      = Signal(str)
    done     = Signal(bool)

    def __init__(self, force_update=False):
        super().__init__()
        self.force_update = force_update
        self._running     = False

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

            # Pequeña pausa para que el usuario lea el mensaje
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
            installed      = is_installed()
            update, version = needs_update(lambda _: None)
            if not installed:
                self.result.emit("not_installed", version or "")
            elif update:
                self.result.emit("update", version or "")
            else:
                self.result.emit("ready", version or "")
        except Exception:
            self.result.emit("ready", "")



#   SPINNER

class Spinner(QWidget):
    def __init__(self, size=22, color="#f97316", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color)
        self._size  = size
        self._t     = QTimer(self)
        self._t.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self._t.start(18)
        self.show()

    def stop(self):
        self._t.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 5) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s, m = self._size, 3
        pen = QPen()
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor(255, 255, 255, 12))
        p.setPen(pen)
        p.drawEllipse(m, m, s-m*2, s-m*2)
        pen.setColor(self._color)
        p.setPen(pen)
        p.drawArc(m, m, s-m*2, s-m*2, (-self._angle)*16, -270*16)



#   BARRA PROGRESO CON GLOW

class GlowBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(5)
        self._val  = 0
        self._anim = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(40)

    def setValue(self, v):
        self._val = max(0, min(100, v))
        self.update()

    def _tick(self):
        self._anim = (self._anim + 0.025) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 8))
        p.drawRoundedRect(0, 0, w, h, r+1, r+1)
        if self._val <= 0:
            return
        fill = int(w * self._val / 100)
        for i in range(4, 0, -1):
            p.setBrush(QColor(249, 115, 22, 9 * i))
            p.drawRoundedRect(-i, -1, fill+i*2, h+2, r+1, r+1)
        g = QLinearGradient(0, 0, fill, 0)
        s = self._anim
        g.setColorAt(max(0.0, s-0.4), QColor("#c2410c"))
        g.setColorAt(s,               QColor("#fb923c"))
        g.setColorAt(min(1.0, s+0.4), QColor("#c2410c"))
        p.setBrush(g)
        p.drawRoundedRect(0, 0, fill, h, r, r)



#   LOG BOX

class LogBox(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(400)
        self.setFont(QFont("Cascadia Code", 9))
        self.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                padding: 0px;
            }
            QScrollBar:vertical {
                background: transparent; width: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3a2a1a; border-radius: 2px; min-height: 16px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)

    def append_log(self, text):
        t = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        if   any(x in text for x in ["✅","completad","finaliz","¡List"]): c = "#fb923c"
        elif any(x in text for x in ["❌","Error","error","ERROR"]):        c = "#f87171"
        elif any(x in text for x in ["⚠️","fallback","alternativ"]):       c = "#fbbf24"
        elif any(x in text for x in ["⬇️","📦","🔄","🆕","💾","🎉","🔍"]): c = "#60a5fa"
        elif "────" in text:                                                 c = "#2a1a0a"
        elif "|" in text and ("MB" in text or "%" in text):                 c = "#a87050"
        else:                                                                c = "#7a5a40"
        self.append(
            f'<span style="color:{c};font-family:Cascadia Code,Consolas;font-size:9pt">'
            f'&gt; {t}</span>'
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())



#   SIDEBAR BUTTON

class SideBtn(QWidget):
    clicked = Signal()

    def __init__(self, icon_text, active=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self._icon   = icon_text
        self._active = active
        self._hover  = False
        self.setCursor(Qt.PointingHandCursor)

    def setActive(self, v):
        self._active = v
        self.update()

    def enterEvent(self, e):   self._hover = True;  self.update()
    def leaveEvent(self, e):   self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self._active:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#f97316"))
            p.drawRoundedRect(0, 14, 3, 20, 1, 1)
            p.setBrush(QColor(249, 115, 22, 18))
            p.drawRoundedRect(4, 4, w-8, h-8, 8, 8)
        elif self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 7))
            p.drawRoundedRect(4, 4, w-8, h-8, 8, 8)
        color = "#f97316" if self._active else ("#d6d3d1" if self._hover else "#6b5a50")
        p.setPen(QColor(color))
        p.setFont(QFont("Segoe UI", 14))
        p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self._icon)



#   PLAY BUTTON

class PlayBtn(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(165, 48)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hov   = False
        self._prs   = False
        self._ena   = True
        self._pulse = 0.0
        self._mode  = "play"
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(40)

    def setMode(self, mode):
        self._mode = mode
        self.update()

    def _tick(self):
        self._pulse = (self._pulse + 0.03) % (2 * math.pi)
        self.update()

    def enterEvent(self, e):   self._hov = True;  self.update()
    def leaveEvent(self, e):   self._hov = False; self.update()
    def mousePressEvent(self, e):
        self._prs = True;  self.update(); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        self._prs = False; self.update(); super().mouseReleaseEvent(e)
    def setEnabled(self, v):
        self._ena = v; super().setEnabled(v); self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r    = 10

        if not self._ena:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#1a1208"))
            p.drawRoundedRect(0, 0, w, h, r, r)
            p.setPen(QColor("#5a4030"))
            p.setFont(QFont("Segoe UI", 11, QFont.Bold))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self.text())
            return

        pa = int(14 + 10 * math.sin(self._pulse))
        GLOW = {
            "play":    (249, 115, 22),
            "install": (56,  189, 248),
            "update":  (6,   182, 212),
        }.get(self._mode, (249, 115, 22))

        for i in range(6, 0, -1):
            p.setBrush(QColor(*GLOW, max(0, pa - i*2)))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(-i, -i, w+i*2, h+i*2, r+i, r+i)

        g = QLinearGradient(0, 0, w, 0)
        if self._mode == "install":
            c0 = "#0ea5e9" if not self._prs else "#0284c7"
            c1 = "#0284c7" if not self._prs else "#0369a1"
        elif self._mode == "update":
            c0 = "#06b6d4" if not self._prs else "#0891b2"
            c1 = "#0891b2" if not self._prs else "#0e7490"
        else:
            if self._prs:   c0, c1 = "#c2410c", "#9a3412"
            elif self._hov: c0, c1 = "#f97316", "#ea580c"
            else:           c0, c1 = "#ea580c", "#c2410c"

        g.setColorAt(0, QColor(c0))
        g.setColorAt(1, QColor(c1))
        p.setBrush(g); p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        hi = QLinearGradient(0, 0, 0, h)
        hi.setColorAt(0, QColor(255, 255, 255, 45))
        hi.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(hi)
        p.drawRoundedRect(0, 0, w, h//2+1, r, r)

        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self.text())



#   BOTÓN SECUNDARIO

class SecBtn(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(150, 48)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 10px;
                color: #d6d3d1;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.10);
                color: #f5f5f4;
                border-color: rgba(255,255,255,0.22);
            }
            QPushButton:pressed { background: rgba(255,255,255,0.03); }
            QPushButton:disabled {
                color: #2a1a0a;
                border-color: rgba(255,255,255,0.04);
                background: rgba(255,255,255,0.02);
            }
        """)



#   TITLEBAR BUTTON

class WinBtn(QWidget):
    clicked = Signal()

    def __init__(self, symbol, hover_bg="#2a1a0a", hover_fg="#e2e8f0", parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 38)
        self._sym   = symbol
        self._hbg   = QColor(hover_bg)
        self._hfg   = QColor(hover_fg)
        self._hover = False
        self._press = False
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):   self._hover = True;  self.update()
    def leaveEvent(self, e):   self._hover = False; self._press = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = True; self.update()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._hover:
            self._press = False; self.update()
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        if self._press:   p.fillRect(0, 0, w, h, self._hbg.darker(130))
        elif self._hover: p.fillRect(0, 0, w, h, self._hbg)
        fg = self._hfg if (self._hover or self._press) else QColor("#6b5a50")
        p.setPen(fg)
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self._sym)



#   SPLASH SCREEN

class SplashScreen(QWidget):
    def __init__(self, resource_fn=None, parent=None):
        super().__init__(parent)
        self._resource_fn = resource_fn
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(0)
        lay.addStretch(3)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        px = QPixmap(_get_logo(self._resource_fn))
        if not px.isNull():
            logo_lbl.setPixmap(px.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_lbl.setText("⬡")
            logo_lbl.setStyleSheet("font-size:72px; color:#f97316;")
        lay.addWidget(logo_lbl)
        lay.addSpacing(22)

        # Título
        t = QLabel("CFL LAUNCHER")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("""
            font-family:'Segoe UI'; font-size:46px; font-weight:900;
            color:#ffffff; letter-spacing:10px;
        """)
        lay.addWidget(t)
        lay.addSpacing(6)

        # Subtítulo
        s = QLabel("CHAFALAND MODPACK")
        s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet("""
            font-family:'Segoe UI'; font-size:13px; font-weight:500;
            color:#fb923c; letter-spacing:8px;
        """)
        lay.addWidget(s)
        lay.addSpacing(40)

        # Spinner + estado
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(12)

        self._spinner = Spinner(size=20, color="#f97316")
        self._spinner.start()
        row.addWidget(self._spinner)

        self._lbl = QLabel("Verificando actualizaciones...")
        self._lbl.setStyleSheet("""
            font-family:'Segoe UI'; font-size:11px;
            color:#a8a29e; letter-spacing:1px;
        """)
        row.addWidget(self._lbl)
        lay.addLayout(row)
        lay.addStretch(4)

        ver = QLabel(f"v{LAUNCHER_VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("font-family:'Cascadia Code'; font-size:10px; color:#3a2a1a;")
        lay.addWidget(ver)
        lay.addSpacing(20)

    def set_status(self, text):
        self._lbl.setText(text)

    def set_progress(self, v):
        if not hasattr(self, "_pbar"):
            from PySide6.QtWidgets import QProgressBar
            self._pbar = QProgressBar()
            self._pbar.setTextVisible(False)
            self._pbar.setFixedHeight(3)
            self._pbar.setStyleSheet("""
                QProgressBar { background: rgba(255,255,255,0.05); border-radius:1px; border:none; }
                QProgressBar::chunk { background: #f97316; border-radius:1px; }
            """)
            # Insertar antes del último stretch
            lay = self.layout()
            lay.insertWidget(lay.count() - 2, self._pbar)
        self._pbar.setValue(v)
        self._pbar.show()

    def hide_progress(self):
        if hasattr(self, "_pbar"):
            self._pbar.hide()

    def stop(self):
        self._spinner.stop()
        self._lbl.setText("Listo")



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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── SIDEBAR ───────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(64)
        sidebar.setStyleSheet("background: rgba(8,5,3,0.88);")
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(8, 16, 8, 16)
        sb.setSpacing(6)
        sb.setAlignment(Qt.AlignTop)

        logo = QLabel()
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignCenter)
        px = QPixmap(_get_logo(getattr(self, "_resource_fn", None)))
        if not px.isNull():
            logo.setPixmap(px.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("CFL")
        logo.setStyleSheet("""
            font-family:'Segoe UI'; font-size:10px; font-weight:900;
            color:#f97316; background:rgba(249,115,22,0.08); border-radius:10px;
        """)
        sb.addWidget(logo)
        sb.addSpacing(12)

        self._sb_home   = SideBtn("⌂", active=True)
        self._sb_mods   = SideBtn("⊞")
        self._sb_config = SideBtn("⚙")
        for b in [self._sb_home, self._sb_mods, self._sb_config]:
            sb.addWidget(b)
        sb.addStretch()
        root.addWidget(sidebar)

        # ── CONTENIDO ─────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # Topbar
        topbar = QWidget()
        topbar.setFixedHeight(48)
        topbar.setStyleSheet("background:rgba(8,5,3,0.75);")
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 0, 0, 0)
        tb.setSpacing(0)

        bread = QLabel("CFL LAUNCHER  /  INICIO")
        bread.setStyleSheet("""
            font-family:'Segoe UI'; font-size:10px;
            color:#6b5a50; letter-spacing:2px;
        """)
        tb.addWidget(bread)
        tb.addStretch()

        self._ver_badge = QLabel(f"Modpack v{MODPACK_VERSION}")
        self._ver_badge.setStyleSheet("""
            font-family:'Cascadia Code'; font-size:10px;
            color:#fb923c; background:rgba(249,115,22,0.09);
            border:1px solid rgba(249,115,22,0.22);
            border-radius:4px; padding:3px 10px;
        """)
        tb.addWidget(self._ver_badge)
        tb.addSpacing(8)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(20)
        sep.setStyleSheet("color:rgba(255,255,255,0.06);")
        tb.addWidget(sep)

        self._min_btn   = WinBtn("─", hover_bg="#1a1208", hover_fg="#e2e8f0")
        self._close_btn = WinBtn("✕", hover_bg="#7f1d1d", hover_fg="#ffffff")
        tb.addWidget(self._min_btn)
        tb.addWidget(self._close_btn)
        cl.addWidget(topbar)

        # Hero
        hero = QWidget()
        hero.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hero.setStyleSheet("background:transparent;")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(52, 0, 52, 0)
        hl.setSpacing(0)
        hl.addStretch(2)

        self._tag = QLabel("MODPACK  ·  MINECRAFT 1.20.1")
        self._tag.setStyleSheet("""
            font-family:'Segoe UI'; font-size:12px; font-weight:600;
            color:#fb923c; letter-spacing:5px;
        """)
        hl.addWidget(self._tag)
        hl.addSpacing(8)

        self._title = QLabel("CFL LAUNCHER")
        self._title.setStyleSheet("""
            font-family:'Segoe UI'; font-size:52px; font-weight:900;
            color:#ffffff; letter-spacing:3px;
        """)
        hl.addWidget(self._title)
        hl.addSpacing(10)

        self._desc = QLabel("ChafaLand Modpack Oficial  ·  +340 Mods activos")
        self._desc.setStyleSheet("""
            font-family:'Segoe UI'; font-size:13px; font-weight:400; color:#a07050;
        """)
        hl.addWidget(self._desc)
        hl.addSpacing(28)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.setAlignment(Qt.AlignLeft)

        self._main_btn = PlayBtn()
        self._main_btn.setText("CARGANDO...")
        self._main_btn.setEnabled(False)
        self._main_btn.clicked.connect(self._on_main)

        self._sec_btn = SecBtn("...")
        self._sec_btn.setEnabled(False)
        self._sec_btn.clicked.connect(self._on_sec)

        self._chk_spin = Spinner(size=20, color="#fb923c")

        btn_row.addWidget(self._main_btn)
        btn_row.addWidget(self._sec_btn)
        btn_row.addSpacing(6)
        btn_row.addWidget(self._chk_spin)
        hl.addLayout(btn_row)
        hl.addStretch(1)

        # Panel inferior
        bottom = QWidget()
        bottom.setFixedHeight(185)
        bottom.setStyleSheet("""
            background:rgba(8,5,3,0.70);
            border-top:1px solid rgba(255,255,255,0.04);
        """)
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(52, 14, 52, 16)
        bl.setSpacing(6)

        sr = QHBoxLayout()
        self._st_lbl = QLabel("INICIANDO")
        self._st_lbl.setStyleSheet("""
            font-family:'Segoe UI'; font-size:10px; font-weight:700;
            color:#fb923c; letter-spacing:3px;
        """)
        self._pct_lbl = QLabel("")
        self._pct_lbl.setStyleSheet("font-family:'Cascadia Code'; font-size:9px; color:#7a5a40;")
        sr.addWidget(self._st_lbl)
        sr.addStretch()
        sr.addWidget(self._pct_lbl)
        bl.addLayout(sr)

        self._bar = GlowBar()
        bl.addWidget(self._bar)
        bl.addSpacing(5)

        self._log = LogBox()
        bl.addWidget(self._log)

        cl.addWidget(hero)
        cl.addWidget(bottom)
        root.addWidget(content)

    # ── Máquina de estados ────────────────────────────────────────
    def set_state(self, state, remote_version=""):
        self._state = state

        if state == self.S_CHECKING:
            self._main_btn.setText("VERIFICANDO...")
            self._main_btn.setMode("play")
            self._main_btn.setEnabled(False)
            self._sec_btn.setText("...")
            self._sec_btn.setEnabled(False)
            self._chk_spin.start()
            self._set_st("VERIFICANDO", "#fb923c")

        elif state == self.S_NONE:
            self._main_btn.setText("⬇  INSTALAR")
            self._main_btn.setMode("install")
            self._main_btn.setEnabled(True)
            self._sec_btn.hide()
            self._chk_spin.stop()
            self._set_st("PRIMERA INSTALACIÓN", "#38bdf8")
            self._log.append_log("🆕 Modpack no instalado — pulsa INSTALAR para comenzar")

        elif state == self.S_UPDATE:
            self._main_btn.setText("▶  JUGAR")
            self._main_btn.setMode("play")
            self._main_btn.setEnabled(True)
            self._sec_btn.setText("⬆  ACTUALIZAR")
            self._sec_btn.show()
            self._sec_btn.setEnabled(True)
            self._chk_spin.stop()
            self._set_st("ACTUALIZACIÓN DISPONIBLE", "#22d3ee")
            if remote_version:
                self._ver_badge.setText(f"Nueva: v{remote_version}")
                self._ver_badge.setStyleSheet("""
                    font-family:'Cascadia Code'; font-size:10px; color:#22d3ee;
                    background:rgba(6,182,212,0.09);
                    border:1px solid rgba(6,182,212,0.25);
                    border-radius:4px; padding:3px 10px;
                """)
            self._log.append_log("⬆️ Actualización disponible — se recomienda actualizar antes de jugar")

        elif state == self.S_READY:
            self._main_btn.setText("▶  JUGAR")
            self._main_btn.setMode("play")
            self._main_btn.setEnabled(True)
            self._sec_btn.setText("✅  AL DÍA")
            self._sec_btn.show()
            self._sec_btn.setEnabled(False)
            self._chk_spin.stop()
            self._set_st("LISTO PARA JUGAR", "#fb923c")
            self._log.append_log("✅ Todo al día, ¡listo para jugar!")

        elif state == self.S_BUSY:
            self._main_btn.setText("PROCESANDO...")
            self._main_btn.setEnabled(False)
            self._sec_btn.setEnabled(False)
            self._chk_spin.stop()

        elif state == self.S_ERROR:
            self._main_btn.setText("⬇  REINTENTAR")
            self._main_btn.setMode("install")
            self._main_btn.setEnabled(True)
            self._sec_btn.setEnabled(False)
            self._chk_spin.stop()
            self._set_st("ERROR", "#f87171")
            self._bar.setValue(0)
            self._pct_lbl.setText("")

    def _set_st(self, text, color):
        self._st_lbl.setText(text)
        self._st_lbl.setStyleSheet(f"""
            font-family:'Segoe UI'; font-size:10px; font-weight:700;
            color:{color}; letter-spacing:3px;
        """)

    def set_done_ok(self):
        self._bar.setValue(100)
        self._pct_lbl.setText("100%")
        self.set_state(self.S_READY)

    def set_status_text(self, text):
        self._st_lbl.setText(text.upper())

    def on_progress(self, v):
        self._bar.setValue(v)
        self._pct_lbl.setText(f"{v}%")

    def append_log(self, text):
        self._log.append_log(text)

    def update_version_badge(self, version):
        self._ver_badge.setText(f"Modpack v{version}")
        self._ver_badge.setStyleSheet("""
            font-family:'Cascadia Code'; font-size:10px; color:#fb923c;
            background:rgba(249,115,22,0.09); border:1px solid rgba(249,115,22,0.22);
            border-radius:4px; padding:3px 10px;
        """)

    def _on_main(self):
        if self._state in (self.S_NONE, self.S_ERROR):
            self.request_action.emit("install")
        elif self._state in (self.S_READY, self.S_UPDATE):
            self.request_action.emit("play")

    def _on_sec(self):
        if self._state == self.S_UPDATE:
            self.request_action.emit("update")


#   BACKGROUND

class BgPainter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(55)

    def _tick(self):
        self._t += 0.008
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#080503"))

        orbs = [
            (0.08, 0.22, 340, 42, 30, "#1c0a00", 0.45),
            (0.78, 0.08, 400, 48, 24, "#1a0800", 0.38),
            (0.58, 0.78, 300, 35, 38, "#150500", 0.32),
            (0.22, 0.68, 260, 30, 46, "#0f0400", 0.28),
            (0.88, 0.52, 220, 22, 32, "#1c0a00", 0.40),
        ]
        for bx, by, br, ax, ay, col, sp in orbs:
            ox = int(bx * w + math.sin(self._t * sp) * ax)
            oy = int(by * h + math.cos(self._t * sp * 0.75) * ay)
            c  = QColor(col)
            g  = QRadialGradient(ox, oy, br)
            g.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 95))
            g.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(ox-br, oy-br, br*2, br*2)

        p.setPen(QColor(255, 255, 255, 3))
        step = 42
        for x in range(0, w, step): p.drawLine(x, 0, x, h)
        for y in range(0, h, step): p.drawLine(0, y, w, y)


#   MAIN WINDOW

class MainWindow(QWidget):
    def __init__(self, resource_fn=None):
        super().__init__()
        self._resource_fn = resource_fn
        self.setWindowTitle("CFL Launcher")
        self.setMinimumSize(WIN_MIN_W, WIN_MIN_H)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        self._busy     = False
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        # Restaurar o calcular tamaño inicial
        screen = QApplication.primaryScreen().availableGeometry()
        def_w  = min(WIN_DEFAULT_W, int(screen.width()  * 0.85))
        def_h  = min(WIN_DEFAULT_H, int(screen.height() * 0.82))
        w = max(self._settings.value("win/w", def_w, int), WIN_MIN_W)
        h = max(self._settings.value("win/h", def_h, int), WIN_MIN_H)
        self.resize(w, h)

        self._build()
        self._restore_pos()

        # Iniciar check INMEDIATAMENTE — splash ya muestra el spinner
        QTimer.singleShot(100, self._start_check)

    # ── Persistencia ──────────────────────────────────────────────
    def _restore_pos(self):
        screen = QApplication.primaryScreen().availableGeometry()
        if self._settings.contains("win/x"):
            x = max(0, min(self._settings.value("win/x", 0, int), screen.width()  - self.width()))
            y = max(0, min(self._settings.value("win/y", 0, int), screen.height() - self.height()))
            self.move(x, y)
        else:
            self.move(
                (screen.width()  - self.width())  // 2,
                (screen.height() - self.height()) // 2,
            )

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
        p.setBrush(QColor("#080503"))
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

        # Borde decorativo
        self._border = QWidget(self)
        self._border.setGeometry(0, 0, w, h)
        self._border.setStyleSheet(
            "background:transparent;"
            "border:1px solid rgba(255,255,255,0.06);"
            "border-radius:14px;"
        )
        self._border.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Grip redimensionado
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

    # ── Check inicial: primero launcher, luego modpack ────────────
    def _start_check(self):
        self._splash.set_status("Verificando launcher...")
        self._launcher_update_thread = LauncherUpdateWorker()
        self._launcher_update_thread.status.connect(self._splash.set_status)
        self._launcher_update_thread.progress.connect(self._splash.set_progress)
        self._launcher_update_thread.done.connect(self._on_launcher_check_done)
        self._launcher_update_thread.start()

    def _on_launcher_check_done(self, updated):
        # Si updated=True el launcher ya se cerró solo (apply_update → sys.exit)
        # Si llegamos aquí: no había update o falló → continuar normal
        self._splash.set_status("Verificando modpack...")
        self._splash.hide_progress()
        self._checker = CheckWorker()
        self._checker.result.connect(self._on_check_result)
        self._checker.start()

    def _on_check_result(self, state, version):
        self._check_state   = state
        self._check_version = version
        self._splash.set_status("Listo")
        QTimer.singleShot(500, self._show_main)

    def _show_main(self):
        self._splash.stop()
        self._stack.setCurrentIndex(1)
        state   = getattr(self, "_check_state",   "ready")
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