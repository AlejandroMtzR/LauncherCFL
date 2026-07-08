# -*- coding: utf-8 -*-
"""
Widgets reutilizables y pintados a mano: spinner, barra de progreso, log,
botones, fondo animado, íconos vectoriales, ítem de barra lateral y layout
de flujo (para los recuadros de la galería).
"""
import math
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from . import theme as T


#   ICONOS VECTORIALES — se dibujan tintados con cualquier color

def draw_icon(p, kind, x, y, s, color):
    p.save()
    col = QColor(color)
    pen = QPen(col)
    pen.setWidthF(max(2.4, s * 0.12))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)

    def X(f): return x + s * f
    def Y(f): return y + s * f

    if kind == "home":
        p.setPen(Qt.NoPen); p.setBrush(col)
        p.drawPolygon(QPolygonF([QPointF(X(0.5), Y(0.10)), QPointF(X(0.92), Y(0.48)), QPointF(X(0.08), Y(0.48))]))
        p.drawRoundedRect(QRectF(X(0.23), Y(0.44), s * 0.54, s * 0.44), s * 0.05, s * 0.05)

    elif kind == "grid":
        p.setPen(Qt.NoPen); p.setBrush(col)
        g = s * 0.30; gap = s * 0.10; o = s * 0.15
        for ix in range(2):
            for iy in range(2):
                p.drawRoundedRect(QRectF(X(0) + o + ix * (g + gap), Y(0) + o + iy * (g + gap), g, g), g * 0.28, g * 0.28)

    elif kind == "gear":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        cx, cy = X(0.5), Y(0.5); rO = s * 0.32; rI = s * 0.21
        path = QPainterPath(); teeth = 8
        for i in range(teeth * 2):
            ang = math.pi * i / teeth
            r = rO if i % 2 == 0 else rI
            px = cx + r * math.cos(ang); py = cy + r * math.sin(ang)
            path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QPointF(cx, cy), s * 0.085, s * 0.085)

    elif kind == "sword":

        p.setPen(pen)

        p.drawLine(
            QPointF(X(0.25), Y(0.25)),
            QPointF(X(0.75), Y(0.75))
        )

        p.drawLine(
            QPointF(X(0.75), Y(0.25)),
            QPointF(X(0.25), Y(0.75))
        )

        p.drawLine(
            QPointF(X(0.18), Y(0.32)),
            QPointF(X(0.32), Y(0.18))
        )

        p.drawLine(
            QPointF(X(0.68), Y(0.82)),
            QPointF(X(0.82), Y(0.68))
        )

    elif kind == "globe":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        cx, cy = X(0.5), Y(0.5); r = s * 0.33
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.drawEllipse(QPointF(cx, cy), r * 0.45, r)
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))

    elif kind == "shield":
        p.setPen(Qt.NoPen); p.setBrush(col)
        path = QPainterPath()
        path.moveTo(X(0.5), Y(0.09))
        path.lineTo(X(0.86), Y(0.24)); path.lineTo(X(0.86), Y(0.52))
        path.cubicTo(X(0.86), Y(0.75), X(0.69), Y(0.87), X(0.5), Y(0.93))
        path.cubicTo(X(0.31), Y(0.87), X(0.14), Y(0.75), X(0.14), Y(0.52))
        path.lineTo(X(0.14), Y(0.24)); path.closeSubpath()
        p.drawPath(path)

    elif kind == "tech":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        top = QPointF(X(0.5), Y(0.10)); rt = QPointF(X(0.88), Y(0.31)); lt = QPointF(X(0.12), Y(0.31))
        b = QPointF(X(0.5), Y(0.52)); bot = QPointF(X(0.5), Y(0.91))
        br = QPointF(X(0.88), Y(0.69)); bl = QPointF(X(0.12), Y(0.69))
        p.drawPolygon(QPolygonF([top, rt, br, bot, bl, lt]))
        p.drawLine(lt, b); p.drawLine(rt, b); p.drawLine(b, bot)

    elif kind == "pickaxe":
        pen.setWidthF(max(2.8, s * 0.14))
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(X(0.30), Y(0.30)), QPointF(X(0.74), Y(0.88)))
        path = QPainterPath()
        path.moveTo(X(0.11), Y(0.42))
        path.cubicTo(X(0.34), Y(0.10), X(0.66), Y(0.10), X(0.89), Y(0.42))
        p.drawPath(path)

    elif kind == "spark":
        p.setPen(Qt.NoPen); p.setBrush(col)
        path = QPainterPath()
        pts = [(0.5, 0.06), (0.60, 0.40), (0.94, 0.5), (0.60, 0.60),
               (0.5, 0.94), (0.40, 0.60), (0.06, 0.5), (0.40, 0.40)]
        path.moveTo(X(pts[0][0]), Y(pts[0][1]))
        for fx, fy in pts[1:]:
            path.lineTo(X(fx), Y(fy))
        path.closeSubpath()
        p.drawPath(path)

    p.restore()



