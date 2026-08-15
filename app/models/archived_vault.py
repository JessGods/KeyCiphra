"""Descrição não secreta de um cofre fora do catálogo ativo."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.managed_vault import ManagedVault


@dataclass(frozen=True, slots=True)
class ArchivedVault:
    archive_key: str
    vault: ManagedVault
    archived_at: str
    has_manifest: bool
