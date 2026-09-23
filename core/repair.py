

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping

from config import APP_DIR, INSTALLED_FILE, PACK_FILE, VERSION_FILE
from core.paths import get_minecraft_dir


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int], None]

_MARKER_NAME = ".cfl-repair-session"
_BACKUP_TAG = ".cfl-backup-"
_RECORDS_DIR_NAME = "repair-backups"
_SENSITIVE_STATE_NAMES = {"account.json", "offline_profiles.json"}


class RepairStageError(RuntimeError):

    def __init__(
        self,
        message: str,
        *,
        session: "RepairSession",
        original_error: BaseException,
        rollback_error: BaseException,
    ) -> None:
        super().__init__(message)
        self.session = session
        self.original_error = original_error
        self.rollback_error = rollback_error
        self.recovery_ok = False


@dataclass(frozen=True)
class _StateSnapshot:
    original_path: Path
    snapshot_path: Path | None
    existed: bool
    sha256: str | None = None


@dataclass
class RepairSession:

    minecraft_dir: Path
    backup_dir: Path
    record_dir: Path
    app_dir: Path
    timestamp: str
    session_id: str
    state_files: tuple[Path, ...]
    profile_snapshot: Path | None = None
    status: str = "preparing"
    worlds_restored: bool = False
    _state_snapshots: tuple[_StateSnapshot, ...] = field(
        default_factory=tuple, repr=False
    )

    @property
    def committed(self) -> bool:
        return self.status == "committed"

    @property
    def rolled_back(self) -> bool:
        return self.status == "rolled_back"


@dataclass(frozen=True)
class RepairRecoveryInfo:


    minecraft_dir: Path
    backup_dir: Path
    record_dir: Path
    status: str


def _log(callback: LogCallback | None, message: str) -> None:
    if callback is not None:
        try:
            callback(message)
        except Exception:
            # A UI/logging failure must never interrupt a filesystem transaction.
            pass


def _progress(callback: ProgressCallback | None, value: int) -> None:
    if callback is not None:
        try:
            callback(max(0, min(100, int(value))))
        except Exception:
            pass


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _is_reparse_point(path: Path) -> bool:


    if not _lexists(path):
        return False
    if path.is_symlink():
        return True
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return False


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path_text = os.path.normcase(os.path.abspath(path))
        parent_text = os.path.normcase(os.path.abspath(parent))
        return os.path.commonpath((path_text, parent_text)) == parent_text
    except (OSError, ValueError):
        return False


def _resolved(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def validate_repair_target(
    mc_dir: os.PathLike[str] | str,
    *,
    app_dir: os.PathLike[str] | str | None = None,
    require_exists: bool = True,
) -> Path:

    if mc_dir is None or not os.fspath(mc_dir).strip():
        raise ValueError("La ruta de .minecraft esta vacia")

    raw = Path(mc_dir).expanduser()
    if not raw.is_absolute():
        raise ValueError("La ruta de reparacion debe ser absoluta")
    if _is_reparse_point(raw):
        raise ValueError("La carpeta .minecraft no puede ser un enlace o junction")

    target = raw.resolve(strict=False)
    if target.name.casefold() != ".minecraft":
        raise ValueError("La reparacion solo acepta una carpeta llamada .minecraft")
    if target.parent == target or not target.anchor:
        raise ValueError("No se puede reparar una raiz de disco")

    persistent_dir = _resolved(app_dir or APP_DIR)
    dangerous_roots = [
        Path(target.anchor).resolve(strict=False),
        Path.home().resolve(strict=False),
        persistent_dir,
    ]
    for env_name in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        value = os.getenv(env_name)
        if value:
            dangerous_roots.append(_resolved(value))

    if any(_same_path(target, root) for root in dangerous_roots):
        raise ValueError("La ruta elegida es una carpeta del sistema o de datos")
    if _is_within(persistent_dir, target):
        raise ValueError(".minecraft no puede contener los datos persistentes de CFL")
    if _is_within(target, persistent_dir / _RECORDS_DIR_NAME):
        raise ValueError(".minecraft no puede estar dentro de repair-backups")

    # These locations must never be accepted merely because somebody created a
    # directory named '.minecraft' below them.  APPDATA itself is intentionally
    # not in this descendant check because it is the launcher's current default.
    protected_parents = []
    for env_name in (
        "SYSTEMROOT",
        "WINDIR",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMDATA",
    ):
        value = os.getenv(env_name)
        if value:
            protected_parents.append(_resolved(value))
    if any(_is_within(target, root) for root in protected_parents):
        raise ValueError("La instalacion no puede estar dentro de una carpeta protegida")

    parent = target.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"No existe la carpeta padre: {parent}")
    if require_exists:
        if not target.exists():
            raise FileNotFoundError(f"No existe la instalacion: {target}")
        if not target.is_dir():
            raise ValueError("La ruta de Minecraft no es una carpeta")
    elif _lexists(target) and not target.is_dir():
        raise ValueError("La ruta de Minecraft no es una carpeta")

    if _is_reparse_point(target):
        raise ValueError("La carpeta .minecraft no puede ser un enlace o junction")
    return target


