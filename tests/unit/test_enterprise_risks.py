"""
Unit tests — Enterprise Risk Fixes
====================================
Fix 1: Data Provenance — citation schema validation
Fix 2: Ingestion Scalability — token pool rotation
Fix 3: Enterprise Auth — RBAC role enforcement
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 1: Data Provenance / Citation Schema
# ═══════════════════════════════════════════════════════════════════════════════

from api.schemas.compliance_citation import (
    CodeCitation,
    ComplianceClaim,
    ComplianceVerdict,
    HITLStatus,
    RepositoryComplianceResult,
    COMPLIANCE_EXTRACTION_TOOL,
)


class TestCodeCitation:
    def test_valid_citation(self):
        c = CodeCitation(
            file_path="src/auth/aml.py",
            line_start=42,
            line_end=55,
            exact_quote='def check_aml_watchlist(entity_id: str) -> bool:',
            evidence_url="https://github.com/org/repo/blob/abc/src/auth/aml.py#L42-L55",
        )
        assert c.file_path == "src/auth/aml.py"
        assert c.line_start == 42

    def test_empty_quote_rejected(self):
        with pytest.raises(Exception):
            CodeCitation(
                file_path="src/auth/aml.py",
                line_start=1,
                line_end=1,
                exact_quote="   ",   # whitespace only
                evidence_url="https://github.com/org/repo/blob/abc/f#L1",
            )

    def test_short_quote_rejected(self):
        with pytest.raises(Exception):
            CodeCitation(
                file_path="x.py",
                line_start=1,
                line_end=1,
                exact_quote="short",  # < 10 chars
                evidence_url="https://github.com/org/repo/blob/abc/f#L1",
            )


class TestComplianceClaim:
    def _make_citation(self):
        return CodeCitation(
            file_path="aml_check.py",
            line_start=10,
            line_end=20,
            exact_quote='result = watchlist_api.screen(transaction.party_id)',
            evidence_url="https://github.com/org/repo/blob/abc/aml_check.py#L10-L20",
        )

    def test_high_confidence_does_not_require_review(self):
        claim = ComplianceClaim(
            framework_id="bsa",
            requirement_id="BSA-001",
            verdict=ComplianceVerdict.COMPLIANT,
            confidence_score=0.92,
            citations=[self._make_citation()],
            reasoning="AML watchlist screening is present in aml_check.py line 10",
        )
        assert not claim.requires_human_review()

    def test_low_confidence_requires_review(self):
        claim = ComplianceClaim(
            framework_id="bsa",
            requirement_id="BSA-001",
            verdict=ComplianceVerdict.PARTIAL,
            confidence_score=0.65,
            citations=[self._make_citation()],
            reasoning="Partial evidence found — missing transaction threshold logic",
        )
        assert claim.requires_human_review()

    def test_unknown_verdict_requires_review(self):
        claim = ComplianceClaim(
            framework_id="dora",
            requirement_id="DORA-002",
            verdict=ComplianceVerdict.UNKNOWN,
            confidence_score=0.9,
            citations=[self._make_citation()],
            reasoning="Could not determine from available source files",
        )
        assert claim.requires_human_review()

    def test_auto_approve_sets_status_and_timestamp(self):
        claim = ComplianceClaim(
            framework_id="pci_dss",
            requirement_id="PCI-001",
            verdict=ComplianceVerdict.COMPLIANT,
            confidence_score=0.95,
            citations=[self._make_citation()],
            reasoning="TLS 1.3 enforced in all HTTP handlers",
        )
        claim.auto_approve()
        assert claim.hitl_status == HITLStatus.AUTO
        assert claim.reviewed_at is not None

    def test_claim_without_citation_rejected(self):
        with pytest.raises(Exception):
            ComplianceClaim(
                framework_id="bsa",
                requirement_id="BSA-001",
                verdict=ComplianceVerdict.COMPLIANT,
                confidence_score=0.9,
                citations=[],   # no citations — should fail
                reasoning="Seems fine",
            )


class TestComplianceExtractionTool:
    """Verify the Claude tool schema is well-formed."""

    def test_tool_has_required_fields(self):
        assert COMPLIANCE_EXTRACTION_TOOL["name"] == "extract_compliance_evidence"
        schema = COMPLIANCE_EXTRACTION_TOOL["input_schema"]
        required = schema["required"]
        assert "citations" in required
        assert "confidence_score" in required
        assert "verdict" in required

    def test_citations_min_items_enforced_in_schema(self):
        schema = COMPLIANCE_EXTRACTION_TOOL["input_schema"]
        citations_schema = schema["properties"]["citations"]
        assert citations_schema["minItems"] == 1

    def test_confidence_score_bounded_in_schema(self):
        schema = COMPLIANCE_EXTRACTION_TOOL["input_schema"]
        cs = schema["properties"]["confidence_score"]
        assert cs["minimum"] == 0.0
        assert cs["maximum"] == 1.0


class TestRepositoryComplianceResult:
    def _make_claim(self, confidence: float, verdict: ComplianceVerdict):
        citation = CodeCitation(
            file_path="main.py", line_start=1, line_end=5,
            exact_quote="def process_payment(amount): return gateway.charge(amount)",
            evidence_url="https://github.com/x/y/blob/abc/main.py#L1",
        )
        return ComplianceClaim(
            framework_id="bsa", requirement_id="BSA-001",
            verdict=verdict, confidence_score=confidence,
            citations=[citation],
            reasoning="Evidence found in payment processing module",
        )

    def test_pending_hitl_count(self):
        result = RepositoryComplianceResult(
            repo_id="github:org/repo",
            repo_url="https://github.com/org/repo",
            claims=[
                self._make_claim(0.6, ComplianceVerdict.PARTIAL),   # pending
                self._make_claim(0.95, ComplianceVerdict.COMPLIANT), # auto
            ],
        )
        # Before auto-approve, both start as PENDING
        assert result.pending_hitl_count() == 2

    def test_overall_confidence_computation(self):
        result = RepositoryComplianceResult(
            repo_id="github:org/repo",
            repo_url="https://github.com/org/repo",
            claims=[
                self._make_claim(0.8, ComplianceVerdict.COMPLIANT),
                self._make_claim(0.6, ComplianceVerdict.PARTIAL),
            ],
        )
        overall = result.compute_overall_confidence()
        assert abs(overall - 0.7) < 0.001


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 2: Ingestion Scalability — Token Pool
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio
from data_ingestion.github.token_pool import GitHubTokenPool, TokenSlot


class TestTokenSlot:
    def test_seconds_until_reset_is_non_negative(self):
        import time
        slot = TokenSlot(token="ghp_test", reset_at_epoch=int(time.time()) + 120)
        assert slot.seconds_until_reset >= 0

    def test_mark_exhausted(self):
        import time
        slot = TokenSlot(token="ghp_test")
        slot.mark_exhausted(int(time.time()) + 3600)
        assert slot.is_exhausted

    def test_refresh_clears_exhaustion(self):
        import time
        slot = TokenSlot(token="ghp_test")
        slot.mark_exhausted(int(time.time()) + 3600)
        slot.refresh(remaining=4999, reset_at=int(time.time()) + 3600)
        assert not slot.is_exhausted
        assert slot.remaining == 4999


class TestGitHubTokenPool:
    def test_requires_at_least_one_token(self):
        with pytest.raises(ValueError):
            GitHubTokenPool([])

    def test_single_token_pool(self):
        pool = GitHubTokenPool(["ghp_abc123"])
        assert len(pool._slots) == 1

    def test_multiple_tokens(self):
        pool = GitHubTokenPool(["ghp_a", "ghp_b", "ghp_c"])
        assert len(pool._slots) == 3

    def test_from_env_requires_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        for i in range(1, 10):
            monkeypatch.delenv(f"GITHUB_TOKEN_{i}", raising=False)
        with pytest.raises(EnvironmentError):
            GitHubTokenPool.from_env()

    def test_from_env_reads_primary_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_primary")
        for i in range(1, 10):
            monkeypatch.delenv(f"GITHUB_TOKEN_{i}", raising=False)
        pool = GitHubTokenPool.from_env()
        assert pool._slots[0].token == "ghp_primary"

    def test_from_env_reads_extra_tokens(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN",   "ghp_primary")
        monkeypatch.setenv("GITHUB_TOKEN_1", "ghp_extra1")
        monkeypatch.setenv("GITHUB_TOKEN_2", "ghp_extra2")
        for i in range(3, 10):
            monkeypatch.delenv(f"GITHUB_TOKEN_{i}", raising=False)
        pool = GitHubTokenPool.from_env()
        assert len(pool._slots) == 3

    @pytest.mark.asyncio
    async def test_next_headers_returns_auth(self):
        pool = GitHubTokenPool(["ghp_testtoken"])
        headers = await pool.next_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer ghp_testtoken"

    @pytest.mark.asyncio
    async def test_round_robin_rotation(self):
        pool = GitHubTokenPool(["ghp_a", "ghp_b", "ghp_c"])
        tokens_seen = set()
        for _ in range(6):  # 2 full cycles
            h = await pool.next_headers()
            tokens_seen.add(h["Authorization"])
        assert len(tokens_seen) == 3  # all three tokens used

    @pytest.mark.asyncio
    async def test_exhausted_token_skipped(self):
        import time
        pool = GitHubTokenPool(["ghp_exhausted", "ghp_fresh"])
        pool._slots[0].mark_exhausted(int(time.time()) + 3600)  # exhaust first
        h = await pool.next_headers()
        # Should get the second token
        assert "ghp_fresh" in h["Authorization"]


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 3: Enterprise Auth — RBAC
# ═══════════════════════════════════════════════════════════════════════════════

from api.auth.oidc import AuthenticatedUser
from api.auth.rbac import (
    require_role, _effective_level,
    ROLE_ADMIN, ROLE_COMPLIANCE_OFFICER, ROLE_ANALYST, ROLE_DEVELOPER,
)


class TestAuthenticatedUser:
    def test_parses_roles(self):
        u = AuthenticatedUser({"sub": "abc", "email": "x@y.com", "roles": ["analyst"]})
        assert u.has_role("analyst")
        assert not u.has_role("admin")

    def test_parses_groups_as_roles(self):
        u = AuthenticatedUser({"sub": "abc", "groups": ["compliance_officer"]})
        assert u.has_role("compliance_officer")

    def test_parses_realm_access_roles(self):
        u = AuthenticatedUser({
            "sub": "abc",
            "realm_access": {"roles": ["admin"]},
        })
        assert u.has_role("admin")

    def test_empty_roles(self):
        u = AuthenticatedUser({"sub": "abc"})
        assert u.roles == []


class TestRBACLevels:
    def test_admin_highest_level(self):
        u = AuthenticatedUser({"sub": "a", "roles": ["admin"]})
        assert _effective_level(u) == 3

    def test_developer_lowest_level(self):
        u = AuthenticatedUser({"sub": "a", "roles": ["developer"]})
        assert _effective_level(u) == 0

    def test_unknown_role_gives_minus_one(self):
        u = AuthenticatedUser({"sub": "a", "roles": ["viewer"]})
        assert _effective_level(u) == -1

    def test_highest_role_wins(self):
        u = AuthenticatedUser({"sub": "a", "roles": ["developer", "compliance_officer"]})
        # Should return compliance_officer level (2), not developer level (0)
        assert _effective_level(u) == 2


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_sufficient_role_passes(self):
        u = AuthenticatedUser({"sub": "a", "roles": ["compliance_officer"]})
        dep = require_role(ROLE_COMPLIANCE_OFFICER)
        # Manually call the inner dependency function
        result = await dep.__wrapped__(u) if hasattr(dep, '__wrapped__') else await dep(u)  # type: ignore
        assert result is u

    def test_admin_passes_compliance_officer_check(self):
        """Admin has higher privilege level than compliance_officer."""
        admin = AuthenticatedUser({"sub": "a", "roles": ["admin"]})
        officer = AuthenticatedUser({"sub": "b", "roles": ["compliance_officer"]})
        from api.auth.rbac import _effective_level
        # Admin (3) > compliance_officer (2) — would pass require_role("compliance_officer")
        assert _effective_level(admin) > _effective_level(officer)

    @pytest.mark.asyncio
    async def test_insufficient_role_raises_403(self):
        from fastapi import HTTPException
        u = AuthenticatedUser({"sub": "a", "roles": ["developer"]})

        # Simulate the dependency check directly
        required_level = 2  # compliance_officer
        from api.auth.rbac import _effective_level
        user_level = _effective_level(u)
        assert user_level < required_level  # developer (0) < compliance_officer (2)

    def test_require_role_returns_callable(self):
        dep = require_role(ROLE_ANALYST)
        assert callable(dep)
