import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ui import workers


class RepairWorkerTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.zip_path = str(Path(self._temp.name) / "modpack.zip")

    def tearDown(self):
        self._temp.cleanup()

    def _run_worker(self, *, download_effect=None, stage_effect=None, update_effect=None):
        session = SimpleNamespace(
            status="staged",
            backup_dir=Path(self._temp.name) / ".minecraft.cfl-backup-test",
            record_dir=Path(self._temp.name) / "repair-test",
            minecraft_dir=Path(self._temp.name) / ".minecraft",
        )

        def default_download(progress, _log, _url):
            progress(100)

        patches = (
            mock.patch.object(workers, "ZIP_NAME", self.zip_path),
            mock.patch.object(workers, "MODPACK_FULL_LINK_URL", "full"),
            mock.patch.object(workers, "MODPACK_UPDATE_LINK_URL", "overlay"),
            mock.patch.object(workers.game_launcher, "is_game_running", return_value=False),
            mock.patch.object(workers, "needs_update", return_value=(True, "5.0")),
            mock.patch.object(
                workers,
                "download_modpack",
                side_effect=download_effect or default_download,
            ),
            mock.patch.object(
                workers,
                "stage_repair",
                side_effect=stage_effect,
                return_value=None if stage_effect else session,
            ),
            mock.patch.object(workers, "install_modpack"),
            mock.patch.object(
                workers,
                "update_modpack",
                side_effect=update_effect,
                return_value=0,
            ),
            mock.patch.object(workers, "restore_worlds"),
            mock.patch.object(workers, "is_installed", return_value=True),
            mock.patch.object(workers, "save_local_version"),
            mock.patch.object(workers, "commit_repair"),
            mock.patch.object(workers, "rollback_repair"),
            mock.patch.object(
                workers, "install_health", return_value={"have_count": 348}
            ),
            mock.patch.object(workers, "_forget_verified"),
        )

        active = []
        try:
            for patcher in patches:
                active.append(patcher.start())
            result = []
            worker = workers.RepairWorker()
            worker.done.connect(lambda *args: result.append(args))
            worker.run()
            return result, dict(zip(
                (
                    "zip", "full_url", "overlay_url", "game_running",
                    "needs_update", "download", "stage", "install",
                    "update", "restore", "is_installed", "save_version",
                    "commit", "rollback", "health", "forget_verified",
                ),
                active,
            )), session
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_success_reports_backup_and_marks_remote_version(self):
        result, calls, session = self._run_worker()

        self.assertEqual(
            result,
            [(True, str(session.backup_dir), True, True)],
        )
        calls["save_version"].assert_called_once_with("5.0")
        calls["commit"].assert_called_once_with(session, log=mock.ANY)
        calls["rollback"].assert_not_called()
        # La instalación cambió: el próximo Jugar debe verificar todo.
        calls["forget_verified"].assert_called_once()

    def test_download_failure_never_stages_or_modifies_installation(self):
        def fail_download(_progress, _log, _url):
            raise OSError("server unavailable")

        result, calls, _session = self._run_worker(
            download_effect=fail_download
        )

        self.assertEqual(result, [(False, "", True, False)])
        calls["stage"].assert_not_called()
        calls["install"].assert_not_called()
        calls["rollback"].assert_not_called()

    def test_incomplete_stage_recovery_surfaces_backup_and_locks_state(self):
        failed_session = SimpleNamespace(
            status="recovery_failed",
            backup_dir=Path(self._temp.name) / ".minecraft.cfl-backup-failed",
            record_dir=Path(self._temp.name) / "repair-failed",
            minecraft_dir=Path(self._temp.name) / ".minecraft",
        )
        error = RuntimeError("stage and recovery failed")
        error.session = failed_session
        error.recovery_ok = False
        error.rollback_error = PermissionError("locked")

        result, calls, _session = self._run_worker(stage_effect=error)

        self.assertEqual(
            result,
            [(False, str(failed_session.backup_dir), False, False)],
        )
        calls["install"].assert_not_called()
        calls["rollback"].assert_not_called()

    def test_overlay_failure_keeps_clean_base_but_does_not_mark_it_current(self):
        attempts = 0

        def fail_second_download(progress, _log, _url):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                raise OSError("overlay unavailable")
            progress(100)

        result, calls, session = self._run_worker(
            download_effect=fail_second_download
        )

        self.assertEqual(
            result,
            [(True, str(session.backup_dir), True, False)],
        )
        calls["save_version"].assert_not_called()
        calls["commit"].assert_called_once()
        calls["restore"].assert_called_once()

    def test_startup_check_blocks_an_incomplete_repair(self):
        pending = SimpleNamespace(backup_dir=Path(r"C:\backup"))
        result = []

        with mock.patch.object(
            workers, "find_pending_repair", return_value=pending
        ), mock.patch.object(workers, "clear_stale_state") as clear:
            checker = workers.CheckWorker()
            checker.result.connect(lambda *args: result.append(args))
            checker.run()

        self.assertEqual(result, [("recovery", str(pending.backup_dir))])
        clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
