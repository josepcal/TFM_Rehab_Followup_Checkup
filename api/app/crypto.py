"""Application-layer encryption for sensitive PII columns (national_id).

Key management:
- Dev:  NATIONAL_ID_ENCRYPTION_KEY env var (base64-url Fernet key)
- Prod: replace get_fernet() with a KMS-backed key fetch

Generate a key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        from app.config import get_settings
        key = get_settings().national_id_encryption_key
        if not key:
            raise RuntimeError(
                "NATIONAL_ID_ENCRYPTION_KEY is not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_field(plaintext: str) -> bytes:
    return get_fernet().encrypt(plaintext.encode())


def decrypt_field(ciphertext: bytes | memoryview) -> str:
    try:
        return get_fernet().decrypt(bytes(ciphertext)).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt field — wrong key or corrupted data") from exc
