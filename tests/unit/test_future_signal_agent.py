"""
Unit tests — FutureSignalAgent (Agent 11)
==========================================
Tests the pure-Python trajectory computation — no Neo4j needed.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from ai_agents.signals.future_signal_agent import (
    ScoreSnapshot,
    TrajectoryProfile,
    fit_linear_trajectory,
    classify_trajectory,
    predict_score,
    build_trajectory_profile,
    BREAKOUT_SLOPE,
    ACCELERATING_SLOPE,
    PREDICTION_CAP,
    MIN_SNAPSHOTS_FOR_TREND,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_snapshots(scores: list, weeks_apart: int = 1) -> list:
    """Build snapshot dicts spaced `weeks_apart` apart."""
    base = datetime(2025, 9, 1, tzinfo=timezone.utc)
    snapshots = []
    for i, score in enumerate(scores):
        ts = base + timedelta(weeks=i * weeks_apart)
        snapshots.append({
            "captured_at": ts.isoformat(),
            "score":       float(score),
        })
    return snapshots


# ── fit_linear_trajectory ─────────────────────────────────────────────────────

class TestFitLinearTrajectory:
    def test_perfect_linear_increase(self):
        # Score +5 per week: 10, 15, 20, 25, 30
        snaps = _make_snapshots([10, 15, 20, 25, 30])
        ts    = [s["captured_at"] for s in snaps]
        ys    = [s["score"]       for s in snaps]
        slope, intercept, r_sq = fit_linear_trajectory(ts, ys)
        assert abs(slope - 5.0) < 0.1
        assert r_sq >= 0.99

    def test_perfect_flat_line(self):
        snaps = _make_snapshots([50, 50, 50, 50, 50])
        ts    = [s["captured_at"] for s in snaps]
        ys    = [s["score"]       for s in snaps]
        slope, _, r_sq = fit_linear_trajectory(ts, ys)
        assert abs(slope) < 0.01
        assert r_sq >= 0.99  # perfect flat = perfect fit

    def test_declining_score(self):
        snaps = _make_snapshots([80, 74, 68, 62, 56])  # -6/week
        ts    = [s["captured_at"] for s in snaps]
        ys    = [s["score"]       for s in snaps]
        slope, _, r_sq = fit_linear_trajectory(ts, ys)
        assert slope < 0
        assert abs(slope - (-6.0)) < 0.1

    def test_two_points_returns_slope(self):
        snaps = _make_snapshots([40, 60])   # +20 pts in 1 week
        ts    = [s["captured_at"] for s in snaps]
        ys    = [s["score"]       for s in snaps]
        slope, _, _ = fit_linear_trajectory(ts, ys)
        assert slope > 0

    def test_single_point_returns_zero_slope(self):
        ts    = [datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()]
        ys    = [55.0]
        slope, intercept, r_sq = fit_linear_trajectory(ts, ys)
        assert slope == 0.0
        assert intercept == 55.0

    def test_noisy_but_trending_up(self):
        # Noisy increasing series
        snaps = _make_snapshots([30, 38, 35, 44, 40, 50, 48, 58])
        ts    = [s["captured_at"] for s in snaps]
        ys    = [s["score"]       for s in snaps]
        slope, _, r_sq = fit_linear_trajectory(ts, ys)
        assert slope > 0, "Noisy but upward-trending should have positive slope"
        assert r_sq >= 0.80, "Should fit reasonably well"


# ── classify_trajectory ───────────────────────────────────────────────────────

class TestClassifyTrajectory:
    def test_breakout(self):
        assert classify_trajectory(BREAKOUT_SLOPE + 1) == "BREAKOUT"
        assert classify_trajectory(BREAKOUT_SLOPE)     == "BREAKOUT"

    def test_accelerating(self):
        assert classify_trajectory(ACCELERATING_SLOPE + 0.5) == "ACCELERATING"

    def test_stable_upper_bound(self):
        assert classify_trajectory(1.0) == "STABLE"

    def test_stable_lower_bound(self):
        assert classify_trajectory(-0.5) == "STABLE"

    def test_decelerating(self):
        assert classify_trajectory(-2.0) == "DECELERATING"

    def test_stalling(self):
        assert classify_trajectory(-5.0) == "STALLING"


# ── predict_score ─────────────────────────────────────────────────────────────

class TestPredictScore:
    def test_30_day_prediction_with_positive_slope(self):
        predicted = predict_score(current_score=60.0, slope_per_week=2.0, days_ahead=30)
        # 30 days ≈ 4.3 weeks → 60 + 2 * 4.3 ≈ 68.6
        assert 68 <= predicted <= 70

    def test_prediction_capped_at_100(self):
        assert predict_score(95.0, 5.0, 90) == PREDICTION_CAP

    def test_prediction_floored_at_0(self):
        assert predict_score(5.0, -5.0, 90) == 0.0

    def test_zero_slope_gives_current_score(self):
        assert predict_score(72.5, 0.0, 180) == 72.5


# ── build_trajectory_profile ──────────────────────────────────────────────────

class TestBuildTrajectoryProfile:
    def test_returns_none_with_too_few_snapshots(self):
        snaps = _make_snapshots([50, 60])  # only 2, need MIN_SNAPSHOTS_FOR_TREND
        assert build_trajectory_profile("repo:test", snaps) is None

    def test_breakout_detected(self):
        # +7 pts/week = well above BREAKOUT_SLOPE of 5
        snaps = _make_snapshots([20, 27, 34, 41, 48, 55])
        profile = build_trajectory_profile("repo:test", snaps)
        assert profile is not None
        assert profile.trajectory_class == "BREAKOUT"
        assert profile.trajectory_alert is True

    def test_stable_repo(self):
        snaps = _make_snapshots([55, 55.5, 54.5, 55, 55.5, 55])
        profile = build_trajectory_profile("repo:test", snaps)
        assert profile is not None
        assert profile.trajectory_class == "STABLE"
        assert profile.trajectory_alert is False

    def test_stalling_repo(self):
        snaps = _make_snapshots([80, 75, 70, 65, 60, 55])   # -5/week
        profile = build_trajectory_profile("repo:test", snaps)
        assert profile is not None
        assert profile.trajectory_class in ("DECELERATING", "STALLING")

    def test_predictions_are_forward_looking(self):
        snaps = _make_snapshots([40, 45, 50, 55, 60])  # +5/week
        profile = build_trajectory_profile("repo:test", snaps)
        assert profile.predicted_score_30d  > profile.current_score
        assert profile.predicted_score_90d  > profile.predicted_score_30d
        assert profile.predicted_score_180d >= profile.predicted_score_90d

    def test_momentum_label_is_populated(self):
        snaps = _make_snapshots([20, 27, 34, 41, 48, 55])
        profile = build_trajectory_profile("repo:test", snaps)
        assert len(profile.momentum_label) > 0
        assert "🚀" in profile.momentum_label  # BREAKOUT label

    def test_r_squared_bounded(self):
        snaps = _make_snapshots([50, 55, 60, 65, 70])
        profile = build_trajectory_profile("repo:test", snaps)
        assert 0.0 <= profile.r_squared <= 1.0

    def test_score_delta_is_zero_without_history(self):
        # All snapshots within recent period — no 30/90 day history
        snaps = _make_snapshots([50, 55, 60, 65, 70])
        profile = build_trajectory_profile("repo:test", snaps)
        # score_delta should be 0 when no snapshot is older than 30 days
        assert isinstance(profile.score_delta_30d, float)
        assert isinstance(profile.score_delta_90d, float)
