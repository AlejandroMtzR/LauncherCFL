# -*- coding: utf-8 -*-
"""
Lista de versiones reutilizable (Inicio y diálogo "Ver todas las versiones").

- Una fila por versión pintada con un delegate: cientos de versiones sin crear
  cientos de widgets (antes cada clic reconstruía todas las filas).
- Buscador + filtros Snapshots / Antiguas.
- Insignias: ACTUAL (modpack), INSTALADA, NUEVA.
- La carga corre en un hilo que nunca se destruye mientras trabaja (antes,
  cerrar el diálogo con la lista cargando podía cerrar el launcher).
"""
from PySide6.QtCore import Qt, QThread, Signal, QSize, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QFont, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle, QAbstractItemView,
)

from . import theme as T
from core import game_launcher

ROLE_TARGET = Qt.UserRole
ROLE_BADGE = Qt.UserRole + 1     # (texto, color) o None
ROLE_SUB = Qt.UserRole + 2       # texto secundario a la derecha

# Hilos de carga vivos: se guardan aquí (no en el widget) para que un
# QThread nunca se destruya mientras corre aunque se cierre la ventana.
_LIVE_LOADERS = set()


def _qcolor(hex_color, alpha=1.0):
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


class _VersionLoader(QThread):
    loaded = Signal(int, list, list, list, str)   # token, versiones, forge, instaladas, error

    def __init__(self, token, snapshots, old):
        super().__init__()
        self._token = token
        self._snap = snapshots
        self._old = old

    def run(self):
        versions, forge, installed, error = [], [], [], ""
        try:
            ids = game_launcher.list_versions(self._snap, self._old)
            types = game_launcher.version_type_map()
            versions = [[vid, types.get(vid) or game_launcher.version_type(vid)] for vid in ids]
        except Exception:
            error = "Sin conexión: no se pudo cargar la lista de versiones."
        try:
            forge = game_launcher.list_installed_forge_versions()
            installed = sorted(game_launcher.installed_vanilla_versions())
        except Exception:
            pass
        self.loaded.emit(self._token, versions, forge, installed, error)


class _RowDelegate(QStyledItemDelegate):
    ROW_H = 38

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_H)

    def paint(self, p, option, index):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        selectable = bool(index.flags() & Qt.ItemIsSelectable)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver) and selectable
        r = QRectF(option.rect).adjusted(1, 3, -3, -3)

        if not selectable:
            p.setPen(QColor(T.MUTED))
            p.setFont(QFont(T.FONT, 9))
            p.drawText(r.adjusted(10, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft,
                       index.data(Qt.DisplayRole) or "")
            p.restore()
            return

        if selected:
            bg, border = _qcolor(T.ACCENT, 0.12), _qcolor(T.ACCENT, 0.55)
        elif hover:
            bg, border = QColor(T.CARD_HI), _qcolor(T.ACCENT, 0.30)
        else:
            bg, border = _qcolor(T.SURFACE, 0.70), QColor(255, 255, 255, 16)
        p.setPen(QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, 7, 7)

        x_right = r.right() - 10
        badge = index.data(ROLE_BADGE)
        if badge:
            text, color = badge
            f = QFont(T.FONT, 7, QFont.Black)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(text) + 14
            br = QRectF(x_right - tw, r.center().y() - 9, tw, 18)
            p.setPen(QPen(_qcolor(color, 0.35), 1))
            p.setBrush(_qcolor(color, 0.12))
            p.drawRoundedRect(br, 4, 4)
            p.setPen(QColor(color))
            p.drawText(br, Qt.AlignCenter, text)
            x_right = br.left() - 8

        sub = index.data(ROLE_SUB)
        if sub:
            f = QFont(T.FONT, 8)
            p.setFont(f)
            sw = p.fontMetrics().horizontalAdvance(sub)
            p.setPen(QColor(T.MUTED))
            p.drawText(QRectF(x_right - sw, r.top(), sw, r.height()),
                       Qt.AlignVCenter | Qt.AlignRight, sub)
            x_right -= sw + 10

        f = QFont(T.FONT, 9, QFont.Bold)
        p.setFont(f)
        p.setPen(QColor(T.TEXT if selected else T.TEXT2))
        text_rect = QRectF(r.left() + 12, r.top(), max(10, x_right - r.left() - 12), r.height())
        label = p.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight,
                                           int(text_rect.width()))
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, label)
        p.restore()


def _chip_qss():
    return f"""
        QPushButton {{
            background: transparent; color: {T.MUTED};
            border: 1px solid {T.BORDER_HI}; border-radius: 11px;
            padding: 3px 11px; font-family:'{T.FONT}'; font-size: 11px;
        }}
        QPushButton:hover {{ color: {T.TEXT}; }}
        QPushButton:checked {{
            background: {T.rgba(T.ACCENT, 0.14)}; color: {T.ACCENT_HI};
            border: 1px solid {T.rgba(T.ACCENT, 0.4)};
        }}
    """


