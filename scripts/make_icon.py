"""Convert budget_tracker_icon.svg to a multi-resolution .ico file.

Usage:
    python scripts/make_icon.py

Requires: PySide6 (already a project dep), Pillow (dev dep).
Output:   budget_tracker/ui/icons/budget_tracker_icon.ico
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

_SVG = Path(__file__).parent.parent / "budget_tracker" / "ui" / "icons" / "budget_tracker_icon.svg"
_ICO = _SVG.with_suffix(".ico")

# Sizes to embed in the ICO.  Pillow downsamples from the 256 source image.
_ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def main() -> None:
    QApplication.instance() or QApplication(sys.argv)

    renderer = QSvgRenderer(str(_SVG))
    if not renderer.isValid():
        raise RuntimeError(f"Failed to load SVG: {_SVG}")

    # Render at 256×256 — Pillow downsamples to all other ICO sizes.
    qimg = QImage(256, 256, QImage.Format.Format_ARGB32)
    qimg.fill(Qt.GlobalColor.transparent)
    painter = QPainter(qimg)
    renderer.render(painter)
    painter.end()

    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    if not qimg.save(tmp):
        raise RuntimeError("QImage.save() failed")

    img = Image.open(tmp).copy()
    os.unlink(tmp)

    img.save(_ICO, format="ICO", sizes=_ICO_SIZES)
    print(f"Written: {_ICO}  ({_ICO.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
