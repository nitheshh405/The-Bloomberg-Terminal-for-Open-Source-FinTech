"""
Adoption Opportunity Agent (Agent 7 of 10)

Identifies which open-source FinTech projects are ready — or nearly ready —
for institutional adoption by financial firms, and maps the pathway to adoption:

- Scores repositories on 6 adoption readiness dimensions
- Maps which financial sectors are most likely to adopt which technologies
- Identifies the "last mile" gaps blocking adoption (license, documentation,
  compliance certification, SLA guarantees, etc.)
- Prioritizes opportunities by market size × readiness × strategic fit
- Generates sector-specific adoption opportunity rankings
- Creates ADOPTION_OPPORTUNITY edges between sectors and repositories
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Adoption readiness dimensions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AdoptionReadinessScores:
    """
    6-dimensional adoption readiness framework.
    Each dimension scored 0–100. Composite score is weighted average.
    """

    # 1. Technical maturity: stability, test coverage, versioning discipline
    technical_maturity: float = 0.0

    # 2. Compliance fit: alignment with regulatory requirements for the sector
    compliance_fit: float = 0.0

    # 3. Integration ease: API quality, SDK availability, documentation depth
    integration_ease: float = 0.0

    # 4. Support ecosystem: commercial support options, maintainer responsiveness
    support_ecosystem: float = 0.0

    # 5. License permissiveness: enterprise-friendly license (Apache/MIT > GPL/AGPL)
    license_permissiveness: float = 0.0

    # 6. Market validation: existing adoption by peers / competitors
    market_validation: float = 0.0

    # Computed
    composite_score: float = 0.0
    blocking_gaps: List[str] = field(default_factory=list)
    adoption_stage: str = "experimental"  # experimental | emerging | validated | mainstream

    WEIGHTS = {
        "technical_maturity": 0.25,
        "compliance_fit": 0.22,
        "integration_ease": 0.18,
        "support_ecosystem": 0.15,
        "license_permissiveness": 0.12,
        "market_validation": 0.08,
    }

    def compute_composite(self) -> float:
        raw = (
            self.technical_maturity * self.WEIGHTS["technical_maturity"] +
            self.compliance_fit * self.WEIGHTS["compliance_fit"] +
            self.integration_ease * self.WEIGHTS["integration_ease"] +
            self.support_ecosystem * self.WEIGHTS["support_ecosystem"] +
            self.license_permissiveness * self.WEIGHTS["license_permissiveness"] +
            self.market_validation * self.WEIGHTS["market_validation"]
        )
        self.composite_score = round(raw, 2)
        self.adoption_stage = self._classify_stage(self.composite_score)
        return self.composite_score

    @staticmethod
    def _classify_stage(score: float) -> str:
        if score >= 75:
            return "mainstream"
        elif score >= 55:
            return "validated"
        elif score >= 35:
            return "emerging"
        return "experimental"


# ─────────────────────────────────────────────────────────────────────────────
# Sector-technology affinity matrix
# ─────────────────────────────────────────────────────────────────────────────

# For each financial sector, which technology domains drive the highest adoption value?
SECTOR_TECHNOLOGY_AFFINITY: Dict[str, Dict[str, float]] = {
    "retail_banking": {
        "open_banking": 0.95, "identity_verification": 0.90, "payments": 0.88,
        "fraud_detection": 0.85, "customer_analytics": 0.80, "api_gateway": 0.75,
        "credit_scoring": 0.72, "chatbot": 0.65,
    },
    "investment_banking": {
        "risk_analytics": 0.92, "market_data": 0.90, "trade_execution": 0.88,
        "derivatives_pricing": 0.85, "regulatory_reporting": 0.82,
        "document_intelligence": 0.75, "blockchain": 0.60,
    },
    "asset_management": {
        "portfolio_optimization": 0.93, "risk_analytics": 0.90,
        "esg_data": 0.85, "market_data": 0.83, "alternative_data": 0.80,
        "reporting_automation": 0.75, "factor_modeling": 0.72,
    },
    "insurance": {
        "fraud_detection": 0.92, "document_intelligence": 0.88,
        "pricing_models": 0.85, "claims_automation": 0.83,
        "iot_data_processing": 0.75, "regulatory_reporting": 0.72,
    },
    "payments": {
        "payments": 0.98, "fraud_detection": 0.93, "identity_verification": 0.90,
        "open_banking": 0.87, "crypto_infrastructure": 0.70, "cbdc": 0.65,
    },
    "capital_markets": {
        "market_data": 0.95, "trade_execution": 0.92, "risk_analytics": 0.90,
        "regulatory_reporting": 0.88, "clearing_settlement": 0.85,
        "blockchain": 0.70, "zero_knowledge_proofs": 0.65,
    },
    "compliance_regtech": {
        "aml_kyc": 0.97, "regulatory_reporting": 0.95, "identity_verification": 0.90,
        "transaction_monitoring": 0.88, "sanctions_screening": 0.85,
        "audit_automation": 0.82, "policy_management": 0.75,
    },
    "lending": {
        "credit_scoring": 0.95, "identity_verification": 0.90, "open_banking": 0.88,
        "fraud_detection": 0.85, "document_intelligence": 0.80,
        "loan_origination": 0.78, "collections_analytics": 0.70,
    },
}

# Enterprise-friendly licenses → high permissiveness score
PERMISSIVE_LICENSES = {"mit", "apache-2.0", "apache 2.0", "bsd-2-clause",
                       "bsd-3-clause", "isc", "cc0-1.0"}
COPYLEFT_LICENSES = {"gpl-2.0", "gpl-3.0", "agpl-3.0", "lgpl-2.1", "lgpl-3.0"}


# ─────────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ─────────────────────────────────────────────────────────────────────────────

def _score_technical_maturity(repo: Dict) -> Tuple[float, List[str]]:
    """Estimate technical maturity from available repo signals."""
    gaps = []
    score = 0.0

    stars = repo.get("stars") or 0
    forks = repo.get("forks") or 0
    open_issues = repo.get("open_issues") or 0
    is_archived = repo.get("is_archived") or False
    has_tests = repo.get("has_tests") or False
    has_ci = repo.get("has_ci") or False
    release_count = repo.get("release_count") or 0

    if is_archived:
        return 5.0, ["archived_repository"]

    score += min(math.log1p(stars) * 4, 25.0)
    score += min(math.log1p(forks) * 3, 20.0)
    score += 20.0 if has_tests else 0.0
    score += 15.0 if has_ci else 0.0
    score += min(release_count * 2, 10.0)
    score += max(0, 10.0 - open_issues / 20.0)

    if not has_tests:
        gaps.append("no_automated_tests")
    if not has_ci:
        gaps.append("no_ci_pipeline")
    if release_count == 0:
        gaps.append("no_versioned_releases")

    return round(min(score, 100.0), 2), gaps


def _score_compliance_fit(repo: Dict, sector: str) -> Tuple[float, List[str]]:
    """Score how well the repo aligns with the sector's compliance needs."""
    gaps = []
    regulatory_score = (repo.get("regulatory_relevance_score") or 0) / 100.0
    domains = repo.get("fintech_domains") or []

    sector_affinities = SECTOR_TECHNOLOGY_AFFINITY.get(sector, {})
    domain_match = max(
        (sector_affinities.get(d, 0.0) for d in domains),
        default=0.0,
    )

    score = round((regulatory_score * 0.5 + domain_match * 0.5) * 100, 2)

    if score < 30:
        gaps.append(f"low_domain_alignment_for_{sector}")
    if regulatory_score < 0.2:
        gaps.append("minimal_regulatory_coverage")

    return score, gaps


