using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class UpdateBridge
{
    // Debe coincidir con LAUNCHER_VERSION de core/launcherUpdate.py y con el
    // tag del release de GitHub (tools/build_release.ps1 lo comprueba).
    private const string Version = "5.3.6";
    private const string RealAssetUrl =
        "https://github.com/AlejandroMtzR/LauncherCFL/releases/download/" + Version + "/CFL-Launcher-real.exe";

    [STAThread]
    private static int Main(string[] args)
    {
        if (Array.Exists(args, arg => arg.Equals("--self-test", StringComparison.OrdinalIgnoreCase)))
            return 0;

        try
        {
            ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;

            string currentExe = Process.GetCurrentProcess().MainModule.FileName;
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string appDir = Path.Combine(appData, "CFLLauncher");
            string updatesDir = Path.Combine(appDir, "updates");
            Directory.CreateDirectory(updatesDir);

            string realExe = Path.Combine(updatesDir, "CFL-Launcher-real.exe");
            string partial = realExe + ".download";

            DownloadRealLauncher(partial);
            if (File.Exists(realExe))
                File.Delete(realExe);
            File.Move(partial, realExe);

            string batPath = Path.Combine(appDir, "finish_bridge_update.cmd");
            File.WriteAllText(
                batPath,
                BuildReplacementScript(currentExe, realExe, Process.GetCurrentProcess().Id),
                new UTF8Encoding(false)
            );

            StartCleanCmd(batPath);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "No se pudo finalizar la actualización automática.\n\n" +
                "Abre el launcher manualmente o descarga CFL-Launcher-real.exe.\n\n" +
                ex.Message,
                "CFL Launcher",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }
    }

    private static void DownloadRealLauncher(string dest)
    {
        if (File.Exists(dest))
            File.Delete(dest);

        using (var client = new WebClient())
        {
            client.Headers.Add("User-Agent", "CFL-Launcher-Bridge/" + Version);
            client.DownloadFile(RealAssetUrl, dest);
        }

        var info = new FileInfo(dest);
        if (!info.Exists || info.Length < 50L * 1024L * 1024L)
            throw new InvalidDataException("La descarga del launcher real quedó incompleta.");

        using (var fs = File.OpenRead(dest))
        {
            if (fs.ReadByte() != 'M' || fs.ReadByte() != 'Z')
                throw new InvalidDataException("El archivo descargado no es un .exe válido.");
        }
    }

    private static string BuildReplacementScript(string currentExe, string realExe, int bridgePid)
    {
        return
@"@echo off
chcp 65001 >nul

:wait_bridge
tasklist /FI ""PID eq " + bridgePid + @""" 2>nul | find """ + bridgePid + @""" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_bridge
)

timeout /t 1 /nobreak >nul

set _tries=0
:copyloop
copy /Y """ + realExe + @""" """ + currentExe + @""" >nul
if not errorlevel 1 goto copyok
set /a _tries+=1
if %_tries% geq 20 goto launch_real_copy
timeout /t 1 /nobreak >nul
goto copyloop

:copyok
set ""PYINSTALLER_RESET_ENVIRONMENT=1""
set ""_PYI_ARCHIVE_FILE=""
set ""_PYI_APPLICATION_HOME_DIR=""
set ""_PYI_PARENT_PROCESS_LEVEL=""
set ""_PYI_SPLASH_IPC=""
set ""PYINSTALLER_SUPPRESS_SPLASH_SCREEN=""
start """" """ + currentExe + @"""
goto cleanup

:launch_real_copy
set ""PYINSTALLER_RESET_ENVIRONMENT=1""
set ""_PYI_ARCHIVE_FILE=""
set ""_PYI_APPLICATION_HOME_DIR=""
set ""_PYI_PARENT_PROCESS_LEVEL=""
set ""_PYI_SPLASH_IPC=""
set ""PYINSTALLER_SUPPRESS_SPLASH_SCREEN=""
start """" """ + realExe + @"""

:cleanup
del ""%~f0"" >nul 2>&1
";
    }

    private static void StartCleanCmd(string batPath)
    {
        var psi = new ProcessStartInfo("cmd.exe", "/c \"" + batPath + "\"");
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        CleanPyInstallerEnvironment(psi);
        Process.Start(psi);
    }

    private static void CleanPyInstallerEnvironment(ProcessStartInfo psi)
    {
        foreach (string key in new string[]
        {
            "_PYI_ARCHIVE_FILE",
            "_PYI_APPLICATION_HOME_DIR",
            "_PYI_PARENT_PROCESS_LEVEL",
            "_PYI_SPLASH_IPC",
            "PYINSTALLER_SUPPRESS_SPLASH_SCREEN"
        })
        {
            if (psi.EnvironmentVariables.ContainsKey(key))
                psi.EnvironmentVariables.Remove(key);
        }
        psi.EnvironmentVariables["PYINSTALLER_RESET_ENVIRONMENT"] = "1";
    }
}
