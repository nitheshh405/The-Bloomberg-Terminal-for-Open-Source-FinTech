"""
Agent 11 — FutureSignalAgent
==============================
Transforms the platform from a snapshot tool into a predictive intelligence platform.

Core insight: a repo moving 40 → 55 → 71 over 6 months is MORE valuable
than a static score of 75, because it signals accelerating adoption momentum.

What this agent does
─────────────────────
1. SNAPSHOT      — writes a timestamped score snapshot to Neo4j every run
2. TRAJECTORY    — fits a curve across all historical snapshots
3. PREDICT       — extrapolates 30/90/180-day score forecasts
4. CLASSIFY      — labels each repo: BREAKOUT / ACCELERATING / STABLE /
                   DECELERATING / STALLING
5. ALERT         — flags repos crossing trajectory thresholds
6. RANK          — produces a "Trajectory Leaderboard" (most momentum right now)

Neo4j model
────────────
  (Repository)-[:HAS_SCORE_SNAPSHOT]->(ScoreSnapshot {
      captured_at:             datetime,
      overall_innovation_score: float,
      git_impression:           float,
      innovation_velocity:      float,
      technology_maturity:      float,
      ecosystem_influence:      float,
      sector_relevance:         float,
      adoption_potential:       float,
      startup_opportunity:      float,
      disruption_potential:     float,
  })

  (Repository) properties updated by this agent:
      trajectory_class:      "BREAKOUT" | "ACCELERATING" | "STABLE" | ...
      trajectory_slope:      float   (score points per week)
      trajectory_r_squared:  float   (fit quality, 0–1)
      predicted_score_30d:   float
      predicted_score_90d:   float
      predicted_score_180d:  float
      trajectory_alert:      bool    (true when slope > ALERT_SLOPE_THRESHOLD)
      snapshots_count:       int
      first_snapshot_at:     datetime
      trajectory_updated_at: datetime
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Trajectory classification thresholds (score points / week) ───────────────
BREAKOUT_SLOPE     = 5.0   # +5 pts/week  = ~20 pts/month
ACCELERATING_SLOPE = 1.5   # +1.5 pts/week = ~6 pts/month
STABLE_BAND        = (-1.0, 1.5)
DECELERATING_SLOPE = -1.0  # losing momentum
STALLING_SLOPE     = -3.0  # serious decline

ALERT_SLOPE_THRESHOLD = BREAKOUT_SLOPE   # triggers trajectory_alert
MIN_SNAPSHOTS_FOR_TREND = 3              # need at least 3 points to fit a line
PREDICTION_CAP = 100.0                   # scores can't exceed 100

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ScoreSnapshot:
    """One timestamped score reading for a single repository."""
    repo_id:                 str
    captured_at:             datetime
    overall_innovation_score: float
    git_impression:          float = 0.0
    innovation_velocity:     float = 0.0
    technology_maturity:     float = 0.0
    ecosystem_influence:     float = 0.0
    sector_relevance:        float = 0.0
    adoption_potential:      float = 0.0
    startup_opportunity:     float = 0.0
    disruption_potential:    float = 0.0


@dataclass
class TrajectoryProfile:
    """Full trajectory analysis for a single repository."""
    repo_id:               str
    snapshots_count:       int
    slope_per_week:        float          # score points / week  (positive = growing)
    r_squared:             float          # how well the linear fit explains variance
    trajectory_class:      str            # BREAKOUT / ACCELERATING / STABLE / ...
    predicted_score_30d:   float
    predicted_score_90d:   float
    predicted_score_180d:  float
    trajectory_alert:      bool
    current_score:         float
    score_delta_30d:       float          # change from 30 days ago
    score_delta_90d:       float          # change from 90 days ago
    computed_at:           datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def momentum_label(self) -> str:
        """Human-readable momentum description for dashboard display."""
        if self.trajectory_class == "BREAKOUT":
            return f"🚀 Breakout (+{self.slope_per_week:.1f} pts/wk)"
        if self.trajectory_class == "ACCELERATING":
            return f"📈 Accelerating (+{self.slope_per_week:.1f} pts/wk)"
        if self.trajectory_class == "STABLE":
            return "→ Stable"
        if self.trajectory_class == "DECELERATING":
            return f"📉 Decelerating ({self.slope_per_week:.1f} pts/wk)"
        return f"⚠️  Stalling ({self.slope_per_week:.1f} pts/wk)"


# ── Cypher templates ──────────────────────────────────────────────────────────

_WRITE_SNAPSHOT = """
MATCH (r:Repository {id: $repo_id})
CREATE (s:ScoreSnapshot {
    id:                       $snapshot_id,
    captured_at:              datetime($captured_at),
    overall_innovation_score: $overall_innovation_score,
    git_impression:           $git_impression,
    innovation_velocity:      $innovation_velocity,
    technology_maturity:      $technology_maturity,
    ecosystem_influence:      $ecosystem_influence,
    sector_relevance:         $sector_relevance,
    adoption_potential:       $adoption_potential,
    startup_opportunity:      $startup_opportunity,
    disruption_potential:     $disruption_potential
})
MERGE (r)-[:HAS_SCORE_SNAPSHOT]->(s)
SET r.snapshots_count     = coalesce(r.snapshots_count, 0) + 1,
    r.last_snapshot_at    = datetime($captured_at)
