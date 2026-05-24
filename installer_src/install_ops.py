"""Installation operations — file extraction, shortcuts, registry, config.

All stdlib. No pywin32 required — shortcuts are created via WScript.Shell
through PowerShell, and registry writes use the built-in winreg module.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import winreg
import zipfile
from pathlib import Path
from typing import Callable

_APP_NAME      = "Budget Tracker"
_APP_EXE       = f"{_APP_NAME}.exe"
_UNINSTALL_EXE = "BudgetTrackerUninstall.exe"
_LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
_DEFAULT_DB_DIR = str(Path(_LOCAL_APPDATA) / "BudgetTracker")

_UNINSTALL_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker"
_RUN_REG_KEY       = r"Software\Microsoft\Windows\CurrentVersion\Run"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bundle_root() -> Path:
    """Return the directory containing app_bundle.zip and the uninstaller exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / "build"


def _make_shortcut(lnk_path: str, target: str, work_dir: str) -> None:
    ps = (
        f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{lnk_path}");'
        f'$s.TargetPath="{target}";'
        f'$s.WorkingDirectory="{work_dir}";'
        f'$s.Save()'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_app(install_dir: str, progress_cb: Callable[[int], None]) -> None:
    """Extract app_bundle.zip into install_dir, reporting 0-90% progress."""
    bundle = _bundle_root() / "app_bundle.zip"
    if not bundle.exists():
        raise FileNotFoundError(f"App bundle not found: {bundle}")

    dest = Path(install_dir)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle, "r") as zf:
        members = zf.namelist()
        total = len(members) or 1
        for i, member in enumerate(members):
            zf.extract(member, dest)
            progress_cb(int(i / total * 90))

    progress_cb(90)


def copy_uninstaller(install_dir: str) -> None:
    """Copy the bundled uninstaller exe into the installation directory."""
    src = _bundle_root() / _UNINSTALL_EXE
    if not src.exists():
        return  # Not fatal — uninstaller is optional during dev runs
    shutil.copy2(src, Path(install_dir) / _UNINSTALL_EXE)


def write_config_json(db_dir: str) -> None:
    """Write %LOCALAPPDATA%/BudgetTracker/config.json with a custom db_path.

    Skipped when the user chose the default location — the app handles that
    natively without a config file.
    """
    chosen   = Path(db_dir).resolve()
    default  = Path(_DEFAULT_DB_DIR).resolve()
    if chosen == default:
        return

    config_dir  = Path(_DEFAULT_DB_DIR)
    config_path = config_dir / "config.json"
    db_file     = chosen / "budget.sqlite3"

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"db_path": str(db_file)}, indent=2),
        encoding="utf-8",
    )


def create_shortcuts(install_dir: str, desktop: bool) -> None:
    """Create Start Menu shortcut and optionally a desktop shortcut."""
    exe = str(Path(install_dir) / _APP_EXE)

    # Start Menu
    start_menu = Path(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs",
        f"{_APP_NAME}.lnk",
    )
    _make_shortcut(str(start_menu), exe, install_dir)

    # Desktop
    if desktop:
        desktop_path = Path(os.environ.get("USERPROFILE", Path.home()), "Desktop", f"{_APP_NAME}.lnk")
        _make_shortcut(str(desktop_path), exe, install_dir)


def write_uninstall_registry(install_dir: str, version: str) -> None:
    """Register the app in Add/Remove Programs (HKCU — no elevation needed)."""
    uninstaller = str(Path(install_dir) / _UNINSTALL_EXE)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _UNINSTALL_REG_KEY) as k:
        winreg.SetValueEx(k, "DisplayName",     0, winreg.REG_SZ,    _APP_NAME)
        winreg.SetValueEx(k, "DisplayVersion",  0, winreg.REG_SZ,    version)
        winreg.SetValueEx(k, "Publisher",       0, winreg.REG_SZ,    "Snello")
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ,    install_dir)
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ,    uninstaller)
        winreg.SetValueEx(k, "NoModify",        0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair",        0, winreg.REG_DWORD, 1)


def set_launch_on_startup(install_dir: str, enable: bool) -> None:
    """Add or remove the Windows startup registry entry."""
    exe = str(Path(install_dir) / _APP_EXE)
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_REG_KEY, 0, winreg.KEY_SET_VALUE
    ) as k:
        if enable:
            winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, exe)
        else:
            try:
                winreg.DeleteValue(k, _APP_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_install(
    install_dir: str,
    db_dir: str,
    desktop: bool,
    startup: bool,
    version: str,
    progress_cb: Callable[[int], None],
    log_cb: Callable[[str], None],
) -> None:
    """Run the full installation sequence. Called from InstallPage's thread."""

    log_cb("Extracting files…")
    extract_app(install_dir, progress_cb)

    log_cb("Copying uninstaller…")
    copy_uninstaller(install_dir)
    progress_cb(92)

    log_cb("Writing database configuration…")
    write_config_json(db_dir)
    progress_cb(94)

    log_cb("Creating shortcuts…")
    create_shortcuts(install_dir, desktop)
    progress_cb(96)

    log_cb("Registering application…")
    write_uninstall_registry(install_dir, version)
    progress_cb(98)

    log_cb("Configuring startup…")
    set_launch_on_startup(install_dir, startup)
    progress_cb(100)

    log_cb("Installation complete.")