def _normalise_timestamp(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now().strftime("%Y%m%d-%H%M%S")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d-%H%M%S")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip(".-_")
    if not cleaned:
        raise ValueError("El timestamp de reparacion es invalido")
    return cleaned[:64]


def _normalise_state_files(
    app_path: Path,
    state_files: Iterable[os.PathLike[str] | str] | None,
) -> tuple[Path, ...]:
    if state_files is None:
        requested: Iterable[os.PathLike[str] | str] = (
            app_path / Path(PACK_FILE).name,
            app_path / Path(VERSION_FILE).name,
            app_path / Path(INSTALLED_FILE).name,
        )
    else:
        requested = state_files

    records_root = app_path / _RECORDS_DIR_NAME
    normalised: list[Path] = []
    seen: set[str] = set()
    for item in requested:
        candidate = Path(item).expanduser()
        if not candidate.is_absolute():
            candidate = app_path / candidate
        candidate = candidate.resolve(strict=False)
        if not _is_within(candidate, app_path) or _same_path(candidate, app_path):
            raise ValueError(f"Archivo de estado fuera de APP_DIR: {candidate}")
        if _is_within(candidate, records_root):
            raise ValueError("Un archivo de estado no puede estar en repair-backups")
        if candidate.name.casefold() in _SENSITIVE_STATE_NAMES:
            raise ValueError("Las cuentas no se pueden limpiar como estado de instalacion")
        if _lexists(candidate):
            if _is_reparse_point(candidate):
                raise ValueError(f"Archivo de estado inseguro: {candidate}")
            if not candidate.is_file():
                raise ValueError(f"El estado no es un archivo: {candidate}")
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen:
            seen.add(key)
            normalised.append(candidate)
    return tuple(normalised)


def _reserve_paths(
    minecraft_dir: Path, app_path: Path, stamp: str
) -> tuple[str, Path, Path]:
    records_root = app_path / _RECORDS_DIR_NAME
    records_root.mkdir(parents=True, exist_ok=True)
    if _is_reparse_point(records_root):
        raise ValueError("repair-backups no puede ser un enlace o junction")

    for number in range(1, 10_000):
        suffix = "" if number == 1 else f"-{number}"
        token = f"{stamp}{suffix}"
        backup = minecraft_dir.with_name(
            f"{minecraft_dir.name}{_BACKUP_TAG}{token}"
        )
        record = records_root / f"repair-{token}"
        if _lexists(backup):
            continue
        try:
            record.mkdir()
        except FileExistsError:
            continue
        return f"repair-{token}", backup, record
    raise RuntimeError("No se pudo reservar un nombre unico para el respaldo")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: object) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp, path)


def _account_data(account: object | None, app_path: Path) -> dict | None:
    if account is None:
        account_file = app_path / "account.json"
        if not account_file.is_file() or _is_reparse_point(account_file):
            return None
        try:
            with account_file.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None
    if isinstance(account, Mapping):
        return dict(account)
    if is_dataclass(account):
        return asdict(account)
    return {
        name: getattr(account, name, "")
        for name in ("mode", "username", "uuid", "skin_path")
    }


