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

    elif kind == "cube":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        top = QPointF(X(0.5), Y(0.08))
        right = QPointF(X(0.86), Y(0.29))
        center = QPointF(X(0.5), Y(0.50))
        left = QPointF(X(0.14), Y(0.29))
        bottom = QPointF(X(0.5), Y(0.91))
        p.drawPolygon(QPolygonF([top, right, center, left]))
        p.drawPolygon(QPolygonF([left, center, bottom, QPointF(X(0.14), Y(0.69))]))
        p.drawPolygon(QPolygonF([right, QPointF(X(0.86), Y(0.69)), bottom, center]))
        p.drawLine(center, bottom)

    elif kind == "puzzle":
        p.setPen(Qt.NoPen); p.setBrush(col)
        path = QPainterPath()
        path.moveTo(X(0.20), Y(0.20))
        path.lineTo(X(0.40), Y(0.20))
        path.cubicTo(X(0.39), Y(0.08), X(0.61), Y(0.08), X(0.60), Y(0.20))
        path.lineTo(X(0.80), Y(0.20))
        path.lineTo(X(0.80), Y(0.40))
        path.cubicTo(X(0.92), Y(0.39), X(0.92), Y(0.61), X(0.80), Y(0.60))
        path.lineTo(X(0.80), Y(0.80))
        path.lineTo(X(0.58), Y(0.80))
        path.cubicTo(X(0.59), Y(0.68), X(0.41), Y(0.68), X(0.42), Y(0.80))
        path.lineTo(X(0.20), Y(0.80))
        path.lineTo(X(0.20), Y(0.58))
        path.cubicTo(X(0.08), Y(0.59), X(0.08), Y(0.41), X(0.20), Y(0.42))
        path.closeSubpath()
        p.drawPath(path)

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

    elif kind == "check-circle":
        pen.setWidthF(max(2.0, s * 0.10))
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        cx, cy = X(0.5), Y(0.5)
        p.drawEllipse(QPointF(cx, cy), s * 0.36, s * 0.36)
        p.drawLine(QPointF(X(0.31), Y(0.51)), QPointF(X(0.45), Y(0.65)))
        p.drawLine(QPointF(X(0.45), Y(0.65)), QPointF(X(0.72), Y(0.36)))

    elif kind == "warning":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF([
            QPointF(X(0.50), Y(0.12)),
            QPointF(X(0.88), Y(0.82)),
            QPointF(X(0.12), Y(0.82)),
        ]))
        p.drawLine(QPointF(X(0.50), Y(0.34)), QPointF(X(0.50), Y(0.57)))
        p.drawPoint(QPointF(X(0.50), Y(0.69)))

    elif kind == "download":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(X(0.50), Y(0.13)), QPointF(X(0.50), Y(0.62)))
        p.drawLine(QPointF(X(0.30), Y(0.43)), QPointF(X(0.50), Y(0.63)))
        p.drawLine(QPointF(X(0.70), Y(0.43)), QPointF(X(0.50), Y(0.63)))
        p.drawLine(QPointF(X(0.18), Y(0.78)), QPointF(X(0.82), Y(0.78)))
        p.drawLine(QPointF(X(0.18), Y(0.66)), QPointF(X(0.18), Y(0.78)))
        p.drawLine(QPointF(X(0.82), Y(0.66)), QPointF(X(0.82), Y(0.78)))

    elif kind == "file":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(X(0.22), Y(0.12))
        path.lineTo(X(0.61), Y(0.12))
        path.lineTo(X(0.80), Y(0.31))
        path.lineTo(X(0.80), Y(0.88))
        path.lineTo(X(0.22), Y(0.88))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(X(0.61), Y(0.12)), QPointF(X(0.61), Y(0.31)))
        p.drawLine(QPointF(X(0.61), Y(0.31)), QPointF(X(0.80), Y(0.31)))
        p.drawLine(QPointF(X(0.34), Y(0.49)), QPointF(X(0.68), Y(0.49)))
        p.drawLine(QPointF(X(0.34), Y(0.64)), QPointF(X(0.62), Y(0.64)))

    elif kind == "monitor":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(X(0.13), Y(0.20), s * 0.74, s * 0.49), s * 0.05, s * 0.05)
        p.drawLine(QPointF(X(0.50), Y(0.69)), QPointF(X(0.50), Y(0.82)))
        p.drawLine(QPointF(X(0.33), Y(0.84)), QPointF(X(0.67), Y(0.84)))

    elif kind == "folder":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(X(0.12), Y(0.27))
        path.lineTo(X(0.39), Y(0.27))
        path.lineTo(X(0.47), Y(0.38))
        path.lineTo(X(0.88), Y(0.38))
        path.lineTo(X(0.88), Y(0.80))
        path.lineTo(X(0.12), Y(0.80))
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(X(0.12), Y(0.38)), QPointF(X(0.88), Y(0.38)))

    elif kind == "java":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(X(0.34), Y(0.14)), QPointF(X(0.27), Y(0.27)))
        p.drawLine(QPointF(X(0.51), Y(0.12)), QPointF(X(0.44), Y(0.28)))
        p.drawLine(QPointF(X(0.67), Y(0.15)), QPointF(X(0.60), Y(0.28)))
        p.drawRoundedRect(QRectF(X(0.22), Y(0.43), s * 0.48, s * 0.25), s * 0.05, s * 0.05)
        path = QPainterPath()
        path.moveTo(X(0.70), Y(0.48))
        path.cubicTo(X(0.90), Y(0.46), X(0.90), Y(0.66), X(0.70), Y(0.63))
        p.drawPath(path)
        p.drawLine(QPointF(X(0.18), Y(0.78)), QPointF(X(0.78), Y(0.78)))

    elif kind == "clock":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        cx, cy = X(0.5), Y(0.5)
        p.drawEllipse(QPointF(cx, cy), s * 0.35, s * 0.35)
        p.drawLine(QPointF(cx, cy), QPointF(X(0.50), Y(0.29)))
        p.drawLine(QPointF(cx, cy), QPointF(X(0.66), Y(0.58)))

    elif kind == "layers":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygonF([
            QPointF(X(0.50), Y(0.12)),
            QPointF(X(0.84), Y(0.30)),
            QPointF(X(0.50), Y(0.48)),
            QPointF(X(0.16), Y(0.30)),
        ]))
        p.drawPolyline(QPolygonF([QPointF(X(0.18), Y(0.47)), QPointF(X(0.50), Y(0.64)), QPointF(X(0.82), Y(0.47))]))
        p.drawPolyline(QPolygonF([QPointF(X(0.18), Y(0.63)), QPointF(X(0.50), Y(0.80)), QPointF(X(0.82), Y(0.63))]))

    elif kind == "anvil":
        p.setPen(Qt.NoPen); p.setBrush(col)
        p.drawPolygon(QPolygonF([
            QPointF(X(0.12), Y(0.32)),
            QPointF(X(0.75), Y(0.32)),
            QPointF(X(0.91), Y(0.42)),
            QPointF(X(0.72), Y(0.52)),
            QPointF(X(0.58), Y(0.52)),
            QPointF(X(0.58), Y(0.64)),
            QPointF(X(0.72), Y(0.64)),
            QPointF(X(0.72), Y(0.77)),
            QPointF(X(0.24), Y(0.77)),
            QPointF(X(0.24), Y(0.64)),
            QPointF(X(0.39), Y(0.64)),
            QPointF(X(0.39), Y(0.52)),
            QPointF(X(0.18), Y(0.52)),
        ]))

    elif kind == "dots":
        p.setPen(Qt.NoPen); p.setBrush(col)
        for fx in (0.28, 0.50, 0.72):
            p.drawEllipse(QPointF(X(fx), Y(0.5)), s * 0.06, s * 0.06)

    elif kind == "chevron-down":
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(X(0.22), Y(0.38)), QPointF(X(0.50), Y(0.66)))
        p.drawLine(QPointF(X(0.78), Y(0.38)), QPointF(X(0.50), Y(0.66)))

    p.restore()


