"""Testes do serviço AES-256-GCM."""

import pytest

from app.services.crypto_service import CryptoService, DecryptionError, EncryptedData


@pytest.fixture
def service() -> CryptoService:
    return CryptoService(bytes(range(32)))


def test_encrypt_decrypt_returns_original_plaintext(service: CryptoService) -> None:
    plaintext = b"segredo de teste"
    encrypted = service.encrypt(plaintext)

    assert service.decrypt(encrypted) == plaintext


def test_encryptions_use_different_nonces_and_ciphertexts(service: CryptoService) -> None:
    first = service.encrypt(b"mesmo valor")
    second = service.encrypt(b"mesmo valor")

    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext


def test_wrong_key_fails_authentication(service: CryptoService) -> None:
    encrypted = service.encrypt(b"segredo")
    other_service = CryptoService(b"x" * 32)

    with pytest.raises(DecryptionError):
        other_service.decrypt(encrypted)


def test_modified_ciphertext_fails_authentication(service: CryptoService) -> None:
    encrypted = service.encrypt(b"segredo")
    modified = bytearray(encrypted.ciphertext)
    modified[0] ^= 1

    with pytest.raises(DecryptionError):
        service.decrypt(EncryptedData(encrypted.nonce, bytes(modified)))


def test_modified_nonce_fails_authentication(service: CryptoService) -> None:
    encrypted = service.encrypt(b"segredo")
    modified = bytearray(encrypted.nonce)
    modified[0] ^= 1

    with pytest.raises(DecryptionError):
        service.decrypt(EncryptedData(bytes(modified), encrypted.ciphertext))


def test_empty_plaintext(service: CryptoService) -> None:
    encrypted = service.encrypt(b"")

    assert service.decrypt(encrypted) == b""


def test_unicode_text(service: CryptoService) -> None:
    plaintext = "Senha longa: café, 🔐 e 日本語"
    encrypted = service.encrypt_text(plaintext)

    assert service.decrypt_text(encrypted) == plaintext


def test_associated_data_is_authenticated(service: CryptoService) -> None:
    encrypted = service.encrypt(b"segredo", associated_data=b"credential:42")

    with pytest.raises(DecryptionError):
        service.decrypt(encrypted, associated_data=b"credential:43")


def test_rejects_non_aes_256_key() -> None:
    with pytest.raises(ValueError):
        CryptoService(b"curta")
