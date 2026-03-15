"""OIDC/SSO service — OIDC discovery, state management, token exchange, JIT provisioning."""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sso_connection import SSOConnection
from app.models.user import User
from app.services.auth_service import create_access_token, create_refresh_token
from app.services.crypto_service import decrypt, encrypt


_STATE_TTL = 600  # 10 minutes


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


async def initiate_sso(
    db: AsyncSession,
    redis: Redis,
    connection_id: str,
    redirect_uri: str,
) -> str:
    """Return the IdP authorization URL and store state in Redis."""
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
                "redirect_uri": redirect_uri,
                "client_id": conn.client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not token_response.is_success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"IdP token exchange failed: {token_response.text[:200]}",
            )
        token_data = token_response.json()

    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No id_token in IdP response",
        )

    claims = _decode_id_token_payload(id_token)

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


def _decode_id_token_payload(id_token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (trust TLS + nonce)."""
    parts = id_token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed id_token",
        )
    padding = 4 - len(parts[1]) % 4
    payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
    return json.loads(payload_bytes)


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