def _snapshot_offline_profile(
    account: object | None, app_path: Path, record_dir: Path
) -> Path | None:
    raw = _account_data(account, app_path)
    if not raw or str(raw.get("mode", "")).casefold() != "offline":
        return None

    # Whitelisting is intentional: access/refresh tokens can never reach a
    # repair record, even if the Account model gains more secret fields later.
    safe = {
        "mode": "offline",
        "username": str(raw.get("username", "")),
        "uuid": str(raw.get("uuid", "")),
        "skin_path": str(raw.get("skin_path", "")),
    }
    destination = record_dir / "offline-profile.json"
    _write_json_atomic(destination, safe)
    return destination


def _snapshot_state_files(
    state_files: tuple[Path, ...], record_dir: Path
) -> tuple[_StateSnapshot, ...]:
    state_dir = record_dir / "state"
    state_dir.mkdir()
    snapshots: list[_StateSnapshot] = []
    for index, original in enumerate(state_files):
        if not _lexists(original):
            snapshots.append(_StateSnapshot(original, None, False, None))
            continue
        if _is_reparse_point(original) or not original.is_file():
            raise ValueError(f"Archivo de estado inseguro: {original}")
        destination = state_dir / f"{index:03d}-{original.name}"
        shutil.copy2(original, destination)
        snapshots.append(
            _StateSnapshot(original, destination, True, _sha256(destination))
        )
    return tuple(snapshots)


def _manifest_payload(session: RepairSession) -> dict:
    return {
        "schema": 1,
        "session_id": session.session_id,
        "timestamp": session.timestamp,
        "status": session.status,
        "minecraft_dir": str(session.minecraft_dir),
        "backup_dir": str(session.backup_dir),
        "worlds_restored": session.worlds_restored,
        "offline_profile": (
            session.profile_snapshot.name if session.profile_snapshot else None
        ),
        "state_files": [
            {
                "path": str(item.original_path),
                "existed": item.existed,
                "snapshot": (
                    str(item.snapshot_path.relative_to(session.record_dir))
                    if item.snapshot_path
                    else None
                ),
                "sha256": item.sha256,
            }
            for item in session._state_snapshots
        ],
    }


def _write_manifest(session: RepairSession) -> None:
    _write_json_atomic(session.record_dir / "manifest.json", _manifest_payload(session))


def _write_marker(session: RepairSession) -> None:
    marker = session.minecraft_dir / _MARKER_NAME
    with marker.open("x", encoding="utf-8") as handle:
        handle.write(session.session_id + "\n")


def _assert_staged_target(session: RepairSession) -> Path:
    target = validate_repair_target(
        session.minecraft_dir, app_dir=session.app_dir, require_exists=True
    )
    if not _same_path(target, session.minecraft_dir):
        raise RuntimeError("La ruta de la sesion de reparacion cambio")
    marker = target / _MARKER_NAME
    if not marker.is_file() or _is_reparse_point(marker):
        raise RuntimeError("Falta el marcador seguro de la reparacion")
    try:
        marker_value = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("No se pudo validar el marcador de reparacion") from exc
    if marker_value != session.session_id:
        raise RuntimeError("El destino pertenece a otra sesion de reparacion")
    return target


def _assert_backup(session: RepairSession) -> Path:
    raw_backup = Path(session.backup_dir)
    if _is_reparse_point(raw_backup):
        raise RuntimeError("El respaldo no puede ser un enlace o junction")
    backup = raw_backup.resolve(strict=False)
    if not _same_path(backup.parent, session.minecraft_dir.parent):
        raise RuntimeError("El respaldo ya no es hermano de .minecraft")
    token_prefix = "repair-"
    if not session.session_id.startswith(token_prefix):
        raise RuntimeError("El identificador de reparacion no es valido")
    token = session.session_id[len(token_prefix):]
    expected_name = f"{session.minecraft_dir.name}{_BACKUP_TAG}{token}"
    if backup.name != expected_name:
        raise RuntimeError("El nombre del respaldo no es valido")
    if not backup.is_dir() or _is_reparse_point(backup):
        raise RuntimeError("El respaldo de Minecraft no esta disponible")
    return backup


