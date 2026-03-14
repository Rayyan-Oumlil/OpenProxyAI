"""Symmetric encryption for sensitive secrets stored in the database.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
The encryption key is derived deterministically from SECRET_KEY via PBKDF2 so
that secrets can be decrypted across restarts as long as SECRET_KEY is stable.

Usage:
    from app.services.crypto_service import encrypt, decrypt

    ciphertext = encrypt("sk-ant-api03-...")
    plaintext  = decrypt(ciphertext)
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

# Fixed salt — security comes from SECRET_KEY, not the salt.
# Changing this salt invalidates all existing ciphertexts.
_SALT = b"openproxyai-llm-provider-keys-v1"
_PBKDF2_ITERATIONS = 100_000

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
	"""Return (and cache) the Fernet instance derived from SECRET_KEY."""
	global _fernet
	if _fernet is None:
		kdf = PBKDF2HMAC(
			algorithm=hashes.SHA256(),
			length=32,
			salt=_SALT,
			iterations=_PBKDF2_ITERATIONS,
		)
		key_bytes = kdf.derive(settings.SECRET_KEY.encode())
		_fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
	return _fernet


def encrypt(plaintext: str) -> str:
	"""Return a URL-safe base64 Fernet token for *plaintext*."""
	return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
	"""Decrypt a Fernet token produced by :func:`encrypt`.

	Raises :class:`ValueError` if the token is invalid or tampered with.
	"""
	try:
		return _get_fernet().decrypt(ciphertext.encode()).decode()
	except InvalidToken as exc:
		raise ValueError("Failed to decrypt value — token is invalid or the SECRET_KEY has changed") from exc