#   SPINNER

class Spinner(QWidget):
    def __init__(self, size=22, color=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color or T.ACCENT)
        self._size  = size
        self._t     = QTimer(self)
        self._t.timeout.connect(self._tick)
        self.hide()

    def start(self): self._t.start(18); self.show()
    def stop(self):  self._t.stop(); self.hide()

    def _tick(self):
        self._angle = (self._angle + 5) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s, m = self._size, 3
        pen = QPen(); pen.setWidth(2); pen.setCapStyle(Qt.RoundCap)
        pen.setColor(QColor(255, 255, 255, 12)); p.setPen(pen)
        p.drawEllipse(m, m, s - m * 2, s - m * 2)
        pen.setColor(self._color); p.setPen(pen)
        p.drawArc(m, m, s - m * 2, s - m * 2, (-self._angle) * 16, -270 * 16)



#   BARRA DE PROGRESO CON GLOW

class GlowBar(QWidget):
    def __init__(self, parent=None, height=10):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._val  = 0
        self._anim = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def setValue(self, v):
        self._val = max(0, min(100, v)); self.update()

    def _tick(self):
        self._anim = (self._anim + 0.025) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = max(4, h // 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 11))
        p.drawRoundedRect(0, 0, w, h, r, r)
        if self._val <= 0:
            return
        fill = int(w * self._val / 100)
        ar, ag, ab = T.ACCENT_RGB
        for i in range(4, 0, -1):
            p.setBrush(QColor(ar, ag, ab, 9 * i))
            p.drawRoundedRect(-i, -1, fill + i * 2, h + 2, r, r)
        g = QLinearGradient(0, 0, fill, 0)
        s = self._anim
        g.setColorAt(max(0.0, s - 0.4), QColor(T.ACCENT_LO))
        g.setColorAt(s,                 QColor(T.ACCENT_HI))
        g.setColorAt(min(1.0, s + 0.4), QColor(T.ACCENT_LO))
        p.setBrush(g); p.drawRoundedRect(0, 0, fill, h, r, r)



#   LOG BOX

class LogBox(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(400)
        self.setFont(QFont(T.FONT_MONO, 10))
        self.setStyleSheet(f"""
            QTextEdit {{ background: transparent; border: none; padding: 2px 0px; }}
            QScrollBar:vertical {{ background: transparent; width: 7px; }}
            QScrollBar::handle:vertical {{ background: {T.rgba(T.MUTED, 0.45)}; border-radius: 3px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def append_log(self, text):
        t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if   any(x in text for x in ["✅", "completad", "finaliz", "¡List"]): c = T.ACCENT_HI
        elif any(x in text for x in ["❌", "Error", "error", "ERROR"]):       c = T.ERROR
        elif any(x in text for x in ["⚠️", "fallback", "alternativ"]):       c = T.WARN
        elif any(x in text for x in ["⬇️", "📦", "🔄", "🆕", "💾", "🎉", "🔍"]): c = T.INFO
        elif "────" in text:                                                  c = T.DIM
        elif "|" in text and ("MB" in text or "%" in text):                  c = T.TEXT2
        else:                                                                 c = T.MUTED
        self.append(
            f'<span style="color:{c};font-family:{T.FONT_MONO},Consolas;font-size:10pt">'
            f'&gt; {t}</span>'
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())



#   PLAY BUTTON

class PlayBtn(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(190, 52)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hov = False; self._prs = False; self._ena = True
        self._pulse = 0.0; self._mode = "play"
        t = QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def setMode(self, mode): self._mode = mode; self.update()
    def _tick(self):
        self._pulse = (self._pulse + 0.03) % (2 * math.pi); self.update()
    def enterEvent(self, e): self._hov = True;  self.update()
    def leaveEvent(self, e): self._hov = False; self.update()
    def mousePressEvent(self, e):  self._prs = True;  self.update(); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e): self._prs = False; self.update(); super().mouseReleaseEvent(e)
    def setEnabled(self, v): self._ena = v; super().setEnabled(v); self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h, r = self.width(), self.height(), 10
        if not self._ena:
            p.setPen(Qt.NoPen); p.setBrush(QColor(T.CARD))
            p.drawRoundedRect(0, 0, w, h, r, r)
            p.setPen(QColor(T.DIM)); p.setFont(QFont(T.FONT, 11, QFont.Bold))
            p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self.text())
            return
        pa = int(14 + 10 * math.sin(self._pulse))
        GLOW = {"play": T.ACCENT_RGB, "install": (56, 189, 248), "update": (6, 182, 212)}.get(self._mode, T.ACCENT_RGB)
        for i in range(6, 0, -1):
            p.setBrush(QColor(*GLOW, max(0, pa - i * 2))); p.setPen(Qt.NoPen)
            p.drawRoundedRect(-i, -i, w + i * 2, h + i * 2, r + i, r + i)
        g = QLinearGradient(0, 0, w, 0)
        if self._mode == "install":
            c0, c1 = ("#0284c7", "#0369a1") if self._prs else ("#0ea5e9", "#0284c7")
        elif self._mode == "update":
            c0, c1 = ("#0891b2", "#0e7490") if self._prs else ("#06b6d4", "#0891b2")
        else:
            if self._prs:   c0, c1 = T.ACCENT_LO, "#9a3412"
            elif self._hov: c0, c1 = T.ACCENT, "#ea580c"
            else:           c0, c1 = "#ea580c", T.ACCENT_LO
        g.setColorAt(0, QColor(c0)); g.setColorAt(1, QColor(c1))
        p.setBrush(g); p.setPen(Qt.NoPen); p.drawRoundedRect(0, 0, w, h, r, r)
        hi = QLinearGradient(0, 0, 0, h)
        hi.setColorAt(0, QColor(255, 255, 255, 45)); hi.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(hi); p.drawRoundedRect(0, 0, w, h // 2 + 1, r, r)
        p.setPen(QColor("#ffffff"))

        font = QFont(T.FONT, 11)
        font.setBold(True)
        font.setLetterSpacing(
            QFont.AbsoluteSpacing,
            1.2
        )

        p.setFont(font)
        p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self.text())



#   BOTÓN SECUNDARIO

class SecBtn(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(170, 52)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.05);
                border: 1px solid {T.BORDER_HI};
                border-radius: 10px; color: {T.TEXT2};
                font-family: '{T.FONT}'; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.10); color: {T.TEXT};
                border-color: rgba(255,255,255,0.22);
            }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.03); }}
            QPushButton:disabled {{
                color: {T.DIM}; border-color: rgba(255,255,255,0.04);
                background: rgba(255,255,255,0.02);
            }}
        """)



#   TITLEBAR BUTTON

class WinBtn(QWidget):
    clicked = Signal()

    def __init__(self, symbol, hover_bg=None, hover_fg=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 38)
        self._sym   = symbol
        self._hbg   = QColor(hover_bg or "#1b2230")
        self._hfg   = QColor(hover_fg or T.TEXT)
        self._hover = False; self._press = False
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e): self._hover = True;  self.update()
    def leaveEvent(self, e): self._hover = False; self._press = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self._press = True; self.update()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._hover:
            self._press = False; self.update(); self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); w, h = self.width(), self.height()
        if self._press:   p.fillRect(0, 0, w, h, self._hbg.darker(130))
        elif self._hover: p.fillRect(0, 0, w, h, self._hbg)
        fg = self._hfg if (self._hover or self._press) else QColor(T.MUTED)
        p.setPen(fg); p.setFont(QFont(T.FONT, 10))
        p.drawText(QRect(0, 0, w, h), Qt.AlignCenter, self._sym)



