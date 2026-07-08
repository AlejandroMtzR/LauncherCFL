
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QThread, Signal, QSize

from . import theme as T
from core import game_launcher


class _VersionLoader(QThread):
    loaded = Signal(list)

    def __init__(self, snapshots, old):
        super().__init__()
        self._snap = snapshots
        self._old = old

    def run(self):
        try:
            self.loaded.emit(game_launcher.list_versions(self._snap, self._old))
        except Exception:
            self.loaded.emit([])


class VersionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CFL Launcher — Elegir versión")
        self.setModal(True)
        self.setFixedSize(560, 600)
        self.selected = "modpack"
        self._snap = False
        self._old = False
        self.setStyleSheet(f"QDialog {{ background: {T.BG}; }}")
        self._build()
        self._reload_versions()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(4)

        eyebrow = QLabel("CFL LAUNCHER")
        eyebrow.setStyleSheet(f"font-family:'{T.FONT}'; font-size:10px; font-weight:600;"
                              f" color:{T.ACCENT_HI}; letter-spacing:5px;")
        root.addWidget(eyebrow)
        title = QLabel("¿Qué quieres jugar?")
        title.setStyleSheet(f"font-family:'{T.FONT}'; font-size:24px; font-weight:900;"
                            f" color:{T.TEXT};")
        root.addWidget(title)
        root.addSpacing(14)

        # ── Tarjeta MODPACK (recomendado, seleccionada por defecto) ──
        self._modpack_card = QFrame()
        self._modpack_card.setCursor(Qt.PointingHandCursor)
        self._modpack_card.mousePressEvent = lambda e: self._select_modpack()
        mc = QHBoxLayout(self._modpack_card)
        mc.setContentsMargins(18, 16, 18, 16)
        mc.setSpacing(14)
        badge = QLabel("◆")
        badge.setStyleSheet(f"font-size:30px; color:{T.ACCENT}; background:transparent;")
        mc.addWidget(badge)
        txt = QVBoxLayout(); txt.setSpacing(2)
        n = QLabel("ChafaLand Modpack")
        n.setStyleSheet(f"font-family:'{T.FONT}'; font-size:16px; font-weight:800;"
                        f" color:{T.TEXT}; background:transparent;")
        d = QLabel("Forge 1.20.1  ·  +340 mods")
        d.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; color:{T.TEXT2};"
                        f" background:transparent;")
        txt.addWidget(n); txt.addWidget(d)
        mc.addLayout(txt); mc.addStretch()
        rec = QLabel("RECOMENDADO")
        rec.setStyleSheet(f"font-family:'{T.FONT}'; font-size:9px; font-weight:700;"
                          f" color:{T.ACCENT_HI}; background:{T.rgba(T.ACCENT,0.10)};"
                          f" border:1px solid {T.rgba(T.ACCENT,0.25)}; border-radius:4px;"
                          f" padding:3px 8px;")
        mc.addWidget(rec)
        root.addWidget(self._modpack_card)
        root.addSpacing(16)

        # ── "Otra versión (vanilla)" ──
        lab = QLabel("O juega otra versión (sin mods)")
        lab.setStyleSheet(f"font-family:'{T.FONT}'; font-size:12px; font-weight:600;"
                          f" color:{T.TEXT2};")
        root.addWidget(lab)
        root.addSpacing(6)

        chips = QHBoxLayout(); chips.setSpacing(8); chips.setAlignment(Qt.AlignLeft)
        self._chip_snap = self._make_chip("+ Snapshots", self._toggle_snap)
        self._chip_old = self._make_chip("+ Antiguas", self._toggle_old)
        chips.addWidget(QLabel("Releases", styleSheet=f"color:{T.MUTED}; font-size:11px;"))
        chips.addWidget(self._chip_snap)
        chips.addWidget(self._chip_old)
        chips.addStretch()
        root.addLayout(chips)
        root.addSpacing(6)

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {T.SURFACE}; border: 1px solid {T.BORDER};
                border-radius: 10px; padding: 4px;
                font-family:'{T.FONT}'; font-size: 13px; color: {T.TEXT2};
                outline: 0;
            }}
            QListWidget::item {{ padding: 7px 10px; border-radius: 6px; }}
            QListWidget::item:selected {{ background: {T.rgba(T.ACCENT,0.18)}; color: {T.TEXT}; }}
            QListWidget::item:hover {{ background: {T.CARD_HI}; }}
        """)
        self._list.itemClicked.connect(self._select_vanilla)
        root.addWidget(self._list, stretch=1)
        root.addSpacing(12)

        # ── Botones ──
        btns = QHBoxLayout(); btns.setSpacing(10)
        cancel = QPushButton("Cancelar")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(self._ghost_qss())
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self._play = QPushButton("Jugar")
        self._play.setCursor(Qt.PointingHandCursor)
        self._play.setStyleSheet(self._primary_qss())
        self._play.clicked.connect(self.accept)
        btns.addWidget(self._play, stretch=1)
        root.addLayout(btns)

        self._refresh_card_style()

    # ── chips ──
    def _make_chip(self, text, cb):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(cb)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T.MUTED};
                border: 1px solid {T.BORDER_HI}; border-radius: 12px;
                padding: 4px 12px; font-family:'{T.FONT}'; font-size: 11px;
            }}
            QPushButton:checked {{
                background: {T.rgba(T.ACCENT,0.14)}; color: {T.ACCENT_HI};
                border: 1px solid {T.rgba(T.ACCENT,0.4)};
            }}
        """)
        return b

    def _toggle_snap(self):
        self._snap = self._chip_snap.isChecked(); self._reload_versions()

    def _toggle_old(self):
        self._old = self._chip_old.isChecked(); self._reload_versions()

    # ── carga de versiones ──
    def _reload_versions(self):
        self._list.clear()
        item = QListWidgetItem("Cargando versiones...")
        item.setFlags(Qt.NoItemFlags)
        self._list.addItem(item)
        self._loader = _VersionLoader(self._snap, self._old)
        self._loader.loaded.connect(self._on_versions)
        self._loader.start()

    def _on_versions(self, versions):
        self._list.clear()
        if not versions:
            it = QListWidgetItem("No se pudieron cargar (revisa tu internet)")
            it.setFlags(Qt.NoItemFlags)
            self._list.addItem(it)
            return
        for v in versions:
            self._list.addItem(QListWidgetItem(v))

    # ── selección ──
    def _select_modpack(self):
        self.selected = "modpack"
        self._list.clearSelection()
        self._refresh_card_style()

    def _select_vanilla(self, item):
        if not (item.flags() & Qt.ItemIsSelectable):
            return
        self.selected = ("vanilla", item.text())
        self._refresh_card_style()

    def _refresh_card_style(self):
        on = self.selected == "modpack"
        self._modpack_card.setStyleSheet(f"""
            QFrame {{
                background: {T.CARD_HI if on else T.CARD};
                border: 1.5px solid {T.ACCENT if on else T.BORDER};
                border-radius: 14px;
            }}
        """)

    # ── estilos ──
    def _primary_qss(self):
        return f"""
            QPushButton {{
                background: {T.ACCENT}; color: #1a1206; border: none;
                border-radius: 10px; padding: 12px 18px;
                font-family:'{T.FONT}'; font-size: 14px; font-weight: 800;
            }}
            QPushButton:hover {{ background: {T.ACCENT_HI}; }}
        """

    def _ghost_qss(self):
        return f"""
            QPushButton {{
                background: transparent; color: {T.TEXT2};
                border: 1px solid {T.BORDER_HI}; border-radius: 10px;
                padding: 12px 18px; font-family:'{T.FONT}'; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {T.CARD_HI}; color: {T.TEXT}; }}
        """