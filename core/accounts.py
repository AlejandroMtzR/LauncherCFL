# -*- coding: utf-8 -*-
"""
core/accounts.py
Manejo de cuentas: PREMIUM (Microsoft) u OFFLINE (no premium).

El UUID offline se calcula IGUAL que lo hace el servidor en online-mode=false
(UUID v3 de "OfflinePlayer:<nombre>"), así los datos del jugador PERSISTEN
en ChafaLand entre sesiones.
"""

import os
import re
import json
import shutil
import hashlib
import uuid as _uuid
from dataclasses import dataclass, asdict

try:
    from config import APP_DIR
except Exception:
    APP_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "CFLLauncher")
    os.makedirs(APP_DIR, exist_ok=True)

ACCOUNT_FILE = os.path.join(APP_DIR, "account.json")
PROFILES_FILE = os.path.join(APP_DIR, "offline_profiles.json")
SKINS_DIR = os.path.join(APP_DIR, "skins")
os.makedirs(SKINS_DIR, exist_ok=True)

# Nombre de Minecraft: 3-16 chars, letras/números/guion bajo
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
    mode: str                 # "offline" | "premium"
    username: str
    uuid: str
    token: str = "0"          # offline: dummy. premium: access_token real
    refresh_token: str = ""   # solo premium
    skin_path: str = ""       # ruta local a la skin .png (opcional, offline)

    def to_options(self) -> dict:
        return {
            "username": self.username,
            "uuid": self.uuid,
            "token": self.token or "0",
        }


def save_skin(name: str, src_png: str) -> str:
    """Copia la skin elegida a %APPDATA%\\CFLLauncher\\skins\\<nombre>.png."""
    dst = os.path.join(SKINS_DIR, f"{name}.png")
    shutil.copy2(src_png, dst)
    return dst


def make_offline(name: str, skin_path: str = "") -> Account:
    if not is_valid_name(name):
        raise ValueError("Nombre inválido: usa 3-16 letras, números o _")
    return Account(
        mode="offline",
        username=name,
        uuid=offline_uuid(name),
        token="0",
        skin_path=skin_path or "",
    )


# ── Persistencia ──────────────────────────────────────────────────────────
def _profile_data(account: Account) -> dict:
    data = asdict(account)
    data["uuid"] = account.uuid or offline_uuid(account.username)
    return data


def list_profiles() -> list[Account]:
    if not os.path.exists(PROFILES_FILE):
        return []
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out = []
        for item in raw if isinstance(raw, list) else []:
            item.setdefault("token", "0")
            item.setdefault("refresh_token", "")
            item.setdefault("skin_path", "")
            if item.get("mode") == "offline" and is_valid_name(item.get("username", "")):
                out.append(Account(**item))
        return out
    except Exception:
        return []


def remember_profile(account: Account) -> None:
    if not account or account.mode != "offline" or not is_valid_name(account.username):
        return
    profiles = list_profiles()
    data = _profile_data(account)
    kept = [
        p for p in profiles
        if p.uuid != account.uuid and p.username.lower() != account.username.lower()
    ]
    ordered = [Account(**data)] + kept
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in ordered[:12]], f, indent=2)


def save(account: Account) -> None:
    remember_profile(account)
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(account), f, indent=2)


def load() -> Account | None:
    if not os.path.exists(ACCOUNT_FILE):
        return None
    try:
        with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("skin_path", "")
        return Account(**d)
    except Exception:
        return None


def clear() -> None:
    try:
        os.remove(ACCOUNT_FILE)
    except FileNotFoundError:
        pass
