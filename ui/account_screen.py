
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QStackedWidget, QFrame, QFileDialog, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QIcon

from . import theme as T
from core import accounts

try:
    from .screens import get_logo
except Exception:
    def get_logo(resource_fn=None):
        return ""


# ═══════════════════════════════════════════════════════════════════════════
#  AVATAR  (identicon determinista desde el UUID, o cara real de la skin)
# ═══════════════════════════════════════════════════════════════════════════
class Avatar(QWidget):
    def __init__(self, size=132, parent=None):
        super().__init__(parent)
        self._px = size
        self.setFixedSize(size, size)
        self._uuid = ""
        self._skin_face = None  # QPixmap 8x8 o None

    def set_name(self, name: str):
        self._uuid = accounts.offline_uuid(name) if accounts.is_valid_name(name) else ""
        self.update()

    def set_skin(self, path: str):
        self._skin_face = self._face_from_skin(path)
        self.update()

    def clear_skin(self):
        self._skin_face = None
        self.update()

    @staticmethod
    def _face_from_skin(path):
        img = QImage(path)
        if img.isNull() or img.width() < 64:
            return None
        face = img.copy(8, 8, 8, 8)
        hat = img.copy(40, 8, 8, 8)
        base = QImage(8, 8, QImage.Format_ARGB32)
        base.fill(Qt.transparent)
        p = QPainter(base)
        p.drawImage(0, 0, face)
        p.drawImage(0, 0, hat)
        p.end()
        return QPixmap.fromImage(base)

    def _hue_color(self, seed_byte, s=150, v=225):
        return QColor.fromHsv(int(seed_byte / 255 * 359), s, v)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w = self._px
        r = 16

        # marco/tarjeta
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.CARD_HI))
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawRoundedRect(0, 0, w, w, r, r)
        p.setRenderHint(QPainter.Antialiasing, False)

        inner = 14
        cell_area = w - inner * 2

        if self._skin_face is not None:
            scaled = self._skin_face.scaled(cell_area, cell_area,
                                            Qt.KeepAspectRatio, Qt.FastTransformation)
            p.drawPixmap(inner, inner, scaled)
            return

        if not self._uuid:
            # placeholder tenue
            p.setPen(QColor(T.MUTED))
            f = self.font(); f.setPointSize(int(w * 0.32)); p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "?")
            return

        # identicon 8x8 espejado (4 columnas -> 8) desde el hash del uuid
        h = self._uuid.replace("-", "")
        data = bytes.fromhex(h)  # 16 bytes
        accent = self._hue_color(data[0])
        cell = cell_area / 8.0
        p.setPen(Qt.NoPen)
        for y in range(8):
            for x in range(4):
                idx = (y * 4 + x) % len(data)
                if data[idx] & 0x80:
                    p.setBrush(accent if (data[idx] & 0x40) else accent.darker(135))
                    for cx in (x, 7 - x):  # espejo horizontal
                        p.drawRect(int(inner + cx * cell), int(inner + y * cell),
                                   int(cell + 1), int(cell + 1))


# ═══════════════════════════════════════════════════════════════════════════
#  TARJETA DE ELECCIÓN  (premium / offline) — clickeable, con hover
# ═══════════════════════════════════════════════════════════════════════════
class ChoiceCard(QFrame):
    clicked = Signal()

    def __init__(self, glyph, title, subtitle, note, accent, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(260, 230)
        self._accent = accent
        self.setProperty("hover", "false")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 26, 24, 24)
        lay.setSpacing(10)

        ic = QLabel(glyph)
        ic.setAlignment(Qt.AlignLeft)
        ic.setStyleSheet(f"font-size:40px; color:{accent}; background:transparent;")
        lay.addWidget(ic)
        lay.addSpacing(4)

        t = QLabel(title)
        t.setStyleSheet(f"font-family:'{T.FONT}'; font-size:18px; font-weight:800;"
                        f" color:{T.TEXT}; background:transparent;")
        lay.addWidget(t)

        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; color:{T.TEXT2};"
                        f" background:transparent;")
        lay.addWidget(s)

        lay.addStretch(1)

        n = QLabel(note)
        n.setWordWrap(True)
        n.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; color:{T.MUTED};"
                        f" letter-spacing:0.5px; background:transparent;")
        lay.addWidget(n)

        self._restyle()

    def _restyle(self):
        hover = self.property("hover") == "true"
        bg = T.CARD_HI if hover else T.CARD
        border = self._accent if hover else T.BORDER
        self.setStyleSheet(f"""
            ChoiceCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}
        """)

    def enterEvent(self, e):
        self.setProperty("hover", "true"); self._restyle(); super().enterEvent(e)

    def leaveEvent(self, e):
        self.setProperty("hover", "false"); self._restyle(); super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


