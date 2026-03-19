"""Unit tests for crypto_service — Fernet encrypt/decrypt round-trips."""

import pytest

import app.services.crypto_service as crypto_mod
from app.services.crypto_service import decrypt, encrypt


@pytest.fixture(autouse=True)
def _reset_fernet_cache():
    """Clear module-level _fernet cache to avoid cross-test poisoning."""
    crypto_mod._fernet = None
    yield
    crypto_mod._fernet = None


# ── encrypt ─────────────────────────────────────────────────────────────


class TestEncrypt:
    def test_returns_nonempty_string(self):
        ct = encrypt("hello")
        assert isinstance(ct, str)
        assert len(ct) > 0

    def test_ciphertext_differs_from_plaintext(self):
        ct = encrypt("my-secret")
        assert ct != "my-secret"

    def test_multiple_encryptions_produce_different_ciphertexts(self):
        results = {encrypt("same-input") for _ in range(5)}
        assert len(results) > 1, "Fernet should produce non-deterministic ciphertexts"


# ── round-trip (decrypt ∘ encrypt) ──────────────────────────────────────


class TestRoundTrip:
    @pytest.mark.parametrize(
        "plaintext",
        [
            "",
            "hello world",
            "sk-ant-api03-VERY-LONG-KEY-" + "x" * 500,
            "日本語テスト 🚀 emojis ñ ü ö",
            "line1\nline2\ttab",
            'quotes "and" \'single\' too',
        ],
        ids=["empty", "basic", "long", "unicode", "whitespace", "quotes"],
    )
    def test_decrypt_inverts_encrypt(self, plaintext: str):
        assert decrypt(encrypt(plaintext)) == plaintext


# ── decrypt error handling ──────────────────────────────────────────────


class TestDecryptErrors:
    def test_invalid_ciphertext_raises_value_error(self):
        with pytest.raises(ValueError, match="invalid"):
            decrypt("not-a-valid-fernet-token")

    def test_tampered_ciphertext_raises_value_error(self):
        ct = encrypt("secret")
        tampered = ct[:-4] + "XXXX"
        with pytest.raises(ValueError):
            decrypt(tampered)

    def test_empty_ciphertext_raises_value_error(self):
        with pytest.raises(ValueError):
            decrypt("")

    def test_garbage_bytes_raises_value_error(self):
        with pytest.raises(ValueError):
            decrypt("aGVsbG8gd29ybGQ=")