def _score_license(license_str: str) -> Tuple[float, List[str]]:
    """Score license permissiveness for enterprise adoption."""
    if not license_str:
        return 40.0, ["no_license_specified"]
    lic = license_str.lower().strip()
    if lic in PERMISSIVE_LICENSES:
        return 100.0, []
    elif any(lic.startswith(c) for c in ["apache", "mit", "bsd", "isc"]):
        return 90.0, []
    elif lic in COPYLEFT_LICENSES:
        return 20.0, ["copyleft_license_enterprise_risk"]
    elif "proprietary" in lic or "commercial" in lic:
        return 30.0, ["non_oss_license"]
    return 50.0, ["unrecognized_license"]


def _score_integration_ease(repo: Dict) -> Tuple[float, List[str]]:
    """Estimate integration ease from documentation and API signals."""
    gaps = []
    score = 0.0

    has_readme = bool(repo.get("readme_snippet"))
    has_docs = repo.get("has_docs") or False
    has_api_docs = repo.get("has_api_docs") or False
    has_sdk = repo.get("has_sdk") or False
    language = (repo.get("language") or "").lower()

    score += 25.0 if has_readme else 0.0
    score += 25.0 if has_docs else 0.0
    score += 20.0 if has_api_docs else 0.0
    score += 20.0 if has_sdk else 0.0
    score += 10.0 if language in {"python", "javascript", "typescript", "java"} else 5.0

    if not has_docs:
        gaps.append("missing_documentation")
    if not has_api_docs:
        gaps.append("missing_api_documentation")
    if not has_sdk:
        gaps.append("no_official_sdk")

    return round(min(score, 100.0), 2), gaps


