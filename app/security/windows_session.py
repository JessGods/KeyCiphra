"""Bloqueio imediato quando a sessão do Windows deixa de estar disponível."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

WM_WTSSESSION_CHANGE = 0x02B1
LOCKING_SESSION_EVENTS = frozenset({2, 4, 6, 7})


def is_locking_session_event(message_id: int, event_code: int) -> bool:
    """Reconhece desconexão, logoff e bloqueio sem depender do Windows nos testes."""
    return message_id == WM_WTSSESSION_CHANGE and event_code in LOCKING_SESSION_EVENTS


class _SessionEventFilter(QAbstractNativeEventFilter):
    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type: bytes, message: int) -> tuple[bool, int]:
        del event_type
        native_message = ctypes.cast(
            int(message),
            ctypes.POINTER(wintypes.MSG),
        ).contents
        if is_locking_session_event(native_message.message, int(native_message.wParam)):
            self._callback()
        return False, 0


class WindowsSessionMonitor(QObject):
    """Emite um sinal quando o Windows bloqueia ou desconecta a sessão atual."""

    session_locked = Signal()

    def __init__(
        self,
        application: QApplication,
        *,
        platform_name: str | None = None,
    ) -> None:
        super().__init__(application)
        self._application = application
        self._window: QWidget | None = None
        self._filter: _SessionEventFilter | None = None
        self._registered = False
        if (platform_name or sys.platform) == "win32":
            self._register()

    def _register(self) -> None:
        wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
        wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
        wtsapi32.WTSRegisterSessionNotification.restype = wintypes.BOOL
        self._window = QWidget()
        self._window.setObjectName("windowsSessionMonitor")
        window_handle = wintypes.HWND(int(self._window.winId()))
        if not wtsapi32.WTSRegisterSessionNotification(window_handle, 0):
            self._window.deleteLater()
            self._window = None
            return
        self._filter = _SessionEventFilter(self.session_locked.emit)
        self._application.installNativeEventFilter(self._filter)
        self._registered = True

    def close(self) -> None:
        if self._filter is not None:
            self._application.removeNativeEventFilter(self._filter)
            self._filter = None
        if self._registered and self._window is not None:
            wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
            wtsapi32.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
            wtsapi32.WTSUnRegisterSessionNotification.restype = wintypes.BOOL
            wtsapi32.WTSUnRegisterSessionNotification(wintypes.HWND(int(self._window.winId())))
        self._registered = False
        if self._window is not None:
            self._window.deleteLater()
            self._window = None
