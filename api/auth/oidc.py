"""
OpenID Connect (OIDC) / JWT Authentication
===========================================
Validates JWTs issued by any OIDC-compliant provider:
  • Azure Active Directory (Entra ID)
  • Okta
  • Ping Identity
  • Auth0
  • Keycloak (self-hosted)

How it works
────────────
  1. React frontend uses react-oidc-context to redirect users to the
     enterprise IdP for login.
  2. IdP returns an access_token JWT to the browser.
  3. Every FastAPI request carries: Authorization: Bearer <JWT>
  4. This module fetches the IdP's JWKS (JSON Web Key Set) to verify
     the JWT signature — no shared secret needed.
  5. Decoded claims (sub, email, roles/groups) are injected into the
     FastAPI request state for RBAC checks.

Configuration (via environment variables)
──────────────────────────────────────────
  OIDC_ISSUER_URL      e.g. https://login.microsoftonline.com/{tenant}/v2.0
  OIDC_AUDIENCE        e.g. api://gitkt-platform  (App ID URI in Azure AD)
  OIDC_JWKS_URI        optional — overrides auto-discovery
  AUTH_ENABLED         set to "false" to bypass auth in local dev
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() != "false"


# ── JWKS cache ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_jwks_uri() -> str:
    """Discover JWKS URI from the OIDC discovery document."""
    override = os.getenv("OIDC_JWKS_URI")
    if override:
        return override

    issuer = os.getenv("OIDC_ISSUER_URL", "")
    if not issuer:
        logger.warning("OIDC_ISSUER_URL not set — auth will fail for all requests")
        return ""

    discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        resp = httpx.get(discovery_url, timeout=10)
        resp.raise_for_status()
        return resp.json()["jwks_uri"]
    except Exception as exc:
        logger.error("OIDC discovery failed: %s", exc)
        return ""


@lru_cache(maxsize=1)
def _get_jwks() -> Dict[str, Any]:
    """Fetch and cache the JWKS (public keys for JWT verification)."""
    uri = _get_jwks_uri()
    if not uri:
        return {}
    try:
        resp = httpx.get(uri, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Failed to fetch JWKS from %s: %s", uri, exc)
        return {}


# ── JWT decoder ───────────────────────────────────────────────────────────────

def _decode_jwt(token: str) -> Dict[str, Any]:
    """
    Validate JWT signature using JWKS and return decoded claims.
    Raises HTTPException 401 on any validation failure.
    """
    try:
        from jose import jwt, JWTError, ExpiredSignatureError
        from jose.exceptions import JWTClaimsError
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="python-jose not installed. Add it to requirements.txt",
        )

    jwks = _get_jwks()
    audience = os.getenv("OIDC_AUDIENCE", "")
    issuer   = os.getenv("OIDC_ISSUER_URL", "")

    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256", "RS384", "RS512", "ES256"],
            audience=audience or None,
            issuer=issuer or None,
            options={"verify_aud": bool(audience), "verify_iss": bool(issuer)},
        )
        return claims
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTClaimsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Current user dependency ───────────────────────────────────────────────────

class AuthenticatedUser:
    """Parsed JWT claims attached to the request via dependency injection."""

    def __init__(self, claims: Dict[str, Any]) -> None:
        self.sub:    str       = claims.get("sub", "")
        self.email:  str       = claims.get("email", "") or claims.get("preferred_username", "")
        self.name:   str       = claims.get("name", "")
        # Roles can be in 'roles', 'groups', or nested 'realm_access.roles'
        self.roles:  List[str] = (
            claims.get("roles")
            or claims.get("groups")
            or (claims.get("realm_access") or {}).get("roles")
            or []
        )
        self._raw = claims

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def __repr__(self) -> str:
        return f"<User sub={self.sub} email={self.email} roles={self.roles}>"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency: validates Bearer JWT and returns AuthenticatedUser.

    If AUTH_ENABLED=false (local dev), returns a synthetic admin user.
    If no Authorization header, raises 401.
    """
    if not AUTH_ENABLED:
        # Dev bypass — synthetic superuser
        return AuthenticatedUser({
            "sub": "dev-user",
            "email": "dev@gitkt.local",
            "name": "Dev User",
            "roles": ["admin", "compliance_officer", "analyst"],
        })

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _decode_jwt(credentials.credentials)
    return AuthenticatedUser(claims)