RETURN s.id AS snapshot_id
"""

_GET_SNAPSHOTS = """
MATCH (r:Repository {id: $repo_id})-[:HAS_SCORE_SNAPSHOT]->(s:ScoreSnapshot)
RETURN
    s.captured_at              AS captured_at,
    s.overall_innovation_score AS score,
    s.git_impression           AS git_impression,
    s.innovation_velocity      AS innovation_velocity
ORDER BY s.captured_at ASC
"""

_GET_REPOS_WITH_ENOUGH_SNAPSHOTS = """
MATCH (r:Repository)
WHERE r.snapshots_count >= $min_snapshots
RETURN r.id AS repo_id, r.snapshots_count AS count
ORDER BY r.snapshots_count DESC
LIMIT $limit
"""

_UPDATE_TRAJECTORY = """
MATCH (r:Repository {id: $repo_id})
SET
    r.trajectory_class      = $trajectory_class,
    r.trajectory_slope      = $slope_per_week,
    r.trajectory_r_squared  = $r_squared,
    r.predicted_score_30d   = $predicted_score_30d,
    r.predicted_score_90d   = $predicted_score_90d,
    r.predicted_score_180d  = $predicted_score_180d,
    r.trajectory_alert      = $trajectory_alert,
    r.score_delta_30d       = $score_delta_30d,
    r.score_delta_90d       = $score_delta_90d,
    r.trajectory_updated_at = datetime()
RETURN r.id AS repo_id
"""

_TRAJECTORY_LEADERBOARD = """
MATCH (r:Repository)
WHERE r.trajectory_slope IS NOT NULL
  AND r.trajectory_class IN ['BREAKOUT', 'ACCELERATING']
RETURN
    r.id                   AS repo_id,
    r.full_name            AS full_name,
    r.overall_innovation_score AS current_score,
    r.trajectory_slope     AS slope_per_week,
    r.trajectory_class     AS trajectory_class,
    r.predicted_score_30d  AS predicted_30d,
    r.trajectory_alert     AS alert
