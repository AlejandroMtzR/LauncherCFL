from PySide6.QtCore import QThread, Signal
from core import game_launcher


class PlayWorker(QThread):
    progress = Signal(int)
    log      = Signal(str)
    done     = Signal(bool, str)      # ok, mensaje de error (vacío si ok)
    already_running = Signal()

    def __init__(self, account, target="modpack", ram_gb=6, parent=None):
        super().__init__(parent)
        self._account = account
        self._target = target
        self._ram = ram_gb

    def run(self):
        try:
            # El escaneo completo (PowerShell) tarda ~1 s: aquí no congela la UI.
            if game_launcher.is_game_running():
                self.already_running.emit()
                return
            if self._target == "modpack":
                game_launcher.play_modpack(
                    self._account, self.log.emit, self.progress.emit, ram_gb=self._ram)
            else:
                kind, version = self._target
                if kind == "installed":
                    game_launcher.play_installed(
                        version, self._account, self.log.emit, self.progress.emit, ram_gb=self._ram)
                else:
                    game_launcher.play_vanilla(
                        version, self._account, self.log.emit, self.progress.emit, ram_gb=self._ram)
            self.done.emit(True, "")
        except Exception as e:
            msg = str(e).strip() or e.__class__.__name__
            self.log.emit(f"❌ Error al lanzar: {msg}")
            self.done.emit(False, msg)
