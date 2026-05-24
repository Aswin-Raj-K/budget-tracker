"""Budget Tracker uninstaller.

When launched from the install directory it copies itself to %TEMP% and
re-launches with --do-uninstall <install_dir> so it can delete its own
source directory (Windows locks the exe that is currently running).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

_APP_NAME = "Budget Tracker"
_UNINSTALL_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\BudgetTracker"
_RUN_REG_KEY       = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _read_install_dir_from_registry() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _UNINSTALL_REG_KEY) as k:
            value, _ = winreg.QueryValueEx(k, "InstallLocation")
            return str(value)
    except OSError:
        return None


def _remove_registry() -> None:
    for root, key, value_name in [
        (winreg.HKEY_CURRENT_USER, _UNINSTALL_REG_KEY, None),
        (winreg.HKEY_CURRENT_USER, _RUN_REG_KEY, _APP_NAME),
    ]:
        try:
            if value_name:
                with winreg.OpenKey(root, key, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, value_name)
            else:
                winreg.DeleteKey(root, key)
        except OSError:
            pass


def _remove_shortcuts() -> None:
    appdata = os.environ.get("APPDATA", "")
    start_menu = Path(appdata, "Microsoft", "Windows", "Start Menu", "Programs",
                      f"{_APP_NAME}.lnk")
    desktop = Path(os.environ.get("USERPROFILE", Path.home()), "Desktop",
                   f"{_APP_NAME}.lnk")
    for lnk in (start_menu, desktop):
        try:
            lnk.unlink(missing_ok=True)
        except OSError:
            pass


def _do_uninstall(install_dir: str) -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    answer = QMessageBox.question(
        None,
        f"Uninstall {_APP_NAME}",
        f"This will permanently remove {_APP_NAME} from:\n\n{install_dir}\n\n"
        "Your financial database will NOT be deleted.\n\nContinue?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return

    _remove_shortcuts()
    _remove_registry()

    # Remove install directory (we're running from %TEMP% at this point)
    shutil.rmtree(install_dir, ignore_errors=True)

    QMessageBox.information(
        None,
        f"Uninstall {_APP_NAME}",
        f"{_APP_NAME} has been successfully removed from your computer.",
    )


def main() -> int:
    if "--do-uninstall" in sys.argv:
        idx = sys.argv.index("--do-uninstall")
        install_dir = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if not install_dir:
            install_dir = _read_install_dir_from_registry() or ""
        _do_uninstall(install_dir)
        return 0

    # First launch: copy self to temp and re-launch with the flag
    exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__)
    install_dir = str(exe.parent)

    tmp_exe = Path(tempfile.gettempdir()) / exe.name
    try:
        shutil.copy2(exe, tmp_exe)
    except OSError:
        # Fallback: run in-place (can't delete self, but still cleans everything else)
        _do_uninstall(install_dir)
        return 0

    subprocess.Popen(
        [str(tmp_exe), "--do-uninstall", install_dir],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