def icon_pixmap(kind, size=18, color=None):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    draw_icon(p, kind, 1, 1, size - 2, color or T.MUTED)
    p.end()
    return pm


def make_icon(kind, size=18, color=None):
    return QIcon(icon_pixmap(kind, size, color))


class IconLabel(QWidget):
    def __init__(self, kind, size=18, color=None, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._size = size
        self._color = color or T.MUTED
        self.setFixedSize(size, size)

    def setIcon(self, kind=None, color=None):
        if kind is not None:
            self._kind = kind
        if color is not None:
            self._color = color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_icon(p, self._kind, 1, 1, self._size - 2, self._color)



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

    def show(self):
        if self.parentWidget() is None:
            return
        super().show()

    def start(self):
        self._t.start(18)
        self.show()

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
        # El brillo solo se anima mientras hay progreso visible; antes el
        # timer repintaba 25 veces/s siempre, aunque la barra estuviera oculta.
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)

    def setValue(self, v):
        self._val = max(0, min(100, int(v))); self._sync_timer(); self.update()

    def _sync_timer(self):
        animate = self.isVisible() and 0 < self._val < 100
        if animate and not self._timer.isActive():
            self._timer.start(40)
        elif not animate and self._timer.isActive():
            self._timer.stop()

    def showEvent(self, e):
        super().showEvent(e); self._sync_timer()

    def hideEvent(self, e):
        super().hideEvent(e); self._sync_timer()

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
        bar = self.verticalScrollBar()
        # Solo seguir al final si el usuario no subió a leer algo anterior.
        at_bottom = bar.value() >= bar.maximum() - 4
        self.append(
            f'<span style="color:{c};font-family:{T.FONT_MONO},Consolas;font-size:10pt">'
            f'&gt; {t}</span>'
        )
        if at_bottom:
            bar.setValue(bar.maximum())



#   PLAY BUTTON

