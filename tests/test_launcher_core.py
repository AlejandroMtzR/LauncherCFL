import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import requests

from core import checker, installer, game_launcher, paths, launcherUpdate, downloader
from core import installer_update
from ui import gallery


class _TempDirTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)

    def tearDown(self):
        self._temp.cleanup()


class ModListTests(_TempDirTest):
    def test_expected_mods_ignore_non_jar_entries(self):
        pack = self.root / "pack_mods.txt"
        pack.write_text("a.jar\nconfig\nB.JAR\nnotes.txt\n\n", encoding="utf-8")
        with mock.patch.object(checker, "PACK_FILE", str(pack)):
            self.assertEqual(checker.expected_mod_set(), {"a.jar", "B.JAR"})

    def test_legacy_cp1252_pack_file_is_readable(self):
        pack = self.root / "pack_mods.txt"
        pack.write_bytes("Mañana-mod.jar\nplain.jar\n".encode("cp1252"))
        with mock.patch.object(checker, "PACK_FILE", str(pack)):
            self.assertEqual(checker.expected_mod_set(), {"Mañana-mod.jar", "plain.jar"})

    def test_health_is_case_insensitive_and_ignores_folders(self):
        mc = self.root / ".minecraft"
        (mc / "mods" / "subfolder").mkdir(parents=True)
        (mc / "mods" / "Create.jar").write_bytes(b"x")
        pack = self.root / "pack_mods.txt"
        pack.write_text("create.jar\nsubfolder\n", encoding="utf-8")
        with mock.patch.object(checker, "PACK_FILE", str(pack)):
            health = checker.install_health(str(mc))
        self.assertEqual(health["missing_count"], 0)

    def test_auto_created_folders_in_mods_never_count_as_missing(self):
        # Caso reportado: el ZIP trae 2 carpetas dentro de mods/ (o las crean
        # los mods). Quedaban en pack_mods.txt y salía "Faltan 2 mods".
        mc = self.root / ".minecraft"
        mods = mc / "mods"
        mods.mkdir(parents=True)
        for i in range(12):
            (mods / f"mod{i}.jar").write_bytes(b"x")
        (mods / "carpeta-auto").mkdir()
        (mods / "otra.jar").mkdir()          # carpeta con nombre engañoso
        pack = self.root / "pack_mods.txt"
        with mock.patch.object(installer, "PACK_FILE", str(pack)):
            installer.save_pack({p.name for p in mods.iterdir()} - {"otra.jar"} | {"carpeta-2"})
        with mock.patch.object(checker, "PACK_FILE", str(pack)):
            health = checker.install_health(str(mc))
            self.assertEqual(health["missing_count"], 0)
            self.assertEqual(health["have_count"], 12)
            self.assertTrue(checker.is_installed(str(mc)))

    def test_save_pack_roundtrip_is_utf8(self):
        pack = self.root / "pack_mods.txt"
        with mock.patch.object(installer, "PACK_FILE", str(pack)):
            installer.save_pack({"Año.jar", "b.jar"})
            self.assertEqual(installer.load_old_pack(), {"Año.jar", "b.jar"})
        self.assertIn("Año.jar", pack.read_text(encoding="utf-8"))


class FakeMinecraft:
    """Arma un .minecraft mínimo lanzable para 1.20.1 + un Forge encima."""

    def __init__(self, root: Path):
        self.mc = root / ".minecraft"
        self.version = "1.20.1"
        self.forge = "1.20.1-forge-47.4.10"
        lib = "com/example/lib/1.0/lib-1.0.jar"
        self._write_json(self.version, {
            "id": self.version,
            "type": "release",
            "assetIndex": {"id": "5"},
            "javaVersion": {"component": "java-runtime-gamma"},
            "libraries": [
                {"name": "com.example:lib:1.0", "downloads": {"artifact": {"path": lib}}},
                {"name": "org.windows:only:1.0", "rules": [{"action": "allow", "os": {"name": "osx"}}]},
            ],
        })
        (self.mc / "versions" / self.version / f"{self.version}.jar").write_bytes(b"jar")
        (self.mc / "assets" / "indexes").mkdir(parents=True)
        (self.mc / "assets" / "indexes" / "5.json").write_text("{}")
        (self.mc / "libraries" / lib).parent.mkdir(parents=True)
        (self.mc / "libraries" / lib).write_bytes(b"lib")
        platform = game_launcher.mll.runtime._get_jvm_platform_string()
        java = (self.mc / "runtime" / "java-runtime-gamma" / platform / "java-runtime-gamma" / "bin")
        java.mkdir(parents=True)
        (java / "java.exe").write_bytes(b"")
        (java.parent / "release").write_text('JAVA_VERSION="17.0.8"\n')
        self._write_json(self.forge, {"id": self.forge, "inheritsFrom": self.version,
                                      "libraries": []})

    def _write_json(self, vid, data):
        folder = self.mc / "versions" / vid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{vid}.json").write_text(json.dumps(data), encoding="utf-8")


