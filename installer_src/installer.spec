# installer.spec
# Builds BudgetTrackerSetup.exe — a single self-contained installer executable.
# Must be run AFTER build.ps1 has produced:
#   ../build/app_bundle.zip
#   ../build/uninstaller/BudgetTrackerUninstall.exe

block_cipher = None

datas = [
    ("../build/app_bundle.zip",                                        "."),
    ("../build/uninstaller/BudgetTrackerUninstall.exe",                "."),
    ("../budget_tracker/ui/icons/budget_tracker_icon.ico",             "."),
]

a = Analysis(
    ["__main__.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtSvg", "install_ops"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile: single distributable exe
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BudgetTrackerSetup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="../budget_tracker/ui/icons/budget_tracker_icon.ico",
    disable_windowed_traceback=False,
)
