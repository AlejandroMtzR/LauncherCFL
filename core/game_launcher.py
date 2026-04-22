def launch_minecraft(log):
    import subprocess
    import os

    log("🎮 Intentando abrir Minecraft...")

    # 1. EXE clásico
    paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Minecraft Launcher\MinecraftLauncher.exe"),
        os.path.expandvars(r"%ProgramFiles%\Minecraft Launcher\MinecraftLauncher.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Minecraft Launcher\MinecraftLauncher.exe")
    ]

    for path in paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path])
                log(f"✅ Launcher abierto (exe)\n📂 {path}")
                return True
            except Exception as e:
                log(f"❌ Error exe: {e}")

    # 2. Microsoft Store (más fiable)
    try:
        subprocess.run(
            'start shell:AppsFolder\\Microsoft.4297127D64EC6_8wekyb3d8bbwe!Minecraft',
            shell=True
        )
        log("✅ Launcher abierto")
        return True
    except Exception as e:
        log(f"❌ Error Store: {e}")

    # 3. fallback
    try:
        subprocess.run("start minecraft://", shell=True)
        log("⚠️ Intento con protocolo minecraft://")
        return True
    except Exception as e:
        log(f"❌ Fallback falló: {e}")

    log("❌ No se pudo abrir Minecraft")
    return False