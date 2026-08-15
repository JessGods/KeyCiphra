"""Regras de organização e reclassificação de categorias."""

from __future__ import annotations

from dataclasses import replace

from app.models.category import Category
from app.models.credential import Credential
from app.repositories.category_repository import CategoryRepository
from app.repositories.credential_repository import CredentialRepository


class CategoryValidationError(ValueError):
    """Indica nome de categoria vazio, longo ou duplicado."""


class CategoryService:
    """Mantém o catálogo criptografado coerente com as credenciais."""

    MAX_NAME_LENGTH = 60

    def __init__(
        self,
        repository: CategoryRepository,
        credential_repository: CredentialRepository,
    ) -> None:
        self._repository = repository
        self._credential_repository = credential_repository

    def synchronize(self, credentials: list[Credential] | None = None) -> list[Category]:
        """Importa categorias livres antigas sem duplicar nomes equivalentes."""
        known = self._repository.list_all()
        normalized = {self._key(category.name) for category in known}
        source = credentials if credentials is not None else self._credential_repository.list_all()
        for credential in source:
            name = self._clean_optional(credential.category)
            if name and self._key(name) not in normalized:
                created = self._repository.add(Category.create(name))
                known.append(created)
                normalized.add(self._key(name))
        return self._sorted(known)

    def list_all(self) -> list[Category]:
        return self._sorted(self._repository.list_all())

    def create(self, name: str) -> Category:
        clean = self._validate_name(name)
        self._reject_duplicate(clean)
        return self._repository.add(Category.create(clean))

    def rename(self, category_id: str, new_name: str) -> Category:
        clean = self._validate_name(new_name)
        current = self._repository.get(category_id)
        self._reject_duplicate(clean, excluding_id=category_id)
        if current.name == clean:
            return current
        updated = self._repository.update(replace(current, name=clean))
        self._credential_repository.replace_category(current.name, clean)
        return updated

    def delete(self, category_id: str, replacement_name: str = "") -> int:
        current = self._repository.get(category_id)
        replacement = self._clean_optional(replacement_name)
        if replacement and self._key(replacement) == self._key(current.name):
            raise CategoryValidationError("Escolha uma categoria de destino diferente.")
        if replacement and not any(
            self._key(category.name) == self._key(replacement)
            for category in self._repository.list_all()
        ):
            raise CategoryValidationError("A categoria de destino não existe.")
        changed = self._credential_repository.replace_category(current.name, replacement)
        self._repository.delete(category_id)
        return changed

    def usage_count(self, name: str) -> int:
        key = self._key(name)
        return sum(
            1
            for credential in self._credential_repository.list_all()
            if self._key(credential.category) == key
        )

    def _reject_duplicate(self, name: str, *, excluding_id: str | None = None) -> None:
        key = self._key(name)
        if any(
            category.id != excluding_id and self._key(category.name) == key
            for category in self._repository.list_all()
        ):
            raise CategoryValidationError("Já existe uma categoria com esse nome.")

    @classmethod
    def _validate_name(cls, name: str) -> str:
        clean = cls._clean_optional(name)
        if not clean:
            raise CategoryValidationError("Informe um nome para a categoria.")
        if len(clean) > cls.MAX_NAME_LENGTH:
            raise CategoryValidationError(
                f"Use no máximo {cls.MAX_NAME_LENGTH} caracteres no nome da categoria."
            )
        return clean

    @staticmethod
    def _clean_optional(name: str) -> str:
        return " ".join(name.strip().split())

    @classmethod
    def _key(cls, name: str) -> str:
        return cls._clean_optional(name).casefold()

    @staticmethod
    def _sorted(categories: list[Category]) -> list[Category]:
        return sorted(categories, key=lambda category: category.name.casefold())
