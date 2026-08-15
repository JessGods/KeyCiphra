"""Bloqueio da sessão após inatividade do usuário."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication


_ACTIVITY_EVENTS = {
    QEvent.Type.KeyPress,
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonDblClick,
    QEvent.Type.MouseMove,
    QEvent.Type.Wheel,
    QEvent.Type.TouchBegin,
    QEvent.Type.TabletPress,
}


class AutoLockManager(QObject):
    """Reinicia um temporizador em eventos reais de entrada do usuário."""

    timed_out = Signal()

    def __init__(self, application: QApplication, timeout_seconds: int = 300) -> None:
        if timeout_seconds < 1:
            raise ValueError("O tempo de bloqueio deve ser positivo.")
        super().__init__(application)
        self._application = application
        self._active = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_seconds * 1_000)
        self._timer.timeout.connect(self._on_timeout)
        application.installEventFilter(self)

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def timeout_seconds(self) -> int:
        return self._timer.interval() // 1_000

    def set_timeout_seconds(self, timeout_seconds: int) -> None:
        if timeout_seconds < 1:
            raise ValueError("O tempo de bloqueio deve ser positivo.")
        self._timer.setInterval(timeout_seconds * 1_000)
        if self._active:
            self._timer.start()

    def start(self) -> None:
        self._active = True
        self._timer.start()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()

    def reset(self) -> None:
        if self._active:
            self._timer.start()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._active and event.type() in _ACTIVITY_EVENTS:
            self.reset()
        return super().eventFilter(watched, event)

    def _on_timeout(self) -> None:
        if not self._active:
            return
        self._active = False
        self.timed_out.emit()
