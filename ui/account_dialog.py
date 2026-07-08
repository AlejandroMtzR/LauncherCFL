# -*- coding: utf-8 -*-
"""
ui/account_dialog.py
Diálogo que sale al inicio (después de verificar mods) para elegir:
  - PREMIUM  -> se usa el flujo normal / login Microsoft
  - NO PREMIUM (offline) -> se pide el nombre de usuario

Devuelve un core.accounts.Account, o None si el usuario cancela.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt

from core import accounts


class AccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CFL Launcher — Cuenta")
        self.setModal(True)
        self.account = None

        root = QVBoxLayout(self)
        root.addWidget(QLabel("¿Tienes Minecraft premium?"))

        row = QHBoxLayout()
        self.btn_premium = QPushButton("Sí, soy premium")
        self.btn_offline = QPushButton("No premium")
        row.addWidget(self.btn_premium)
        row.addWidget(self.btn_offline)
        root.addLayout(row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre de usuario (3-16, letras/números/_)")
        self.name_edit.setVisible(False)
        root.addWidget(self.name_edit)

        self.btn_ok = QPushButton("Continuar")
        self.btn_ok.setVisible(False)
        root.addWidget(self.btn_ok)

        self.btn_premium.clicked.connect(self._on_premium)
        self.btn_offline.clicked.connect(self._on_offline_choice)
        self.btn_ok.clicked.connect(self._on_offline_confirm)
        self.name_edit.returnPressed.connect(self._on_offline_confirm)

    def _on_premium(self):
        # Opción A (mínima): premium sigue el flujo actual (abre launcher oficial).
        # Marcamos la cuenta como premium; el nombre/uuid reales los pone el
        # launcher oficial. Si luego haces login Microsoft in-app, sustitúyelo aquí.
        self.account = accounts.Account(
            mode="premium", username="", uuid="", token=""
        )
        self.accept()

    def _on_offline_choice(self):
        self.name_edit.setVisible(True)
        self.btn_ok.setVisible(True)
        self.name_edit.setFocus()

    def _on_offline_confirm(self):
        name = self.name_edit.text().strip()
        if not accounts.is_valid_name(name):
            QMessageBox.warning(self, "Nombre inválido",
                                "Usa 3-16 caracteres: letras, números o _")
            return
        self.account = accounts.make_offline(name)
        accounts.save(self.account)
        self.accept()


def pick_account(parent=None):
    """Devuelve un Account reutilizando el guardado, o abriendo el diálogo."""
    saved = accounts.load()
    if saved:
        return saved
    dlg = AccountDialog(parent)
    if dlg.exec() == QDialog.Accepted:
        return dlg.account
    return None