ORDER BY r.trajectory_slope DESC
LIMIT $limit
"""


# ── Core scoring logic (pure Python — no external deps, fully testable) ───────

def fit_linear_trajectory(
    timestamps_iso: List[str],
    scores: List[float],
) -> Tuple[float, float, float]:
    """
    Fit a linear regression to (time, score) pairs.

    Returns:
        slope_per_week : score points gained per calendar week
        intercept      : y-intercept of the fitted line
        r_squared      : coefficient of determination (fit quality, 0–1)

    Uses only stdlib + basic arithmetic — no numpy/scipy required for the
    linear case, making the core algorithm dependency-free and unit-testable.
    """
    if len(scores) < 2:
        return 0.0, scores[0] if scores else 0.0, 0.0

    # Convert ISO timestamps to "weeks since first snapshot"
    t0 = datetime.fromisoformat(timestamps_iso[0].replace("Z", "+00:00"))
    weeks: List[float] = []
    for ts in timestamps_iso:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        weeks.append((t - t0).total_seconds() / (7 * 86400))

    n = len(weeks)
    mean_x = sum(weeks) / n
    mean_y = sum(scores) / n

    ss_xy = sum((weeks[i] - mean_x) * (scores[i] - mean_y) for i in range(n))
    ss_xx = sum((weeks[i] - mean_x) ** 2 for i in range(n))

    if ss_xx == 0:
        return 0.0, mean_y, 0.0

    slope     = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # R²
    ss_tot = sum((scores[i] - mean_y) ** 2 for i in range(n))
    if ss_tot == 0:
        return slope, intercept, 1.0
    ss_res = sum((scores[i] - (intercept + slope * weeks[i])) ** 2 for i in range(n))
    r_squared = max(0.0, 1.0 - ss_res / ss_tot)

    return slope, intercept, r_squared


def classify_trajectory(slope_per_week: float) -> str:
    """Map a slope value to a trajectory class label."""
    if slope_per_week >= BREAKOUT_SLOPE:
        return "BREAKOUT"
    if slope_per_week >= ACCELERATING_SLOPE:
        return "ACCELERATING"
    if STABLE_BAND[0] <= slope_per_week < STABLE_BAND[1]:
        return "STABLE"
    if slope_per_week >= STALLING_SLOPE:
        return "DECELERATING"
    return "STALLING"


def predict_score(
    current_score: float,
    slope_per_week: float,
    days_ahead: int,
) -> float:
    """Extrapolate score linearly, capped at PREDICTION_CAP."""
    weeks_ahead = days_ahead / 7.0
    predicted   = current_score + slope_per_week * weeks_ahead
    return round(min(max(predicted, 0.0), PREDICTION_CAP), 2)


def build_trajectory_profile(
    repo_id: str,
    snapshots: List[Dict[str, Any]],
) -> Optional[TrajectoryProfile]:
    """
    Given a list of snapshot dicts (from Neo4j), compute a full TrajectoryProfile.
    Returns None if there are fewer than MIN_SNAPSHOTS_FOR_TREND snapshots.
    """
    if len(snapshots) < MIN_SNAPSHOTS_FOR_TREND:
        return None

    timestamps = [str(s["captured_at"]) for s in snapshots]
    scores     = [float(s["score"]) for s in snapshots]

    slope, _, r_sq = fit_linear_trajectory(timestamps, scores)
    current        = scores[-1]

    # Delta vs 30 and 90 days ago
    now = datetime.now(timezone.utc)
    def _delta(days: int) -> float:
        cutoff = now - timedelta(days=days)
        older  = [
            float(s["score"])
            for s in snapshots
            if datetime.fromisoformat(
                str(s["captured_at"]).replace("Z", "+00:00")
            ) <= cutoff
        ]
        return round(current - older[-1], 2) if older else 0.0

    return TrajectoryProfile(
        repo_id             = repo_id,
        snapshots_count     = len(snapshots),
        slope_per_week      = round(slope, 4),
        r_squared           = round(r_sq, 4),
        trajectory_class    = classify_trajectory(slope),
        predicted_score_30d = predict_score(current, slope, 30),
        predicted_score_90d = predict_score(current, slope, 90),
        predicted_score_180d= predict_score(current, slope, 180),
        trajectory_alert    = slope >= ALERT_SLOPE_THRESHOLD,
        current_score       = current,
        score_delta_30d     = _delta(30),
        score_delta_90d     = _delta(90),
    )


# ── Agent class ───────────────────────────────────────────────────────────────

class FutureSignalAgent:
    """
    Agent 11: FutureSignalAgent

    Run this agent once per weekly intelligence cycle (after InnovationScoringEngine
    has computed fresh scores). It writes snapshots, fits trajectories, and
    updates every repository with forward-looking score predictions.

    Usage (standalone):
        agent = FutureSignalAgent(neo4j_driver)
        result = agent.run(batch_limit=5000)
        print(result.trajectory_leaderboard[:10])

    Usage (from Celery task):
        from ai_agents.signals.future_signal_agent import FutureSignalAgent
        FutureSignalAgent(driver).run()
    """

    agent_id   = "future_signal_agent"
    agent_name = "FutureSignalAgent"
    version    = "1.0.0"

    def __init__(self, neo4j_driver) -> None:
        self._driver = neo4j_driver

    # ── Public API ─────────────────────────────────────────────────────────────

    def snapshot_repo(self, snapshot: ScoreSnapshot) -> str:
        """Write a single score snapshot to Neo4j. Returns the snapshot node ID."""
        snapshot_id = str(uuid.uuid4())
        with self._driver.session() as session:
            session.run(
                _WRITE_SNAPSHOT,
                repo_id                  = snapshot.repo_id,
                snapshot_id              = snapshot_id,
                captured_at              = snapshot.captured_at.isoformat(),
                overall_innovation_score = snapshot.overall_innovation_score,
                git_impression           = snapshot.git_impression,
                innovation_velocity      = snapshot.innovation_velocity,
                technology_maturity      = snapshot.technology_maturity,
                ecosystem_influence      = snapshot.ecosystem_influence,
                sector_relevance         = snapshot.sector_relevance,
                adoption_potential       = snapshot.adoption_potential,
                startup_opportunity      = snapshot.startup_opportunity,
                disruption_potential     = snapshot.disruption_potential,
            )
        return snapshot_id

    def compute_trajectory(self, repo_id: str) -> Optional[TrajectoryProfile]:
        """Fetch all snapshots for repo_id and compute its trajectory profile."""
        with self._driver.session() as session:
            records   = session.run(_GET_SNAPSHOTS, repo_id=repo_id)
            snapshots = [dict(r) for r in records]

        profile = build_trajectory_profile(repo_id, snapshots)
        if profile:
            self._persist_trajectory(profile)
        return profile

    def get_trajectory_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return top BREAKOUT / ACCELERATING repos ranked by slope."""
        with self._driver.session() as session:
            records = session.run(_TRAJECTORY_LEADERBOARD, limit=limit)
            return [dict(r) for r in records]

    def run(self, batch_limit: int = 5_000) -> Dict[str, Any]:
        """
        Full weekly cycle:
          1. Find repos with enough snapshots to compute trajectories
          2. Compute & persist trajectory for each
          3. Return summary stats + leaderboard
        """
        with self._driver.session() as session:
            repos = [
                dict(r) for r in session.run(
                    _GET_REPOS_WITH_ENOUGH_SNAPSHOTS,
                    min_snapshots=MIN_SNAPSHOTS_FOR_TREND,
                    limit=batch_limit,
                )
            ]

        processed     = 0
        breakouts     = 0
        alerts        = 0

        for repo in repos:
            profile = self.compute_trajectory(repo["repo_id"])
            if profile:
                processed += 1
                if profile.trajectory_class == "BREAKOUT":
                    breakouts += 1
                if profile.trajectory_alert:
                    alerts += 1
                logger.info(
                    "Trajectory %s: %s slope=%.2f 90d_pred=%.1f",
                    repo["repo_id"], profile.trajectory_class,
                    profile.slope_per_week, profile.predicted_score_90d,
                )

        leaderboard = self.get_trajectory_leaderboard(limit=10)

        return {
            "agent_id":   self.agent_id,
            "processed":  processed,
            "breakouts":  breakouts,
            "alerts":     alerts,
            "leaderboard": leaderboard,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _persist_trajectory(self, profile: TrajectoryProfile) -> None:
        with self._driver.session() as session:
            session.run(
                _UPDATE_TRAJECTORY,
                repo_id             = profile.repo_id,
                trajectory_class    = profile.trajectory_class,
                slope_per_week      = profile.slope_per_week,
                r_squared           = profile.r_squared,
                predicted_score_30d = profile.predicted_score_30d,
                predicted_score_90d = profile.predicted_score_90d,
                predicted_score_180d= profile.predicted_score_180d,
                trajectory_alert    = profile.trajectory_alert,
                score_delta_30d     = profile.score_delta_30d,
                score_delta_90d     = profile.score_delta_90d,
            )
