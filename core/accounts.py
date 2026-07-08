

import os
import re
import json
import hashlib
import uuid as _uuid
from dataclasses import dataclass, asdict

# Usa tu APP_DIR de config.py (%APPDATA%\CFLLauncher\)
try:
    from config import APP_DIR
except Exception:
    APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "CFLLauncher")
    os.makedirs(APP_DIR, exist_ok=True)

ACCOUNT_FILE = os.path.join(APP_DIR, "account.json")

# Reglas de nombre de Minecraft: 3-16 chars, letras/números/guion bajo
_NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def is_valid_name(name: str) -> bool:
    return bool(_NAME_RE.match(name or ""))


def offline_uuid(name: str) -> str:
    """UUID offline idéntico al que asigna el server en online-mode=false."""
    data = ("OfflinePlayer:" + name).encode("utf-8")
    b = bytearray(hashlib.md5(data).digest())
    b[6] = (b[6] & 0x0F) | 0x30  # versión 3
    b[8] = (b[8] & 0x3F) | 0x80  # variante RFC 4122
    return str(_uuid.UUID(bytes=bytes(b)))


@dataclass
class Account:
    mode: str            # "offline" | "premium"
    username: str
    uuid: str
    token: str = "0"     # offline: dummy. premium: access_token real
    refresh_token: str = ""  # solo premium (para re-loguear sin pedir password)

    def to_options(self) -> dict:
        """Opciones que espera minecraft_launcher_lib.command.get_minecraft_command"""
        return {
            "username": self.username,
            "uuid": self.uuid,
            "token": self.token or "0",
        }


def make_offline(name: str) -> Account:
    if not is_valid_name(name):
        raise ValueError("Nombre inválido: usa 3-16 letras, números o _")
    return Account(mode="offline", username=name, uuid=offline_uuid(name), token="0")


# ── Persistencia ──────────────────────────────────────────────────────────
def save(account: Account) -> None:
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(account), f, indent=2)


def load() -> Account | None:
    if not os.path.exists(ACCOUNT_FILE):
        return None
    try:
        with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return Account(**d)
    except Exception:
        return None


def clear() -> None:
    try:
        os.remove(ACCOUNT_FILE)
    except FileNotFoundError:
        pass