#   NAV ITEM — botón de la barra lateral (ícono + texto)

class NavItem(QWidget):
    clicked = Signal()

    def __init__(self, kind, label, active=False, parent=None):
        super().__init__(parent)
        self._kind = kind; self._label = label
        self._active = active; self._hover = False
        self.setFixedHeight(46); self.setCursor(Qt.PointingHandCursor)

    def setActive(self, v): self._active = v; self.update()
    def enterEvent(self, e): self._hover = True;  self.update()
    def leaveEvent(self, e): self._hover = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        ar, ag, ab = T.ACCENT_RGB
        if self._active:
            p.setPen(Qt.NoPen); p.setBrush(QColor(ar, ag, ab, 32))
            p.drawRoundedRect(8, 4, w - 14, h - 8, 11, 11)
            p.setBrush(QColor(T.ACCENT)); p.drawRoundedRect(0, h // 2 - 12, 4, 24, 2, 2)
        elif self._hover:
            p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 11))
            p.drawRoundedRect(8, 4, w - 14, h - 8, 11, 11)
        icol = T.ACCENT_HI if self._active else (T.TEXT if self._hover else T.MUTED)
        draw_icon(p, self._kind, 20, h / 2 - 10, 20, icol)
        p.setPen(QColor(icol))
        f = QFont(T.FONT, 10, QFont.Bold); f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f)
        p.drawText(QRect(54, 0, w - 60, h), Qt.AlignVCenter | Qt.AlignLeft, self._label)



