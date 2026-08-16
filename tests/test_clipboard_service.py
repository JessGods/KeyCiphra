"""Testes do clipboard temporário e das exclusões do Windows."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.services.clipboard_service import (  # noqa: E402
    WINDOWS_EXCLUDE_MONITOR,
    WINDOWS_INCLUDE_HISTORY,
    WINDOWS_UPLOAD_CLOUD,
    ClipboardService,
)


def test_windows_secret_is_excluded_from_history_and_cloud() -> None:
    application = QApplication.instance() or QApplication([])
    clipboard = application.clipboard()
    service = ClipboardService(clipboard, platform_name="win32")

    service.copy_secret("segredo-ficticio")

    mime = clipboard.mimeData()
    assert clipboard.text() == "segredo-ficticio"
    assert bytes(mime.data(WINDOWS_EXCLUDE_MONITOR)) == b"1"
    assert bytes(mime.data(WINDOWS_INCLUDE_HISTORY)) == b"\x00\x00\x00\x00"
    assert bytes(mime.data(WINDOWS_UPLOAD_CLOUD)) == b"\x00\x00\x00\x00"
    service.clear_secret()


def test_secret_is_only_cleared_if_unchanged() -> None:
    application = QApplication.instance() or QApplication([])
    clipboard = application.clipboard()
    service = ClipboardService(clipboard, platform_name="linux")
    service.copy_secret("segredo-controlado")
    clipboard.setText("texto-do-usuario")

    service.clear_secret()

    assert clipboard.text() == "texto-do-usuario"
