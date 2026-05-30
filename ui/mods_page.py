# -*- coding: utf-8 -*-
"""
Página MODS: dos pestañas (Descripción / Imágenes).
- Descripción: tarjetas por categoría (ícono de color, contador, desplegable).
- Imágenes: descarga de Drive y muestra recuadros; el clic abre el visor
  (la señal open_image la consume MainScreen, que es dueño del visor).
"""
import re
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from . import theme as T
from .components import draw_icon, FlowLayout
from .gallery import GalleryWorker, Thumb
import qtawesome as qta
from core.utils import resource_path


#   Cabecera clickeable de cada tarjeta

class _CardHeader(QWidget):
    clicked = Signal()

    def __init__(self, kind, title, color, count, parent=None):
        super().__init__(parent)
        self._kind = kind; self._title = title.upper()
        self._color = color; self._count = count
        self._expanded = True
        self.setFixedHeight(56); self.setCursor(Qt.PointingHandCursor)

    def set_expanded(self, v): self._expanded = v; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.clicked.emit()

        import qtawesome as qta

        for k in sorted(qta._instance().charmap.keys()):
            if "cube" in k.lower():
                print(k)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        col = QColor(self._color)

        bs = h
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(col.red(), col.green(), col.blue(), 70))
        p.drawRoundedRect(0, 0, bs, bs, 14, 14)
        icon_map = {
            "sword": "fa5s.dragon",
            "globe": "fa5s.globe-americas",
            "shield": "fa5s.shield-alt",
            "tech": "fa5s.cube",
            "pickaxe": "fa5s.hammer",
            "grid": "fa5s.th-large"
        }

        icon_name = icon_map.get(self._kind, "fa5s.th-large")

        icon = qta.icon(
            icon_name,
            color=self._color
        )

        pm = icon.pixmap(32, 32)

        p.drawPixmap(
            int(bs * 0.20),
            int(bs * 0.20),
            pm
        )

        badge = "%d MODS" % self._count
        p.setFont(QFont(T.FONT, 11, QFont.Black))
        tw = p.fontMetrics().horizontalAdvance(badge)
        bw, bh, chev = tw + 32, 34, 26
        bx = w - chev - bw; by = (h - bh) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(col.red(), col.green(), col.blue(), 32))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 7, 7)
        p.setPen(col); p.drawText(QRectF(bx, by, bw, bh), Qt.AlignCenter, badge)

        p.setPen(col)
        ft = QFont(T.FONT, 13, QFont.Black); ft.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        p.setFont(ft)
        p.drawText(QRect(int(bs + 14), 0, int(bx - bs - 20), h),
                   Qt.AlignVCenter | Qt.AlignLeft, self._title)

        chx, chy = w - 12, h / 2
        pen = QPen(QColor(T.MUTED)); pen.setWidthF(2); pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        if self._expanded:
            p.drawLine(QPointF(chx - 6, chy - 2), QPointF(chx, chy + 3))
            p.drawLine(QPointF(chx, chy + 3), QPointF(chx + 6, chy - 2))
        else:
            p.drawLine(QPointF(chx - 6, chy + 3), QPointF(chx, chy - 2))
            p.drawLine(QPointF(chx, chy - 2), QPointF(chx + 6, chy + 3))


#   Tarjeta desplegable de una categoría