def _score_market_validation(repo: Dict) -> float:
    """Estimate how much market validation exists via star/fork counts."""
    stars = repo.get("stars") or 0
    forks = repo.get("forks") or 0
    # Log scale: 1000 stars ≈ 50 points, 10000 stars ≈ 90 points
    return round(min(math.log1p(stars) * 7 + math.log1p(forks) * 3, 100.0), 2)


def _score_support_ecosystem(repo: Dict) -> Tuple[float, List[str]]:
    """Estimate availability of commercial support and maintainer responsiveness."""
    gaps = []
    org = (repo.get("org_name") or "").lower()
    stars = repo.get("stars") or 0
    contributors = repo.get("contributors_count") or 0

    # Proxies for support availability
    score = 0.0
    score += min(math.log1p(contributors) * 8, 40.0)  # more contributors = more support
    score += min(math.log1p(stars) * 3, 30.0)         # popular = community support
    score += 20.0 if contributors >= 10 else 10.0      # bus factor proxy
    score += 10.0 if contributors >= 50 else 0.0       # large community

    if contributors < 3:
        gaps.append("bus_factor_risk_single_maintainer")
    if stars < 100:
        gaps.append("limited_community_support")

    return round(min(score, 100.0), 2), gaps


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

class AdoptionOpportunityAgent(BaseAgent):
    """
    Agent 7: Scores and ranks open-source FinTech repositories for institutional adoption.

    Creates :AdoptionOpportunity nodes and edges:
    - (FinancialSector)-[:HAS_ADOPTION_OPPORTUNITY {score, stage, gaps}]->(Repository)
    """

    def __init__(self, **kwargs):
        super().__init__(name="AdoptionOpportunityAgent", **kwargs)

    async def _run(self, result: AgentResult) -> AgentResult:
        repos = await self._fetch_repos_for_adoption_scoring()
        result.items_processed = len(repos)

        total_opportunities = 0
        mainstream_count = 0
        validated_count = 0
        sector_leaders: Dict[str, List[Tuple[str, float]]] = {}

        for batch in self._chunk(repos, 50):
            tasks = [self._score_repo_for_all_sectors(r) for r in batch]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    result.errors.append(str(outcome))
                elif isinstance(outcome, list):
                    for opp in outcome:
                        total_opportunities += 1
                        if opp["stage"] == "mainstream":
                            mainstream_count += 1
                        elif opp["stage"] == "validated":
                            validated_count += 1
                        sector = opp["sector"]
                        if sector not in sector_leaders:
                            sector_leaders[sector] = []
                        sector_leaders[sector].append(
                            (opp["repo_full_name"], opp["composite_score"])
                        )

        result.items_created = total_opportunities

        result.insights.append(
            f"Scored {result.items_processed} repos across "
            f"{len(SECTOR_TECHNOLOGY_AFFINITY)} sectors: "
            f"{total_opportunities} adoption opportunities identified"
        )
        if mainstream_count:
            result.insights.append(
                f"Mainstream-ready (score ≥75): {mainstream_count} repo-sector pairs"
            )
        if validated_count:
            result.insights.append(
                f"Validated stage (score ≥55): {validated_count} repo-sector pairs"
            )

        # Top opportunity per sector
        for sector, opps in sector_leaders.items():
            if opps:
                top = max(opps, key=lambda x: x[1])
                result.insights.append(
                    f"Top opportunity in {sector}: {top[0]} (score={top[1]:.1f})"
                )

        return result

    async def _fetch_repos_for_adoption_scoring(self) -> List[Dict]:
        return await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.primary_sector IS NOT NULL
              AND r.stars >= 50
              AND (
                r.adoption_score_at IS NULL
                OR r.adoption_score_at < datetime() - duration({days: 14})
              )
            RETURN r.id AS id,
                   r.full_name AS full_name,
                   r.stars AS stars,
                   r.forks AS forks,
                   r.open_issues AS open_issues,
                   r.contributors_count AS contributors_count,
                   r.language AS language,
                   r.license AS license,
                   r.is_archived AS is_archived,
                   r.readme_snippet AS readme_snippet,
                   r.fintech_domains AS fintech_domains,
                   r.regulatory_relevance_score AS regulatory_relevance_score,
                   r.has_tests AS has_tests,
                   r.has_ci AS has_ci,
                   r.has_docs AS has_docs,
                   r.release_count AS release_count
            ORDER BY r.stars DESC
            LIMIT 5000
        """)

    async def _score_repo_for_all_sectors(self, repo: Dict) -> List[Dict]:
        """Score this repo against every relevant financial sector."""
        repo_id = repo["id"]
        domains = repo.get("fintech_domains") or []
        opportunities = []

        # Determine which sectors this repo is relevant to
        relevant_sectors = []
        for sector, affinities in SECTOR_TECHNOLOGY_AFFINITY.items():
            max_affinity = max(
                (affinities.get(d, 0.0) for d in domains),
                default=0.0,
            )
            if max_affinity >= 0.6:
                relevant_sectors.append((sector, max_affinity))

        if not relevant_sectors:
            # Default to top-3 sectors by domain match
            all_sectors = []
            for sector, affinities in SECTOR_TECHNOLOGY_AFFINITY.items():
                score = sum(affinities.get(d, 0.0) for d in domains)
                all_sectors.append((sector, score))
            relevant_sectors = sorted(all_sectors, key=lambda x: x[1], reverse=True)[:3]

        for sector, sector_affinity in relevant_sectors:
            scores = AdoptionReadinessScores()
            all_gaps = []

            tech_score, tech_gaps = _score_technical_maturity(repo)
            scores.technical_maturity = tech_score
            all_gaps.extend(tech_gaps)

            comp_score, comp_gaps = _score_compliance_fit(repo, sector)
            scores.compliance_fit = comp_score
            all_gaps.extend(comp_gaps)

            int_score, int_gaps = _score_integration_ease(repo)
            scores.integration_ease = int_score
            all_gaps.extend(int_gaps)

            sup_score, sup_gaps = _score_support_ecosystem(repo)
            scores.support_ecosystem = sup_score
            all_gaps.extend(sup_gaps)

            lic_score, lic_gaps = _score_license(repo.get("license") or "")
            scores.license_permissiveness = lic_score
            all_gaps.extend(lic_gaps)

            scores.market_validation = _score_market_validation(repo)
            scores.blocking_gaps = all_gaps
            scores.compute_composite()

            # Only create opportunities for repos with meaningful scores
            if scores.composite_score < 20:
                continue

            opportunity = {
                "repo_id": repo_id,
                "repo_full_name": repo.get("full_name", repo_id),
                "sector": sector,
                "composite_score": scores.composite_score,
                "stage": scores.adoption_stage,
                "technical_maturity": scores.technical_maturity,
                "compliance_fit": scores.compliance_fit,
                "integration_ease": scores.integration_ease,
                "support_ecosystem": scores.support_ecosystem,
                "license_permissiveness": scores.license_permissiveness,
                "market_validation": scores.market_validation,
                "blocking_gaps": all_gaps[:10],
                "sector_affinity": round(sector_affinity * 100, 2),
            }
            opportunities.append(opportunity)

            # Write to Neo4j
            now = datetime.now(timezone.utc).isoformat()
            await self._neo4j_write("""
                MATCH (r:Repository {id: $repo_id})
                MERGE (s:FinancialSector {name: $sector})
                MERGE (s)-[opp:HAS_ADOPTION_OPPORTUNITY]->(r)
                SET opp.composite_score       = $composite_score,
                    opp.adoption_stage        = $stage,
                    opp.technical_maturity    = $technical_maturity,
                    opp.compliance_fit        = $compliance_fit,
                    opp.integration_ease      = $integration_ease,
                    opp.support_ecosystem     = $support_ecosystem,
                    opp.license_permissiveness= $license_permissiveness,
                    opp.market_validation     = $market_validation,
                    opp.blocking_gaps         = $blocking_gaps,
                    opp.sector_affinity       = $sector_affinity,
                    opp.scored_at             = datetime($now)
            """, {**opportunity, "now": now})

        # Mark repo as scored
        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.adoption_score_at = datetime($now)
        """, {"id": repo_id, "now": datetime.now(timezone.utc).isoformat()})

        return opportunities

    async def get_sector_adoption_leaderboard(self, sector: str, limit: int = 20) -> List[Dict]:
        """Return the top adoption opportunities for a given financial sector."""
        return await self._neo4j_query("""
            MATCH (s:FinancialSector {name: $sector})-[opp:HAS_ADOPTION_OPPORTUNITY]->(r:Repository)
            RETURN r.full_name AS repo,
                   opp.composite_score AS score,
                   opp.adoption_stage AS stage,
                   opp.blocking_gaps AS gaps,
                   opp.compliance_fit AS compliance_fit,
                   opp.technical_maturity AS technical_maturity,
                   r.stars AS stars,
                   r.primary_sector AS primary_sector
            ORDER BY opp.composite_score DESC
            LIMIT $limit
        """, {"sector": sector, "limit": limit})

    async def get_mainstream_ready_repos(self) -> List[Dict]:
        """Return all repositories that are mainstream-ready (score ≥75) in any sector."""
        return await self._neo4j_query("""
            MATCH (s:FinancialSector)-[opp:HAS_ADOPTION_OPPORTUNITY]->(r:Repository)
            WHERE opp.adoption_stage = 'mainstream'
            WITH r, collect({sector: s.name, score: opp.composite_score}) AS sector_opps
            RETURN r.full_name AS repo,
                   r.stars AS stars,
                   r.license AS license,
                   sector_opps,
                   size(sector_opps) AS sector_count
            ORDER BY sector_count DESC, r.stars DESC
            LIMIT 50
        """)

    async def get_gap_analysis_report(self) -> List[Dict]:
        """
        Aggregate the most common blocking gaps across all repos.
        Shows where the ecosystem needs investment to unlock institutional adoption.
        """
        return await self._neo4j_query("""
            MATCH (:FinancialSector)-[opp:HAS_ADOPTION_OPPORTUNITY]->(:Repository)
            UNWIND opp.blocking_gaps AS gap
            WITH gap, count(*) AS frequency
            ORDER BY frequency DESC
            RETURN gap, frequency
            LIMIT 20
        """)
