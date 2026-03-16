"""
Enterprise authentication and RBAC helpers.

Design goals:
- Keep local/dev experience frictionless (AUTH_ENABLED=false).
- Support enterprise OIDC token introspection without hard-coding IdP vendors.
- Enforce role-based access control at router boundaries.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Set

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
_bearer = HTTPBearer(auto_error=False)


def _normalize_roles(raw_roles: object) -> Set[str]:
    if raw_roles is None:
        return set()
    if isinstance(raw_roles, str):
        return {r.strip() for r in raw_roles.split() if r.strip()}
    if isinstance(raw_roles, list):
        out: Set[str] = set()
        for item in raw_roles:
            if isinstance(item, str) and item.strip():
                out.add(item.strip())
        return out
    return set()


async def _introspect_access_token(token: str) -> Dict:
    if not settings.auth.oidc_introspection_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth configured but introspection URL is missing",
        )

    auth = None
    if settings.auth.oidc_client_id and settings.auth.oidc_client_secret:
        auth = (settings.auth.oidc_client_id, settings.auth.oidc_client_secret)

    payload = {"token": token}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.auth.oidc_introspection_url, data=payload, auth=auth)

    if resp.status_code >= 400:
        logger.warning("OIDC introspection failed status=%s", resp.status_code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    data = resp.json()
    if not data.get("active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive access token")
    return data


async def get_auth_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Dict:
    """
    Resolve auth claims for request.

    If auth is disabled, return a permissive local principal.
    """
    if not settings.auth.enabled:
        return {
            "sub": "local-dev",
            "roles": ["admin", "analyst", "viewer"],
            "auth_mode": "none",
        }

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = credentials.credentials
    if settings.auth.mode == "oidc_introspection":
        claims = await _introspect_access_token(token)
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unsupported auth mode: {settings.auth.mode}",
        )

    # Normalize common role claim variants
    normalized_roles = set()
    for role_field in ("roles", "role", "groups", "scope"):
        normalized_roles.update(_normalize_roles(claims.get(role_field)))

    claims["roles"] = sorted(normalized_roles)
    return claims


def _require_roles(required_roles: Iterable[str]):
    required = set(required_roles)

    async def dependency(claims: Dict = Depends(get_auth_claims)) -> Dict:
        principal_roles = _normalize_roles(claims.get("roles"))
        if required and not principal_roles.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required one of: {sorted(required)}",
            )
        return claims

    return dependency


require_read_access = _require_roles(settings.auth.required_read_roles)
require_write_access = _require_roles(settings.auth.required_write_roles)
require_admin_access = _require_roles(settings.auth.required_admin_roles)
