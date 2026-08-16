"""Exclusão mútua para proteger o catálogo contra duas instâncias."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile


class ApplicationAlreadyRunningError(RuntimeError):
    """Indica que outra instância ativa já controla os cofres locais."""


def acquire_instance_lock(path: Path) -> QLockFile:
    """Adquire um lock vitalício; locks de processo ativo nunca expiram por tempo."""
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise ApplicationAlreadyRunningError("O KeyCiphra já está aberto.")
    return lock
