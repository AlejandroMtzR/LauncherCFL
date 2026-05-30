# -*- coding: utf-8 -*-
"""
Galería de imágenes: descarga (con caché) imágenes públicas de Google Drive,
las muestra como recuadros y abre un visor grande con cerrar / siguiente /
anterior. No abre el navegador ni enlaza a Drive: solo descarga y muestra.
"""
import os
import re
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from . import theme as T


#   DRIVE — utilidades de descarga

def extract_drive_id(s):
    """Acepta un link de Drive (cualquier formato) o un ID pelado -> ID."""
    if not s:
        return None
    s = str(s).strip()
    m = re.search(r'/file/d/([a-zA-Z0-9_\-]+)', s)
    if m: return m.group(1)
    m = re.search(r'[?&]id=([a-zA-Z0-9_\-]+)', s)
    if m: return m.group(1)
    m = re.search(r'/folders/([a-zA-Z0-9_\-]+)', s)
    if m: return m.group(1)
    if re.fullmatch(r'[a-zA-Z0-9_\-]{20,}', s):
        return s
    return None


def drive_download(file_id, dest):
    """Descarga un archivo público de Drive (maneja la página de 'confirmar')."""
    base = "https://drive.google.com/uc?export=download&id=" + file_id
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        import requests
        s = requests.Session()
        r = s.get(base, headers=headers, stream=True, timeout=30)
        token = None
        for k, v in r.cookies.items():
            if k.startswith("download_warning"):
                token = v
        if "text/html" in r.headers.get("Content-Type", ""):
            txt = r.text
            if token is None:
                mt = re.search(r'confirm=([0-9A-Za-z_\-]+)', txt)
                if mt: token = mt.group(1)
            ma = re.search(r'action="(https://drive\.usercontent\.google\.com/download[^"]+)"', txt)
            if ma:
                action = ma.group(1).replace("&amp;", "&")
                fields = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', txt))
                r = s.get(action, params=fields, headers=headers, stream=True, timeout=60)
                token = "ok"
            if token and token != "ok":
                r = s.get(base + "&confirm=" + token, headers=headers, stream=True, timeout=60)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except ImportError:
        pass
    except Exception:
        pass
    # fallback urllib
    import urllib.request
    req = urllib.request.Request(base, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        f.write(resp.read())
    return os.path.exists(dest) and os.path.getsize(dest) > 0


class GalleryWorker(QThread):
    """Descarga (con caché) las imágenes de la lista en segundo plano."""
    image_ready  = Signal(int, str)   # índice, ruta local
    image_fail   = Signal(int)        # índice
    finished_all = Signal(int)        # cuántas se cargaron

    def __init__(self, items, dest_dir):
        super().__init__()
        self._items = list(items)
        self._dest  = dest_dir

    def run(self):
        ok = 0
        for i, raw in enumerate(self._items):
            fid = extract_drive_id(raw)
            if not fid:
                self.image_fail.emit(i); continue
            path = os.path.join(self._dest, "img_%s.jpg" % fid)
            try:
                if not (os.path.exists(path) and os.path.getsize(path) > 0):
                    drive_download(fid, path)
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    self.image_ready.emit(i, path); ok += 1
                else:
                    self.image_fail.emit(i)
            except Exception:
                self.image_fail.emit(i)
        self.finished_all.emit(ok)



#   THUMB — recuadro clickeable

class Thumb(QWidget):
    clicked = Signal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self._index = index
        self._pix   = None
        self._state = "load"   # load | ok | error
        self._hover = False
        self.setFixedSize(178, 110)
        self.setCursor(Qt.PointingHandCursor)

    def set_pixmap(self, pix): self._pix = pix; self._state = "ok"; self.update()
    def set_error(self):       self._state = "error"; self.update()
    def enterEvent(self, e):   self._hover = True;  self.update()
    def leaveEvent(self, e):   self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._state == "ok":
            self.clicked.emit(self._index)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h, r = self.width(), self.height(), 8
        path = QPainterPath(); path.addRoundedRect(0, 0, w, h, r, r)
        p.setClipPath(path)
        p.fillRect(0, 0, w, h, QColor(T.CARD))
        if self._state == "ok" and self._pix and not self._pix.isNull():
            scaled = self._pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            ox = (scaled.width() - w) // 2; oy = (scaled.height() - h) // 2
            p.drawPixmap(-ox, -oy, scaled)
            if self._hover:
                ar, ag, ab = T.ACCENT_RGB
                p.fillRect(0, 0, w, h, QColor(ar, ag, ab, 38))
                p.setPen(QColor("#ffffff")); p.setFont(QFont(T.FONT, 18))
                p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, "⤢")
        else:
            p.setPen(QColor(T.MUTED)); p.setFont(QFont(T.FONT, 9))
            msg = "Descargando…" if self._state == "load" else "No disponible"
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, msg)
        p.setClipping(False)
        ar, ag, ab = T.ACCENT_RGB
        p.setPen(QPen(QColor(ar, ag, ab, 160 if self._hover else 40), 1)); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(0, 0, w - 1, h - 1, r, r)



