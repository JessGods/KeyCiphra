"""Testes do encerramento limpo pelo terminal."""

from __future__ import annotations

import os
import signal
from collections.abc import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.main import (  # noqa: E402
    SIGNAL_POLL_INTERVAL_MS,
    install_graceful_interrupt_handler,
)


def test_ctrl_c_uses_qt_shutdown_instead_of_keyboard_interrupt(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    application = QApplication.instance() or QApplication([])
    handlers: dict[int, Callable[[int, object], None]] = {}

    monkeypatch.setattr(
        signal,
        "signal",
        lambda number, handler: handlers.__setitem__(number, handler),
    )

    poller = install_graceful_interrupt_handler(application)

    assert signal.SIGINT in handlers
    assert poller.isActive()
    assert poller.interval() == SIGNAL_POLL_INTERVAL_MS
    handlers[signal.SIGINT](signal.SIGINT, None)
    poller.stop()
