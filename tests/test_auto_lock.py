"""Testes do temporizador de bloqueio automático."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.security.auto_lock import AutoLockManager


def test_auto_lock_emits_once_and_stops() -> None:
    application = QApplication.instance() or QApplication([])
    manager = AutoLockManager(application, timeout_seconds=300)
    emissions: list[bool] = []
    manager.timed_out.connect(lambda: emissions.append(True))

    manager.start()
    manager._on_timeout()
    manager._on_timeout()

    assert emissions == [True]
    assert not manager.is_active


def test_auto_lock_can_be_started_stopped_and_reset() -> None:
    application = QApplication.instance() or QApplication([])
    manager = AutoLockManager(application, timeout_seconds=300)

    manager.start()
    manager.reset()
    assert manager.is_active

    manager.stop()
    assert not manager.is_active


def test_auto_lock_rejects_invalid_timeout() -> None:
    application = QApplication.instance() or QApplication([])

    with pytest.raises(ValueError):
        AutoLockManager(application, timeout_seconds=0)


def test_auto_lock_timeout_can_be_updated_while_active() -> None:
    application = QApplication.instance() or QApplication([])
    manager = AutoLockManager(application, timeout_seconds=300)
    manager.start()

    manager.set_timeout_seconds(720)

    assert manager.timeout_seconds == 720
    assert manager.is_active
