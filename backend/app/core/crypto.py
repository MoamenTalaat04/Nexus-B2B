"""Symmetric encryption for secrets at rest (CONTRACTS section 5), e.g. channel access tokens.

Fernet (AES-128-CBC + HMAC-SHA256) keyed by settings.ENCRYPTION_KEY. Generate a key with:
    uv run python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
Never log the plaintext or the token.
"""

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CryptoError(RuntimeError):
    """The key is missing/invalid, or a token cannot be decrypted with the current key."""


@lru_cache(maxsize=4)
def _fernet(key: str) -> Fernet:
    if not key:
        raise CryptoError(
            "ENCRYPTION_KEY is not set. Generate one with `uv run python -c "
            '"from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` '
            "and put it in .env."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise CryptoError("ENCRYPTION_KEY is not a valid Fernet key (32 url-safe base64 bytes).") from exc


def encrypt_json(data: dict[str, Any]) -> str:
    """dict → Fernet token (str)."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _fernet(settings.ENCRYPTION_KEY).encrypt(payload).decode("ascii")


def decrypt_json(token: str) -> dict[str, Any]:
    """Fernet token → dict. Raises CryptoError if the token was made with another key or was tampered with."""
    try:
        raw = _fernet(settings.ENCRYPTION_KEY).decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise CryptoError("Could not decrypt the stored secret (wrong ENCRYPTION_KEY or corrupted).") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise CryptoError("The stored secret is not a JSON object.")
    return data
