"""
Human-In-The-Loop (HITL) Queue for Compliance Verification
============================================================
Manages the lifecycle of AI compliance claims that need human review.

Neo4j relationship model
─────────────────────────
  (Repository)-[:COMPLIES_WITH {
      framework_id:     "bsa",
      requirement_id:   "BSA-001",
      verdict:          "compliant",
      confidence:       0.72,          # < 0.8 → hitl_status = "pending"
      hitl_status:      "pending",
      evidence_url:     "https://github.com/...",
      exact_quote:      "\"aml_check(transaction)\"",
      reviewed_by:      null,
      reviewed_at:      null,
      created_at:       datetime,
  }]->(RegulatoryFramework)

The React dashboard polls GET /api/v1/hitl/pending and renders an
Approve / Reject panel for compliance officers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from api.schemas.compliance_citation import (
    ComplianceClaim,
    HITLStatus,
    RepositoryComplianceResult,
)

logger = logging.getLogger(__name__)


# ── Neo4j Cypher templates ────────────────────────────────────────────────────

_UPSERT_COMPLIES_WITH = """
MERGE (r:Repository {id: $repo_id})
MERGE (f:RegulatoryFramework {id: $framework_id})
MERGE (r)-[rel:COMPLIES_WITH {
    requirement_id: $requirement_id,
    framework_id:   $framework_id
}]->(f)
SET
    rel.verdict       = $verdict,
    rel.confidence    = $confidence,
    rel.hitl_status   = $hitl_status,
    rel.exact_quote   = $exact_quote,
    rel.evidence_url  = $evidence_url,
    rel.reasoning     = $reasoning,
    rel.created_at    = datetime(),
    rel.reviewed_by   = $reviewed_by,
    rel.reviewed_at   = $reviewed_at
RETURN rel
"""

_GET_PENDING_HITL = """
MATCH (r:Repository)-[rel:COMPLIES_WITH]->(f:RegulatoryFramework)
WHERE rel.hitl_status = 'pending'
RETURN
    r.id           AS repo_id,
    r.url          AS repo_url,
    f.id           AS framework_id,
    rel.requirement_id AS requirement_id,
    rel.verdict    AS verdict,
    rel.confidence AS confidence,
    rel.exact_quote AS exact_quote,
    rel.evidence_url AS evidence_url,
    rel.reasoning  AS reasoning,
    rel.created_at AS created_at
ORDER BY rel.confidence ASC   // lowest confidence first
LIMIT $limit
"""

_UPDATE_HITL_STATUS = """
MATCH (r:Repository {id: $repo_id})-[rel:COMPLIES_WITH {
    framework_id:   $framework_id,
    requirement_id: $requirement_id
}]->(f:RegulatoryFramework)
SET
    rel.hitl_status = $hitl_status,
    rel.reviewed_by = $reviewed_by,
    rel.reviewed_at = $reviewed_at
RETURN rel
"""

_HITL_STATS = """
MATCH ()-[rel:COMPLIES_WITH]->()
RETURN
    rel.hitl_status AS status,
    COUNT(rel)      AS count
