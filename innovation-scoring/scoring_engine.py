"""
Innovation Scoring Engine

Computes 8-dimensional innovation scores for each repository:

1. Git Impression Score       — raw community traction
2. Innovation Velocity Score  — rate of change, momentum
3. Technology Maturity Score  — stability and production-readiness
4. Ecosystem Influence Score  — dependency network reach
5. Financial Sector Relevance — relevance to financial services
6. Institutional Adoption     — signals of enterprise/bank uptake
7. Startup Opportunity Score  — commercialization potential
8. Disruption Potential Score — probability of becoming infrastructure
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Score normalization bounds ────────────────────────────────────────────────
# Tuned against the distribution of the top 100k GitHub repos

STAR_BOUNDS = (10, 50000)
FORK_RATIO_BOUNDS = (0.0, 0.5)        # forks/stars
CONTRIBUTOR_BOUNDS = (1, 500)
COMMIT_FREQ_BOUNDS = (0.1, 50.0)       # commits/week
ISSUE_RESOLUTION_BOUNDS = (0.0, 1.0)  # closed/(closed+open)
AGE_MONTHS_BOUNDS = (1, 60)


@dataclass
class InnovationScores:
    """Full 8-dimensional score vector for a repository."""

    git_impression: float = 0.0
    innovation_velocity: float = 0.0
    technology_maturity: float = 0.0
    ecosystem_influence: float = 0.0
    sector_relevance: float = 0.0
    adoption_potential: float = 0.0
    startup_opportunity: float = 0.0
    disruption_potential: float = 0.0

    # Composite
    overall_innovation_score: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "git_impression_score": round(self.git_impression, 2),
            "velocity_score": round(self.innovation_velocity, 2),
            "maturity_score": round(self.technology_maturity, 2),
            "ecosystem_score": round(self.ecosystem_influence, 2),
            "sector_relevance_score": round(self.sector_relevance, 2),
            "adoption_potential": round(self.adoption_potential, 2),
            "startup_score": round(self.startup_opportunity, 2),
            "disruption_score": round(self.disruption_potential, 2),
            "innovation_score": round(self.overall_innovation_score, 2),
        }


# ── Composite score weights ───────────────────────────────────────────────────

COMPOSITE_WEIGHTS: Dict[str, float] = {
    "git_impression": 0.10,
    "innovation_velocity": 0.20,
    "technology_maturity": 0.10,
    "ecosystem_influence": 0.18,
    "sector_relevance": 0.17,
    "adoption_potential": 0.12,
    "startup_opportunity": 0.06,
    "disruption_potential": 0.07,
}


class InnovationScoringEngine:
    """
    Stateless scoring engine. Call score(repo_data) for a normalized
    8-dimensional score vector and composite score.
    """

    def score(self, repo: Dict) -> InnovationScores:
        """Compute full innovation score for one repository record."""
        s = InnovationScores()
        s.git_impression = self._git_impression(repo)
        s.innovation_velocity = self._innovation_velocity(repo)
        s.technology_maturity = self._technology_maturity(repo)
        s.ecosystem_influence = self._ecosystem_influence(repo)
        s.sector_relevance = self._sector_relevance(repo)
        s.adoption_potential = self._adoption_potential(repo)
        s.startup_opportunity = repo.get("startup_score") or 0.0
        s.disruption_potential = repo.get("disruption_score") or 0.0

        s.overall_innovation_score = sum(
            getattr(s, dim) * weight
            for dim, weight in COMPOSITE_WEIGHTS.items()
        )
        return s

    # ── Dimension 1: Git Impression Score ────────────────────────────────────

    def _git_impression(self, repo: Dict) -> float:
        """Raw community traction: stars, forks, watchers, contributors."""
        stars = repo.get("stars") or 0
        forks = repo.get("forks") or 0
        contributors = repo.get("contributors_count") or 0

        star_score = self._log_normalize(stars, *STAR_BOUNDS) * 50
        fork_score = min(forks / max(stars, 1), 0.5) / 0.5 * 25
        contrib_score = self._log_normalize(contributors, *CONTRIBUTOR_BOUNDS) * 25

        return min(star_score + fork_score + contrib_score, 100.0)

    # ── Dimension 2: Innovation Velocity Score ────────────────────────────────

    def _innovation_velocity(self, repo: Dict) -> float:
        """Rate of change: recent commits, issue activity, age-adjusted growth."""
        stars = repo.get("stars") or 0
        age_months = repo.get("age_months") or 12
        commits = repo.get("commits_count") or 0
        open_issues = repo.get("open_issues") or 0

        # Growth rate: stars per month
        monthly_star_rate = stars / max(age_months, 1)
        velocity_star = self._log_normalize(monthly_star_rate, 1, 5000) * 40

        # Commit velocity
        commit_freq = commits / max(age_months * 4, 1)  # commits/week
        velocity_commit = self._log_normalize(commit_freq, *COMMIT_FREQ_BOUNDS) * 35

        # Issue activity (proxy for community engagement)
        issue_score = self._log_normalize(open_issues, 0, 500) * 25

        return min(velocity_star + velocity_commit + issue_score, 100.0)

    # ── Dimension 3: Technology Maturity Score ────────────────────────────────

    def _technology_maturity(self, repo: Dict) -> float:
        """Stability, test coverage signals, documentation, license."""
        age_months = repo.get("age_months") or 0
        has_license = bool(repo.get("license"))
        contributors = repo.get("contributors_count") or 0
        is_archived = repo.get("is_archived") or False

        if is_archived:
            return 20.0  # archived = abandoned, low maturity

        # Age component (sweet spot: 12-36 months)
        age_score = 0
        if 6 <= age_months <= 48:
            age_score = 35 * (1 - abs(age_months - 24) / 24)
        elif age_months > 48:
            age_score = 25  # older but still active

        license_score = 20 if has_license else 0
        contrib_score = self._log_normalize(contributors, 1, 100) * 30
        readme_score = 15 if (repo.get("readme_snippet") or "") else 0

        return min(age_score + license_score + contrib_score + readme_score, 100.0)

    # ── Dimension 4: Ecosystem Influence Score ────────────────────────────────

    def _ecosystem_influence(self, repo: Dict) -> float:
        """Dependency network reach and cross-repo influence."""
        dependent_count = repo.get("dependent_count") or 0
        stars = repo.get("stars") or 0
        forks = repo.get("forks") or 0

        # Downstream dependencies are the strongest signal
        dep_score = self._log_normalize(dependent_count, 0, 1000) * 55

        # Stars from fork ratio (high forks = widely adapted)
        fork_ratio = forks / max(stars, 1)
        fork_score = min(fork_ratio / 0.5, 1.0) * 25

        # Organization backing
        org_score = 20 if repo.get("is_org_backed") else 10

        return min(dep_score + fork_score + org_score, 100.0)

    # ── Dimension 5: Financial Sector Relevance ───────────────────────────────

    def _sector_relevance(self, repo: Dict) -> float:
        """How relevant is this to financial services?"""
        domains = repo.get("fintech_domains") or []
        classification_confidence = repo.get("classification_confidence") or 0.0
        regulatory_relevance = repo.get("regulatory_relevance_score") or 0.0

        # High-value sectors get bonus
        HIGH_VALUE_SECTORS = {
            "payments", "trading", "risk_management", "aml_compliance",
            "digital_identity", "regtech",
        }
        sector_bonus = sum(15 for d in domains if d in HIGH_VALUE_SECTORS)

        confidence_score = classification_confidence * 40
        reg_score = regulatory_relevance * 0.3

        return min(confidence_score + min(sector_bonus, 40) + reg_score, 100.0)

    # ── Dimension 6: Institutional Adoption Potential ─────────────────────────

    def _adoption_potential(self, repo: Dict) -> float:
        """How likely are financial institutions to adopt this?"""
        has_license = bool(repo.get("license"))
        license = repo.get("license") or ""
        language = repo.get("language") or ""
        maturity_level = repo.get("tech_maturity_level") or "unknown"

        # License permissiveness
        PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"}
        license_score = 35 if license in PERMISSIVE_LICENSES else (20 if has_license else 5)

        # Language preference (Java, Python, C++ preferred in finance)
        ENTERPRISE_LANGS = {"Java", "Python", "C++", "C#", "TypeScript", "Kotlin", "Scala"}
        lang_score = 25 if language in ENTERPRISE_LANGS else 10

        maturity_map = {"mature": 40, "growing": 30, "emerging": 15, "legacy": 20}
        maturity_score = maturity_map.get(maturity_level, 20)

        return min(license_score + lang_score + maturity_score, 100.0)

    # ── Utility ────────────────────────────────────────────────────────────────

    @staticmethod
    def _log_normalize(value: float, min_val: float, max_val: float) -> float:
        """Normalize value to [0, 1] using log scale."""
        if value <= min_val:
            return 0.0
        if value >= max_val:
            return 1.0
        log_val = math.log1p(value - min_val)
        log_max = math.log1p(max_val - min_val)
        return log_val / log_max


# ── Scoring Pipeline (batch Neo4j updater) ────────────────────────────────────

class InnovationScoringPipeline:
    """
    Fetches unscored repositories from Neo4j and applies the scoring engine.
    Designed to run inside the Weekly Intelligence pipeline.
    """

    def __init__(self, engine: Optional[InnovationScoringEngine] = None):
        self.engine = engine or InnovationScoringEngine()

    def score_batch(self, repos: List[Dict]) -> List[Tuple[str, Dict]]:
        """Return list of (repo_id, scores_dict) tuples."""
        results = []
        for repo in repos:
            try:
                scores = self.engine.score(repo)
                results.append((repo["id"], scores.to_dict()))
            except Exception as exc:
                logger.warning("Scoring failed for %s: %s", repo.get("id"), exc)
        return results
