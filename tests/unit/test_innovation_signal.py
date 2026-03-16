"""
Unit tests for the InnovationSignalAgent helpers.
"""

import pytest
from ai_agents.signals.innovation_signal_agent import (
    _compute_pre_viral_score,
    _compute_cross_pollination,
    _compute_regulatory_anticipation,
    _compute_velocity_signal,
    _composite_iss,
    VelocitySignal,
    InnovationSignalProfile,
)


class TestPreViralScore:
    def test_zero_age_returns_zero(self):
        score = _compute_pre_viral_score(stars=1000, age_days=0, contributors=50, forks=100)
        assert score == 0.0

    def test_young_repo_with_many_stars_scores_high(self):
        # 30 days old, 500 stars — very pre-viral
        score = _compute_pre_viral_score(stars=500, age_days=30, contributors=20, forks=50)
        assert score > 50.0

    def test_old_repo_with_same_stars_scores_lower(self):
        young = _compute_pre_viral_score(stars=500, age_days=30, contributors=20, forks=50)
        old = _compute_pre_viral_score(stars=500, age_days=1825, contributors=20, forks=50)
        assert young > old

    def test_score_bounded_0_to_100(self):
        score = _compute_pre_viral_score(stars=999999, age_days=1, contributors=10000, forks=50000)
        assert 0.0 <= score <= 100.0

    def test_zero_engagement_scores_zero(self):
        score = _compute_pre_viral_score(stars=0, age_days=365, contributors=0, forks=0)
        assert score == 0.0


class TestCrossPollination:
    def test_zk_proof_in_compliance_context(self):
        topics = ["zero_knowledge", "zkp"]
        domains = ["kyc", "compliance"]
        score = _compute_cross_pollination(topics, domains)
        assert score > 0.0

    def test_no_overlap_scores_zero(self):
        topics = ["webserver", "database", "orm"]
        domains = ["web", "backend"]
        score = _compute_cross_pollination(topics, domains)
        assert score == 0.0

    def test_federated_learning_fraud_detection(self):
        topics = ["federated_learning", "privacy"]
        domains = ["fraud_detection", "anti_money_laundering"]
        score = _compute_cross_pollination(topics, domains)
        assert score > 0.0

    def test_score_bounded_0_to_1(self):
        topics = ["zero_knowledge", "zkp", "federated_learning", "homomorphic_encryption",
                  "blockchain", "smart_contracts", "cbdc", "llm"]
        domains = ["kyc", "compliance", "banking", "fraud_detection", "payments",
                   "credit_scoring", "trade_finance", "regulatory_reporting"]
        score = _compute_cross_pollination(topics, domains)
        assert 0.0 <= score <= 1.0


class TestRegulatoryAnticipation:
    def test_dora_keywords_detected(self):
        description = "Digital operational resilience framework for financial services"
        score, tags = _compute_regulatory_anticipation(description, [], "")
        assert score > 0.0
        assert "dora" in tags

    def test_eu_ai_act_detected(self):
        description = "High risk AI system compliance toolkit"
        score, tags = _compute_regulatory_anticipation(description, [], "")
        assert score > 0.0
        assert "eu_ai_act" in tags

    def test_t1_settlement_detected(self):
        readme = "Accelerated settlement T+1 support for US equity markets"
        score, tags = _compute_regulatory_anticipation("", [], readme)
        assert "t1_settlement" in tags

    def test_no_regulatory_content_scores_zero(self):
        description = "A simple web scraper for news sites"
        score, tags = _compute_regulatory_anticipation(description, [], "")
        assert score == 0.0
        assert tags == []

    def test_returns_tuple(self):
        result = _compute_regulatory_anticipation("test", [], "")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestVelocitySignal:
    def test_growth_rate_calculation(self):
        signal = VelocitySignal(metric="stars", current_value=200, baseline_value=100)
        assert signal.growth_rate == pytest.approx(1.0)

    def test_zero_baseline_handled(self):
        signal = VelocitySignal(metric="stars", current_value=50, baseline_value=0)
        assert signal.growth_rate > 0

    def test_inflection_at_100_percent_growth(self):
        signal = VelocitySignal(metric="stars", current_value=200, baseline_value=100)
        assert signal.is_inflection is True

    def test_no_inflection_below_100_percent(self):
        signal = VelocitySignal(metric="stars", current_value=150, baseline_value=100)
        assert signal.is_inflection is False

    def test_no_growth_is_not_inflection(self):
        signal = VelocitySignal(metric="stars", current_value=100, baseline_value=100)
        assert signal.is_inflection is False


class TestCompositeISS:
    def test_empty_profile_scores_near_zero(self):
        profile = InnovationSignalProfile(repo_id="test", repo_full_name="test/repo")
        score = _composite_iss(profile)
        assert score >= 0.0
        assert score < 20.0

    def test_inflection_drives_high_score(self):
        profile = InnovationSignalProfile(
            repo_id="test",
            repo_full_name="test/repo",
            star_velocity=VelocitySignal("stars", 2000, 100),  # 19x growth
            pre_viral_score=80.0,
            cross_pollination_score=0.5,
        )
        score = _composite_iss(profile)
        assert score > 30.0

    def test_score_bounded_0_to_100(self):
        profile = InnovationSignalProfile(
            repo_id="test",
            repo_full_name="test/repo",
            star_velocity=VelocitySignal("stars", 99999, 1),
            pre_viral_score=100.0,
            cross_pollination_score=1.0,
            regulatory_anticipation_score=1.0,
            enterprise_discovery_score=1.0,
        )
        score = _composite_iss(profile)
        assert 0.0 <= score <= 100.0
