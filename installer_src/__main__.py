"""Budget Tracker installer wizard.

Run directly:  python installer_src
Frozen (exe):  BudgetTrackerSetup.exe
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

import install_ops

# ---------------------------------------------------------------------------
# Version embedded by the build script (falls back gracefully)
# ---------------------------------------------------------------------------
try:
    from _installer_version import APP_VERSION  # type: ignore[import]
except ImportError:
    APP_VERSION = "0.1.0"

_APP_NAME = "Budget Tracker"

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
_LOCAL_APPDATA = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
_DEFAULT_INSTALL_DIR = str(Path(_LOCAL_APPDATA) / "BudgetTracker" / "App")
_DEFAULT_DB_DIR      = str(Path(_LOCAL_APPDATA) / "BudgetTracker")


# ---------------------------------------------------------------------------
# Shared stylesheet (dark-violet, matches the app)
# ---------------------------------------------------------------------------
_STYLE = """
QWizard, QWidget {
    background-color: #0A0A0F;
    color: #E8E8EE;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}
QWizardPage {
    background-color: #0A0A0F;
}
QLabel#title {
    font-size: 20px;
    font-weight: 600;
    color: #E8E8EE;
}
QLabel#subtitle {
    color: #9494A8;
    font-size: 13px;
}
QLabel#muted {
    color: #6B6B7A;
    font-size: 12px;
}
QLineEdit {
    background-color: #18181F;
    border: 1px solid #2A2A35;
    border-radius: 6px;
    padding: 8px 10px;
    color: #E8E8EE;
}
QLineEdit:focus { border-color: #7C5CFF; }
QPushButton {
    background-color: #18181F;
    border: 1px solid #2A2A35;
    border-radius: 6px;
    padding: 7px 16px;
    color: #E8E8EE;
}
QPushButton:hover  { background-color: #22222E; border-color: #7C5CFF; }
QPushButton:pressed { background-color: #1A1A26; }
QPushButton#primary {
    background-color: #7C5CFF;
    border-color: #7C5CFF;
    color: #FFFFFF;
    font-weight: 600;
}
QPushButton#primary:hover   { background-color: #8F72FF; }
QPushButton#primary:pressed { background-color: #6A4EE0; }
QCheckBox { spacing: 8px; color: #E8E8EE; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #2A2A35;
    border-radius: 4px;
    background: #18181F;
}
QCheckBox::indicator:checked {
    background: #7C5CFF;
    border-color: #7C5CFF;
    image: none;
}
QProgressBar {
    border: 1px solid #2A2A35;
    border-radius: 6px;
    background-color: #18181F;
    text-align: center;
    color: #E8E8EE;
}
QProgressBar::chunk { background-color: #7C5CFF; border-radius: 5px; }
QTextEdit {
    background-color: #0D0D14;
    border: 1px solid #1E1E28;
    border-radius: 6px;
    color: #6B6B7A;
    font-family: "Consolas", monospace;
    font-size: 11px;
}
"""


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(32, 28, 32, 16)

        title = QLabel(f"Welcome to {_APP_NAME} Setup")
        title.setObjectName("title")
        layout.addWidget(title)

        ver = QLabel(f"Version {APP_VERSION}")
        ver.setObjectName("subtitle")
        layout.addWidget(ver)

        layout.addSpacing(8)

        body = QLabel(
            "This wizard will guide you through installing Budget Tracker "
            "on your computer.\n\n"
            "Budget Tracker is a modern, locally-stored personal finance manager. "
            "Your data never leaves your device.\n\n"
            "Click Next to choose where to install the application."
        )
        body.setWordWrap(True)
        body.setObjectName("subtitle")
        layout.addWidget(body)

        layout.addStretch(1)

        note = QLabel("Click Next to continue, or Cancel to exit Setup.")
        note.setObjectName("muted")
        layout.addWidget(note)


class InstallDirPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installation Folder")
        self.setSubTitle(
            "Choose where Budget Tracker should be installed. "
            "The default location requires no administrator rights."
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 16)
        layout.setSpacing(8)

        self._edit = QLineEdit(_DEFAULT_INSTALL_DIR)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.addWidget(self._edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        hint = QLabel(
            "Installing to your user folder means no administrator prompt is needed."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)

        self.registerField("installDir*", self._edit)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select installation folder", self._edit.text()
        )
        if path:
            self._edit.setText(path)


class DatabasePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Database Location")
        self.setSubTitle(
            "Choose where Budget Tracker stores your financial database. "
            "Pick a synced folder (OneDrive, Dropbox) for automatic backup."
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 16)
        layout.setSpacing(8)

        self._edit = QLineEdit(_DEFAULT_DB_DIR)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.addWidget(self._edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        hint = QLabel(
            "You can move the database later from Settings → Data inside the app."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)

        self.registerField("dbDir", self._edit)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select database folder", self._edit.text()
        )
        if path:
            self._edit.setText(path)


class OptionsPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Install Options")
        self.setSubTitle("Choose additional shortcuts and startup behaviour.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 16)
        layout.setSpacing(14)

        self._desktop_cb = QCheckBox("Create a desktop shortcut")
        self._desktop_cb.setChecked(True)
        layout.addWidget(self._desktop_cb)

        self._startup_cb = QCheckBox(f"Launch {_APP_NAME} automatically when Windows starts")
        self._startup_cb.setChecked(False)
        layout.addWidget(self._startup_cb)

        layout.addStretch(1)

        self.registerField("desktopShortcut", self._desktop_cb)
        self.registerField("launchOnStartup", self._startup_cb)


# ---------------------------------------------------------------------------
# Worker thread that calls install_ops
# ---------------------------------------------------------------------------

class _InstallWorker(QObject):
    progress = Signal(int)    # 0-100
    log      = Signal(str)
    finished = Signal(bool)   # True = success

    def __init__(self, install_dir: str, db_dir: str,
                 desktop: bool, startup: bool, version: str):
        super().__init__()
        self._install_dir = install_dir
        self._db_dir      = db_dir
        self._desktop     = desktop
        self._startup     = startup
        self._version     = version

    def run(self) -> None:
        try:
            install_ops.run_install(
                install_dir  = self._install_dir,
                db_dir       = self._db_dir,
                desktop      = self._desktop,
                startup      = self._startup,
                version      = self._version,
                progress_cb  = lambda p: self.progress.emit(p),
                log_cb       = lambda m: self.log.emit(m),
            )
            self.finished.emit(True)
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"ERROR: {exc}")
            self.finished.emit(False)


class InstallPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installing")
        self.setSubTitle("Please wait while Budget Tracker is being installed…")
        self._complete = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 16)
        layout.setSpacing(10)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(140)
        layout.addWidget(self._log)

        layout.addStretch(1)

    def initializePage(self):
        self._complete = False
        self.completeChanged.emit()
        self._start_install()

    def isComplete(self) -> bool:
        return self._complete

    def _start_install(self):
        install_dir = self.field("installDir")
        db_dir      = self.field("dbDir")
        desktop     = bool(self.field("desktopShortcut"))
        startup     = bool(self.field("launchOnStartup"))

        self._thread = QThread(self)
        self._worker = _InstallWorker(install_dir, db_dir, desktop, startup, APP_VERSION)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _append_log(self, message: str):
        self._log.append(message)

    def _on_finished(self, success: bool):
        if success:
            self._complete = True
            self.completeChanged.emit()
            self.wizard().next()
        else:
            QMessageBox.critical(
                self, "Installation failed",
                "An error occurred during installation. Check the log above for details.",
            )


class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installation complete")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 16)
        layout.setSpacing(12)

        title = QLabel(f"{_APP_NAME} has been installed successfully.")
        title.setObjectName("title")
        title.setWordWrap(True)
        layout.addWidget(title)

        layout.addSpacing(8)

        info = QLabel(
            "Click Finish to exit Setup. "
            "You can launch the app from the Start Menu or desktop shortcut."
        )
        info.setObjectName("subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(16)

        self._launch_cb = QCheckBox(f"Launch {_APP_NAME} now")
        self._launch_cb.setChecked(True)
        layout.addWidget(self._launch_cb)

        layout.addStretch(1)

    def validatePage(self) -> bool:
        if self._launch_cb.isChecked():
            install_dir = self.field("installDir")
            exe = Path(install_dir) / f"{_APP_NAME}.exe"
            if exe.exists():
                import subprocess
                subprocess.Popen([str(exe)], creationflags=subprocess.DETACHED_PROCESS)
        return True


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------

class InstallerWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{_APP_NAME} Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(600, 440)
        self.setStyleSheet(_STYLE)
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage, True)
        self.setOption(QWizard.WizardOption.NoCancelButtonOnLastPage, True)

        self.addPage(WelcomePage())
        self.addPage(InstallDirPage())
        self.addPage(DatabasePage())
        self.addPage(OptionsPage())
        self.addPage(InstallPage())
        self.addPage(FinishPage())

        # Style the wizard buttons
        self.button(QWizard.WizardButton.NextButton).setObjectName("primary")
        self.button(QWizard.WizardButton.FinishButton).setObjectName("primary")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(_APP_NAME)
    wizard = InstallerWizard()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
