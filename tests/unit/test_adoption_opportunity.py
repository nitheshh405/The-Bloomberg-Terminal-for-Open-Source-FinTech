"""
Unit tests for the AdoptionOpportunityAgent scoring helpers.
"""

import pytest
from ai_agents.adoption.adoption_opportunity_agent import (
    AdoptionReadinessScores,
    _score_technical_maturity,
    _score_compliance_fit,
    _score_license,
    _score_integration_ease,
    _score_market_validation,
    _score_support_ecosystem,
    SECTOR_TECHNOLOGY_AFFINITY,
)


@pytest.fixture
def mature_repo():
    return {
        "stars": 8000,
        "forks": 1200,
        "open_issues": 30,
        "is_archived": False,
        "has_tests": True,
        "has_ci": True,
        "has_docs": True,
        "has_api_docs": True,
        "has_sdk": True,
        "release_count": 42,
        "license": "apache-2.0",
        "contributors_count": 85,
        "language": "python",
        "fintech_domains": ["payments", "open_banking"],
        "regulatory_relevance_score": 72,
    }


@pytest.fixture
def early_stage_repo():
    return {
        "stars": 45,
        "forks": 5,
        "open_issues": 12,
        "is_archived": False,
        "has_tests": False,
        "has_ci": False,
        "has_docs": False,
        "has_api_docs": False,
        "has_sdk": False,
        "release_count": 0,
        "license": "",
        "contributors_count": 1,
        "language": "python",
        "fintech_domains": [],
        "regulatory_relevance_score": 0,
    }


class TestAdoptionReadinessScores:
    def test_composite_computed_correctly(self):
        scores = AdoptionReadinessScores(
            technical_maturity=80.0,
            compliance_fit=70.0,
            integration_ease=75.0,
            support_ecosystem=65.0,
            license_permissiveness=100.0,
            market_validation=60.0,
        )
        composite = scores.compute_composite()
        assert composite > 0.0
        assert composite <= 100.0

    def test_all_zeros_gives_zero_composite(self):
        scores = AdoptionReadinessScores()
        composite = scores.compute_composite()
        assert composite == 0.0

    def test_adoption_stage_mainstream(self):
        scores = AdoptionReadinessScores(
            technical_maturity=90.0,
            compliance_fit=85.0,
            integration_ease=88.0,
            support_ecosystem=80.0,
            license_permissiveness=100.0,
            market_validation=75.0,
        )
        scores.compute_composite()
        assert scores.adoption_stage == "mainstream"

    def test_adoption_stage_experimental(self):
        scores = AdoptionReadinessScores(
            technical_maturity=15.0,
            compliance_fit=10.0,
            integration_ease=5.0,
            support_ecosystem=5.0,
            license_permissiveness=40.0,
            market_validation=5.0,
        )
        scores.compute_composite()
        assert scores.adoption_stage == "experimental"

    def test_weights_sum_to_one(self):
        total = sum(AdoptionReadinessScores.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestTechnicalMaturity:
    def test_mature_repo_scores_high(self, mature_repo):
        score, gaps = _score_technical_maturity(mature_repo)
        assert score >= 60.0
        assert len(gaps) == 0

    def test_early_stage_scores_low(self, early_stage_repo):
        score, gaps = _score_technical_maturity(early_stage_repo)
        assert score < 40.0
        assert len(gaps) > 0

    def test_archived_repo_scores_very_low(self):
        repo = {"is_archived": True, "stars": 5000, "forks": 1000}
        score, gaps = _score_technical_maturity(repo)
        assert score <= 10.0
        assert "archived_repository" in gaps

    def test_missing_tests_creates_gap(self):
        repo = {
            "stars": 1000, "forks": 100, "is_archived": False,
            "has_tests": False, "has_ci": True, "release_count": 5,
            "open_issues": 10,
        }
        _, gaps = _score_technical_maturity(repo)
        assert "no_automated_tests" in gaps

    def test_score_bounded_0_to_100(self, mature_repo):
        score, _ = _score_technical_maturity(mature_repo)
        assert 0.0 <= score <= 100.0


class TestComplianceFit:
    def test_payment_repo_in_payments_sector_scores_high(self):
        repo = {
            "regulatory_relevance_score": 80,
            "fintech_domains": ["payments", "open_banking"],
        }
        score, gaps = _score_compliance_fit(repo, "payments")
        assert score >= 40.0

    def test_irrelevant_repo_in_sector_scores_low(self):
        repo = {"regulatory_relevance_score": 5, "fintech_domains": []}
        score, gaps = _score_compliance_fit(repo, "capital_markets")
        assert score < 30.0
        assert len(gaps) > 0

    def test_score_bounded_0_to_100(self):
        repo = {"regulatory_relevance_score": 100, "fintech_domains": ["payments"]}
        score, _ = _score_compliance_fit(repo, "payments")
        assert 0.0 <= score <= 100.0


class TestLicenseScoring:
    def test_mit_scores_100(self):
        score, gaps = _score_license("mit")
        assert score == 100.0
        assert gaps == []

    def test_apache_scores_high(self):
        score, gaps = _score_license("apache-2.0")
        assert score >= 90.0

    def test_agpl_scores_low(self):
        score, gaps = _score_license("agpl-3.0")
        assert score <= 25.0
        assert len(gaps) > 0

    def test_gpl_enterprise_risk_flagged(self):
        score, gaps = _score_license("gpl-3.0")
        assert "copyleft_license_enterprise_risk" in gaps

    def test_empty_license_flags_missing(self):
        score, gaps = _score_license("")
        assert "no_license_specified" in gaps

    def test_bsd_scores_high(self):
        score, _ = _score_license("bsd-3-clause")
        assert score >= 90.0


class TestIntegrationEase:
    def test_fully_documented_repo_scores_high(self, mature_repo):
        score, gaps = _score_integration_ease(mature_repo)
        assert score >= 70.0
        assert len(gaps) == 0

    def test_undocumented_repo_has_gaps(self, early_stage_repo):
        score, gaps = _score_integration_ease(early_stage_repo)
        assert "missing_documentation" in gaps

    def test_score_bounded_0_to_100(self, mature_repo):
        score, _ = _score_integration_ease(mature_repo)
        assert 0.0 <= score <= 100.0


class TestMarketValidation:
    def test_zero_stars_scores_zero(self):
        score = _score_market_validation({"stars": 0, "forks": 0})
        assert score == 0.0

    def test_high_stars_scores_high(self):
        score = _score_market_validation({"stars": 10000, "forks": 2000})
        assert score >= 60.0

    def test_score_bounded_0_to_100(self):
        score = _score_market_validation({"stars": 999999, "forks": 999999})
        assert 0.0 <= score <= 100.0


class TestSectorAffinityMatrix:
    def test_all_major_sectors_present(self):
        expected = {"retail_banking", "investment_banking", "asset_management",
                    "insurance", "payments", "capital_markets", "compliance_regtech", "lending"}
        actual = set(SECTOR_TECHNOLOGY_AFFINITY.keys())
        assert expected.issubset(actual)

    def test_affinity_scores_bounded_0_to_1(self):
        for sector, affinities in SECTOR_TECHNOLOGY_AFFINITY.items():
            for tech, score in affinities.items():
                assert 0.0 <= score <= 1.0, \
                    f"Affinity {score} out of bounds for {sector}/{tech}"

    def test_payments_has_high_affinity_for_payments_tech(self):
        assert SECTOR_TECHNOLOGY_AFFINITY["payments"]["payments"] >= 0.9