class GameLauncherTests(_TempDirTest):
    def setUp(self):
        super().setUp()
        self.fake = FakeMinecraft(self.root)
        self.instances = self.root / "instances"
        self.patches = [
            mock.patch.object(game_launcher.paths, "get_minecraft_dir", return_value=str(self.fake.mc)),
            mock.patch.object(paths, "INSTANCES_DIR", str(self.instances)),
            mock.patch.object(game_launcher, "VERIFIED_FILE", str(self.root / "verified.json")),
        ]
        for p in self.patches:
            p.start()
        game_launcher._manifest_cache.update(at=0.0, versions=None)
        game_launcher._running = None
        game_launcher._last_exit = None

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        game_launcher._manifest_cache.update(at=0.0, versions=None)
        super().tearDown()

    # ── carpetas independientes ────────────────────────────────────
    def test_other_versions_never_use_the_modpack_folder(self):
        game_launcher._manifest_cache.update(at=time.time(), versions=[
            {"id": "1.21.4", "type": "release"},
            {"id": "24w14a", "type": "snapshot"},
            {"id": "b1.7.3", "type": "old_beta"},
        ])
        mc = str(self.fake.mc)
        self.assertEqual(game_launcher.game_dir_for("modpack"), mc)
        dirs = {
            game_launcher.game_dir_for(("vanilla", "1.21.4")),
            game_launcher.game_dir_for(("vanilla", "24w14a")),
            game_launcher.game_dir_for(("vanilla", "b1.7.3")),
            game_launcher.game_dir_for(("installed", "1.20.1-forge-47.3.0")),
        }
        self.assertEqual(len(dirs), 4)
        for d in dirs:
            self.assertTrue(d.startswith(str(self.instances)), d)
            self.assertTrue(os.path.isdir(d))
            self.assertNotEqual(os.path.normcase(d), os.path.normcase(mc))

    def test_modpack_forge_is_not_listed_as_separate_version(self):
        other = "1.20.1-forge-47.3.0"
        self.fake._write_json(other, {"id": other, "inheritsFrom": "1.20.1", "libraries": []})
        self.assertEqual(game_launcher.list_installed_forge_versions(), [other])

    # ── chequeo rápido y verificación ──────────────────────────────
    def test_is_launchable_detects_missing_files(self):
        mc = str(self.fake.mc)
        self.assertTrue(game_launcher.is_launchable(mc, self.fake.forge))
        os.remove(self.fake.mc / "versions" / "1.20.1" / "1.20.1.jar")
        self.assertFalse(game_launcher.is_launchable(mc, self.fake.forge))

    def test_offline_launch_uses_local_files(self):
        logs = []
        err = requests.ConnectionError("sin red")
        with mock.patch.object(game_launcher.mll.install, "install_minecraft_version", side_effect=err):
            game_launcher.ensure_vanilla("1.20.1", logs.append, lambda _v: None)
        self.assertTrue(any("archivos que ya tienes" in line for line in logs))

    def test_offline_without_files_gives_friendly_error(self):
        err = requests.ConnectionError("sin red")
        with mock.patch.object(game_launcher.mll.install, "install_minecraft_version", side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                game_launcher.ensure_vanilla("1.21.4", lambda _m: None, lambda _v: None)
        self.assertIn("Sin conexión", str(ctx.exception))

    def test_recent_verification_skips_full_hash_check(self):
        install = mock.Mock()
        with mock.patch.object(game_launcher.mll.install, "install_minecraft_version", install):
            game_launcher.ensure_vanilla("1.20.1", lambda _m: None, lambda _v: None)
            game_launcher.ensure_vanilla("1.20.1", lambda _m: None, lambda _v: None)
            self.assertEqual(install.call_count, 1)
            game_launcher.forget_verified(str(self.fake.mc))
            game_launcher.ensure_vanilla("1.20.1", lambda _m: None, lambda _v: None)
            self.assertEqual(install.call_count, 2)

    # ── lista de versiones ─────────────────────────────────────────
    def test_manifest_is_downloaded_once_for_all_filters(self):
        response = mock.Mock()
        response.json.return_value = {"versions": [
            {"id": "1.21.4", "type": "release"},
            {"id": "24w14a", "type": "snapshot"},
        ]}
        with mock.patch("requests.get", return_value=response) as get:
            self.assertEqual(game_launcher.list_versions(), ["1.21.4"])
            self.assertEqual(game_launcher.list_versions(True), ["1.21.4", "24w14a"])
        self.assertEqual(get.call_count, 1)

    def test_version_list_offline_falls_back_to_installed(self):
        with mock.patch("requests.get", side_effect=requests.ConnectionError()):
            self.assertEqual(game_launcher.list_versions(), ["1.20.1"])

    # ── lanzamiento y cierre inesperado ────────────────────────────
    def test_launch_uses_instance_dir_ram_and_logs_output(self):
        account = mock.Mock(username="Steve", mode="offline")
        account.to_options.return_value = {"username": "Steve", "uuid": "u", "token": "0"}
        proc = mock.Mock()
        proc.poll.return_value = None
        game_dir = str(self.instances / "vanilla")
        with mock.patch.object(game_launcher.mll.command, "get_minecraft_command",
                               return_value=["java"]) as cmd, \
                mock.patch.object(game_launcher.subprocess, "Popen", return_value=proc) as popen:
            game_launcher.launch_version("1.20.1", account, lambda _m: None, ram_gb=6,
                                         game_dir=game_dir)
        options = cmd.call_args[0][2]
        self.assertEqual(options["gameDirectory"], game_dir)
        self.assertIn("-Xmx6G", options["jvmArguments"])
        self.assertIn("-XX:+UseG1GC", options["jvmArguments"])
        self.assertEqual(popen.call_args.kwargs["cwd"], game_dir)
        self.assertTrue(os.path.isfile(os.path.join(game_dir, game_launcher.LAUNCH_LOG_NAME)))
        self.assertTrue(game_launcher.is_tracked_game_running())

    def test_early_crash_is_reported_and_forces_reverification(self):
        game_launcher._mark_verified(str(self.fake.mc), "1.20.1")
        log_path = self.root / "out.log"
        log_path.write_text("linea 1\nException: boom\n", encoding="utf-8")
        proc = mock.Mock()
        proc.poll.return_value = 1
        game_launcher._running = {
            "proc": proc, "started": time.monotonic() - 5, "version_id": self.fake.forge,
            "game_dir": str(self.fake.mc), "mc_dir": str(self.fake.mc), "log_path": str(log_path),
        }
        self.assertFalse(game_launcher.is_tracked_game_running())
        info = game_launcher.pop_last_exit()
        self.assertTrue(game_launcher.is_early_crash(info))
        self.assertIn("boom", game_launcher.crash_log_tail(info))
        self.assertIsNone(game_launcher.pop_last_exit())
        self.assertFalse(game_launcher._recently_verified(str(self.fake.mc), "1.20.1"))

    def test_java_label_reads_runtime_without_processes(self):
        with mock.patch.object(game_launcher.subprocess, "run") as run:
            self.assertEqual(game_launcher.java_label("modpack"), "17.0.8")
        run.assert_not_called()


class MiscTests(_TempDirTest):
    def test_local_launcher_version_uses_the_newest(self):
        vfile = self.root / "launcherVersion.txt"
        with mock.patch.object(launcherUpdate, "LOCAL_VERSION_FILE", str(vfile)), \
                mock.patch.object(launcherUpdate, "LAUNCHER_VERSION", "5.3.6"):
            vfile.write_text("5.3.5")
            self.assertEqual(launcherUpdate.get_local_version(), "5.3.6")
            vfile.write_text("5.4.0")
            self.assertEqual(launcherUpdate.get_local_version(), "5.4.0")
            vfile.unlink()
            self.assertEqual(launcherUpdate.get_local_version(), "5.3.6")

    def test_truncated_zip_is_rejected(self):
        good = self.root / "good.zip"
        with zipfile.ZipFile(good, "w") as z:
            z.writestr("mods/a.jar", "x" * 5000)
        data = good.read_bytes()
        cut = self.root / "cut.zip"
        cut.write_bytes(data[: len(data) // 2])
        with mock.patch.object(downloader, "ZIP_NAME", str(good)):
            self.assertTrue(downloader.validate_zip(lambda _m: None))
        with mock.patch.object(downloader, "ZIP_NAME", str(cut)):
            self.assertFalse(downloader.validate_zip(lambda _m: None))

    def test_gallery_rejects_html_saved_as_image(self):
        html = self.root / "img.jpg"
        html.write_bytes(b"<!DOCTYPE html><html>")
        png = self.root / "ok.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 10)
        self.assertFalse(gallery.is_image_file(str(html)))
        self.assertTrue(gallery.is_image_file(str(png)))

    def test_update_blocks_only_when_minecraft_really_runs(self):
        with mock.patch.object(game_launcher, "is_game_running", return_value=False):
            self.assertFalse(installer_update.is_minecraft_running())
        with mock.patch.object(game_launcher, "is_game_running", return_value=True):
            self.assertTrue(installer_update.is_minecraft_running())


if __name__ == "__main__":
    unittest.main()
