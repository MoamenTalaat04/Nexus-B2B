"""P0-2: app.core.crypto round-trip and failure modes."""

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.core import crypto


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> str:
    value = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", value)
    return value


def test_round_trip(key: str) -> None:
    data = {"access_token": "EAAG-secret", "nested": {"n": 1}, "arabic": "مرحبا"}
    token = crypto.encrypt_json(data)
    assert "EAAG" not in token
    assert crypto.decrypt_json(token) == data


def test_tokens_differ_each_time(key: str) -> None:
    assert crypto.encrypt_json({"a": 1}) != crypto.encrypt_json({"a": 1})


def test_wrong_key_is_a_clear_error(key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    token = crypto.encrypt_json({"a": 1})
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(crypto.CryptoError, match="decrypt"):
        crypto.decrypt_json(token)


def test_missing_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", "")
    with pytest.raises(crypto.CryptoError, match="ENCRYPTION_KEY is not set"):
        crypto.encrypt_json({"a": 1})


def test_invalid_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", "not-a-key")
    with pytest.raises(crypto.CryptoError, match="not a valid Fernet key"):
        crypto.encrypt_json({"a": 1})
