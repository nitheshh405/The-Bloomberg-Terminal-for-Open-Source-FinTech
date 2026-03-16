"""
Role-Based Access Control (RBAC) Middleware
============================================
FastAPI dependency injection pattern — attach to any route like:

    @router.get("/sensitive-data")
    async def get_data(_: AuthenticatedUser = Depends(require_role("analyst"))):
        ...

Role hierarchy
──────────────
  admin              — full access (Nithesh / platform owner)
  compliance_officer — can read all data, approve/reject HITL claims
  analyst            — read-only access to repositories, scores, reports
  developer          — API access for automated pipelines

Enterprise IdP role mapping (Azure AD example)
───────────────────────────────────────────────
  Azure AD App Role "GitKT.ComplianceOfficer" → maps to "compliance_officer"
  Azure AD App Role "GitKT.Analyst"           → maps to "analyst"
  Azure AD Security Group "gitkt-admins"      → maps to "admin"

  Configure in Azure Portal → App Registrations → App Roles
  Then assign users/groups to roles in Enterprise Applications.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import Depends, HTTPException, status

from api.auth.oidc import AuthenticatedUser, get_current_user

logger = logging.getLogger(__name__)

# ── Role constants ────────────────────────────────────────────────────────────

ROLE_ADMIN              = "admin"
ROLE_COMPLIANCE_OFFICER = "compliance_officer"
ROLE_ANALYST            = "analyst"
ROLE_DEVELOPER          = "developer"

# Role hierarchy: higher index → higher privilege
_HIERARCHY: List[str] = [
    ROLE_DEVELOPER,
    ROLE_ANALYST,
    ROLE_COMPLIANCE_OFFICER,
    ROLE_ADMIN,
]


def _effective_level(user: AuthenticatedUser) -> int:
    """Return the user's highest privilege level (0 = none, 3 = admin)."""
    level = -1
    for role in user.roles:
        try:
            level = max(level, _HIERARCHY.index(role))
        except ValueError:
            pass   # unknown role — skip
    return level


# ── Dependency factory ────────────────────────────────────────────────────────

def require_role(minimum_role: str):
    """
    Returns a FastAPI dependency that enforces a minimum role.

    Usage:
        @router.post("/hitl/{repo_id}/approve")
        async def approve(
            repo_id: str,
            user: AuthenticatedUser = Depends(require_role("compliance_officer")),
        ):
            ...
    """
    required_level = _HIERARCHY.index(minimum_role) if minimum_role in _HIERARCHY else 0

    async def _check(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        user_level = _effective_level(user)
        if user_level < required_level:
            logger.warning(
                "Access denied: user=%s roles=%s required=%s",
                user.email, user.roles, minimum_role,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{minimum_role}' or higher required. "
                    f"Your roles: {user.roles}"
                ),
            )

        logger.debug("Access granted: user=%s role_level=%d", user.email, user_level)
        return user

    return _check


# ── Shorthand dependencies ─────────────────────────────────────────────────────

require_admin              = require_role(ROLE_ADMIN)
require_compliance_officer = require_role(ROLE_COMPLIANCE_OFFICER)
require_analyst            = require_role(ROLE_ANALYST)
require_developer          = require_role(ROLE_DEVELOPER)


# ── Audit logging helper ───────────────────────────────────────────────────────

def audit_log(user: AuthenticatedUser, action: str, resource: str) -> None:
    """
    Append a structured audit trail entry.
    In production: write to a separate audit Neo4j node or SIEM stream.
    """
    logger.info(
        "[AUDIT] user=%s email=%s action=%s resource=%s",
        user.sub, user.email, action, resource,
    )