def _clear_state_files(session: RepairSession) -> None:
    for path in session.state_files:
        if not _lexists(path):
            continue
        if _is_reparse_point(path) or not path.is_file():
            raise RuntimeError(f"El archivo de estado cambio de forma insegura: {path}")
        path.unlink()


def _preflight_state_snapshots(session: RepairSession) -> None:
    for snapshot in session._state_snapshots:
        if not snapshot.existed:
            continue
        source = snapshot.snapshot_path
        if source is None or not source.is_file() or _is_reparse_point(source):
            raise RuntimeError(f"Falta el snapshot de estado: {snapshot.original_path}")
        if not _is_within(source, session.record_dir):
            raise RuntimeError("Snapshot de estado fuera del registro de reparacion")
        if snapshot.sha256 and _sha256(source) != snapshot.sha256:
            raise RuntimeError(f"Snapshot de estado alterado: {snapshot.original_path}")


def _restore_state_files(session: RepairSession) -> None:
    _preflight_state_snapshots(session)
    for snapshot in session._state_snapshots:
        target = snapshot.original_path
        if _lexists(target):
            if _is_reparse_point(target):
                # Unlinking the link itself is safe; never follow it.
                target.unlink()
            elif target.is_file():
                target.unlink()
            else:
                raise RuntimeError(f"No se reemplazara un directorio de estado: {target}")
        if snapshot.existed:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snapshot.snapshot_path, target)


def _atomic_rename(source: Path, destination: Path) -> None:
    os.replace(source, destination)


def stage_repair(
    account: object | None = None,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    *,
    minecraft_dir: os.PathLike[str] | str | None = None,
    app_dir: os.PathLike[str] | str | None = None,
    state_files: Iterable[os.PathLike[str] | str] | None = None,
    timestamp: str | datetime | None = None,
) -> RepairSession:
    """Move the current installation aside and prepare a clean destination.

    Nothing in the old installation is deleted.  If staging fails after the
    rename, this function makes a best-effort rollback before re-raising.
    """

    app_path = _resolved(app_dir or APP_DIR)
    app_path.mkdir(parents=True, exist_ok=True)
    if _is_reparse_point(app_path):
        raise ValueError("APP_DIR no puede ser un enlace o junction")
    target = validate_repair_target(
        minecraft_dir or get_minecraft_dir(), app_dir=app_path, require_exists=True
    )
    normalised_state = _normalise_state_files(app_path, state_files)
    stamp = _normalise_timestamp(timestamp)

    _log(log, f"Preparando reparacion segura de {target}")
    _progress(progress, 0)
    session_id, backup_dir, record_dir = _reserve_paths(target, app_path, stamp)
    session = RepairSession(
        minecraft_dir=target,
        backup_dir=backup_dir,
        record_dir=record_dir,
        app_dir=app_path,
        timestamp=stamp,
        session_id=session_id,
        state_files=normalised_state,
    )

    moved = False
    clean_created = False
    marker_created = False
    try:
        session._state_snapshots = _snapshot_state_files(
            normalised_state, record_dir
        )
        session.profile_snapshot = _snapshot_offline_profile(
            account, app_path, record_dir
        )
        _write_manifest(session)
        _progress(progress, 20)

        # Revalidate immediately before the only operation that moves user data.
        validate_repair_target(target, app_dir=app_path, require_exists=True)
        if _lexists(backup_dir):
            raise FileExistsError(f"El respaldo ya existe: {backup_dir}")
        _atomic_rename(target, backup_dir)
        moved = True
        _progress(progress, 45)

        target.mkdir()
        clean_created = True
        _write_marker(session)
        marker_created = True
        _clear_state_files(session)

        session.status = "staged"
        _write_manifest(session)
        _progress(progress, 100)
        _log(log, f"Instalacion anterior respaldada en {backup_dir}")
        return session
    except Exception as original_error:
        # Restore the exact pre-stage state whenever the old directory moved.
        rollback_error: BaseException | None = None
        if moved:
            try:
                if clean_created and target.exists():
                    if marker_created:
                        _assert_staged_target(session)
                        shutil.rmtree(target)
                    else:
                        target.rmdir()  # It was created empty by this function.
                if backup_dir.exists() and not target.exists():
                    _atomic_rename(backup_dir, target)
                _restore_state_files(session)
            except Exception as recovery_error:
                rollback_error = recovery_error
                _log(log, f"Rollback automatico incompleto: {recovery_error}")
        session.status = "recovery_failed" if rollback_error else "stage_failed"
        try:
            _write_manifest(session)
        except Exception:
            pass
        if rollback_error is not None:
            raise RepairStageError(
                "La preparacion fallo y no se pudo restaurar automaticamente; "
                f"respaldo/registro: {backup_dir} / {record_dir}",
                session=session,
                original_error=original_error,
                rollback_error=rollback_error,
            ) from original_error
        raise