# ═══════════════════════════════════════════════════════════════════════════
#  PANTALLA
# ═══════════════════════════════════════════════════════════════════════════
class AccountScreen(QWidget):
    account_ready = Signal(object)  # emite un accounts.Account

    def __init__(self, resource_fn=None, parent=None):
        super().__init__(parent)
        self._resource_fn = resource_fn
        self._skin_path = ""
        self._build()

    # ── construcción ──────────────────────────────────────────────
    def _build(self):
        # Scrim para que el texto se lea sobre el banner
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._scrim = QWidget(self)
        self._scrim.setStyleSheet(f"background: {T.rgba(T.BG, 0.82)};")
        root.addWidget(self._scrim)

        outer = QVBoxLayout(self._scrim)
        outer.setAlignment(Qt.AlignCenter)

        self._steps = QStackedWidget()
        self._steps.setStyleSheet("background:transparent;")
        self._steps.addWidget(self._build_choice())
        self._steps.addWidget(self._build_offline())
        outer.addWidget(self._steps, alignment=Qt.AlignCenter)

    def _eyebrow(self):
        e = QLabel("CFL LAUNCHER")
        e.setAlignment(Qt.AlignCenter)
        e.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; font-weight:600;"
                        f" color:{T.ACCENT_HI}; letter-spacing:6px; background:transparent;")
        return e

    # ── PASO 1: elección ──────────────────────────────────────────
    def _build_choice(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)

        lay.addWidget(self._eyebrow())

        title = QLabel("¿Cómo quieres jugar?")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:30px; font-weight:900;"
                            f" color:{T.TEXT}; letter-spacing:1px; background:transparent;")
        lay.addWidget(title)
        lay.addSpacing(2)

        sub = QLabel("Elige una opción para continuar al modpack")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:13px; color:{T.TEXT2};"
                          f" background:transparent;")
        lay.addWidget(sub)
        lay.addSpacing(26)

        cards = QHBoxLayout()
        cards.setSpacing(20)
        cards.setAlignment(Qt.AlignCenter)

        premium = ChoiceCard(
            "◆", "Cuenta premium",
            "Inicia con tu cuenta de Microsoft.",
            "SKINS OFICIALES · SERVIDORES ONLINE", T.INFO)
        offline = ChoiceCard(
            "▶", "Modo offline",
            "Elige un nombre y juega sin cuenta.",
            "PARA CHAFALAND Y SERVERS OFFLINE", T.ACCENT)

        premium.clicked.connect(self._choose_premium)
        offline.clicked.connect(self._goto_offline)
        cards.addWidget(premium)
        cards.addWidget(offline)
        lay.addLayout(cards)
        lay.addSpacing(18)

        foot = QLabel("El modo offline requiere tener el juego. Úsalo solo entre amigos "
                      "en el server privado.")
        foot.setAlignment(Qt.AlignCenter)
        foot.setWordWrap(True)
        foot.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; color:{T.DIM};"
                           f" background:transparent;")
        foot.setMaximumWidth(540)
        lay.addWidget(foot, alignment=Qt.AlignCenter)

        return page

    # ── PASO 2: offline ───────────────────────────────────────────
    def _build_offline(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(4)

        lay.addWidget(self._eyebrow())
        title = QLabel("Jugar en modo offline")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:26px; font-weight:900;"
                            f" color:{T.TEXT}; background:transparent;")
        lay.addWidget(title)
        lay.addSpacing(20)

        # Tarjeta central: avatar + formulario
        card = QFrame()
        card.setFixedWidth(560)
        card.setStyleSheet(f"""
            QFrame {{
                background: {T.CARD};
                border: 1px solid {T.BORDER};
                border-radius: 18px;
            }}
        """)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(28, 28, 28, 28)
        cl.setSpacing(26)

        # Izquierda: avatar
        left = QVBoxLayout()
        left.setAlignment(Qt.AlignTop)
        self._avatar = Avatar(132)
        left.addWidget(self._avatar, alignment=Qt.AlignCenter)
        left.addSpacing(10)

        self._skin_btn = QPushButton("Subir skin (.png)")
        self._skin_btn.setCursor(Qt.PointingHandCursor)
        self._skin_btn.setFixedWidth(132)
        self._skin_btn.setStyleSheet(self._ghost_btn_qss())
        self._skin_btn.clicked.connect(self._pick_skin)
        left.addWidget(self._skin_btn, alignment=Qt.AlignCenter)

        self._skin_lbl = QLabel("Steve por defecto")
        self._skin_lbl.setAlignment(Qt.AlignCenter)
        self._skin_lbl.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px;"
                                     f" color:{T.MUTED}; background:transparent;")
        left.addWidget(self._skin_lbl)
        cl.addLayout(left)

        # Derecha: formulario
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignTop)
        right.setSpacing(8)

        lab = QLabel("Nombre de jugador")
        lab.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; font-weight:600;"
                          f" color:{T.TEXT2}; background:transparent;")
        right.addWidget(lab)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Ej. ChafaPlayer")
        self._name.setMaxLength(16)
        self._name.setStyleSheet(self._input_qss(T.BORDER))
        self._name.textChanged.connect(self._on_name_changed)
        self._name.returnPressed.connect(self._confirm)
        right.addWidget(self._name)

        self._hint = QLabel("3–16 caracteres · letras, números o _")
        self._hint.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                                 f" color:{T.MUTED}; background:transparent;")
        right.addWidget(self._hint)
        right.addSpacing(14)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        back = QPushButton("Volver")
        back.setCursor(Qt.PointingHandCursor)
        back.setStyleSheet(self._ghost_btn_qss())
        back.clicked.connect(lambda: self._steps.setCurrentIndex(0))
        btns.addWidget(back)

        self._play = QPushButton("Guardar y jugar")
        self._play.setCursor(Qt.PointingHandCursor)
        self._play.setEnabled(False)
        self._play.setStyleSheet(self._primary_btn_qss())
        self._play.clicked.connect(self._confirm)
        btns.addWidget(self._play, stretch=1)
        right.addLayout(btns)

        note = QLabel("Tu nombre se guarda para la próxima. La skin se ve en ChafaLand "
                      "con SkinsRestorer (te ayudo a activarlo).")
        note.setWordWrap(True)
        note.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; color:{T.DIM};"
                           f" background:transparent;")
        right.addSpacing(6)
        right.addWidget(note)

        cl.addLayout(right, stretch=1)
        lay.addWidget(card, alignment=Qt.AlignCenter)
        return page

    # ── estilos reutilizables ─────────────────────────────────────
    def _input_qss(self, border):
        return f"""
            QLineEdit {{
                background: {T.SURFACE};
                border: 1.5px solid {border};
                border-radius: 10px;
                padding: 11px 14px;
                font-family:'{T.FONT}'; font-size: 15px; color: {T.TEXT};
            }}
            QLineEdit:focus {{ border: 1.5px solid {T.ACCENT}; }}
        """

    def _primary_btn_qss(self):
        return f"""
            QPushButton {{
                background: {T.ACCENT}; color: #1a1206;
                border: none; border-radius: 10px;
                padding: 12px 18px;
                font-family:'{T.FONT}'; font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ background: {T.ACCENT_HI}; }}
            QPushButton:disabled {{ background: {T.rgba(T.ACCENT, 0.25)}; color: {T.MUTED}; }}
        """

    def _ghost_btn_qss(self):
        return f"""
            QPushButton {{
                background: transparent; color: {T.TEXT2};
                border: 1px solid {T.BORDER_HI}; border-radius: 10px;
                padding: 11px 16px;
                font-family:'{T.FONT}'; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {T.CARD_HI}; color: {T.TEXT}; }}
        """

    # ── lógica ────────────────────────────────────────────────────
    def reset(self):
        self._steps.setCurrentIndex(0)
        self._skin_path = ""
        if hasattr(self, "_name"):
            self._name.clear()
            self._avatar.clear_skin()
            self._skin_lbl.setText("Steve por defecto")

    def _choose_premium(self):
        self.account_ready.emit(accounts.Account(mode="premium", username="", uuid="", token=""))

    def _goto_offline(self):
        self._steps.setCurrentIndex(1)
        self._name.setFocus()

    def _on_name_changed(self, text):
        text = text.strip()
        valid = accounts.is_valid_name(text)
        self._play.setEnabled(valid)
        self._avatar.set_name(text)
        if not text:
            self._hint.setText("3–16 caracteres · letras, números o _")
            self._hint.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                                     f" color:{T.MUTED}; background:transparent;")
            self._name.setStyleSheet(self._input_qss(T.BORDER))
        elif valid:
            self._hint.setText("✓  Nombre disponible")
            self._hint.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                                     f" color:{T.OK}; background:transparent;")
            self._name.setStyleSheet(self._input_qss(T.rgba(T.OK, 0.5)))
        else:
            self._hint.setText("Usa 3–16 caracteres: letras, números o _")
            self._hint.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px;"
                                     f" color:{T.ERROR}; background:transparent;")
            self._name.setStyleSheet(self._input_qss(T.rgba(T.ERROR, 0.5)))

    def _pick_skin(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elige tu skin", "", "Skin de Minecraft (*.png)")
        if not path:
            return
        img = QImage(path)
        if img.isNull() or img.width() < 64 or img.height() < 32:
            self._skin_lbl.setText("PNG inválido (usa 64×64)")
            return
        self._skin_path = path
        self._avatar.set_skin(path)
        self._skin_lbl.setText(os.path.basename(path))

    def _confirm(self):
        name = self._name.text().strip()
        if not accounts.is_valid_name(name):
            return
        skin_saved = ""
        if self._skin_path:
            try:
                skin_saved = accounts.save_skin(name, self._skin_path)
            except Exception:
                skin_saved = ""
        acc = accounts.make_offline(name, skin_path=skin_saved)
        accounts.save(acc)
        self.account_ready.emit(acc)