"""


# ── Queue manager ──────────────────────────────────────────────────────────────

@dataclass
class HITLQueueItem:
    repo_id:        str
    repo_url:       str
    framework_id:   str
    requirement_id: str
    verdict:        str
    confidence:     float
    exact_quote:    str
    evidence_url:   str
    reasoning:      str
    created_at:     Optional[str] = None


@dataclass
class HITLStats:
    pending:  int = 0
    approved: int = 0
    rejected: int = 0
    auto:     int = 0

    @property
    def total(self) -> int:
        return self.pending + self.approved + self.rejected + self.auto

    @property
    def review_backlog(self) -> int:
        return self.pending


class HITLQueueManager:
    """
    Persists ComplianceClaims into Neo4j and manages human-review lifecycle.
    Uses the Neo4j driver injected at construction time so it can be
    used both from FastAPI (async context) and from agent pipelines.
    """

    def __init__(self, neo4j_driver):
        self._driver = neo4j_driver

    # ── Write path ────────────────────────────────────────────────────────────

    def persist_result(self, result: RepositoryComplianceResult) -> int:
        """
        Write all claims from a RepositoryComplianceResult to Neo4j.
        Claims with confidence ≥ 0.8 are auto-approved; others are queued.
        Returns the number of claims written.
        """
        written = 0
        with self._driver.session() as session:
            for claim in result.claims:
                # Auto-approve high-confidence claims
                if not claim.requires_human_review():
                    claim.auto_approve()

                # Use first citation as primary evidence anchor
                primary = claim.citations[0]
                session.run(
                    _UPSERT_COMPLIES_WITH,
                    repo_id=result.repo_id,
                    framework_id=claim.framework_id,
                    requirement_id=claim.requirement_id,
                    verdict=claim.verdict.value,
                    confidence=claim.confidence_score,
                    hitl_status=claim.hitl_status.value,
                    exact_quote=primary.exact_quote,
                    evidence_url=primary.evidence_url,
                    reasoning=claim.reasoning,
                    reviewed_by=claim.reviewed_by,
                    reviewed_at=(
                        claim.reviewed_at.isoformat() if claim.reviewed_at else None
                    ),
                )
                written += 1

                if claim.hitl_status == HITLStatus.PENDING:
                    logger.warning(
                        "HITL required: repo=%s framework=%s req=%s confidence=%.2f",
                        result.repo_id, claim.framework_id,
                        claim.requirement_id, claim.confidence_score,
                    )

        return written

    # ── Read path ─────────────────────────────────────────────────────────────

    def get_pending_queue(self, limit: int = 50) -> List[HITLQueueItem]:
        """Return items awaiting human review, lowest confidence first."""
        with self._driver.session() as session:
            records = session.run(_GET_PENDING_HITL, limit=limit)
            return [
                HITLQueueItem(
                    repo_id=r["repo_id"],
                    repo_url=r["repo_url"] or "",
                    framework_id=r["framework_id"],
                    requirement_id=r["requirement_id"],
                    verdict=r["verdict"],
                    confidence=r["confidence"],
                    exact_quote=r["exact_quote"] or "",
                    evidence_url=r["evidence_url"] or "",
                    reasoning=r["reasoning"] or "",
                    created_at=str(r["created_at"]) if r["created_at"] else None,
                )
                for r in records
            ]

    def get_stats(self) -> HITLStats:
        """Return aggregate counts by status."""
        stats = HITLStats()
        with self._driver.session() as session:
            records = session.run(_HITL_STATS)
            for r in records:
                status = r["status"]
                count  = r["count"]
                if status == "pending":   stats.pending  = count
                elif status == "approved": stats.approved = count
                elif status == "rejected": stats.rejected = count
                elif status == "auto":     stats.auto     = count
        return stats

    # ── Review actions ────────────────────────────────────────────────────────

    def approve(
        self,
        repo_id: str,
        framework_id: str,
        requirement_id: str,
        reviewer: str,
    ) -> bool:
        return self._set_status(
            repo_id, framework_id, requirement_id,
            HITLStatus.APPROVED, reviewer,
        )

    def reject(
        self,
        repo_id: str,
        framework_id: str,
        requirement_id: str,
        reviewer: str,
    ) -> bool:
        return self._set_status(
            repo_id, framework_id, requirement_id,
            HITLStatus.REJECTED, reviewer,
        )

    def _set_status(
        self,
        repo_id: str,
        framework_id: str,
        requirement_id: str,
        status: HITLStatus,
        reviewer: str,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._driver.session() as session:
            result = session.run(
                _UPDATE_HITL_STATUS,
                repo_id=repo_id,
                framework_id=framework_id,
                requirement_id=requirement_id,
                hitl_status=status.value,
                reviewed_by=reviewer,
                reviewed_at=now,
            )
            summary = result.consume()
            return summary.counters.properties_set > 0
