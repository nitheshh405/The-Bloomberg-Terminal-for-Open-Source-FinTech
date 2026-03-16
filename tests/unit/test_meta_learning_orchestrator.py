"""
Unit tests — MetaLearningOrchestrator
=======================================
Tests the pure-logic pieces — no Neo4j needed.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from ai_agents.orchestration.meta_learning_orchestrator import (
    Prediction,
    AgentAccuracyReport,
    WeightTuningResult,
    PredictionType,
    EVALUATION_HORIZON,
    evaluate_pre_viral,
    evaluate_breakout,
    evaluate_sandbox_entry,
    tune_weights,
    MetaLearningOrchestrator,
)


# ── Evaluation horizons ────────────────────────────────────────────────────────

class TestEvaluationHorizons:
    def test_all_prediction_types_have_horizons(self):
        for ptype in [
            PredictionType.PRE_VIRAL,
            PredictionType.REGULATORY_FOCUS,
            PredictionType.BREAKOUT,
            PredictionType.SANDBOX_ENTRY,
            PredictionType.ACQUISITION,
        ]:
            assert ptype in EVALUATION_HORIZON

    def test_breakout_is_shortest_horizon(self):
        """Breakout should evaluate fastest — 3 months."""
        assert EVALUATION_HORIZON[PredictionType.BREAKOUT].days == 90

    def test_pre_viral_is_6_months(self):
        assert EVALUATION_HORIZON[PredictionType.PRE_VIRAL].days == 180

    def test_regulatory_and_acquisition_are_12_months(self):
        assert EVALUATION_HORIZON[PredictionType.REGULATORY_FOCUS].days == 365
        assert EVALUATION_HORIZON[PredictionType.ACQUISITION].days == 365


# ── Outcome evaluators ─────────────────────────────────────────────────────────

class TestEvaluatePreViral:
    def _pred(self, threshold: float = 3.0) -> dict:
        return {"prediction_type": "PRE_VIRAL", "threshold": threshold}

    def test_3x_growth_is_true(self):
        outcome, ratio = evaluate_pre_viral(self._pred(), current_stars=3000, original_stars=1000)
        assert outcome == "TRUE"
        assert abs(ratio - 3.0) < 0.001

    def test_less_than_3x_is_false(self):
        outcome, ratio = evaluate_pre_viral(self._pred(), current_stars=2500, original_stars=1000)
        assert outcome == "FALSE"

    def test_zero_original_returns_false(self):
        outcome, _ = evaluate_pre_viral(self._pred(), current_stars=1000, original_stars=0)
        assert outcome == "FALSE"

    def test_custom_threshold(self):
        outcome, _ = evaluate_pre_viral(self._pred(2.0), current_stars=2100, original_stars=1000)
        assert outcome == "TRUE"


class TestEvaluateBreakout:
    def _pred(self) -> dict:
        return {"prediction_type": "BREAKOUT"}

    def test_breakout_class_is_true(self):
        outcome, value = evaluate_breakout(self._pred(), "BREAKOUT")
        assert outcome == "TRUE"
        assert value == 1.0

    def test_accelerating_is_false(self):
        outcome, _ = evaluate_breakout(self._pred(), "ACCELERATING")
        assert outcome == "FALSE"

    def test_none_is_false(self):
        outcome, _ = evaluate_breakout(self._pred(), None)
        assert outcome == "FALSE"


class TestEvaluateSandboxEntry:
    def _pred(self) -> dict:
        return {"prediction_type": "SANDBOX_ENTRY"}

    def test_participant_is_true(self):
        outcome, value = evaluate_sandbox_entry(self._pred(), sandbox_participant=True)
        assert outcome == "TRUE"
        assert value == 1.0

    def test_not_participant_is_false(self):
        outcome, value = evaluate_sandbox_entry(self._pred(), sandbox_participant=False)
        assert outcome == "FALSE"
        assert value == 0.0


# ── Weight tuning ─────────────────────────────────────────────────────────────

class TestTuneWeights:
    BASE_WEIGHTS = {
        "git_impression":      0.10,
        "velocity":            0.20,
        "technology_maturity": 0.10,
        "ecosystem_influence": 0.18,
        "sector_relevance":    0.17,
        "adoption_potential":  0.12,
        "startup_opportunity": 0.06,
        "disruption_potential": 0.07,
    }

    def _preds(self, count: int) -> list:
        return [{"predicted_value": 75.0}] * count

    def test_insufficient_data_returns_unchanged(self):
        new_weights, changes = tune_weights(self.BASE_WEIGHTS, self._preds(4), self._preds(4))
        assert "unchanged" in changes[0].lower()

    def test_high_accuracy_returns_similar_weights(self):
        # 80% accuracy → small nudge
        true_preds  = self._preds(16)
        false_preds = self._preds(4)
        new_weights, changes = tune_weights(self.BASE_WEIGHTS, true_preds, false_preds)
        for k in self.BASE_WEIGHTS:
            assert abs(new_weights[k] - self.BASE_WEIGHTS[k]) < 0.05

    def test_low_accuracy_boosts_velocity(self):
        # 30% accuracy → velocity should be boosted
        true_preds  = self._preds(3)
        false_preds = self._preds(7)
        new_weights, changes = tune_weights(self.BASE_WEIGHTS, true_preds, false_preds)
        if "velocity" in new_weights:
            assert new_weights["velocity"] >= self.BASE_WEIGHTS["velocity"]

    def test_returned_weights_sum_to_one(self):
        true_preds  = self._preds(8)
        false_preds = self._preds(5)
        new_weights, _ = tune_weights(self.BASE_WEIGHTS, true_preds, false_preds)
        total = sum(new_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_no_negative_weights(self):
        true_preds  = self._preds(2)
        false_preds = self._preds(18)  # very low accuracy
        new_weights, _ = tune_weights(self.BASE_WEIGHTS, true_preds, false_preds)
        for k, v in new_weights.items():
            assert v >= 0.0, f"Weight {k} is negative: {v}"


# ── AgentAccuracyReport ────────────────────────────────────────────────────────

class TestAgentAccuracyReport:
    def _report(self, total: int, true_count: int) -> AgentAccuracyReport:
        return AgentAccuracyReport(
            agent_id               = "future_signal_agent",
            prediction_type        = PredictionType.PRE_VIRAL,
            total_evaluated        = total,
            true_count             = true_count,
            false_count            = total - true_count,
            pending_count          = 0,
            accuracy               = true_count / total if total > 0 else 0.0,
            precision_at_high_conf = 0.0,
        )

    def test_accuracy_calculation(self):
        r = self._report(10, 7)
        assert abs(r.accuracy - 0.7) < 0.001

    def test_accuracy_zero_when_no_evaluations(self):
        r = self._report(0, 0)
        assert r.accuracy == 0.0


# ── Insight generation ────────────────────────────────────────────────────────

class TestInsightGeneration:
    def test_high_accuracy_positive_insight(self):
        insight = MetaLearningOrchestrator._generate_insight(
            "agent", "PRE_VIRAL", 0.85, 50
        )
        assert "reliable" in insight.lower() or "strong" in insight.lower()

    def test_low_accuracy_warning(self):
        insight = MetaLearningOrchestrator._generate_insight(
            "agent", "PRE_VIRAL", 0.25, 30
        )
        assert "below chance" in insight.lower() or "flagged" in insight.lower()

    def test_insufficient_data_message(self):
        insight = MetaLearningOrchestrator._generate_insight(
            "agent", "PRE_VIRAL", 0.80, 5   # only 5 predictions
        )
        assert "insufficient" in insight.lower() or "need" in insight.lower()

    def test_moderate_accuracy_nuanced_insight(self):
        insight = MetaLearningOrchestrator._generate_insight(
            "agent", "PRE_VIRAL", 0.65, 25
        )
        assert "moderate" in insight.lower() or "useful" in insight.lower()
