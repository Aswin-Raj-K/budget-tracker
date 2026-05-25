# budget_tracker.spec
# Usage: pyinstaller budget_tracker.spec --clean --noconfirm

import os
import re

block_cipher = None

datas = [
    ("budget_tracker/core/migrations/*.sql",   "budget_tracker/core/migrations"),
    ("budget_tracker/ui/styles/*.template",    "budget_tracker/ui/styles"),
    ("budget_tracker/ui/styles/themes/*.json", "budget_tracker/ui/styles/themes"),
    ("budget_tracker/ui/icons/*.svg",          "budget_tracker/ui/icons"),
    ("budget_tracker/ui/icons/*.ico",          "budget_tracker/ui/icons"),
]

hiddenimports = [
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtXml",
]

# Qt modules this app never uses — excluding them from Python imports
# prevents the PySide6 hook from pulling in their .pyd bindings.
excludes = [
    "tkinter", "unittest", "pydoc",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.QtQmlModels",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtMultimedia",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
]

a = Analysis(
    ["budget_tracker/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# Strip DLLs that the PySide6 hook collects regardless of the excludes list.
#
# Savings breakdown (approximate):
#   opengl32sw  — 19.7 MB  software OpenGL rasterizer, unnecessary on any
#                           system with actual GPU drivers (all Win10+ machines)
#   Qt6Quick    —  6.3 MB  QML/Quick UI framework, app uses Widgets only
#   Qt6Qml      —  5.1 MB  QML engine
#   Qt6Pdf      —  4.4 MB  PDF rendering, unused
#   Qt6QmlModels—  0.9 MB  QML data models
#   Qt6Network  —  1.7 MB  Qt networking stack; update check uses urllib/ssl
#   QtNetwork   —  1.0 MB  Python binding for Qt6Network
#
# Qt6OpenGL is intentionally kept — Qt6Widgets uses it for hardware rendering.
# SSL/crypto libs are kept — urllib (used by the update checker) needs them.
# ---------------------------------------------------------------------------
_STRIP = re.compile(
    r"^(opengl32sw|Qt6Quick|Qt6Qml|Qt6Pdf|Qt6Network|QtNetwork)",
    re.IGNORECASE,
)

a.binaries = [
    (name, path, kind)
    for name, path, kind in a.binaries
    if not _STRIP.match(os.path.basename(name))
]

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
    upx=False,   # UPX not installed; set to True if you install it later
    console=False,
    icon="budget_tracker/ui/icons/budget_tracker_icon.ico",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Budget Tracker",
)
