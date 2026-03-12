"""API key hashing (SHA-256), constant-time comparison, bcrypt password hashing."""

import hashlib
import secrets

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key(env: str = "dev") -> tuple[str, str, str]:
	"""Generate and return (full_key, key_hash, key_prefix)."""
	normalized_env = env.lower().strip()
	if normalized_env not in {"dev", "prod"}:
		normalized_env = "dev"

	key_id = secrets.token_hex(4)
	secret = secrets.token_hex(16)
	raw = f"opai_{normalized_env}_{key_id}_{secret}"
	checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:4]
	full_key = f"{raw}{checksum}"
	key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
	key_prefix = full_key[:18]
	return full_key, key_hash, key_prefix


def verify_api_key(api_key: str, stored_hash: str) -> bool:
	"""Hash provided key and compare against stored hash in constant time."""
	computed = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
	return secrets.compare_digest(computed, stored_hash)


def hash_password(password: str) -> str:
	"""Hash password using bcrypt via passlib."""
	return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
	"""Verify plain password against hashed bcrypt string."""
	return pwd_context.verify(plain, hashed)
