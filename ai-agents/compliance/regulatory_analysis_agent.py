"""
Regulatory Analysis Agent (Agent 6 of 10)

Evaluates each repository's regulatory and compliance implications:
- Maps repos to relevant regulations (BSA, Dodd-Frank, SOX, PCI-DSS, etc.)
- Generates Compliance Risk Score, Regulatory Relevance Score, Auditability Score
- Links new regulatory documents to affected technologies
- Detects repos that could directly support compliance workflows
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)

# ── Compliance signal patterns ────────────────────────────────────────────────

DATA_PRIVACY_SIGNALS = [
    "encryption", "AES", "TLS", "GDPR", "CCPA", "data masking",
    "tokenization", "anonymization", "pseudonymization",
    "access control", "RBAC", "data classification",
]

TRANSACTION_MONITORING_SIGNALS = [
    "transaction monitoring", "rule engine", "alert", "SAR", "CTR",
    "threshold", "pattern detection", "behavior analytics", "velocity check",
    "watchlist", "sanctions", "OFAC",
]

IDENTITY_VERIFICATION_SIGNALS = [
    "KYC", "identity verification", "document check", "biometric",
    "liveness detection", "face recognition", "passport", "driver license",
    "NFC", "OCR", "PEP screening",
]

AUDIT_TRAIL_SIGNALS = [
    "audit log", "immutable log", "event sourcing", "CQRS",
    "append-only", "tamper-evident", "blockchain log", "Merkle",
    "non-repudiation", "digital signature",
]

CRYPTOGRAPHIC_SIGNALS = [
    "cryptography", "PKI", "HSM", "key management", "digital signature",
    "RSA", "ECDSA", "Ed25519", "zero-knowledge", "homomorphic",
    "MPC", "threshold signature",
]

REPORTING_SIGNALS = [
    "regulatory reporting", "XBRL", "EDGAR", "MiFID II", "EMIR",
    "form ADV", "form PF", "Basel reporting", "DFAST", "CCAR",
    "financial report", "SEC filing",
]

# ── Regulation-to-technology mapping ─────────────────────────────────────────

REGULATION_TECH_REQUIREMENTS: Dict[str, List[str]] = {
    "regulation:bsa": TRANSACTION_MONITORING_SIGNALS + IDENTITY_VERIFICATION_SIGNALS,
    "regulation:glba": DATA_PRIVACY_SIGNALS + CRYPTOGRAPHIC_SIGNALS,
    "regulation:pci-dss": CRYPTOGRAPHIC_SIGNALS + ["PCI", "cardholder", "payment card"],
    "regulation:sox": AUDIT_TRAIL_SIGNALS + REPORTING_SIGNALS,
    "regulation:dodd-frank": REPORTING_SIGNALS + ["derivatives", "swaps", "clearing"],
    "regulation:basel-iii": ["capital", "liquidity", "LCR", "NSFR", "stress test"],
}

# ── Scoring weights ───────────────────────────────────────────────────────────

MIN_REGULATION_SIGNAL_HITS = 2

COMPLIANCE_SCORE_WEIGHTS = {
    "data_privacy": 0.20,
    "transaction_monitoring": 0.20,
    "identity_verification": 0.15,
    "audit_trail": 0.20,
    "cryptographic_security": 0.15,
    "regulatory_reporting": 0.10,
}


@dataclass
class ComplianceScores:
    compliance_risk_score: float = 0.0      # 0=low risk, 100=high risk
    regulatory_relevance: float = 0.0       # how relevant to financial regulation
    auditability_score: float = 0.0         # how auditable/traceable
    data_governance_score: float = 0.0      # data privacy/security practices
    matched_regulations: List[str] = None
    compliance_capabilities: List[str] = None

    def __post_init__(self):
        if self.matched_regulations is None:
            self.matched_regulations = []
        if self.compliance_capabilities is None:
            self.compliance_capabilities = []


class RegulatoryAnalysisAgent(BaseAgent):
    """Agent 6: Evaluates regulatory implications of fintech repositories."""

    def __init__(self, **kwargs):
        super().__init__(name="RegulatoryAnalysisAgent", **kwargs)

    async def _run(self, result: AgentResult) -> AgentResult:
        # Fetch repos that need compliance scoring
        repos = await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.primary_sector IS NOT NULL
              AND (r.compliance_risk_score IS NULL
                   OR r.last_compliance_scored_at IS NULL
                   OR r.last_compliance_scored_at < datetime() - duration({days: 7}))
            RETURN r.id AS id,
                   r.description AS description,
                   r.readme_snippet AS readme,
                   r.topics AS topics,
                   r.fintech_domains AS domains,
                   r.primary_sector AS sector
            ORDER BY r.stars DESC
            LIMIT 3000
        """)

        result.items_processed = len(repos)
        logger.info("[%s] Scoring compliance for %d repos", self.name, len(repos))

        scored = 0
        for repo in repos:
            try:
                await self._score_repo(repo)
                scored += 1
            except Exception as exc:
                result.errors.append(f"{repo['id']}: {exc}")

        result.items_updated = scored
        result.insights.append(f"Compliance-scored {scored} repositories")

        # Process new regulatory documents and link to technologies
        await self._link_regulatory_docs_to_technologies()
        return result

    async def _score_repo(self, repo: Dict) -> None:
        full_text = " ".join([
            repo.get("description") or "",
            repo.get("readme") or "",
            " ".join(repo.get("topics") or []),
        ]).lower()

        scores = self._compute_compliance_scores(full_text)
        matched_regs = self._match_regulations(full_text)
        capabilities = self._detect_compliance_capabilities(full_text)
        evidence_by_reg = {
            reg_id: self._build_regulation_provenance(reg_id, full_text)
            for reg_id in matched_regs
        }

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.compliance_risk_score     = $risk,
                r.regulatory_relevance_score = $relevance,
                r.auditability_score        = $audit,
                r.data_governance_score     = $data_gov,
                r.compliance_capabilities   = $capabilities,
                r.regulatory_mapping_method = "rule_based_v1",
                r.regulatory_mapping_review_status = "auto_generated",
                r.last_compliance_scored_at = datetime($now)
        """, {
            "id": repo["id"],
            "risk": scores.compliance_risk_score,
            "relevance": scores.regulatory_relevance,
            "audit": scores.auditability_score,
            "data_gov": scores.data_governance_score,
            "capabilities": capabilities,
            "now": now,
        })

        # Link to matched regulations
        for reg_id in matched_regs:
            risk_level = self._assess_regulation_risk(reg_id, full_text)
            evidence = evidence_by_reg[reg_id]
            await self._neo4j_write("""
                MATCH (r:Repository {id: $repo_id})
                MATCH (rl:Regulation {id: $reg_id})
                MERGE (r)-[rel:SUBJECT_TO]->(rl)
                SET rel.risk_level = $risk_level,
                    rel.provenance_method = $provenance_method,
                    rel.provenance_signal_count = $signal_count,
                    rel.provenance_signals = $signals,
                    rel.provenance_hash = $provenance_hash,
                    rel.confidence = $confidence,
                    rel.updated_at = datetime($now)
            """, {
                "repo_id": repo["id"],
                "reg_id": reg_id,
                "risk_level": risk_level,
                "provenance_method": evidence["method"],
                "signal_count": evidence["signal_count"],
                "signals": evidence["signals"],
                "provenance_hash": evidence["hash"],
                "confidence": evidence["confidence"],
                "now": now,
            })

            # Also add SUPPORTS_COMPLIANCE for repos with compliance capabilities
            if capabilities:
                await self._neo4j_write("""
                    MATCH (r:Repository {id: $repo_id})
                    MATCH (rl:Regulation {id: $reg_id})
                    MERGE (r)-[rel:SUPPORTS_COMPLIANCE]->(rl)
                    SET rel.capabilities = $capabilities,
                        rel.provenance_method = $provenance_method,
                        rel.provenance_signal_count = $signal_count,
                        rel.provenance_signals = $signals,
                        rel.provenance_hash = $provenance_hash,
                        rel.confidence = $confidence,
                        rel.updated_at = datetime($now)
                """, {
                    "repo_id": repo["id"],
                    "reg_id": reg_id,
                    "capabilities": capabilities,
                    "provenance_method": evidence["method"],
                    "signal_count": evidence["signal_count"],
                    "signals": evidence["signals"],
                    "provenance_hash": evidence["hash"],
                    "confidence": evidence["confidence"],
                    "now": now,
                })

    def _compute_compliance_scores(self, text: str) -> ComplianceScores:
        """Score each compliance dimension based on signal matching."""

        def _signal_score(signals: List[str]) -> float:
            matches = sum(1 for s in signals if s.lower() in text)
            return min(100.0, (matches / max(len(signals) * 0.3, 1)) * 100)

        privacy = _signal_score(DATA_PRIVACY_SIGNALS)
        monitoring = _signal_score(TRANSACTION_MONITORING_SIGNALS)
        identity = _signal_score(IDENTITY_VERIFICATION_SIGNALS)
        audit = _signal_score(AUDIT_TRAIL_SIGNALS)
        crypto = _signal_score(CRYPTOGRAPHIC_SIGNALS)
        reporting = _signal_score(REPORTING_SIGNALS)

        regulatory_relevance = (
            privacy * COMPLIANCE_SCORE_WEIGHTS["data_privacy"] +
            monitoring * COMPLIANCE_SCORE_WEIGHTS["transaction_monitoring"] +
            identity * COMPLIANCE_SCORE_WEIGHTS["identity_verification"] +
            audit * COMPLIANCE_SCORE_WEIGHTS["audit_trail"] +
            crypto * COMPLIANCE_SCORE_WEIGHTS["cryptographic_security"] +
            reporting * COMPLIANCE_SCORE_WEIGHTS["regulatory_reporting"]
        )

        # Compliance risk = high regulatory relevance + low security signals
        # (repos doing regulated activities without sufficient security)
        security_coverage = (privacy + crypto + audit) / 3
        monitoring_coverage = (monitoring + reporting) / 2
        compliance_risk = max(0, regulatory_relevance - security_coverage * 0.5)

        return ComplianceScores(
            compliance_risk_score=round(compliance_risk, 2),
            regulatory_relevance=round(regulatory_relevance, 2),
            auditability_score=round(audit, 2),
            data_governance_score=round((privacy + crypto) / 2, 2),
        )

    def _match_regulations(self, text: str) -> List[str]:
        matched = []
        for reg_id, signals in REGULATION_TECH_REQUIREMENTS.items():
            hits = sum(1 for s in signals if s.lower() in text)
            if hits >= MIN_REGULATION_SIGNAL_HITS:
                matched.append(reg_id)
        return matched

    def _detect_compliance_capabilities(self, text: str) -> List[str]:
        capabilities = []
        signal_map = {
            "data_privacy": DATA_PRIVACY_SIGNALS,
            "transaction_monitoring": TRANSACTION_MONITORING_SIGNALS,
            "identity_verification": IDENTITY_VERIFICATION_SIGNALS,
            "audit_trail": AUDIT_TRAIL_SIGNALS,
            "cryptographic_security": CRYPTOGRAPHIC_SIGNALS,
            "regulatory_reporting": REPORTING_SIGNALS,
        }
        for cap, signals in signal_map.items():
            hits = sum(1 for s in signals if s.lower() in text)
            if hits >= MIN_REGULATION_SIGNAL_HITS:
                capabilities.append(cap)
        return capabilities

    def _build_regulation_provenance(self, reg_id: str, text: str) -> Dict[str, object]:
        signals = REGULATION_TECH_REQUIREMENTS.get(reg_id, [])
        matched_signals = [s for s in signals if s.lower() in text]
        signal_count = len(matched_signals)
        coverage = signal_count / max(len(signals), 1)
        digest = hashlib.sha256("|".join(sorted(matched_signals)).encode("utf-8")).hexdigest()[:16]

        # Deterministic confidence for governance/review workflows.
        confidence = min(1.0, round(0.35 + coverage, 2))

        return {
            "method": "rule_based_v1",
            "signals": matched_signals,
            "signal_count": signal_count,
            "hash": digest,
            "confidence": confidence,
        }

    def _assess_regulation_risk(self, reg_id: str, text: str) -> str:
        signals = REGULATION_TECH_REQUIREMENTS.get(reg_id, [])
        hits = sum(1 for s in signals if s.lower() in text)
        density = hits / max(len(signals), 1)
        if density >= 0.4:
            return "high"
        elif density >= 0.2:
            return "medium"
        return "low"

    async def _link_regulatory_docs_to_technologies(self) -> None:
        """Link recently ingested regulatory docs to affected Technology nodes."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        # Find recent regulatory events with fintech relevance tags
        docs = await self._neo4j_query("""
            MATCH (rd:RegulatoryDocument)
            WHERE rd.processed = false OR rd.processed IS NULL
            RETURN rd.id AS id, rd.fintech_tags AS tags, rd.title AS title
            LIMIT 100
        """)

        for doc in docs:
            tags = doc.get("tags") or []
            for tag in tags:
                tech_id = f"tech:{tag.lower().replace(' ', '-')}"
                await self._neo4j_write("""
                    MERGE (t:Technology {id: $tech_id})
                    ON CREATE SET t.name = $tag
                    WITH t
                    MATCH (rd:RegulatoryDocument {id: $doc_id})
                    MERGE (rd)-[:AFFECTS_TECHNOLOGY]->(t)
                    SET rd.processed = true
                """, {"tech_id": tech_id, "tag": tag, "doc_id": doc["id"]})