#   BACKGROUND animado (gris/azul)

class BgPainter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(55)

    def _tick(self):
        self._t += 0.008; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(T.BG))
        orbs = [

        ]
        for bx, by, br, ax, ay, col, sp in orbs:
            ox = int(bx * w + math.sin(self._t * sp) * ax)
            oy = int(by * h + math.cos(self._t * sp * 0.75) * ay)
            c = QColor(col)
            g = QRadialGradient(ox, oy, br)
            g.setColorAt(0, QColor(c.red(), c.green(), c.blue(), 110))
            g.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(ox - br, oy - br, br * 2, br * 2)
        p.setPen(QColor(255, 255, 255, 3))
        step = 42
        #for x in range(0, w, step): p.drawLine(x, 0, x, h)
        #for y in range(0, h, step): p.drawLine(0, y, w, y)



#   FLOW LAYOUT — acomoda los recuadros y los envuelve a la siguiente fila

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=12):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def addItem(self, item):       self._items.append(item)
    def count(self):               return len(self._items)
    def itemAt(self, i):           return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i):           return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self):   return True
    def heightForWidth(self, w):   return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect); self._do(rect, False)

    def sizeHint(self):    return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        s += QSize(m.left() + m.right(), m.top() + m.bottom())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self._items:
            wq = it.sizeHint().width(); hq = it.sizeHint().height()
            nx = x + wq + sp
            if nx - sp > rect.right() and line_h > 0:
                x = rect.x(); y = y + line_h + sp
                nx = x + wq + sp; line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), it.sizeHint()))
            x = nx; line_h = max(line_h, hq)
        return y + line_h - rect.y()