class VersionList(QWidget):
    """Buscador + filtros + lista. Emite target_changed al elegir una fila."""
    target_changed = Signal(object)
    activated = Signal(object)          # doble clic

    def __init__(self, parent=None, include_modpack=True):
        super().__init__(parent)
        self._include_modpack = include_modpack
        self._target = "modpack" if include_modpack else None
        self._snap = False
        self._old = False
        self._token = 0
        self._modpack_badge = ("ACTUAL", T.OK)
        self._modpack_sub = f"Forge {game_launcher.MODPACK_FORGE_VERSION.split('-', 1)[-1]}"
        self._build()
        QTimer.singleShot(0, self.reload)

    # ── construcción ──────────────────────────────────────────────
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar versión (ej. 1.21)")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(28)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{T.SURFACE}; border:1px solid {T.BORDER_HI};
                border-radius:8px; padding:3px 9px; color:{T.TEXT};
                font-family:'{T.FONT}'; font-size:11px;
            }}
            QLineEdit:focus {{ border-color:{T.ACCENT}; }}
        """)
        self._search.textChanged.connect(self._apply_filter)
        top.addWidget(self._search, 1)
        self._chip_snap = QPushButton("Snapshots")
        self._chip_old = QPushButton("Antiguas")
        for chip, cb in ((self._chip_snap, self._toggle_snap), (self._chip_old, self._toggle_old)):
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(_chip_qss())
            chip.clicked.connect(cb)
            top.addWidget(chip)
        v.addLayout(top)

        self._list = QListWidget()
        self._list.setItemDelegate(_RowDelegate(self._list))
        self._list.setMouseTracking(True)
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.setStyleSheet(f"""
            QListWidget {{ background:transparent; border:none; outline:0; }}
            QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
            QScrollBar::handle:vertical {{ background:{T.BORDER_HI}; border-radius:4px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self._list.itemClicked.connect(self._on_clicked)
        self._list.itemDoubleClicked.connect(self._on_double)
        v.addWidget(self._list, 1)

    # ── carga ─────────────────────────────────────────────────────
    def reload(self):
        self._token += 1
        self._show_placeholder("Cargando versiones…")
        loader = _VersionLoader(self._token, self._snap, self._old)
        loader.loaded.connect(self._on_loaded)
        for t in list(_LIVE_LOADERS):
            if t.isFinished():
                _LIVE_LOADERS.discard(t)
        _LIVE_LOADERS.add(loader)
        loader.start()

    def _show_placeholder(self, text):
        self._list.clear()
        if self._include_modpack:
            self._add_modpack_item()
        it = QListWidgetItem(text)
        it.setFlags(Qt.NoItemFlags)
        self._list.addItem(it)
        self._sync_selection()

    def _add_modpack_item(self):
        it = QListWidgetItem("ChafaLand Modpack")
        it.setData(ROLE_TARGET, "modpack")
        it.setData(ROLE_BADGE, self._modpack_badge)
        it.setData(ROLE_SUB, self._modpack_sub)
        self._list.addItem(it)
        return it

    def _on_loaded(self, token, versions, forge, installed, error):
        if token != self._token:
            return  # respuesta vieja (el usuario cambió de filtro)
        self._list.setUpdatesEnabled(False)
        self._list.clear()
        if self._include_modpack:
            self._add_modpack_item()
        installed = set(installed)
        for fid in forge:
            it = QListWidgetItem(f"Forge {fid.split('-forge-', 1)[-1]}")
            it.setData(ROLE_TARGET, ("installed", fid))
            it.setData(ROLE_SUB, fid.split("-forge-", 1)[0])
            it.setData(ROLE_BADGE, ("INSTALADA", T.INFO))
            self._list.addItem(it)
        first_release = True
        for ver, vtype in versions:
            it = QListWidgetItem(f"Minecraft {ver}")
            it.setData(ROLE_TARGET, ("vanilla", ver))
            if vtype == "snapshot":
                it.setData(ROLE_SUB, "snapshot")
            elif vtype.startswith("old"):
                it.setData(ROLE_SUB, vtype.replace("old_", ""))
            if ver in installed:
                it.setData(ROLE_BADGE, ("INSTALADA", T.INFO))
            elif first_release and vtype == "release":
                it.setData(ROLE_BADGE, ("NUEVA", T.ACCENT_HI))
            if vtype == "release":
                first_release = False
            self._list.addItem(it)
        if error or not versions:
            it = QListWidgetItem(error or "No hay versiones para mostrar.")
            it.setFlags(Qt.NoItemFlags)
            self._list.addItem(it)
        self._list.setUpdatesEnabled(True)
        self._apply_filter(self._search.text())
        self._sync_selection()

    # ── filtros ───────────────────────────────────────────────────
    def _toggle_snap(self):
        self._snap = self._chip_snap.isChecked()
        self.reload()

    def _toggle_old(self):
        self._old = self._chip_old.isChecked()
        self.reload()

    def _apply_filter(self, text):
        needle = (text or "").strip().lower()
        for i in range(self._list.count()):
            it = self._list.item(i)
            if not (it.flags() & Qt.ItemIsSelectable):
                it.setHidden(bool(needle))
                continue
            it.setHidden(bool(needle) and needle not in it.text().lower())

    # ── selección ─────────────────────────────────────────────────
    def _on_clicked(self, item):
        target = item.data(ROLE_TARGET)
        if target is None:
            return
        self._target = target
        self.target_changed.emit(target)

    def _on_double(self, item):
        target = item.data(ROLE_TARGET)
        if target is not None:
            self._target = target
            self.activated.emit(target)

    def _sync_selection(self):
        self._list.blockSignals(True)
        self._list.clearSelection()
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.data(ROLE_TARGET) == self._target:
                it.setSelected(True)
                self._list.setCurrentItem(it)
                break
        self._list.blockSignals(False)

    def target(self):
        return self._target

    def set_target(self, target):
        self._target = target
        self._sync_selection()

    def set_modpack_badge(self, text, color, sub=None):
        self._modpack_badge = (text, color) if text else None
        if sub is not None:
            self._modpack_sub = sub
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.data(ROLE_TARGET) == "modpack":
                it.setData(ROLE_BADGE, self._modpack_badge)
                it.setData(ROLE_SUB, self._modpack_sub)
                break

    def mark_installed(self, version):
        """Tras instalar una versión, marcarla sin recargar toda la lista."""
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.data(ROLE_TARGET) == ("vanilla", version):
                it.setData(ROLE_BADGE, ("INSTALADA", T.INFO))
                break