#   LIGHTBOX — visor de imagen grande (cerrar / siguiente / anterior)

class Lightbox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths = []; self._idx = 0
        self.hide()
        self.setFocusPolicy(Qt.StrongFocus)

        self._img = QLabel(self)
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setStyleSheet("background:transparent;")

        def navbtn(sym):
            b = QPushButton(sym, self)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{ background:{T.rgba(T.SURFACE,0.9)}; color:{T.TEXT};
                    border:1px solid {T.rgba(T.ACCENT,0.35)}; border-radius:22px;
                    font-size:20px; font-weight:bold; }}
                QPushButton:hover {{ background:{T.rgba(T.ACCENT,0.85)}; color:#fff;
                    border-color:{T.ACCENT_HI}; }}
            """)
            return b

        self._prev_b  = navbtn("‹"); self._prev_b.setFixedSize(44, 44)
        self._next_b  = navbtn("›"); self._next_b.setFixedSize(44, 44)
        self._close_b = navbtn("✕"); self._close_b.setFixedSize(40, 40)
        self._prev_b.clicked.connect(self.prev)
        self._next_b.clicked.connect(self.next)
        self._close_b.clicked.connect(self.close_box)

        self._counter = QLabel(self)
        self._counter.setAlignment(Qt.AlignCenter)
        self._counter.setStyleSheet(f"""
            color:{T.ACCENT_HI}; font-family:'{T.FONT_MONO}'; font-size:11px;
            background:{T.rgba(T.SURFACE,0.9)}; border-radius:11px; padding:4px 12px;
            letter-spacing:1px;
        """)

    def open_at(self, paths, idx):
        self._paths = list(paths)
        self._idx = max(0, min(idx, len(self._paths) - 1))
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show(); self.raise_(); self.setFocus(); self._refresh()

    def close_box(self): self.hide()

    def next(self):
        if self._paths:
            self._idx = (self._idx + 1) % len(self._paths); self._refresh()

    def prev(self):
        if self._paths:
            self._idx = (self._idx - 1) % len(self._paths); self._refresh()

    def _refresh(self):
        if not self._paths:
            return
        self._counter.setText(" %d / %d " % (self._idx + 1, len(self._paths)))
        multi = len(self._paths) > 1
        self._prev_b.setVisible(multi); self._next_b.setVisible(multi)
        self._layout_controls()

    def _layout_controls(self):
        w, h = self.width(), self.height(); margin = 70
        if self._paths:
            px = QPixmap(self._paths[self._idx])
            if not px.isNull():
                px = px.scaled(max(50, w - margin * 2), max(50, h - margin * 2),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._img.setPixmap(px)
        self._img.setGeometry(margin, margin, max(50, w - margin * 2), max(50, h - margin * 2))
        self._prev_b.move(18, h // 2 - 22)
        self._next_b.move(w - 18 - 44, h // 2 - 22)
        self._close_b.move(w - 18 - 40, 18)
        self._counter.adjustSize()
        self._counter.move((w - self._counter.width()) // 2, h - 44)

    def resizeEvent(self, e):
        super().resizeEvent(e); self._layout_controls()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:  self.close_box()
        elif e.key() == Qt.Key_Right: self.next()
        elif e.key() == Qt.Key_Left:  self.prev()

    def mousePressEvent(self, e):
        if not self._img.geometry().contains(e.position().toPoint()):
            self.close_box()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r, g, b = T.rgb(T.BG)
        p.setBrush(QColor(r, g, b, 240))
        p.drawRoundedRect(self.rect(), 14, 14)
