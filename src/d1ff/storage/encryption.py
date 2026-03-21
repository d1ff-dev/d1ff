"""Fernet encryption/decryption utilities for the storage layer."""

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from d1ff.storage.exceptions import StorageEncryptionError


def encrypt_value(plaintext: str, key: SecretStr) -> str:
    """Encrypt a plaintext string using Fernet.

    Returns a URL-safe base64 Fernet token as a plain str.
    """
    f = Fernet(key.get_secret_value().encode())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str, key: SecretStr) -> str:
    """Decrypt a Fernet-encrypted ciphertext string.

    Returns the decrypted UTF-8 string.
    Raises StorageEncryptionError on invalid token or wrong key.
    # SECURITY: never log return value
    """
    f = Fernet(key.get_secret_value().encode())
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise StorageEncryptionError("Failed to decrypt value") from exc
