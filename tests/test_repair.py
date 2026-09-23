import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import core.repair as repair_module
from core.repair import (
    RepairStageError,
    RepairSession,
    commit_repair,
    find_pending_repair,
    restore_worlds,
    rollback_repair,
    stage_repair,
    validate_repair_target,
)


class RepairTestCase(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.app_dir = self.root / "CFLLauncher"
        self.app_dir.mkdir()
        self.minecraft_dir = self.root / "game" / ".minecraft"
        self.minecraft_dir.mkdir(parents=True)

    def tearDown(self):
        self._temp.cleanup()

    def _write(self, path, content):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _state_files(self):
        return (
            self.app_dir / "pack_mods.txt",
            self.app_dir / "version_local.txt",
            self.app_dir / "installed.flag",
            self.app_dir / "missing-before-repair.txt",
        )

    def _populated_install(self):
        self._write(self.minecraft_dir / "mods" / "example.jar", "jar")
        self._write(
            self.minecraft_dir / "saves" / "Mi Mundo" / "level.dat", "world"
        )
        self._write(self.minecraft_dir / "config" / "example.toml", "old=true")
        state = self._state_files()
        self._write(state[0], "example.jar\n")
        self._write(state[1], "4.5.6")
        self._write(state[2], "installed")
        return state

    def _stage(self, account=None, timestamp="20260723-120000"):
        state = self._populated_install()
        session = stage_repair(
            account=account,
            minecraft_dir=self.minecraft_dir,
            app_dir=self.app_dir,
            state_files=state,
            timestamp=timestamp,
        )
        return session, state

    def test_validate_repair_target_rejects_unsafe_paths(self):
        accepted = validate_repair_target(
            self.minecraft_dir, app_dir=self.app_dir
        )
        self.assertEqual(accepted, self.minecraft_dir.resolve())

        with self.assertRaises(ValueError):
            validate_repair_target(".minecraft", app_dir=self.app_dir)
        with self.assertRaises(ValueError):
            validate_repair_target(self.root / "game", app_dir=self.app_dir)
        with self.assertRaises(FileNotFoundError):
            validate_repair_target(
                self.root / "missing" / ".minecraft", app_dir=self.app_dir
            )

        app_inside_target = self.minecraft_dir / "CFLLauncher"
        app_inside_target.mkdir()
        with self.assertRaises(ValueError):
            validate_repair_target(
                self.minecraft_dir, app_dir=app_inside_target
            )

    def test_stage_moves_install_clears_state_and_sanitizes_profile(self):
        account = {
            "mode": "offline",
            "username": "Jugador_1",
            "uuid": "offline-uuid",
            "skin_path": "skin.png",
            "token": "SUPER-SECRET",
            "refresh_token": "ALSO-SECRET",
        }
        session, state = self._stage(account)

        self.assertIsInstance(session, RepairSession)
        self.assertEqual(session.status, "staged")
        self.assertEqual(session.minecraft_dir, self.minecraft_dir.resolve())
        self.assertEqual(
            session.backup_dir.name,
            ".minecraft.cfl-backup-20260723-120000",
        )
        self.assertTrue(session.backup_dir.is_dir())
        self.assertTrue(
            (session.backup_dir / "mods" / "example.jar").is_file()
        )
        self.assertTrue(self.minecraft_dir.is_dir())
        self.assertFalse((self.minecraft_dir / "mods").exists())
        for path in state:
            self.assertFalse(path.exists())

        profile_path = session.record_dir / "offline-profile.json"
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        self.assertEqual(profile["username"], "Jugador_1")
        self.assertNotIn("token", profile)
        self.assertNotIn("refresh_token", profile)
        record_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in session.record_dir.rglob("*.json")
        )
        self.assertNotIn("SUPER-SECRET", record_text)
        self.assertNotIn("ALSO-SECRET", record_text)

    def test_restore_worlds_then_commit_retains_backup(self):
        progress = []
        session, _ = self._stage()
        self._write(self.minecraft_dir / "mods" / "fresh.jar", "new")

        saves = restore_worlds(session, progress=progress.append)
        self.assertEqual(saves, self.minecraft_dir / "saves")
        self.assertEqual(
            (self.minecraft_dir / "saves" / "Mi Mundo" / "level.dat")
            .read_text(encoding="utf-8"),
            "world",
        )
        self.assertTrue(session.worlds_restored)
        self.assertEqual(progress[-1], 100)

        backup = commit_repair(session)
        self.assertEqual(backup, session.backup_dir)
        self.assertTrue(backup.is_dir())
        self.assertTrue(session.committed)
        self.assertFalse((self.minecraft_dir / ".cfl-repair-session").exists())
        manifest = json.loads(
            (session.record_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "committed")
        self.assertTrue(manifest["worlds_restored"])

    def test_pending_repair_is_detected_until_commit(self):
        session, _ = self._stage(timestamp="20260723-130000")

        pending = find_pending_repair(
            app_dir=self.app_dir, minecraft_dir=self.minecraft_dir
        )
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "staged")
        self.assertEqual(pending.backup_dir, session.backup_dir)

        commit_repair(session)
        self.assertIsNone(
            find_pending_repair(
                app_dir=self.app_dir, minecraft_dir=self.minecraft_dir
            )
        )

    def test_pending_record_is_ignored_after_manual_backup_restore(self):
        session, _ = self._stage(timestamp="20260723-131000")
        shutil.rmtree(self.minecraft_dir)
        os.replace(session.backup_dir, self.minecraft_dir)
        repair_module._restore_state_files(session)

        self.assertIsNone(
            find_pending_repair(
                app_dir=self.app_dir, minecraft_dir=self.minecraft_dir
            )
        )

    def test_folder_only_manual_restore_stays_blocked_without_state(self):
        session, _ = self._stage(timestamp="20260723-131500")
        shutil.rmtree(self.minecraft_dir)
        os.replace(session.backup_dir, self.minecraft_dir)

        pending = find_pending_repair(
            app_dir=self.app_dir, minecraft_dir=self.minecraft_dir
        )
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "staged")

    def test_preparing_record_with_moved_backup_is_pending(self):
        session, _ = self._stage(timestamp="20260723-132000")
        manifest_path = session.record_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "preparing"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        pending = find_pending_repair(
            app_dir=self.app_dir, minecraft_dir=self.minecraft_dir
        )
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "preparing")

    def test_rollback_state_failure_is_durably_marked_for_recovery(self):
        session, _ = self._stage(timestamp="20260723-133000")

        with mock.patch.object(
            repair_module,
            "_restore_state_files",
            side_effect=PermissionError("state locked"),
        ):
            with self.assertRaises(PermissionError):
                rollback_repair(session)

        manifest = json.loads(
            (session.record_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "recovery_failed")
        pending = find_pending_repair(
            app_dir=self.app_dir, minecraft_dir=self.minecraft_dir
        )
        self.assertIsNotNone(pending)
        self.assertEqual(pending.status, "recovery_failed")

    def test_commit_manifest_failure_keeps_marker_and_allows_rollback(self):
        session, _ = self._stage(timestamp="20260723-134000")

        with mock.patch.object(
            repair_module,
            "_write_manifest",
            side_effect=OSError("record locked"),
        ):
            with self.assertRaises(RuntimeError):
                commit_repair(session)

        self.assertEqual(session.status, "staged")
        self.assertTrue((self.minecraft_dir / ".cfl-repair-session").is_file())
        self.assertTrue(session.backup_dir.is_dir())
        rollback_repair(session)
        self.assertTrue((self.minecraft_dir / "mods" / "example.jar").is_file())

    def test_rollback_restores_install_and_exact_state(self):
        session, state = self._stage()
        self._write(self.minecraft_dir / "mods" / "broken.jar", "bad")
        for index, path in enumerate(state):
            self._write(path, f"new-{index}")

        restored = rollback_repair(session)

        self.assertEqual(restored, self.minecraft_dir.resolve())
        self.assertTrue(session.rolled_back)
        self.assertFalse(session.backup_dir.exists())
        self.assertTrue((self.minecraft_dir / "mods" / "example.jar").is_file())
        self.assertFalse((self.minecraft_dir / "mods" / "broken.jar").exists())
        self.assertEqual(state[0].read_text(encoding="utf-8"), "example.jar\n")
        self.assertEqual(state[1].read_text(encoding="utf-8"), "4.5.6")
        self.assertEqual(state[2].read_text(encoding="utf-8"), "installed")
        self.assertFalse(state[3].exists())
        manifest = json.loads(
            (session.record_dir / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "rolled_back")

    def test_rollback_refuses_unmarked_or_replaced_destination(self):
        session, state = self._stage()
        marker = self.minecraft_dir / ".cfl-repair-session"
        marker.write_text("another-session\n", encoding="utf-8")
        self._write(self.minecraft_dir / "do-not-delete.txt", "keep")

        with self.assertRaises(RuntimeError):
            rollback_repair(session)

        self.assertTrue((self.minecraft_dir / "do-not-delete.txt").exists())
        self.assertTrue(session.backup_dir.exists())
        for path in state:
            self.assertFalse(path.exists())

    def test_collision_uses_unique_backup_and_record_names(self):
        state = self._populated_install()
        collision = self.minecraft_dir.with_name(
            ".minecraft.cfl-backup-fixed"
        )
        collision.mkdir()
        (self.app_dir / "repair-backups" / "repair-fixed").mkdir(
            parents=True
        )

        session = stage_repair(
            minecraft_dir=self.minecraft_dir,
            app_dir=self.app_dir,
            state_files=state,
            timestamp="fixed",
        )

        self.assertEqual(session.backup_dir.name, ".minecraft.cfl-backup-fixed-2")
        self.assertEqual(session.record_dir.name, "repair-fixed-2")

    def test_default_state_names_are_scoped_to_custom_app_dir(self):
        self._write(self.minecraft_dir / "mods" / "example.jar", "jar")
        expected = (
            self._write(self.app_dir / "pack_mods.txt", "one.jar\n"),
            self._write(self.app_dir / "version_local.txt", "1"),
            self._write(self.app_dir / "installed.flag", "installed"),
        )
        session = stage_repair(
            minecraft_dir=self.minecraft_dir,
            app_dir=self.app_dir,
            timestamp="default-state",
        )
        self.assertEqual(session.state_files, tuple(p.resolve() for p in expected))
        self.assertTrue(all(not path.exists() for path in expected))

    def test_stage_error_exposes_session_when_internal_rollback_fails(self):
        state = self._populated_install()
        real_rename = repair_module._atomic_rename
        calls = 0

        def fail_second_rename(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError("simulated rollback failure")
            return real_rename(source, destination)

        with mock.patch.object(
            repair_module, "_atomic_rename", side_effect=fail_second_rename
        ), mock.patch.object(
            repair_module, "_write_marker", side_effect=OSError("marker failed")
        ):
            with self.assertRaises(RepairStageError) as raised:
                stage_repair(
                    minecraft_dir=self.minecraft_dir,
                    app_dir=self.app_dir,
                    state_files=state,
                    timestamp="failed-stage",
                )

        error = raised.exception
        self.assertFalse(error.recovery_ok)
        self.assertEqual(error.session.status, "recovery_failed")
        self.assertTrue(error.session.backup_dir.is_dir())
        self.assertTrue(error.session.record_dir.is_dir())
        self.assertFalse(self.minecraft_dir.exists())

    def test_stage_failure_after_move_automatically_restores_everything(self):
        state = self._populated_install()
        with mock.patch.object(
            repair_module, "_write_marker", side_effect=OSError("marker failed")
        ):
            with self.assertRaises(OSError):
                stage_repair(
                    minecraft_dir=self.minecraft_dir,
                    app_dir=self.app_dir,
                    state_files=state,
                    timestamp="automatic-rollback",
                )

        self.assertTrue((self.minecraft_dir / "mods" / "example.jar").is_file())
        self.assertTrue((self.minecraft_dir / "saves" / "Mi Mundo").is_dir())
        self.assertFalse(
            self.minecraft_dir.with_name(
                ".minecraft.cfl-backup-automatic-rollback"
            ).exists()
        )
        self.assertEqual(state[0].read_text(encoding="utf-8"), "example.jar\n")
        manifest = json.loads(
            (
                self.app_dir
                / "repair-backups"
                / "repair-automatic-rollback"
                / "manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "stage_failed")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_validate_rejects_symlink_target_when_supported(self):
        real = self.root / "real" / ".minecraft"
        real.mkdir(parents=True)
        link = self.root / "linked" / ".minecraft"
        link.parent.mkdir()
        try:
            os.symlink(real, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is not permitted")
        with self.assertRaises(ValueError):
            validate_repair_target(link, app_dir=self.app_dir)


if __name__ == "__main__":
    unittest.main()
