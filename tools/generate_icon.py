"""Gera o ICO multirresolução a partir da identidade vetorial do KeyCiphra."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "assets" / "keyciphra.svg"
DESTINATION = PROJECT_ROOT / "assets" / "keyciphra.ico"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()

    encoded = QByteArray()
    buffer = QBuffer(encoded)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Não foi possível renderizar o ícone de {size}px.")
    buffer.close()
    return bytes(encoded)


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + (16 * len(images))
    entries = bytearray()
    payload = bytearray()
    for size, png in images:
        encoded_size = 0 if size == 256 else size
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                encoded_size,
                encoded_size,
                0,
                0,
                1,
                32,
                len(png),
                offset,
            )
        )
        payload.extend(png)
        offset += len(png)
    return header + bytes(entries) + bytes(payload)


def main() -> int:
    application = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(SOURCE))
    if not renderer.isValid():
        raise RuntimeError(f"SVG inválido: {SOURCE}")
    images = [(size, render_png(renderer, size)) for size in ICON_SIZES]
    DESTINATION.write_bytes(build_ico(images))
    print(f"Ícone criado: {DESTINATION} ({DESTINATION.stat().st_size} bytes)")
    del application
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
