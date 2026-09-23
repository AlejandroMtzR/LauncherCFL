import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import version_list  # noqa: E402

_app = QApplication.instance() or QApplication([])


def _visible_targets(widget):
    out = []
    for i in range(widget._list.count()):
        it = widget._list.item(i)
        if not it.isHidden() and it.data(version_list.ROLE_TARGET) is not None:
            out.append(it.data(version_list.ROLE_TARGET))
    return out


class VersionListTests(unittest.TestCase):
    def setUp(self):
        # Sin red ni hilos: la carga se simula llamando a _on_loaded.
        patcher = mock.patch.object(version_list.VersionList, "reload", lambda self: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.widget = version_list.VersionList()

    def test_stale_results_are_ignored(self):
        self.widget._token = 2
        self.widget._on_loaded(1, [["9.9", "release"]], [], [], "")
        self.assertNotIn(("vanilla", "9.9"), _visible_targets(self.widget))
        self.widget._on_loaded(2, [["1.21.4", "release"]], [], [], "")
        self.assertIn(("vanilla", "1.21.4"), _visible_targets(self.widget))

    def test_rows_badges_and_search(self):
        self.widget._token = 1
        self.widget._on_loaded(
            1,
            [["1.21.4", "release"], ["1.21.3", "release"], ["24w14a", "snapshot"]],
            ["1.20.1-forge-47.3.0"],
            ["1.21.3"],
            "",
        )
        items = {self.widget._list.item(i).data(version_list.ROLE_TARGET):
                 self.widget._list.item(i) for i in range(self.widget._list.count())}
        self.assertEqual(items[("vanilla", "1.21.4")].data(version_list.ROLE_BADGE)[0], "NUEVA")
        self.assertEqual(items[("vanilla", "1.21.3")].data(version_list.ROLE_BADGE)[0], "INSTALADA")
        self.assertIn(("installed", "1.20.1-forge-47.3.0"), items)

        self.widget._search.setText("1.21.3")
        self.assertEqual(_visible_targets(self.widget), [("vanilla", "1.21.3")])
        self.widget._search.clear()
        self.assertEqual(len(_visible_targets(self.widget)), 5)

    def test_selection_emits_target(self):
        self.widget._token = 1
        self.widget._on_loaded(1, [["1.21.4", "release"]], [], [], "")
        seen = []
        self.widget.target_changed.connect(seen.append)
        item = next(self.widget._list.item(i) for i in range(self.widget._list.count())
                    if self.widget._list.item(i).data(version_list.ROLE_TARGET) == ("vanilla", "1.21.4"))
        self.widget._on_clicked(item)
        self.assertEqual(seen, [("vanilla", "1.21.4")])
        self.assertEqual(self.widget.target(), ("vanilla", "1.21.4"))

    def test_offline_error_row_is_not_selectable(self):
        self.widget._token = 1
        self.widget._on_loaded(1, [], [], [], "Sin conexión")
        last = self.widget._list.item(self.widget._list.count() - 1)
        self.assertFalse(last.flags() & Qt.ItemIsSelectable)


if __name__ == "__main__":
    unittest.main()