class PlayBtn(QPushButton):
    # Paletas por modo: (base, borde_top_claro, base_oscuro)
    _PALETTE = {
        "play":    ("#f97316", "#fb923c", "#ea580c"),
        "install": ("#0ea5e9", "#38bdf8", "#0284c7"),
        "update":  ("#06b6d4", "#22d3ee", "#0891b2"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(190, 52)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hov = False; self._prs = False; self._ena = True
        self._mode = "play"
        self._round = "both"   # "both" | "left" | "right" (para split-button)

    def setMode(self, mode): self._mode = mode; self.update()
    def setRoundSide(self, side): self._round = side; self.update()
    def enterEvent(self, e): self._hov = True;  self.update()
    def leaveEvent(self, e): self._hov = False; self.update()
    def mousePressEvent(self, e):  self._prs = True;  self.update(); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e): self._prs = False; self.update(); super().mouseReleaseEvent(e)
    def setEnabled(self, v): self._ena = v; super().setEnabled(v); self.update()

    def _shift(self, hex_color, amount):
        """Aclara (+) u oscurece (-) un color hex."""
        c = QColor(hex_color)
        f = 1.0 + amount / 100.0
        return QColor(
            max(0, min(255, int(c.red()   * f))),
            max(0, min(255, int(c.green() * f))),
            max(0, min(255, int(c.blue()  * f))),
        )

    def _shape_path(self, w, h, r):
        """Rectángulo redondeado con esquinas selectivas según self._round."""
        rl = r if self._round in ("both", "left") else 0
        rr = r if self._round in ("both", "right") else 0
        path = QPainterPath()
        path.moveTo(rl, 0)
        path.lineTo(w - rr, 0)
        if rr: path.quadTo(w, 0, w, rr)
        else:  path.lineTo(w, 0)
        path.lineTo(w, h - rr)
        if rr: path.quadTo(w, h, w - rr, h)
        else:  path.lineTo(w, h)
        path.lineTo(rl, h)
        if rl: path.quadTo(0, h, 0, h - rl)
        else:  path.lineTo(0, h)
        path.lineTo(0, rl)
        if rl: path.quadTo(0, 0, rl, 0)
        else:  path.lineTo(0, 0)
        path.closeSubpath()
        return path

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h, r = self.width(), self.height(), 8
        label = self.text()
        path = self._shape_path(w, h, r)

        # ── Deshabilitado / "EN EJECUCIÓN" ────────────────────────
        if not self._ena:
            p.setPen(Qt.NoPen); p.setBrush(QColor(T.CARD_HI)); p.drawPath(path)
            pen = QPen(QColor(T.BORDER)); p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawPath(path)
            font = QFont(T.FONT, 10); font.setBold(True)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
            p.setFont(font); p.setPen(QColor(T.MUTED))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, label)
            return

        base, light, dark = self._PALETTE.get(self._mode, self._PALETTE["play"])

        # Estado: hover aclara, pressed oscurece (mismo esquema que la flecha)
        if self._prs:
            top, bot = self._shift(base, -12), self._shift(dark, -12)
        elif self._hov:
            top, bot = QColor(light), QColor(base)
        else:
            top, bot = QColor(base), QColor(dark)

        # Relleno plano con gradiente vertical sutil (sin glow, sin glossy)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, top); g.setColorAt(1.0, bot)
        p.setBrush(g); p.setPen(Qt.NoPen); p.drawPath(path)

        # Línea superior 1px levemente clara: relieve limpio
        p.setPen(QColor(255, 255, 255, 28)); p.setBrush(Qt.NoBrush)
        p.drawLine(int(r * 0.7), 1, int(w - r * 0.7), 1)

        # ── Texto (+ triángulo de play solo en modo "play") ───────
        font = QFont(T.FONT, 11); font.setBold(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        p.setFont(font)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(label)

        show_icon = (self._mode == "play")
        icon_w, gap = (13, 11) if show_icon else (0, 0)
        total = icon_w + gap + tw
        x0 = (w - total) / 2.0
        cy = h / 2.0

        if show_icon:
            p.setPen(Qt.NoPen); p.setBrush(QColor("#ffffff"))
            tri = QPolygonF([
                QPointF(x0, cy - 7),
                QPointF(x0, cy + 7),
                QPointF(x0 + icon_w, cy),
            ])
            p.drawPolygon(tri)

        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(x0 + icon_w + gap, 0, tw + 4, h),
                   Qt.AlignVCenter | Qt.AlignLeft, label)



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

    def setSymbol(self, symbol): self._sym = symbol; self.update()
    def enterEvent(self, e): self._hover = True;  self.update()
    def leaveEvent(self, e): self._hover = False; self._press = False; self.update()
    def mouseDoubleClickEvent(self, e): e.accept()   # no maximizar al doble clic
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
    # Fondo estático. Antes un timer lo repintaba 18 veces por segundo (sin
    # nada animado), lo que obligaba a redibujar TODA la ventana — banners
    # incluidos — sin parar y gastaba CPU/GPU en segundo plano.
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T.BG))



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