def _world_files(source: Path) -> tuple[list[Path], list[Path]]:
    directories: list[Path] = []
    files: list[Path] = []
    for root, dirnames, filenames in os.walk(source, followlinks=False):
        root_path = Path(root)
        for dirname in list(dirnames):
            path = root_path / dirname
            if _is_reparse_point(path):
                raise RuntimeError(f"El mundo contiene un enlace inseguro: {path}")
            directories.append(path)
        for filename in filenames:
            path = root_path / filename
            if _is_reparse_point(path):
                raise RuntimeError(f"El mundo contiene un enlace inseguro: {path}")
            if not path.is_file():
                raise RuntimeError(f"Entrada de mundo no valida: {path}")
            files.append(path)
    return directories, files


def restore_worlds(
    session: RepairSession,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
) -> Path | None:
    """Copy ``saves`` from the full backup into the clean installation."""

    if session.status != "staged":
        raise RuntimeError("La sesion no esta lista para restaurar mundos")
    target = _assert_staged_target(session)
    backup = _assert_backup(session)
    source = backup / "saves"
    if not source.exists():
        session.worlds_restored = True
        _write_manifest(session)
        _progress(progress, 100)
        _log(log, "No habia mundos locales que restaurar")
        return None
    if not source.is_dir() or _is_reparse_point(source):
        raise RuntimeError("El respaldo de mundos no es una carpeta segura")

    destination = target / "saves"
    if _lexists(destination) and (
        not destination.is_dir() or _is_reparse_point(destination)
    ):
        raise RuntimeError("La carpeta saves de destino no es segura")

    directories, files = _world_files(source)
    destination.mkdir(parents=True, exist_ok=True)
    for directory in directories:
        relative = directory.relative_to(source)
        (destination / relative).mkdir(parents=True, exist_ok=True)

    total = max(len(files), 1)
    _progress(progress, 0)
    for index, file_path in enumerate(files, 1):
        relative = file_path.relative_to(source)
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        if _lexists(output) and _is_reparse_point(output):
            raise RuntimeError(f"Destino de mundo inseguro: {output}")
        shutil.copy2(file_path, output)
        _progress(progress, int(index / total * 100))

    session.worlds_restored = True
    _write_manifest(session)
    _progress(progress, 100)
    _log(log, f"Mundos restaurados en {destination}")
    return destination


def commit_repair(
    session: RepairSession, log: LogCallback | None = None
) -> Path:
    """Finish a repair while retaining the complete sibling backup."""

    if session.status != "staged":
        raise RuntimeError("La sesion de reparacion no se puede confirmar")
    target = _assert_staged_target(session)
    backup = _assert_backup(session)
    # Persistir el commit antes de quitar el marcador. Si este write falla,
    # el destino sigue marcado y Worker todavía puede ejecutar rollback.
    session.status = "committed"
    try:
        _write_manifest(session)
    except Exception as exc:
        session.status = "staged"
        raise RuntimeError(
            "No se pudo confirmar de forma durable la reparacion"
        ) from exc
    try:
        (target / _MARKER_NAME).unlink()
    except OSError as exc:
        # El manifiesto durable ya confirma que la instalación verificada es
        # válida. Un marcador sobrante no participa en el arranque normal.
        _log(log, f"No se pudo retirar el marcador de reparacion: {exc}")
    _log(log, f"Reparacion confirmada; respaldo conservado en {backup}")
    return backup


