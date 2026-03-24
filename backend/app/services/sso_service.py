"""OIDC/SSO service — OIDC discovery, state management, token exchange, JIT provisioning."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sso_connection import SSOConnection
from app.models.user import User
from app.services.auth_service import create_access_token, create_refresh_token
from app.services.crypto_service import decrypt, encrypt

logger = logging.getLogger(__name__)


_STATE_TTL = 600  # 10 minutes
_SSO_CODE_TTL = 90  # 90 seconds for one-time code exchange


async def create_sso_connection(
    db: AsyncSession,
    org_id: str,
    provider_name: str,
    issuer_url: str,
    client_id: str,
    client_secret: str,
    domain_hint: str | None,
) -> SSOConnection:
    """Encrypt client_secret and persist the SSO connection."""
    encrypted = encrypt(client_secret)
    connection = SSOConnection(
        org_id=org_id,
        provider_name=provider_name,
        issuer_url=issuer_url.rstrip("/"),
        client_id=client_id,
        client_secret_encrypted=encrypted,
        domain_hint=domain_hint,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


async def list_sso_connections(
    db: AsyncSession, org_id: str
) -> list[SSOConnection]:
    """Return all SSO connections for an organization."""
    result = await db.execute(
        select(SSOConnection).where(SSOConnection.org_id == org_id)
    )
    return list(result.scalars().all())


async def delete_sso_connection(
    db: AsyncSession, org_id: str, connection_id: str
) -> bool:
    """Delete an SSO connection by id, scoped to org. Returns True if found."""
    result = await db.execute(
        select(SSOConnection).where(
            SSOConnection.id == connection_id,
            SSOConnection.org_id == org_id,
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        return False
    await db.delete(conn)
    await db.commit()
    return True


async def _fetch_oidc_config(issuer_url: str) -> dict[str, Any]:
    """Fetch OIDC discovery document from {issuer}/.well-known/openid-configuration."""
    discovery_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(discovery_url)
        response.raise_for_status()
        return response.json()


def _get_allowed_redirect_uri() -> str:
    """Return the single allowed redirect_uri for OIDC callback (C02)."""
    base = settings.APP_BASE_URL.rstrip("/")
    return f"{base}/api/v1/auth/sso/callback"


def _validate_redirect_uri(redirect_uri: str) -> None:
    """Validate redirect_uri against allowlist; raise if invalid (C02)."""
    allowed = _get_allowed_redirect_uri()
    if not redirect_uri or redirect_uri.strip() != allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri — must match configured APP_BASE_URL callback",
        )


async def initiate_sso(
    db: AsyncSession,
    redis: Redis,
    connection_id: str,
    redirect_uri: str,
) -> str:
    """Return the IdP authorization URL and store state in Redis."""
    _validate_redirect_uri(redirect_uri)
    result = await db.execute(
        select(SSOConnection).where(
            SSOConnection.id == connection_id,
            SSOConnection.is_active == True,  # noqa: E712
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO connection not found",
        )

    oidc_config = await _fetch_oidc_config(conn.issuer_url)
    authorization_endpoint = oidc_config["authorization_endpoint"]

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    state_data = json.dumps({
        "connection_id": str(conn.id),
        "nonce": nonce,
        "redirect_uri": redirect_uri,
    })
    await redis.setex(f"sso_state:{state}", _STATE_TTL, state_data)

    params = {
        "response_type": "code",
        "client_id": conn.client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    return f"{authorization_endpoint}?{urlencode(params)}"


async def handle_sso_callback(
    db: AsyncSession,
    redis: Redis,
    code: str,
    state: str,
    redirect_uri: str,
    base_url: str,
) -> tuple[str, str]:
    """
    Exchange code for tokens, validate id_token, JIT-provision user.
    Returns (access_token, refresh_token).
    """
    raw_state = await redis.get(f"sso_state:{state}")
    if raw_state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired SSO state",
        )

    state_data = json.loads(raw_state)
    await redis.delete(f"sso_state:{state}")

    connection_id = state_data["connection_id"]
    expected_nonce = state_data["nonce"]
    # Use redirect_uri from state (validated at initiate) — OIDC requires exact match
    token_redirect_uri = state_data["redirect_uri"]

    result = await db.execute(
        select(SSOConnection).where(SSOConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO connection not found",
        )

    oidc_config = await _fetch_oidc_config(conn.issuer_url)
    token_endpoint = oidc_config["token_endpoint"]

    client_secret = decrypt(conn.client_secret_encrypted)
    async with httpx.AsyncClient(timeout=15) as http:
        token_response = await http.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": token_redirect_uri,
                "client_id": conn.client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not token_response.is_success:
            logger.warning("IdP token exchange failed (status=%s): %s", token_response.status_code, token_response.text[:500])
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="IdP token exchange failed",
            )
        token_data = token_response.json()

    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No id_token in IdP response",
        )

    jwks_uri = oidc_config.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="IdP discovery missing jwks_uri",
        )
    claims = _verify_and_decode_id_token(
        id_token=id_token,
        jwks_uri=jwks_uri,
        client_id=conn.client_id,
        issuer=oidc_config.get("issuer", conn.issuer_url.rstrip("/")),
    )

    if claims.get("nonce") != expected_nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid nonce in id_token",
        )

    email: str | None = claims.get("email")
    sub: str = claims.get("sub", "")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email claim in id_token",
        )

    user = await _find_or_provision_user(db, conn, email, sub)

    access_token = create_access_token(str(user.id), str(user.org_id), user.role)
    refresh_token = create_refresh_token(str(user.id), str(user.org_id), user.role)
    return access_token, refresh_token


async def create_sso_code(
    redis: Redis,
    access_token: str,
    refresh_token: str,
) -> str:
    """Store tokens in Redis under a one-time code; return the code (C03)."""
    code = secrets.token_urlsafe(32)
    payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    await redis.setex(f"sso_code:{code}", _SSO_CODE_TTL, payload)
    return code


async def exchange_sso_code(redis: Redis, code: str) -> tuple[str, str]:
    """Exchange one-time code for tokens; delete code from Redis. Raises if invalid."""
    key = f"sso_code:{code}"
    raw = await redis.get(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired SSO code",
        )
    await redis.delete(key)
    data = json.loads(raw)
    return data["access_token"], data["refresh_token"]


def _verify_and_decode_id_token(
    id_token: str,
    jwks_uri: str,
    client_id: str,
    issuer: str,
) -> dict[str, Any]:
    """Verify id_token signature via JWKS and decode payload (C01)."""
    try:
        jwks_client = PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256", "PS256"],
            audience=client_id,
            issuer=issuer,
            options={"verify_nonce": False},  # we verify nonce ourselves
        )
        return payload
    except jwt.PyJWKClientError as e:
        logger.warning("IdP JWKS error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SSO authentication failed",
        ) from e
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid id_token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO authentication failed",
        ) from e


async def _find_or_provision_user(
    db: AsyncSession,
    conn: SSOConnection,
    email: str,
    sub: str,
) -> User:
    """Find existing user by email in org or JIT-provision a new one."""
    result = await db.execute(
        select(User).where(User.email == email, User.org_id == conn.org_id)
    )
    user = result.scalar_one_or_none()

    if user is not None:
        if user.sso_sub != sub:
            user.sso_sub = sub
            user.sso_connection_id = conn.id
            await db.commit()
            await db.refresh(user)
        return user

    # JIT provision
    provisioned = User(
        org_id=conn.org_id,
        email=email,
        name=email.split("@")[0],
        password_hash="sso_provisioned",  # placeholder — can't log in with password
        role="developer",
        sso_sub=sub,
        sso_connection_id=conn.id,
    )
    db.add(provisioned)
    await db.commit()
    await db.refresh(provisioned)
    return provisioned
