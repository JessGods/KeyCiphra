"""Clipboard temporário sem registrar o conteúdo copiado."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QClipboard


class ClipboardService(QObject):
    """Copia um segredo e o remove se ainda estiver no clipboard ao expirar."""

    cleared = Signal()

    def __init__(self, clipboard: QClipboard, timeout_seconds: int = 25) -> None:
        if timeout_seconds < 1:
            raise ValueError("O tempo do clipboard deve ser positivo.")
        super().__init__()
        self._clipboard = clipboard
        self._last_value: str | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_seconds * 1_000)
        self._timer.timeout.connect(self.clear_if_unchanged)

    @property
    def timeout_seconds(self) -> int:
        return self._timer.interval() // 1_000

    def set_timeout_seconds(self, timeout_seconds: int) -> None:
        if timeout_seconds < 1:
            raise ValueError("O tempo do clipboard deve ser positivo.")
        self._timer.setInterval(timeout_seconds * 1_000)
        if self._timer.isActive():
            self._timer.start()

    def copy_secret(self, value: str) -> None:
        self._last_value = value
        self._clipboard.setText(value)
        self._timer.start()

    def clear_if_unchanged(self) -> None:
        if self._last_value is not None and self._clipboard.text() == self._last_value:
            self._clipboard.clear()
            self.cleared.emit()
        self._last_value = None

    def clear_secret(self) -> None:
        """Interrompe o temporizador e remove somente o segredo ainda controlado."""
        self._timer.stop()
        self.clear_if_unchanged()
