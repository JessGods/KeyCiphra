"""Testes dos dados fictícios opcionais do cofre."""

from __future__ import annotations

from pathlib import Path

from app.models.credential import Credential
from app.repositories.category_repository import CategoryRepository
from app.repositories.credential_repository import CredentialRepository
from app.security.kdf import KDFParameters
from app.services.category_service import CategoryService
from app.services.demo_data_service import DEMO_CREDENTIALS, DemoDataService
from app.services.vault_service import VaultService


FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)
MASTER_PASSWORD = "frase-mestra-ficticia-longa"


def test_demo_dataset_is_complete_encrypted_and_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "vault.db"
    session = VaultService(database_path).create(MASTER_PASSWORD, FAST_TEST_PARAMETERS)
    credentials = CredentialRepository(database_path, session)
    categories = CategoryRepository(database_path, session)
    category_service = CategoryService(categories, credentials)
    category_service.create("Pessoal")
    credentials.add(Credential.create(title="Credencial do usuário", category="Pessoal"))
    service = DemoDataService(category_service, credentials)

    first = service.populate()
    second = service.populate()
    stored = credentials.list_all()
    demo = [item for item in stored if "/keyciphra-demo/" in item.url]

    assert first.created_categories == 9
    assert first.created_credentials == len(DEMO_CREDENTIALS) == 20
    assert second.created_categories == 0
    assert second.created_credentials == 0
    assert len(stored) == 21
    assert len(demo) == 20
    assert len({item.password for item in demo}) == 20
    assert all(len(item.password) >= 20 for item in demo)
    assert all(item.url.startswith("https://example.invalid/") for item in demo)
    assert {item.category for item in demo} == {
        "Pessoal",
        "Financeiro",
        "Trabalho",
        "Desenvolvimento",
        "Estudos",
        "Entretenimento",
        "Compras",
        "Redes sociais",
        "Saúde",
        "Viagens",
    }
    database_bytes = database_path.read_bytes()
    for template in DEMO_CREDENTIALS:
        assert template.title.encode("utf-8") not in database_bytes
        assert template.username.encode("utf-8") not in database_bytes
        assert template.notes.encode("utf-8") not in database_bytes