def rollback_repair(
    session: RepairSession, log: LogCallback | None = None
) -> Path:
    """Delete only this session's marked target and restore the old install."""

    if session.status != "staged":
        raise RuntimeError("La sesion de reparacion no se puede revertir")
    backup = _assert_backup(session)
    _preflight_state_snapshots(session)

    target = validate_repair_target(
        session.minecraft_dir, app_dir=session.app_dir, require_exists=False
    )
    if target.exists():
        _assert_staged_target(session)
        shutil.rmtree(target)
    if target.exists():
        raise RuntimeError("No se pudo retirar la instalacion incompleta")

    _atomic_rename(backup, target)
    try:
        _restore_state_files(session)
    except Exception:
        session.status = "recovery_failed"
        try:
            _write_manifest(session)
        except Exception:
            pass
        raise
    session.status = "rolled_back"
    try:
        _write_manifest(session)
    except Exception as exc:
        _log(log, f"No se pudo actualizar el registro de rollback: {exc}")
    _log(log, f"Instalacion anterior restaurada en {target}")
    return target


def _recorded_state_is_restored(
    raw: Mapping[str, object], app_path: Path
) -> bool:
    """Verify state files against hashes stored before staging."""

    items = raw.get("state_files")
    if not isinstance(items, list) or not items:
        return False
    try:
        for item in items:
            if not isinstance(item, Mapping):
                return False
            target = _resolved(item.get("path", ""))
            if not _is_within(target, app_path) or _same_path(target, app_path):
                return False
            existed = bool(item.get("existed", False))
            if not existed:
                if _lexists(target):
                    return False
                continue
            if not target.is_file() or _is_reparse_point(target):
                return False
            expected = str(item.get("sha256", ""))
            if not expected or _sha256(target) != expected:
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False


def find_pending_repair(
    *,
    app_dir: os.PathLike[str] | str | None = None,
    minecraft_dir: os.PathLike[str] | str | None = None,
) -> RepairRecoveryInfo | None:
    """Return the newest staged/recovery-failed record for this instance.

    This is intentionally read-only.  It lets startup block Play/Install after
    a power loss or crash instead of treating a partially written instance as
    healthy.  The existing sibling backup remains the recovery source.
    """

    app_path = _resolved(app_dir or APP_DIR)
    records_root = app_path / _RECORDS_DIR_NAME
    if not records_root.is_dir() or _is_reparse_point(records_root):
        return None

    requested = _resolved(minecraft_dir or get_minecraft_dir())
    manifests = sorted(
        records_root.glob("repair-*/manifest.json"),
        key=lambda path: path.parent.name,
        reverse=True,
    )
    for manifest in manifests:
        record_dir = manifest.parent
        if record_dir.parent != records_root or _is_reparse_point(record_dir):
            continue
        try:
            with manifest.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            status = str(raw.get("status", ""))
            if status not in {"preparing", "staged", "recovery_failed"}:
                continue
            recorded_mc = _resolved(raw.get("minecraft_dir", ""))
            if not _same_path(recorded_mc, requested):
                continue
            backup = _resolved(raw.get("backup_dir", ""))
            if (
                not _same_path(backup.parent, recorded_mc.parent)
                or not backup.name.startswith(
                    f"{recorded_mc.name}{_BACKUP_TAG}"
                )
            ):
                continue
            # Sin backup ni marcador, un registro preparing/staged solo está
            # resuelto si los tres archivos de estado coinciden byte por byte
            # con el snapshot previo. Esto distingue un rollback completo cuyo
            # último write falló de otro que recuperó la carpeta pero no estado.
            if (
                not backup.exists()
                and recorded_mc.is_dir()
                and not (recorded_mc / _MARKER_NAME).exists()
                and status != "recovery_failed"
                and _recorded_state_is_restored(raw, app_path)
            ):
                continue
            return RepairRecoveryInfo(
                minecraft_dir=recorded_mc,
                backup_dir=backup,
                record_dir=record_dir,
                status=status,
            )
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return None


__all__ = [
    "RepairRecoveryInfo",
    "RepairStageError",
    "RepairSession",
    "commit_repair",
    "find_pending_repair",
    "restore_worlds",
    "rollback_repair",
    "stage_repair",
    "validate_repair_target",
]