class CategoryCard(QFrame):
    def __init__(self, kind, title, color, mods, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {T.rgba(T.CARD, 0.45)};"
            f" border: 1px solid {T.BORDER}; border-radius: 18px; }}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 13, 16, 15); v.setSpacing(11)
        self._header = _CardHeader(kind, title, color, len(mods))
        self._header.clicked.connect(self._toggle)
        v.addWidget(self._header)

        sep = "<span style='color:%s;'>&nbsp;&nbsp;&bull;&nbsp;&nbsp;</span>" % color
        items = sep.join("<span style='color:%s;'>%s</span>" % (T.TEXT2, m) for m in mods)
        self._body = QLabel()
        self._body.setWordWrap(True); self._body.setTextFormat(Qt.RichText)
        self._body.setText(
            "<div style='font-family:%s; font-size:12px; line-height:172%%;'>%s</div>"
            % (T.FONT, items)
        )
        self._body.setStyleSheet(f"background:transparent; border:none; color:{T.TEXT2};")
        v.addWidget(self._body)
        self._expanded = True

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._header.set_expanded(self._expanded)


#   Banner destacado superior

class _SparkBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(40, 40)
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        ar, ag, ab = T.ACCENT_RGB
        p.setPen(Qt.NoPen); p.setBrush(QColor(ar, ag, ab, 38))
        p.drawRoundedRect(0, 0, 40, 40, 12, 12)
        draw_icon(p, "spark", 9, 9, 22, T.ACCENT_HI)




class HeroBanner(QFrame):
    def __init__(
        self,
        image_path,
        show_text=True,
        parent=None
    ):
        super().__init__(parent)

        self._pix = QPixmap(image_path)
        self._show_text = show_text

        self.setMinimumHeight(260)

        self.setStyleSheet("""
            QFrame {
                background: transparent;
                border-radius: 18px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 25)
        root.setSpacing(0)

        if self._show_text:

            root.addStretch()

            self.title = QLabel("MODS")
            self.title.setStyleSheet(f"""
                color:white;
                font-family:'{T.FONT}';
                font-size:48px;
                font-weight:900;
                background:transparent;
            """)
            root.addWidget(self.title)

            self.subtitle = QLabel("DEL MODPACK")
            self.subtitle.setStyleSheet(f"""
                color:#ff7b1f;
                font-family:'{T.FONT}';
                font-size:24px;
                font-weight:700;
                background:transparent;
            """)
            root.addWidget(self.subtitle)

            self.desc = QLabel(
                "ChafaLand Modpack Oficial · Minecraft 1.20.1"
            )

            self.desc.setStyleSheet(f"""
                color:{T.TEXT2};
                font-family:'{T.FONT}';
                font-size:11px;
                background:transparent;
            """)

            root.addWidget(self.desc)

            root.addSpacing(14)

            badges = QHBoxLayout()
            badges.setSpacing(12)

            badges.addWidget(
                self._badge(
                    "fa5s.cube",
                    "+350 MODS"
                )
            )

            badges.addWidget(
                self._badge(
                    "fa5s.folder",
                    "5 CATEGORÍAS"
                )
            )

            badges.addWidget(
                self._badge(
                    "fa5s.gamepad",
                    "1.20.1"
                )
            )

            badges.addStretch()

            root.addLayout(badges)

    def _badge(self, icon_name, text):

        frame = QFrame()

        frame.setStyleSheet("""
            QFrame{
                background:rgba(10,14,20,180);
                border:1px solid rgba(255,255,255,25);
                border-radius:12px;
            }
        """)

        frame.setFixedHeight(36)

        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        icon_lbl = QLabel()

        pm = qta.icon(
            icon_name,
            color="#ffffff"
        ).pixmap(14, 14)

        icon_lbl.setPixmap(pm)

        txt = QLabel(text)

        txt.setStyleSheet(f"""
            color:white;
            font-family:'{T.FONT}';
            font-size:10px;
            font-weight:700;
            background:transparent;
        """)

        lay.addWidget(icon_lbl)
        lay.addWidget(txt)

        return frame

    def resizeEvent(self, event):

        if self._show_text:

            w = self.width()

            title_size = max(
                28,
                min(54, int(w * 0.05))
            )

            subtitle_size = max(
                14,
                min(24, int(w * 0.025))
            )

            self.title.setStyleSheet(f"""
                color:white;
                font-family:'{T.FONT}';
                font-size:{title_size}px;
                font-weight:900;
                background:transparent;
            """)

            self.subtitle.setStyleSheet(f"""
                color:#ff7b1f;
                font-family:'{T.FONT}';
                font-size:{subtitle_size}px;
                font-weight:700;
                background:transparent;
            """)

        super().resizeEvent(event)

    def paintEvent(self, event):

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if not self._pix.isNull():

            scaled = self._pix.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2

            p.drawPixmap(
                0,
                0,
                scaled,
                x,
                y,
                self.width(),
                self.height()
            )

        g = QLinearGradient(
            0,
            0,
            0,
            self.height()
        )

        g.setColorAt(
            0.0,
            QColor(0, 0, 0, 15)
        )

        g.setColorAt(
            0.5,
            QColor(0, 0, 0, 60)
        )

        g.setColorAt(
            1.0,
            QColor(10, 14, 20, 220)
        )

        p.fillRect(
            self.rect(),
            g
        )

        super().paintEvent(event)




class FeatureBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(66)
        self.setStyleSheet(
            f"QFrame {{ background: {T.rgba(T.CARD, 0.65)};"
            f" border: 1px solid {T.BORDER}; border-radius: 14px; }}"
        )
        h = QHBoxLayout(self); h.setContentsMargins(16, 0, 20, 0); h.setSpacing(14)
        h.addWidget(_SparkBadge())
        lbl = QLabel(
            "Selección de los mods más destacados de los "
            f"<b style='color:{T.ACCENT_HI};'>+340</b> activos en el modpack."
        )
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(
            f"background:transparent; border:none; font-family:'{T.FONT}';"
            f" font-size:13px; color:{T.TEXT2};"
        )
        h.addWidget(lbl); h.addStretch()



#   PÁGINA MODS

class ModsPage(QWidget):
    open_image = Signal(list, int)   # rutas, índice -> MainScreen abre el visor

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gallery_started = False
        self._thumbs   = {}    # índice -> Thumb
        self._thumb_px = {}    # índice -> ruta local
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12);
        lay.setSpacing(0)

        hero = HeroBanner(resource_path("assets/mods_banner.png"))
        lay.addWidget(hero)
        lay.addSpacing(24)



        # Pestañas
        tabrow = QHBoxLayout(); tabrow.setSpacing(4); tabrow.setAlignment(Qt.AlignLeft)
        self._tab_desc = self._make_tab("Descripción"); self._tab_desc.setChecked(True)
        self._tab_imgs = self._make_tab("Imágenes")
        grp = QButtonGroup(self); grp.setExclusive(True)
        grp.addButton(self._tab_desc); grp.addButton(self._tab_imgs)
        tabrow.addWidget(self._tab_desc); tabrow.addWidget(self._tab_imgs); tabrow.addStretch()
        lay.addLayout(tabrow)

        line = QFrame(); line.setFixedHeight(1)
        line.setStyleSheet(f"background:{T.BORDER};")
        lay.addWidget(line); lay.addSpacing(14)

        self._stack = QStackedWidget(); self._stack.setStyleSheet("background:transparent;")
        self._stack.addWidget(self._build_desc_tab())   # 0
        self._stack.addWidget(self._build_imgs_tab())    # 1
        lay.addWidget(self._stack, 1)

        self._tab_desc.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        self._tab_imgs.clicked.connect(self._on_imgs_tab)

    def _make_tab(self, text):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)

        b.setStyleSheet(f"""
            QPushButton {{
                background:{T.rgba(T.CARD, 0.85)};
                border:1px solid {T.BORDER};
                border-bottom:none;
                border-top-left-radius:14px;
                border-top-right-radius:14px;

                color:{T.MUTED};

                font-family:'{T.FONT}';
                font-size:12px;
                font-weight:700;

                padding:12px 28px;
                min-width:110px;
            }}

            QPushButton:hover {{
                color:{T.TEXT};
                background:{T.rgba(T.CARD_HI, 0.95)};
            }}

            QPushButton:checked {{
                color:{T.ACCENT_HI};
                background:{T.rgba(T.CARD_HI, 1.0)};
                border:1px solid rgba(255,255,255,0.08);
                border-bottom:3px solid {T.ACCENT};
            }}
        """)

        return b

    # ── categoría -> (ícono, color) por palabra clave ─────────────
    def _cat_meta(self, title):
        t = title.lower()
        C = T.CATEGORIES
        if "rpg" in t or "jefe" in t:        return ("sword",   C["rpg"])
        if "explora" in t:                    return ("globe",   C["explor"])
        if "superviv" in t:                   return ("shield",  C["surviv"])
        if "tecnolog" in t:                   return ("tech",    C["tech"])
        if "construc" in t or "decora" in t:  return ("pickaxe", C["build"])
        return ("grid", C["default"])

    def _scroll(self):
        s = QScrollArea(); s.setWidgetResizable(True); s.setFrameShape(QFrame.NoFrame)
        s.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ background:transparent; width:10px; margin:0px;}}
            QScrollBar::handle:vertical {{ background:{T.rgba(T.MUTED,0.4)}; border-radius:3px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        return s

    def _build_desc_tab(self):
        try:
            from config import MODS_CATEGORIES
        except Exception:
            MODS_CATEGORIES = []
        scroll = self._scroll()
        host = QWidget(); host.setStyleSheet("background:transparent;")
        v = QVBoxLayout(host); v.setContentsMargins(0, 2, 0, 8); v.setSpacing(14)
        v.addWidget(FeatureBanner())
        for raw_title, mods in MODS_CATEGORIES:
            disp = re.sub(r'^[^0-9A-Za-zÁÉÍÓÚÑáéíóúñ]+', '', raw_title).strip()
            kind, color = self._cat_meta(disp)
            v.addWidget(CategoryCard(kind, disp, color, mods))
        v.addStretch()
        scroll.setWidget(host)
        return scroll

    def _build_imgs_tab(self):
        wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(wrap); wl.setContentsMargins(0, 0, 0, 0); wl.setSpacing(10)

        self._gallery_status = QLabel("")
        self._gallery_status.setStyleSheet(
            f"font-family:'{T.FONT_MONO}'; font-size:10px; color:{T.MUTED};"
        )
        wl.addWidget(self._gallery_status)

        scroll = self._scroll()
        self._grid_host = QWidget(); self._grid_host.setStyleSheet("background:transparent;")
        self._grid = FlowLayout(self._grid_host, margin=0, spacing=12)
        scroll.setWidget(self._grid_host)
        wl.addWidget(scroll, 1)
        return wrap

    def _on_imgs_tab(self):
        self._stack.setCurrentIndex(1)
        self._start_gallery()

    # ── galería ───────────────────────────────────────────────────
    def _start_gallery(self):
        if self._gallery_started:
            return
        self._gallery_started = True
        try:
            from config import GALLERY_IMAGES, GALLERY_DIR
        except Exception:
            GALLERY_IMAGES, GALLERY_DIR = [], "."

        if not GALLERY_IMAGES:
            self._gallery_status.setText(
                "⚠️  Aún no hay imágenes. Pega los links en config.py → GALLERY_IMAGES"
            )
            return

        for i in range(len(GALLERY_IMAGES)):
            t = Thumb(i)
            t.clicked.connect(self._open_lightbox)
            self._thumbs[i] = t
            self._grid.addWidget(t)

        self._gallery_status.setText("⬇️  Cargando imágenes… (%d)" % len(GALLERY_IMAGES))
        self._worker = GalleryWorker(GALLERY_IMAGES, GALLERY_DIR)
        self._worker.image_ready.connect(self._on_image_ready)
        self._worker.image_fail.connect(self._on_image_fail)
        self._worker.finished_all.connect(self._on_gallery_done)
        self._worker.start()

    def _on_image_ready(self, index, path):
        px = QPixmap(path)
        if px.isNull():
            self._on_image_fail(index); return
        self._thumb_px[index] = path
        if index in self._thumbs:
            self._thumbs[index].set_pixmap(px)

    def _on_image_fail(self, index):
        if index in self._thumbs:
            self._thumbs[index].set_error()

    def _on_gallery_done(self, count):
        if count == 0:
            self._gallery_status.setText("⚠️  No se pudo cargar ninguna imagen — revisa los links")
        else:
            self._gallery_status.setText("✅  %d imágenes" % count)

    def _open_lightbox(self, index):
        ordered = [self._thumb_px[i] for i in sorted(self._thumb_px.keys())]
        if not ordered:
            return
        path = self._thumb_px.get(index)
        start = ordered.index(path) if path in ordered else 0
        self.open_image.emit(ordered, start)
