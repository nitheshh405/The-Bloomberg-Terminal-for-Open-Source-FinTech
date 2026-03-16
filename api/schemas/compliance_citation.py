"""
Data Provenance & Citation Schema
==================================
Enforces structured extraction with evidence citations.
Every compliance claim the AI makes MUST include:
  - exact_code_citation  : verbatim quote from the repo (prevents hallucination)
  - confidence_score     : 0.0–1.0 (< 0.8 → flagged for HITL review)
  - evidence_url         : deep-link to the exact file/line on GitHub

This schema is passed to Claude as a ``tool`` definition so the LLM is
forced to return a strict JSON object instead of freeform prose.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────

class HITLStatus(str, Enum):
    PENDING   = "pending"    # awaiting human review
    APPROVED  = "approved"   # compliance officer verified
    REJECTED  = "rejected"   # officer rejected the claim
    AUTO      = "auto"       # confidence ≥ 0.8, no human needed


class ComplianceVerdict(str, Enum):
    COMPLIANT     = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL       = "partial"
    UNKNOWN       = "unknown"


# ── Core citation unit ─────────────────────────────────────────────────────────

class CodeCitation(BaseModel):
    """A single piece of verbatim evidence extracted from the repository."""

    file_path: str = Field(
        ...,
        description="Relative path to the file within the repo, e.g. 'src/auth/jwt.py'",
    )
    line_start: int = Field(..., ge=1, description="Starting line number")
    line_end: int   = Field(..., ge=1, description="Ending line number")
    exact_quote: str = Field(
        ...,
        min_length=10,
        description="Verbatim code or comment snippet — no paraphrasing allowed",
    )
    evidence_url: str = Field(
        ...,
        description="Full GitHub permalink, e.g. https://github.com/org/repo/blob/SHA/file#L10-L20",
    )

    @field_validator("exact_quote")
    @classmethod
    def no_empty_quotes(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("exact_quote must not be empty — citation required")
        return v


# ── Compliance claim with provenance ──────────────────────────────────────────

class ComplianceClaim(BaseModel):
    """
    Structured compliance assertion produced by the AI agent.
    Passed to Claude as a tool schema so the model CANNOT omit citations.
    """

    framework_id: str = Field(..., description="e.g. 'bsa', 'pci_dss', 'dora'")
    requirement_id: str = Field(..., description="Requirement ID within the framework")
    verdict: ComplianceVerdict
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model self-assessed confidence. Values < 0.8 trigger HITL queue.",
    )
    citations: List[CodeCitation] = Field(
        ...,
        min_length=1,
        description="At least one verbatim code citation is REQUIRED per claim",
    )
    reasoning: str = Field(
        ...,
        min_length=20,
        description="Brief explanation referencing the citations above",
    )
    # Set automatically — not from LLM
    hitl_status: HITLStatus  = HITLStatus.PENDING
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    @field_validator("citations")
    @classmethod
    def must_have_citations(cls, v: List[CodeCitation]) -> List[CodeCitation]:
        if not v:
            raise ValueError("At least one CodeCitation is required — no citation = hallucination risk")
        return v

    def requires_human_review(self) -> bool:
        return self.confidence_score < 0.8 or self.verdict == ComplianceVerdict.UNKNOWN

    def auto_approve(self) -> None:
        """Mark as auto-approved when confidence ≥ 0.8."""
        self.hitl_status = HITLStatus.AUTO
        self.reviewed_at = datetime.now(timezone.utc)


# ── Batch result (per-repo) ────────────────────────────────────────────────────

class RepositoryComplianceResult(BaseModel):
    """Full compliance scan result for a single repository."""

    repo_id: str
    repo_url: str
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    claims: List[ComplianceClaim] = []
    overall_confidence: float = 0.0

    def pending_hitl_count(self) -> int:
        return sum(1 for c in self.claims if c.hitl_status == HITLStatus.PENDING)

    def compute_overall_confidence(self) -> float:
        if not self.claims:
            return 0.0
        self.overall_confidence = sum(c.confidence_score for c in self.claims) / len(self.claims)
        return self.overall_confidence


# ── Claude tool definition (passed as tools=[...] in Anthropic SDK call) ──────

COMPLIANCE_EXTRACTION_TOOL = {
    "name": "extract_compliance_evidence",
    "description": (
        "Extract structured compliance evidence from a repository. "
        "You MUST provide at least one verbatim code citation per claim. "
        "Never invent citations. If you cannot find evidence, set verdict=unknown."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "framework_id":     {"type": "string"},
            "requirement_id":   {"type": "string"},
            "verdict":          {"type": "string", "enum": ["compliant", "non_compliant", "partial", "unknown"]},
            "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "reasoning":        {"type": "string"},
            "citations": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["file_path", "line_start", "line_end", "exact_quote", "evidence_url"],
                    "properties": {
                        "file_path":    {"type": "string"},
                        "line_start":   {"type": "integer", "minimum": 1},
                        "line_end":     {"type": "integer", "minimum": 1},
                        "exact_quote":  {"type": "string", "minLength": 10},
                        "evidence_url": {"type": "string"},
                    },
                },
            },
        },
        "required": ["framework_id", "requirement_id", "verdict", "confidence_score", "citations", "reasoning"],
    },
}
