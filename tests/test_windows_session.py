"""Testes dos eventos que exigem bloqueio imediato do cofre."""

import pytest

from app.security.windows_session import WM_WTSSESSION_CHANGE, is_locking_session_event


@pytest.mark.parametrize("event_code", [2, 4, 6, 7])
def test_locking_windows_session_events_are_recognized(event_code: int) -> None:
    assert is_locking_session_event(WM_WTSSESSION_CHANGE, event_code)


@pytest.mark.parametrize("event_code", [1, 3, 5, 8])
def test_logon_and_unlock_events_do_not_lock(event_code: int) -> None:
    assert not is_locking_session_event(WM_WTSSESSION_CHANGE, event_code)


def test_unrelated_native_message_is_ignored() -> None:
    assert not is_locking_session_event(0x1234, 7)
