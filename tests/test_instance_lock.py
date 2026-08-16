"""Testes da proteção contra duas instâncias simultâneas."""

from pathlib import Path

import pytest

from app.security.instance_lock import (
    ApplicationAlreadyRunningError,
    acquire_instance_lock,
)


def test_second_instance_is_rejected_until_first_unlocks(tmp_path: Path) -> None:
    path = tmp_path / ".keyciphra.lock"
    first = acquire_instance_lock(path)
    try:
        with pytest.raises(ApplicationAlreadyRunningError):
            acquire_instance_lock(path)
    finally:
        first.unlock()

    second = acquire_instance_lock(path)
    second.unlock()
