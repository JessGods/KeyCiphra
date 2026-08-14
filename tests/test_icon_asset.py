"""Validação da identidade visual usada pelo Windows e pelo Qt."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402

from app.utils.paths import APP_ICON_PATH  # noqa: E402


def test_application_icon_contains_expected_windows_sizes() -> None:
    application = QGuiApplication.instance() or QGuiApplication([])
    icon = QIcon(str(APP_ICON_PATH))

    assert not icon.isNull()
    assert {(size.width(), size.height()) for size in icon.availableSizes()} == {
        (16, 16),
        (24, 24),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256),
    }
    del application
