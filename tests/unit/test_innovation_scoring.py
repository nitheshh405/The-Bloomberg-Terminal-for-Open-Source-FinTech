"""
Unit tests for the Innovation Scoring Engine.
"""

import pytest
from innovation_scoring.scoring_engine import InnovationScoringEngine, InnovationScores


@pytest.fixture
def engine():
    return InnovationScoringEngine()


@pytest.fixture
def high_quality_repo():
    return {
        "id": "github:test/high-quality",
        "stars": 5000,
        "forks": 800,
        "watchers": 4200,
        "contributors_count": 85,
        "commits_last_year": 420,
        "commit_frequency_weekly": 8.0,
        "open_issues": 45,
        "days_since_release": 12,
        "release_count": 24,
        "dependent_repo_count": 310,
        "primary_sector": "payments",
        "fintech_domains": ["payments", "open_banking", "fraud_detection"],
        "innovation_signal_score": 72,
        "disruption_score": 0,
        "startup_score": 0,
        "has_tests": True,
        "has_ci": True,
        "has_docs": True,
        "regulatory_relevance_score": 68,
        "adoption_score": 74,
        "language": "python",
    }


@pytest.fixture
def low_quality_repo():
    return {
        "id": "github:test/low-quality",
        "stars": 12,
        "forks": 2,
        "watchers": 8,
        "contributors_count": 1,
        "commits_last_year": 10,
        "commit_frequency_weekly": 0.2,
        "open_issues": 45,
        "days_since_release": 730,
        "release_count": 0,
        "dependent_repo_count": 0,
        "primary_sector": None,
        "fintech_domains": [],
        "innovation_signal_score": 5,
        "disruption_score": 0,
        "startup_score": 0,
        "has_tests": False,
        "has_ci": False,
        "has_docs": False,
        "regulatory_relevance_score": 0,
        "adoption_score": 0,
        "language": "unknown",
    }


class TestInnovationScores:
    def test_scores_are_dataclass(self):
        scores = InnovationScores()
        assert hasattr(scores, "git_impression")
        assert hasattr(scores, "innovation_velocity")
        assert hasattr(scores, "technology_maturity")
        assert hasattr(scores, "ecosystem_influence")
        assert hasattr(scores, "sector_relevance")
        assert hasattr(scores, "adoption_potential")
        assert hasattr(scores, "startup_opportunity")
        assert hasattr(scores, "disruption_potential")
        assert hasattr(scores, "overall_innovation_score")

    def test_default_scores_are_zero(self):
        scores = InnovationScores()
        assert scores.overall_innovation_score == 0.0
        assert scores.git_impression == 0.0

    def test_composite_property(self):
        scores = InnovationScores(
            git_impression=80.0,
            innovation_velocity=70.0,
            technology_maturity=60.0,
            ecosystem_influence=75.0,
            sector_relevance=65.0,
            adoption_potential=70.0,
            startup_opportunity=55.0,
            disruption_potential=45.0,
        )
        # overall_innovation_score starts at 0 until engine.score() is called
        assert scores.git_impression == 80.0
        assert scores.innovation_velocity == 70.0


class TestInnovationScoringEngine:
    def test_engine_instantiates(self, engine):
        assert engine is not None

    def test_scores_high_quality_repo(self, engine, high_quality_repo):
        scores = engine.score(high_quality_repo)
        assert isinstance(scores, InnovationScores)
        # High quality repo should score meaningfully above a low-quality repo
        assert scores.overall_innovation_score >= 25.0
        assert scores.git_impression >= 40.0

    def test_scores_low_quality_repo(self, engine, low_quality_repo):
        scores = engine.score(low_quality_repo)
        assert isinstance(scores, InnovationScores)
        # Low quality repo should score below threshold
        assert scores.overall_innovation_score < 30.0

    def test_high_scores_higher_than_low(self, engine, high_quality_repo, low_quality_repo):
        high_scores = engine.score(high_quality_repo)
        low_scores = engine.score(low_quality_repo)
        assert high_scores.overall_innovation_score > low_scores.overall_innovation_score

    def test_all_scores_bounded_0_to_100(self, engine, high_quality_repo):
        scores = engine.score(high_quality_repo)
        for field_name in [
            "git_impression", "innovation_velocity", "technology_maturity",
            "ecosystem_influence", "sector_relevance", "adoption_potential",
            "startup_opportunity", "disruption_potential", "overall_innovation_score",
        ]:
            value = getattr(scores, field_name)
            assert 0.0 <= value <= 100.0, f"{field_name} out of bounds: {value}"

    def test_stars_drive_git_impression(self, engine):
        low_stars = {"stars": 10, "forks": 1, "watchers": 8}
        high_stars = {"stars": 10000, "forks": 2000, "watchers": 8000}
        base = {
            "contributors_count": 10, "commits_last_year": 100,
            "commit_frequency_weekly": 2.0, "open_issues": 10,
            "days_since_release": 30, "release_count": 5,
            "dependent_repo_count": 0, "primary_sector": "payments",
            "fintech_domains": ["payments"], "innovation_signal_score": 0,
            "disruption_score": 0, "startup_score": 0,
            "has_tests": False, "has_ci": False, "has_docs": False,
            "regulatory_relevance_score": 0, "adoption_score": 0, "language": "python",
        }
        score_low = engine.score({**base, **low_stars})
        score_high = engine.score({**base, **high_stars})
        assert score_high.git_impression > score_low.git_impression

    def test_missing_fields_do_not_raise(self, engine):
        minimal = {"id": "test", "stars": 100}
        scores = engine.score(minimal)
        assert isinstance(scores, InnovationScores)

    def test_sector_relevance_higher_with_domains(self, engine):
        no_domains = {
            "stars": 500, "forks": 50, "watchers": 400,
            "contributors_count": 10, "commits_last_year": 100,
            "commit_frequency_weekly": 2.0, "open_issues": 5,
            "days_since_release": 30, "release_count": 3,
            "dependent_repo_count": 0, "primary_sector": None,
            "fintech_domains": [], "innovation_signal_score": 0,
            "disruption_score": 0, "startup_score": 0,
            "has_tests": False, "has_ci": False, "has_docs": False,
            "regulatory_relevance_score": 0, "adoption_score": 0, "language": "python",
        }
        with_domains = {
            **no_domains,
            "primary_sector": "payments",
            "fintech_domains": ["payments", "open_banking", "fraud_detection"],
        }
        score_no = engine.score(no_domains)
        score_with = engine.score(with_domains)
        assert score_with.sector_relevance >= score_no.sector_relevance
