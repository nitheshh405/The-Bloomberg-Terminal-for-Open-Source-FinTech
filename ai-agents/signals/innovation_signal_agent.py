"""
Innovation Signal Agent (Agent 5 of 10)

Detects early-stage innovation signals before they register on mainstream radar:
- Monitors velocity inflections: sudden acceleration in stars, forks, contributors
- Detects "pre-viral" repositories: high engagement relative to age and size
- Identifies concept clustering: multiple repos independently solving the same problem
  (signals an emerging technology category)
- Surfaces cross-pollination: when techniques from one sector appear in another
  (e.g., cryptographic proofs moving from blockchain into traditional banking)
- Detects regulatory anticipation: repos that pre-implement regulation before
  the regulation is finalized (suggests insider knowledge or deep domain expertise)
- Computes a composite Innovation Signal Score (ISS) per repository
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
# Signal definitions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VelocitySignal:
    """Captures rate-of-change for a repository metric."""
    metric: str
    current_value: float
    baseline_value: float
    window_days: int = 30

    @property
    def growth_rate(self) -> float:
        """Relative growth rate vs baseline."""
        if self.baseline_value == 0:
            return min(self.current_value, 10.0)
        return (self.current_value - self.baseline_value) / max(self.baseline_value, 1)

    @property
    def is_inflection(self) -> bool:
        """True if growth rate exceeds 100% in window — inflection point."""
        return self.growth_rate >= 1.0


@dataclass
class InnovationSignalProfile:
    """Full innovation signal profile for one repository."""

    repo_id: str
    repo_full_name: str

    # Velocity signals
    star_velocity: Optional[VelocitySignal] = None
    fork_velocity: Optional[VelocitySignal] = None
    contributor_velocity: Optional[VelocitySignal] = None
    commit_velocity: Optional[VelocitySignal] = None

    # Concept signals
    concept_cluster_score: float = 0.0      # 0–1: how many others are solving same problem
    cross_pollination_score: float = 0.0    # 0–1: techniques imported from other sectors
    regulatory_anticipation_score: float = 0.0  # 0–1: pre-implements upcoming regulations

    # Momentum signals
    pre_viral_score: float = 0.0            # high engagement relative to repo age
    enterprise_discovery_score: float = 0.0 # being forked/starred by institution accounts

    # Composite
    innovation_signal_score: float = 0.0    # 0–100 final score

    fired_signals: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Signal detection helpers
# ─────────────────────────────────────────────────────────────────────────────

# Topics/keywords that suggest cross-pollination between sectors
CROSS_POLLINATION_PAIRS = [
    ({"zero_knowledge", "zkp", "zk-snark"}, {"banking", "compliance", "kyc"}),
    ({"homomorphic_encryption"}, {"credit_scoring", "fraud_detection"}),
    ({"blockchain", "smart_contracts"}, {"trade_finance", "securities"}),
    ({"federated_learning"}, {"credit_risk", "anti_money_laundering"}),
    ({"differential_privacy"}, {"open_banking", "data_sharing"}),
    ({"cbdc", "central_bank_digital_currency"}, {"payments", "monetary_policy"}),
    ({"llm", "large_language_model"}, {"compliance", "regulatory_reporting"}),
]

# Upcoming / recently enacted regulations — repos implementing these pre-launch
# signal deep domain knowledge or regulatory insider awareness
REGULATORY_ANTICIPATION_KEYWORDS = {
    "eu_ai_act": ["ai act", "eu ai", "foundation model", "high risk ai"],
    "dora": ["digital operational resilience", "dora", "ict risk", "third party risk"],
    "frtb": ["frtb", "fundamental review trading book", "iba", "sba"],
    "basel4": ["basel iv", "basel 4", "credit risk standardised", "sa-ccr"],
    "t1_settlement": ["t+1", "same day settlement", "accelerated settlement"],
    "open_banking_v3": ["open banking", "psd3", "payment services directive"],
}


def _compute_pre_viral_score(
    stars: int, age_days: int, contributors: int, forks: int
) -> float:
    """
    Pre-viral score: high engagement per unit of time.
    A 3-month-old repo with 500 stars is more signal-worthy than a
    5-year-old repo with 5000 stars.
    """
    if age_days <= 0:
        return 0.0
    stars_per_day = stars / age_days
    forks_per_day = forks / max(age_days, 1)
    contributors_per_day = contributors / max(age_days, 1)

    # Normalize against "exceptional" thresholds
    score = (
        min(stars_per_day / 5.0, 1.0) * 40 +
        min(forks_per_day / 1.0, 1.0) * 30 +
        min(contributors_per_day / 0.5, 1.0) * 30
    )
    return round(min(score, 100.0), 2)


def _compute_cross_pollination(topics: List[str], domains: List[str]) -> float:
    """
    Detect when a repo brings together concepts from different sectors.
    Higher score = more cross-sector innovation.
    """
    combined = set(t.lower().replace("-", "_").replace(" ", "_")
                   for t in (topics + domains))
    matched_pairs = 0
    for tech_set, finance_set in CROSS_POLLINATION_PAIRS:
        if (tech_set & combined) and (finance_set & combined):
            matched_pairs += 1
    return min(matched_pairs / len(CROSS_POLLINATION_PAIRS), 1.0)


def _compute_regulatory_anticipation(
    description: str, topics: List[str], readme: str
) -> Tuple[float, List[str]]:
    """
    Detect if a repo pre-implements or discusses upcoming regulations.
    Returns (score 0-1, list of detected regulation tags).
    """
    text = f"{description} {' '.join(topics)} {readme}".lower()
    matched = []
    for reg_id, keywords in REGULATORY_ANTICIPATION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            matched.append(reg_id)

    score = min(len(matched) / 3.0, 1.0)
    return score, matched


def _compute_velocity_signal(
    current: float, baseline: float, metric: str
) -> VelocitySignal:
    return VelocitySignal(
        metric=metric,
        current_value=current,
        baseline_value=baseline,
        window_days=30,
    )


def _composite_iss(profile: InnovationSignalProfile) -> float:
    """
    Innovation Signal Score (ISS) 0–100.

    Weights reflect the insight value of each signal type:
    - Velocity inflections are the strongest leading indicator (35%)
    - Pre-viral momentum shows organic growth (20%)
    - Cross-pollination signals novel application of tech (20%)
    - Regulatory anticipation shows domain depth (15%)
    - Enterprise discovery validates commercial potential (10%)
    """
    velocity_score = 0.0
    for signal in [
        profile.star_velocity,
        profile.fork_velocity,
        profile.contributor_velocity,
        profile.commit_velocity,
    ]:
        if signal:
            velocity_score = max(velocity_score, min(signal.growth_rate * 50, 35.0))

    return round(
        velocity_score * 0.35 +
        profile.pre_viral_score * 0.20 +
        profile.cross_pollination_score * 100 * 0.20 +
        profile.regulatory_anticipation_score * 100 * 0.15 +
        profile.enterprise_discovery_score * 100 * 0.10,
        2,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

class InnovationSignalAgent(BaseAgent):
    """
    Agent 5: Detects early-stage innovation signals across the FinTech OSS graph.

    Writes ISS scores, signal tags, and SIGNALS_INNOVATION edges back to Neo4j.
    Surfaces the most promising pre-mainstream repositories each week.
    """

    def __init__(self, **kwargs):
        super().__init__(name="InnovationSignalAgent", **kwargs)

    async def _run(self, result: AgentResult) -> AgentResult:
        repos = await self._fetch_repos_for_signal_analysis()
        result.items_processed = len(repos)

        high_iss: List[Tuple[str, float]] = []
        inflection_count = 0
        cross_pollination_count = 0
        reg_anticipation_count = 0
        pre_viral_count = 0

        for batch in self._chunk(repos, 100):
            tasks = [self._analyze_repo(r) for r in batch]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    result.errors.append(str(outcome))
                elif isinstance(outcome, InnovationSignalProfile):
                    result.items_updated += 1
                    if outcome.innovation_signal_score >= 60:
                        high_iss.append((outcome.repo_full_name,
                                         outcome.innovation_signal_score))
                    if any(s and s.is_inflection for s in [
                        outcome.star_velocity, outcome.fork_velocity,
                        outcome.contributor_velocity
                    ]):
                        inflection_count += 1
                    if outcome.cross_pollination_score > 0.3:
                        cross_pollination_count += 1
                    if outcome.regulatory_anticipation_score > 0.3:
                        reg_anticipation_count += 1
                    if outcome.pre_viral_score >= 50:
                        pre_viral_count += 1

        high_iss.sort(key=lambda x: x[1], reverse=True)

        if high_iss:
            result.insights.append(
                f"High Innovation Signal Score (≥60): {len(high_iss)} repos — "
                f"top: {high_iss[0][0]} (ISS={high_iss[0][1]:.1f})"
            )
        if inflection_count:
            result.insights.append(
                f"Velocity inflection points detected: {inflection_count} repos "
                f"with 100%+ growth in a signal metric"
            )
        if cross_pollination_count:
            result.insights.append(
                f"Cross-sector technology transfer: {cross_pollination_count} repos "
                f"applying novel tech to FinTech problems"
            )
        if reg_anticipation_count:
            result.insights.append(
                f"Regulatory anticipation detected: {reg_anticipation_count} repos "
                f"pre-implementing upcoming regulations"
            )
        if pre_viral_count:
            result.insights.append(
                f"Pre-viral momentum: {pre_viral_count} young repos with "
                f"disproportionate engagement"
            )

        return result

    async def _fetch_repos_for_signal_analysis(self) -> List[Dict]:
        return await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.primary_sector IS NOT NULL
              AND (
                r.innovation_signal_at IS NULL
                OR r.innovation_signal_at < datetime() - duration({days: 7})
              )
            RETURN r.id AS id,
                   r.full_name AS full_name,
                   r.stars AS stars,
                   r.stars_baseline AS stars_baseline,
                   r.forks AS forks,
                   r.forks_baseline AS forks_baseline,
                   r.contributors_count AS contributors,
                   r.contributors_baseline AS contributors_baseline,
                   r.description AS description,
                   r.topics AS topics,
                   r.fintech_domains AS domains,
                   r.readme_snippet AS readme,
                   r.created_at AS created_at,
                   r.innovation_score AS innovation_score
            ORDER BY r.stars DESC
            LIMIT 10000
        """)

    async def _analyze_repo(self, repo: Dict) -> InnovationSignalProfile:
        repo_id = repo["id"]
        full_name = repo.get("full_name", repo_id)

        stars = repo.get("stars") or 0
        stars_baseline = repo.get("stars_baseline") or max(stars - 10, 0)
        forks = repo.get("forks") or 0
        forks_baseline = repo.get("forks_baseline") or max(forks - 2, 0)
        contributors = repo.get("contributors") or 0
        contributors_baseline = repo.get("contributors_baseline") or max(contributors - 1, 0)
        topics = repo.get("topics") or []
        domains = repo.get("domains") or []
        description = repo.get("description") or ""
        readme = repo.get("readme") or ""

        # Compute repo age
        created_at = repo.get("created_at")
        age_days = 365  # default fallback
        if created_at:
            try:
                if isinstance(created_at, str):
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    created_dt = created_at
                age_days = max((datetime.now(timezone.utc) - created_dt).days, 1)
            except (ValueError, TypeError):
                pass

        profile = InnovationSignalProfile(
            repo_id=repo_id,
            repo_full_name=full_name,
            star_velocity=_compute_velocity_signal(stars, stars_baseline, "stars"),
            fork_velocity=_compute_velocity_signal(forks, forks_baseline, "forks"),
            contributor_velocity=_compute_velocity_signal(
                contributors, contributors_baseline, "contributors"
            ),
            pre_viral_score=_compute_pre_viral_score(stars, age_days, contributors, forks),
            cross_pollination_score=_compute_cross_pollination(topics, domains),
        )

        reg_score, reg_tags = _compute_regulatory_anticipation(description, topics, readme)
        profile.regulatory_anticipation_score = reg_score

        # Enterprise discovery: estimate from star/fork counts relative to baseline
        enterprise_proxy = min(
            math.log1p(stars) / 15.0 + math.log1p(forks) / 10.0, 1.0
        )
        profile.enterprise_discovery_score = enterprise_proxy

        # Collect fired signal labels
        if profile.star_velocity and profile.star_velocity.is_inflection:
            profile.fired_signals.append("star_inflection")
        if profile.fork_velocity and profile.fork_velocity.is_inflection:
            profile.fired_signals.append("fork_inflection")
        if profile.contributor_velocity and profile.contributor_velocity.is_inflection:
            profile.fired_signals.append("contributor_inflection")
        if profile.pre_viral_score >= 50:
            profile.fired_signals.append("pre_viral")
        if profile.cross_pollination_score > 0.3:
            profile.fired_signals.append("cross_pollination")
        if reg_score > 0.3:
            profile.fired_signals.extend([f"reg_anticipation:{t}" for t in reg_tags])

        profile.innovation_signal_score = _composite_iss(profile)

        # Persist to Neo4j
        now = datetime.now(timezone.utc).isoformat()
        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.innovation_signal_score        = $iss,
                r.pre_viral_score                = $pre_viral,
                r.cross_pollination_score        = $cross_pol,
                r.regulatory_anticipation_score  = $reg_ant,
                r.fired_signals                  = $signals,
                r.star_growth_rate               = $star_growth,
                r.fork_growth_rate               = $fork_growth,
                r.contributor_growth_rate        = $contrib_growth,
                r.innovation_signal_at           = datetime($now)
        """, {
            "id": repo_id,
            "iss": profile.innovation_signal_score,
            "pre_viral": profile.pre_viral_score,
            "cross_pol": round(profile.cross_pollination_score * 100, 2),
            "reg_ant": round(profile.regulatory_anticipation_score * 100, 2),
            "signals": profile.fired_signals,
            "star_growth": round(profile.star_velocity.growth_rate, 4)
                           if profile.star_velocity else 0.0,
            "fork_growth": round(profile.fork_velocity.growth_rate, 4)
                           if profile.fork_velocity else 0.0,
            "contrib_growth": round(profile.contributor_velocity.growth_rate, 4)
                               if profile.contributor_velocity else 0.0,
            "now": now,
        })

        return profile

    async def get_weekly_top_signals(self, limit: int = 20) -> List[Dict]:
        """
        Query: top repositories by Innovation Signal Score updated in the last 7 days.
        Used by the WeeklyIntelligenceAgent to surface emerging opportunities.
        """
        return await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.innovation_signal_score IS NOT NULL
              AND r.innovation_signal_at >= datetime() - duration({days: 7})
            RETURN r.full_name AS repo,
                   r.innovation_signal_score AS iss,
                   r.fired_signals AS signals,
                   r.pre_viral_score AS pre_viral,
                   r.cross_pollination_score AS cross_pol,
                   r.regulatory_anticipation_score AS reg_ant,
                   r.stars AS stars,
                   r.primary_sector AS sector
            ORDER BY r.innovation_signal_score DESC
            LIMIT $limit
        """, {"limit": limit})

    async def get_concept_clusters(self) -> List[Dict]:
        """
        Detect emerging technology categories by finding repositories with
        highly similar topic/domain fingerprints — independent solutions to the same problem.
        """
        return await self._neo4j_query("""
            MATCH (r1:Repository)-[:IMPLEMENTS]->(t:Technology)<-[:IMPLEMENTS]-(r2:Repository)
            WHERE r1.id < r2.id
              AND r1.innovation_signal_score >= 40
              AND r2.innovation_signal_score >= 40
            WITH t.name AS technology,
                 count(*) AS cluster_size,
                 collect(r1.full_name)[..5] + collect(r2.full_name)[..5] AS sample_repos
            WHERE cluster_size >= 3
            ORDER BY cluster_size DESC
            RETURN technology, cluster_size, sample_repos
            LIMIT 20
        """)
