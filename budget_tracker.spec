# budget_tracker.spec
# Usage: pyinstaller budget_tracker.spec --clean --noconfirm

block_cipher = None

datas = [
    ("budget_tracker/core/migrations/*.sql",   "budget_tracker/core/migrations"),
    ("budget_tracker/ui/styles/*.template",    "budget_tracker/ui/styles"),
    ("budget_tracker/ui/styles/themes/*.json", "budget_tracker/ui/styles/themes"),
    ("budget_tracker/ui/icons/*.svg",          "budget_tracker/ui/icons"),
]

hiddenimports = [
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtXml",
]

a = Analysis(
    ["budget_tracker/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Budget Tracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Budget Tracker",
)
