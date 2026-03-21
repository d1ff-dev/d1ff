"""Tests for storage encryption utilities."""

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from d1ff.storage.encryption import decrypt_value, encrypt_value
from d1ff.storage.exceptions import StorageEncryptionError


@pytest.fixture
def test_fernet_key() -> SecretStr:
    return SecretStr(Fernet.generate_key().decode())


def test_encrypt_decrypt_roundtrip(test_fernet_key: SecretStr) -> None:
    plaintext = "my-super-secret-api-key"
    ciphertext = encrypt_value(plaintext, test_fernet_key)
    result = decrypt_value(ciphertext, test_fernet_key)
    assert result == plaintext


def test_invalid_token_raises_storage_error(test_fernet_key: SecretStr) -> None:
    tampered = "not-a-valid-fernet-token"
    with pytest.raises(StorageEncryptionError):
        decrypt_value(tampered, test_fernet_key)


def test_decrypt_wrong_key_raises_storage_error(test_fernet_key: SecretStr) -> None:
    plaintext = "my-super-secret-api-key"
    ciphertext = encrypt_value(plaintext, test_fernet_key)

    other_key = SecretStr(Fernet.generate_key().decode())
    with pytest.raises(StorageEncryptionError):
        decrypt_value(ciphertext, other_key)
