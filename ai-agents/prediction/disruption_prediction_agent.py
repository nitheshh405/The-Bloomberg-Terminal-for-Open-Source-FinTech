"""
Disruption Prediction Agent (Agent 8 of 10)
Startup Opportunity Agent  (Agent 9 of 10)

Predicts which repositories will become critical financial infrastructure
within 3-5 years, and which are likely to spawn fintech startups.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Disruption Prediction Feature Engineering
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DisruptionFeatures:
    """Feature vector for the disruption probability model."""

    # Growth signals
    star_growth_30d: float = 0.0
    fork_growth_30d: float = 0.0
    contributor_growth_30d: float = 0.0
    commit_frequency: float = 0.0          # commits per week (last 3 months)

    # Network signals
    dependent_repo_count: int = 0          # repos that depend on this one
    reverse_dependency_depth: int = 0      # max depth in dependency graph
    cross_sector_adoption: int = 0         # # of sectors using this tech

    # Technology signals
    tech_novelty_score: float = 0.0        # 0=solved problem, 1=novel approach
    regulatory_alignment: float = 0.0     # matches emerging regulatory needs
    protocol_standard_potential: float = 0.0  # could become a standard

    # Community signals
    enterprise_contributor_ratio: float = 0.0  # % from financial institutions
    issue_resolution_velocity: float = 0.0     # issues closed per week
    documentation_quality: float = 0.0

    def to_vector(self) -> List[float]:
        return [
            self.star_growth_30d,
            self.fork_growth_30d,
            self.contributor_growth_30d,
            self.commit_frequency,
            math.log1p(self.dependent_repo_count),
            self.reverse_dependency_depth,
            self.cross_sector_adoption,
            self.tech_novelty_score,
            self.regulatory_alignment,
            self.protocol_standard_potential,
            self.enterprise_contributor_ratio,
            self.issue_resolution_velocity,
            self.documentation_quality,
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic Disruption Scoring Model
# (replace with trained XGBoost/RandomForest once labeled data is available)
# ─────────────────────────────────────────────────────────────────────────────

class DisruptionScoringModel:
    """
    Weighted linear model with sigmoid activation.
    Feature weights derived from domain expertise and validated against
    known infrastructure-level projects (Kafka, Spark, Kubernetes finance forks).

    To replace with trained model:
        from sklearn.ensemble import GradientBoostingClassifier
        model = joblib.load("models/disruption_predictor.pkl")
        proba = model.predict_proba([features.to_vector()])[0][1]
    """

    WEIGHTS = {
        "star_growth_30d": 0.15,
        "fork_growth_30d": 0.10,
        "contributor_growth_30d": 0.12,
        "commit_frequency": 0.08,
        "dependent_repo_count": 0.18,       # strongest signal
        "reverse_dependency_depth": 0.10,
        "cross_sector_adoption": 0.12,
        "tech_novelty_score": 0.05,
        "regulatory_alignment": 0.08,
        "protocol_standard_potential": 0.10,
        "enterprise_contributor_ratio": 0.07,
        "issue_resolution_velocity": 0.04,
        "documentation_quality": 0.03,
    }

    def predict(self, features: DisruptionFeatures) -> float:
        """Return disruption probability in [0, 1]."""
        vec = features.to_vector()
        # Normalize each dimension to [0, 1] with expected max values
        max_vals = [5.0, 3.0, 2.0, 50.0, 6.9, 5.0, 10.0, 1.0, 1.0, 1.0, 1.0, 20.0, 1.0]
        normalized = [min(v / m, 1.0) for v, m in zip(vec, max_vals)]

        weights = list(self.WEIGHTS.values())
        raw_score = sum(w * n for w, n in zip(weights, normalized))

        # Sigmoid for probability
        return 1 / (1 + math.exp(-8 * (raw_score - 0.5)))


# ─────────────────────────────────────────────────────────────────────────────
# Startup Opportunity Signal Patterns
# ─────────────────────────────────────────────────────────────────────────────

STARTUP_SIGNALS = {
    "rapid_star_growth": {
        "description": "Stars doubled in 30 days",
        "weight": 0.20,
    },
    "enterprise_interest": {
        "description": "Contributions from major financial institution GitHub orgs",
        "weight": 0.25,
    },
    "capability_gap_filler": {
        "description": "Solves a problem not currently commercialized",
        "weight": 0.20,
    },
    "developer_community_growth": {
        "description": ">10 new contributors in last 30 days",
        "weight": 0.15,
    },
    "vc_backed_org_interest": {
        "description": "Stars/forks from known VC-backed fintech orgs",
        "weight": 0.20,
    },
}

# Organizations that signal enterprise/VC interest when they contribute
ENTERPRISE_ORG_PATTERNS = [
    "jpmorgan", "goldman", "citi", "stripe", "square", "paypal",
    "visa", "mastercard", "fidelity", "blackrock", "two-sigma",
    "bridgewater", "citadel", "jane-street", "virtu", "iex",
    "a16z", "sequoia", "accel", "andreessen",
]


class DisruptionPredictionAgent(BaseAgent):
    """Agent 8 + 9: Predicts disruption probability and startup opportunity signals."""

    def __init__(self, **kwargs):
        super().__init__(name="DisruptionPredictionAgent", **kwargs)
        self._model = DisruptionScoringModel()

    async def _run(self, result: AgentResult) -> AgentResult:
        repos = await self._fetch_repos_for_prediction()
        result.items_processed = len(repos)

        scored = 0
        high_disruption = []
        high_startup = []

        for repo in repos:
            try:
                disruption_score, startup_score = await self._score_repo(repo)
                scored += 1

                if disruption_score >= 70:
                    high_disruption.append((repo["id"], disruption_score))
                if startup_score >= 65:
                    high_startup.append((repo["id"], startup_score))

            except Exception as exc:
                result.errors.append(f"{repo['id']}: {exc}")

        result.items_updated = scored

        if high_disruption:
            result.insights.append(
                f"High disruption potential (≥70): {len(high_disruption)} repos — "
                f"top: {high_disruption[0][0]} ({high_disruption[0][1]:.1f})"
            )
        if high_startup:
            result.insights.append(
                f"Strong startup signals (≥65): {len(high_startup)} repos"
            )

        return result

    async def _fetch_repos_for_prediction(self) -> List[Dict]:
        return await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.primary_sector IS NOT NULL
              AND r.stars >= 50
              AND (r.disruption_score IS NULL
                   OR r.last_prediction_at IS NULL
                   OR r.last_prediction_at < datetime() - duration({days: 7}))
            OPTIONAL MATCH (r)<-[:DEPENDS_ON]-(dep:Repository)
            RETURN r.id AS id,
                   r.stars AS stars,
                   r.forks AS forks,
                   r.open_issues AS open_issues,
                   r.contributors_count AS contributors,
                   r.fintech_domains AS domains,
                   r.regulatory_relevance_score AS regulatory_relevance,
                   r.classification_confidence AS confidence,
                   count(dep) AS dependent_count
            ORDER BY r.stars DESC
            LIMIT 5000
        """)

    async def _score_repo(self, repo: Dict) -> Tuple[float, float]:
        repo_id = repo["id"]
        stars = repo.get("stars") or 0
        forks = repo.get("forks") or 0
        contributors = repo.get("contributors") or 0
        dependent_count = repo.get("dependent_count") or 0
        regulatory_relevance = (repo.get("regulatory_relevance") or 0) / 100.0
        domains = repo.get("domains") or []

        # Build features
        features = DisruptionFeatures(
            star_growth_30d=self._estimate_growth_rate(stars),
            fork_growth_30d=self._estimate_growth_rate(forks),
            contributor_growth_30d=self._estimate_contributor_growth(contributors),
            commit_frequency=self._estimate_commit_freq(repo),
            dependent_repo_count=dependent_count,
            reverse_dependency_depth=min(int(math.log1p(dependent_count)), 5),
            cross_sector_adoption=len(domains),
            tech_novelty_score=self._estimate_novelty(repo),
            regulatory_alignment=regulatory_relevance,
            protocol_standard_potential=self._estimate_standard_potential(repo),
            enterprise_contributor_ratio=self._estimate_enterprise_ratio(repo),
            issue_resolution_velocity=self._estimate_issue_velocity(repo),
            documentation_quality=0.5,  # default until readme scoring is implemented
        )

        disruption_prob = self._model.predict(features)
        disruption_score = disruption_prob * 100

        startup_score = self._compute_startup_score(features, stars, forks)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.disruption_score      = $disruption_score,
                r.startup_score         = $startup_score,
                r.infra_probability     = $infra_prob,
                r.last_prediction_at    = datetime($now)
        """, {
            "id": repo_id,
            "disruption_score": round(disruption_score, 2),
            "startup_score": round(startup_score, 2),
            "infra_prob": round(disruption_prob, 4),
            "now": now,
        })

        return disruption_score, startup_score

    # ── Feature estimation helpers ────────────────────────────────────────────

    def _estimate_growth_rate(self, current_count: int) -> float:
        """Estimate monthly growth rate from current count (log-scale proxy)."""
        return min(math.log1p(current_count) / 10.0, 5.0)

    def _estimate_contributor_growth(self, contributors: int) -> float:
        return min(math.log1p(contributors) / 8.0, 2.0)

    def _estimate_commit_freq(self, repo: Dict) -> float:
        return min(math.log1p(repo.get("stars", 0)) * 2, 50.0)

    def _estimate_novelty(self, repo: Dict) -> float:
        domains = repo.get("domains") or []
        novel_domains = {"blockchain_defi", "zero_knowledge_proofs", "cbdc",
                         "federated_learning", "homomorphic_encryption"}
        novel_count = sum(1 for d in domains if d in novel_domains)
        return min(novel_count * 0.3, 1.0)

    def _estimate_standard_potential(self, repo: Dict) -> float:
        domains = repo.get("domains") or []
        standard_prone = {"payments", "messaging", "identity"}
        return 0.8 if any(d in standard_prone for d in domains) else 0.2

    def _estimate_enterprise_ratio(self, repo: Dict) -> float:
        return 0.3  # placeholder until contributor org analysis is implemented

    def _estimate_issue_velocity(self, repo: Dict) -> float:
        issues = repo.get("open_issues") or 0
        stars = max(repo.get("stars") or 1, 1)
        return min((stars / max(issues, 1)) * 0.5, 20.0)

    def _compute_startup_score(
        self, features: DisruptionFeatures, stars: int, forks: int
    ) -> float:
        """Startup opportunity = novel technology + community growth + low market saturation."""
        novelty_component = features.tech_novelty_score * 30
        growth_component = min(math.log1p(stars) * 3, 25)
        community_component = min(features.contributor_growth_30d * 10, 20)
        enterprise_signal = features.enterprise_contributor_ratio * 25

        raw = novelty_component + growth_component + community_component + enterprise_signal
        return min(raw, 100.0)
