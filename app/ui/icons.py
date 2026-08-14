"""Ícones vetoriais Lucide renderizados localmente pelo Qt.

Os desenhos usam viewBox 24×24, traço arredondado e não exigem rede em tempo
de execução. Lucide é distribuído sob licença ISC.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_ICON_NODES = {
    "alert-triangle": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
        '<path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    "check": '<path d="m20 6-11 11-5-5"/>',
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    ),
    "database-backup": (
        '<ellipse cx="12" cy="5" rx="8" ry="3"/>'
        '<path d="M4 5v6c0 1.7 3.6 3 8 3 1.1 0 2.1-.1 3-.3"/>'
        '<path d="M4 11v6c0 1.7 3.6 3 8 3"/>'
        '<path d="m16 19 2 2 4-4"/>'
    ),
    "eye": (
        '<path d="M2.06 12.35a1 1 0 0 1 0-.7C3.73 7.6 7.6 5 12 5c4.4 0 8.27 2.6 9.94 6.65a1 1 0 0 1 0 .7C20.27 16.4 16.4 19 12 19c-4.4 0-8.27-2.6-9.94-6.65"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "eye-off": (
        '<path d="m2 2 20 20"/>'
        '<path d="M6.71 6.71C4.96 7.91 3.57 9.6 2.74 11.65a1 1 0 0 0 0 .7C4.41 16.4 8.28 19 12 19c1.48 0 2.9-.3 4.18-.84"/>'
        '<path d="M10.73 5.08A9.8 9.8 0 0 1 12 5c4.4 0 8.27 2.6 9.94 6.65a1 1 0 0 1 0 .7 10.1 10.1 0 0 1-1.55 2.64"/>'
        '<path d="M14.12 14.12A3 3 0 0 1 9.88 9.88"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "maximize": '<rect width="16" height="16" x="4" y="4" rx="2"/>',
    "minimize": '<path d="M5 12h14"/>',
    "pencil": (
        '<path d="M21.17 6.81a1 1 0 0 0-3.98-3.98L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.36a.5.5 0 0 0 .62.62L7 20.66a2 2 0 0 0 .83-.5z"/>'
        '<path d="m15 5 4 4"/>'
    ),
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "restore": (
        '<rect width="13" height="13" x="3" y="8" rx="2"/>'
        '<path d="M8 8V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-3"/>'
    ),
    "shield-check": (
        '<path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3z"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "sparkles": (
        '<path d="m12 3-1.9 5.1L5 10l5.1 1.9L12 17l1.9-5.1L19 10l-5.1-1.9z"/>'
        '<path d="M5 3v4"/><path d="M3 5h4"/><path d="M19 17v4"/><path d="M17 19h4"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
    ),
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "x-circle": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
}


def lucide_icon(name: str, color: str = "#dbeafe", size: int = 20) -> QIcon:
    """Cria um QIcon nítido a partir de um desenho Lucide incorporado."""
    try:
        nodes = _ICON_NODES[name]
    except KeyError as exc:
        raise ValueError(f"Ícone Lucide desconhecido: {name}") from exc

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"
         viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2"
         stroke-linecap="round" stroke-linejoin="round">{nodes}</svg>
    """
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
