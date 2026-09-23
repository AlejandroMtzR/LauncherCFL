import tempfile
import unittest
from pathlib import Path

from core.installer_update import process_deletions


class DeleteManifestSafetyTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.overlay = self.root / "overlay"
        self.minecraft = self.root / ".minecraft"
        self.overlay.mkdir()
        self.minecraft.mkdir()

    def tearDown(self):
        self._temp.cleanup()

    def _manifest(self, text):
        (self.overlay / "delete.txt").write_text(text, encoding="utf-8")

    def test_rejects_parent_traversal_without_deleting_outside_file(self):
        outside = self.root / "outside.txt"
        outside.write_text("keep", encoding="utf-8")
        self._manifest("../outside.txt\n")

        with self.assertRaises(ValueError):
            process_deletions(self.overlay, self.minecraft, lambda _msg: None)

        self.assertEqual(outside.read_text(encoding="utf-8"), "keep")

    def test_safe_glob_only_deletes_matches_inside_minecraft(self):
        mods = self.minecraft / "mods"
        mods.mkdir()
        old_one = mods / "old-one.jar"
        old_two = mods / "old-two.jar"
        keep = mods / "keep.jar"
        for path in (old_one, old_two, keep):
            path.write_text(path.name, encoding="utf-8")
        self._manifest("mods/old-*.jar\n")

        failures = process_deletions(
            self.overlay, self.minecraft, lambda _msg: None
        )

        self.assertEqual(failures, 0)
        self.assertFalse(old_one.exists())
        self.assertFalse(old_two.exists())
        self.assertTrue(keep.exists())


if __name__ == "__main__":
    unittest.main()
