from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PySide6.QtCore import Qt

from . import theme as T
from .version_list import VersionList


class VersionDialog(QDialog):
    """Selector grande de versiones. `selected` queda con el destino elegido."""

    def __init__(self, parent=None, current="modpack", modpack_badge=None):
        super().__init__(parent)
        self.setWindowTitle("CFL Launcher — Elegir versión")
        self.setModal(True)
        self.resize(600, 640)
        self.setMinimumSize(480, 460)
        self.selected = current or "modpack"
        self.setStyleSheet(f"QDialog {{ background: {T.BG}; }}")
        self._build(modpack_badge)

    def _build(self, modpack_badge):
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
        sub = QLabel("Las versiones distintas al modpack se instalan en su propia "
                     "carpeta: no tocan tus mods ni tus mundos del modpack.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"font-family:'{T.FONT}'; font-size:11px; color:{T.MUTED};")
        root.addWidget(sub)
        root.addSpacing(12)

        self._versions = VersionList(self)
        self._versions.set_target(self.selected)
        if modpack_badge:
            self._versions.set_modpack_badge(*modpack_badge)
        self._versions.target_changed.connect(self._on_target)
        self._versions.activated.connect(self._on_activated)
        root.addWidget(self._versions, 1)
        root.addSpacing(12)

        btns = QHBoxLayout(); btns.setSpacing(10)
        cancel = QPushButton("Cancelar")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(self._ghost_qss())
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self._ok = QPushButton("Seleccionar")
        self._ok.setCursor(Qt.PointingHandCursor)
        self._ok.setStyleSheet(self._primary_qss())
        self._ok.clicked.connect(self.accept)
        btns.addWidget(self._ok, stretch=1)
        root.addLayout(btns)

    def _on_target(self, target):
        self.selected = target

    def _on_activated(self, target):
        self.selected = target
        self.accept()

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
