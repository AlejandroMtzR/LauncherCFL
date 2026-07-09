# -*- coding: utf-8 -*-
"""
diagnostico_mods.py
Ponlo en la RAÍZ del repo (junto a main.py) y córrelo:

    python diagnostico_mods.py

No abre la GUI. Solo lee tu carpeta real de mods y pack_mods.txt
para decirte QUÉ considera "faltante" el launcher y POR QUÉ.
"""
import os
from config import PACK_FILE
from core import checker
from core.paths import get_minecraft_dir


def main():
    mc_dir = get_minecraft_dir()
    mods_dir = os.path.join(mc_dir, "mods")

    print("=" * 60)
    print(" DIAGNÓSTICO DE MODS — CFL Launcher")
    print("=" * 60)
    print(f"  .minecraft : {mc_dir}")
    print(f"  mods/      : {mods_dir}")
    print(f"  pack_mods  : {PACK_FILE}")
    print("-" * 60)

    h = checker.install_health()
    print(f"  Esperados (pack_mods.txt) : {h['want_count']}")
    print(f"  Presentes (.jar reales)   : {h['have_count']}")
    print(f"  FALTANTES según checker   : {h['missing_count']}")
    print("-" * 60)

    # Lista cruda de pack_mods.txt (tal cual, incluye no-.jar)
    want_raw = set()
    if os.path.exists(PACK_FILE):
        with open(PACK_FILE, encoding="utf-8") as f:
            want_raw = {ln.strip() for ln in f if ln.strip()}

    have = set(checker.list_installed_mods(mc_dir))
    missing = want_raw - have

    # Separar los "faltantes" en dos grupos
    fantasmas = sorted(m for m in missing if not m.lower().endswith(".jar"))
    reales = sorted(m for m in missing if m.lower().endswith(".jar"))

    if fantasmas:
        print(f"  ⚠️  FALSOS POSITIVOS (no son .jar, nunca van a calzar): {len(fantasmas)}")
        for m in fantasmas:
            tipo = "carpeta" if os.path.isdir(os.path.join(mods_dir, m)) else "no-jar"
            existe = "SÍ existe en disco" if os.path.exists(os.path.join(mods_dir, m)) else "no existe"
            print(f"        - {m!r}   ({tipo}, {existe})")
        print("     → Estos son el bug del filtro. Físicamente no falta nada.")
    else:
        print("  ✔  No hay falsos positivos por no-.jar")

    if reales:
        print(f"  ❗ FALTANTES REALES (.jar que sí deberían estar y no están): {len(reales)}")
        for m in reales:
            print(f"        - {m}")
        print("     → Estos sí faltan de verdad (quizá no se copiaron por estar en uso).")
    else:
        print("  ✔  No falta ningún .jar de verdad")

    print("=" * 60)


if __name__ == "__main__":
    main()