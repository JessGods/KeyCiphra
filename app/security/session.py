"""Sessão desbloqueada do cofre."""

from __future__ import annotations

from app.services.crypto_service import CryptoService


class VaultLockedError(RuntimeError):
    """Indica tentativa de usar uma sessão bloqueada."""


class VaultSession:
    """Mantém material criptográfico somente enquanto o cofre está aberto."""

    def __init__(self, vault_id: str, key: bytes) -> None:
        self.vault_id = vault_id
        self._crypto: CryptoService | None = CryptoService(key)

    @property
    def crypto(self) -> CryptoService:
        """Retorna o serviço enquanto a sessão estiver desbloqueada."""
        if self._crypto is None:
            raise VaultLockedError("O cofre está bloqueado.")
        return self._crypto

    @property
    def is_unlocked(self) -> bool:
        return self._crypto is not None

    def lock(self) -> None:
        """Invalida referências controladas ao material criptográfico."""
        self._crypto = None
