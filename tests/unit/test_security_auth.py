"""Unit tests for enterprise auth and RBAC helpers."""

import pytest
from fastapi import HTTPException

from api.security import _normalize_roles, get_auth_claims, _require_roles


class TestRoleNormalization:
    def test_normalize_space_delimited_string(self):
        assert _normalize_roles("admin analyst") == {"admin", "analyst"}

    def test_normalize_list_roles(self):
        assert _normalize_roles(["admin", "viewer", ""]) == {"admin", "viewer"}

    def test_normalize_unknown_type(self):
        assert _normalize_roles({"admin": True}) == set()


class TestAuthDisabledMode:
    @pytest.mark.asyncio
    async def test_get_auth_claims_returns_local_principal_when_disabled(self):
        claims = await get_auth_claims(credentials=None)
        assert claims["sub"] == "local-dev"
        assert "admin" in claims["roles"]


class TestRBACDependency:
    @pytest.mark.asyncio
    async def test_require_roles_allows_when_intersection_exists(self):
        dep = _require_roles(["admin"])
        claims = await dep({"roles": ["admin", "viewer"]})
        assert claims["roles"] == ["admin", "viewer"]

    @pytest.mark.asyncio
    async def test_require_roles_denies_without_required_role(self):
        dep = _require_roles(["admin"])
        with pytest.raises(HTTPException) as exc:
            await dep({"roles": ["viewer"]})
        assert exc.value.status_code == 403
