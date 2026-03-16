"""
GitKT FinTech OSS Index — Computation Agent
============================================
Produces the monthly "S&P 500 for open-source FinTech health" by aggregating
intelligence from all 12 agents already running in the platform.

Published metrics (each issue)
───────────────────────────────
  • Total repositories tracked
  • Innovation velocity (30-day %)
  • Compliance coverage gap (% of payment repos lacking key controls)
  • Supply-chain risk score (0–10, weighted dependency graph)
  • Emerging technology surges (top tech nodes by MoM growth)
  • Predicted breakout repos   (BREAKOUT class, slope > 5 pts/week)
  • Predicted acquisitions     (disruption_score > 85 + acquisition signals)

Neo4j model (written by this agent)
─────────────────────────────────────
  (GitKTIndex {
      period:                     "2026-03",   ← YYYY-MM
      published_at:               datetime,
      total_repos_tracked:        int,
      innovation_velocity_30d:    float,       ← percentage
      compliance_coverage_gap:    float,       ← percentage
      supply_chain_risk_score:    float,       ← 0–10
      new_repos_this_month:       int,
      active_contributors_30d:    int,
      regulatory_gaps_detected:   int,
  })
  (GitKTIndex)-[:FEATURES_BREAKOUT]->(Repository)
  (GitKTIndex)-[:FLAGS_ACQUISITION]->(Repository)
  (GitKTIndex)-[:HIGHLIGHTS_SURGE]->(Technology)
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class TechSurge:
    """A technology showing outsized month-over-month growth."""
    tech_name:      str
    category:       str
    repo_count_now: int
    repo_count_30d: int
    mom_pct:        float          # month-over-month percentage change
    example_repos:  List[str] = field(default_factory=list)

    @property
    def surge_label(self) -> str:
        return f"{self.tech_name} +{self.mom_pct:.0f}% MoM"


@dataclass
class BreakoutPrediction:
    """A repository predicted to break out in the next 90 days."""
    repo_id:              str
    full_name:            str
    current_score:        float
    predicted_score_90d:  float
    slope_per_week:       float
    trajectory_class:     str
    external_signal_score: float = 0.0    # from ExternalSignalCorrelator
    innovation_signal:    float = 0.0


@dataclass
class AcquisitionPrediction:
    """A repository showing acquisition-grade signals."""
    repo_id:          str
    full_name:        str
    disruption_score: float
    adoption_score:   float
    contributor_orgs: int             # number of institutional contributors
    rationale:        str             # human-readable reason


@dataclass
class GitKTIndex:
    """
    One monthly edition of the GitKT FinTech OSS Index.
    All fields are pure data — no Neo4j driver references.
    """
    period:                   str            # "2026-03"
    published_at:             datetime

    # ── Headline metrics ──────────────────────────────────────────────────────
    total_repos_tracked:      int
    innovation_velocity_30d:  float          # percentage (+12.4 = grew 12.4%)
    compliance_coverage_gap:  float          # percentage lacking key controls
    supply_chain_risk_score:  float          # 0–10

    # ── Supporting stats ──────────────────────────────────────────────────────
    new_repos_this_month:     int
    active_contributors_30d:  int
    regulatory_gaps_detected: int
    highest_disruption_score: float
    top_supply_chain_dep:     str            # e.g. "urllib3"

    # ── Dynamic lists ──────────────────────────────────────────────────────────
    emerging_surges:              List[TechSurge]            = field(default_factory=list)
    predicted_breakout_repos:     List[BreakoutPrediction]   = field(default_factory=list)
    predicted_acquisitions:       List[AcquisitionPrediction] = field(default_factory=list)

    # ── Risk narrative ────────────────────────────────────────────────────────
    supply_chain_alert:       str = ""       # e.g. "urllib3 maintainer inactive"
    compliance_alert:         str = ""       # e.g. "23% of payment repos lack BSA controls"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat()
        return d

    @property
    def headline(self) -> str:
        return (
            f"GitKT FinTech OSS Index — {self.period}\n"
            f"  Total repositories tracked:    {self.total_repos_tracked:,}\n"
            f"  Innovation velocity (30-day):  {self.innovation_velocity_30d:+.1f}%\n"
            f"  Compliance coverage gap:        {self.compliance_coverage_gap:.0f}% of payment repos lack BSA controls\n"
            f"  Supply chain risk score:        {self.supply_chain_risk_score:.1f}/10 "
            f"{'(elevated)' if self.supply_chain_risk_score >= 6.5 else '(moderate)'}\n"
            f"  Emerging technology surge:      "
            f"{self.emerging_surges[0].surge_label if self.emerging_surges else 'none detected'}\n"
            f"  Predicted breakout repos:       {len(self.predicted_breakout_repos)} identified\n"
            f"  Predicted acquisitions:         {len(self.predicted_acquisitions)} identified"
        )


# ── Cypher queries ─────────────────────────────────────────────────────────────

_Q_TOTAL_REPOS = "MATCH (r:Repository) RETURN count(r) AS total"

_Q_NEW_REPOS = """
MATCH (r:Repository)
WHERE r.created_at >= datetime($since)
RETURN count(r) AS new_repos
"""

_Q_ACTIVE_CONTRIBUTORS = """
MATCH (d:Developer)-[c:CONTRIBUTED_TO]->(r:Repository)
WHERE c.last_commit_at >= datetime($since)
RETURN count(DISTINCT d) AS active_devs
"""

_Q_INNOVATION_VELOCITY = """
MATCH (r:Repository)-[:HAS_SCORE_SNAPSHOT]->(s:ScoreSnapshot)
WITH r, s ORDER BY s.captured_at DESC
WITH r, collect(s)[0] AS latest, collect(s)[-1] AS oldest
WHERE oldest.captured_at <= datetime($cutoff)
RETURN
    avg(latest.overall_innovation_score - oldest.overall_innovation_score) AS avg_delta,
    avg(oldest.overall_innovation_score) AS avg_base
"""

_Q_COMPLIANCE_GAP = """
MATCH (r:Repository)-[:RELEVANT_TO]->(fs:FinancialSector {name: 'Payments'})
WITH count(r) AS total_payment
MATCH (r2:Repository)-[:RELEVANT_TO]->(fs2:FinancialSector {name: 'Payments'})
WHERE NOT (r2)-[:SUBJECT_TO]->(:RegulatoryFramework {framework_id: 'BSA'})
RETURN total_payment, count(r2) AS missing_bsa
"""

_Q_SUPPLY_CHAIN_RISK = """
MATCH (r:Repository)-[rel:DEPENDS_ON]->(d:Dependency)
WHERE d.is_critical = true
RETURN
    avg(coalesce(d.vulnerability_score, 5.0)) AS avg_vuln,
    count(DISTINCT d)                          AS critical_deps,
    d.name AS top_dep
ORDER BY d.vulnerability_score DESC
LIMIT 1
"""

_Q_TECH_SURGES = """
MATCH (t:Technology)<-[:IMPLEMENTS]-(r:Repository)
WHERE t.first_seen >= datetime($cutoff_30d)
   OR t.updated_at  >= datetime($cutoff_30d)
WITH t, count(r) AS repo_count_now
MATCH (t)<-[:IMPLEMENTS]-(r2:Repository)
WHERE r2.created_at <= datetime($cutoff_30d)
WITH t, repo_count_now, count(r2) AS repo_count_30d
WHERE repo_count_30d > 0
RETURN
    t.name     AS tech_name,
    t.category AS category,
    repo_count_now,
    repo_count_30d,
    toFloat(repo_count_now - repo_count_30d) / repo_count_30d * 100 AS mom_pct
ORDER BY mom_pct DESC
LIMIT 8
"""

_Q_BREAKOUT_REPOS = """
MATCH (r:Repository)
WHERE r.trajectory_class IN ['BREAKOUT', 'ACCELERATING']
  AND r.trajectory_slope IS NOT NULL
RETURN
    r.id                           AS repo_id,
    coalesce(r.full_name, r.name)  AS full_name,
    r.overall_innovation_score     AS current_score,
    r.predicted_score_90d          AS predicted_score_90d,
    r.trajectory_slope             AS slope_per_week,
    r.trajectory_class             AS trajectory_class,
    coalesce(r.external_signal_score, 0.0) AS external_signal_score,
    coalesce(r.innovation_signal_score, 0.0) AS innovation_signal
ORDER BY r.trajectory_slope DESC
LIMIT 5
"""

_Q_ACQUISITION_CANDIDATES = """
MATCH (r:Repository)
WHERE r.disruption_score >= 80
  AND r.adoption_score   >= 60
OPTIONAL MATCH (d:Developer)-[:CONTRIBUTED_TO]->(r)
        MATCH (d)-[:AFFILIATED_WITH]->(inst:Institution)
WITH r, count(DISTINCT inst) AS contributor_orgs
WHERE contributor_orgs >= 2
RETURN
    r.id                           AS repo_id,
    coalesce(r.full_name, r.name)  AS full_name,
    r.disruption_score             AS disruption_score,
    r.adoption_score               AS adoption_score,
    contributor_orgs
ORDER BY r.disruption_score DESC
LIMIT 3
"""

_Q_REGULATORY_GAPS = """
MATCH (r:Repository)-[:RELEVANT_TO]->(fs:FinancialSector)
WHERE NOT (r)-[:SUBJECT_TO]->(:RegulatoryFramework)
  AND r.overall_innovation_score >= 50
RETURN count(r) AS gap_count
"""

_Q_TOP_DISRUPTION = """
MATCH (r:Repository)
WHERE r.disruption_score IS NOT NULL
RETURN max(r.disruption_score) AS max_score
"""

_Q_SAVE_INDEX = """
MERGE (idx:GitKTIndex {period: $period})
SET
    idx.published_at             = datetime($published_at),
    idx.total_repos_tracked      = $total_repos_tracked,
    idx.innovation_velocity_30d  = $innovation_velocity_30d,
    idx.compliance_coverage_gap  = $compliance_coverage_gap,
    idx.supply_chain_risk_score  = $supply_chain_risk_score,
    idx.new_repos_this_month     = $new_repos_this_month,
    idx.active_contributors_30d  = $active_contributors_30d,
    idx.regulatory_gaps_detected = $regulatory_gaps_detected,
    idx.highest_disruption_score = $highest_disruption_score,
    idx.supply_chain_alert       = $supply_chain_alert,
    idx.compliance_alert         = $compliance_alert,
    idx.index_json               = $index_json
RETURN idx.period AS period
"""

_Q_LINK_BREAKOUT = """
MATCH (idx:GitKTIndex {period: $period})
MATCH (r:Repository {id: $repo_id})
MERGE (idx)-[:FEATURES_BREAKOUT]->(r)
"""

_Q_LINK_ACQUISITION = """
MATCH (idx:GitKTIndex {period: $period})
MATCH (r:Repository {id: $repo_id})
MERGE (idx)-[:FLAGS_ACQUISITION]->(r)
"""

_Q_LINK_SURGE = """
MATCH (idx:GitKTIndex {period: $period})
MATCH (t:Technology {name: $tech_name})
MERGE (idx)-[:HIGHLIGHTS_SURGE]->(t)
"""

_Q_HISTORICAL = """
MATCH (idx:GitKTIndex)
RETURN
    idx.period                   AS period,
    idx.published_at             AS published_at,
    idx.total_repos_tracked      AS total_repos,
    idx.innovation_velocity_30d  AS velocity,
    idx.compliance_coverage_gap  AS compliance_gap,
    idx.supply_chain_risk_score  AS supply_chain_risk
ORDER BY idx.period DESC
LIMIT $limit
"""


# ── Pure computation helpers (no Neo4j — fully testable) ──────────────────────

def compute_innovation_velocity(avg_delta: float, avg_base: float) -> float:
    """
    Convert raw score delta into a percentage velocity.
    e.g. avg_delta=+4.1 on avg_base=33.1 → +12.4%
    """
    if avg_base <= 0:
        return 0.0
    return round((avg_delta / avg_base) * 100, 1)


def compute_compliance_gap(total_payment: int, missing_bsa: int) -> float:
    """Percentage of payment repos lacking BSA controls."""
    if total_payment <= 0:
        return 0.0
    return round((missing_bsa / total_payment) * 100, 1)


def compute_supply_chain_risk(avg_vuln: float, critical_deps: int) -> float:
    """
    Weighted supply-chain risk score (0–10).
    Base = avg vulnerability score (0–10).
    Penalty for having many critical dependencies.
    """
    dep_penalty = min(critical_deps * 0.05, 2.0)
    raw = avg_vuln + dep_penalty
    return round(min(raw, 10.0), 1)


def build_acquisition_rationale(
    full_name: str,
    disruption_score: float,
    adoption_score: float,
    contributor_orgs: int,
) -> str:
    """Generate a human-readable acquisition rationale string."""
    reasons = []
    if disruption_score >= 90:
        reasons.append(f"exceptional disruption score ({disruption_score:.0f}/100)")
    elif disruption_score >= 80:
        reasons.append(f"high disruption score ({disruption_score:.0f}/100)")
    if adoption_score >= 70:
        reasons.append(f"strong enterprise adoption readiness ({adoption_score:.0f}/100)")
    if contributor_orgs >= 3:
        reasons.append(f"multi-institutional backing ({contributor_orgs} orgs)")
    return f"{full_name}: " + "; ".join(reasons) if reasons else f"{full_name}: acquisition-grade signals"


def rank_surges(surges: List[TechSurge], top_n: int = 5) -> List[TechSurge]:
    """Return top-N surges by MoM percentage, filtering out noise (< 50% growth)."""
    meaningful = [s for s in surges if s.mom_pct >= 50.0]
    return sorted(meaningful, key=lambda s: s.mom_pct, reverse=True)[:top_n]


# ── Agent class ────────────────────────────────────────────────────────────────

class GitKTIndexAgent:
    """
    Computes and publishes the monthly GitKT FinTech OSS Index.

    Usage:
        agent = GitKTIndexAgent(neo4j_driver)
        index = agent.compute(period="2026-03")
        agent.save(index)
        print(index.headline)

    The agent is purely read-intensive from Neo4j (it aggregates data written
    by Agents 1–12) and writes a single (GitKTIndex) node per month.
    """

    agent_id   = "gitkt_index_agent"
    agent_name = "GitKTIndexAgent"
    version    = "1.0.0"

    def __init__(self, neo4j_driver) -> None:
        self._driver = neo4j_driver

    # ── Public API ─────────────────────────────────────────────────────────────

    def compute(self, period: Optional[str] = None) -> GitKTIndex:
        """
        Aggregate all agent outputs into one GitKTIndex for the given period.
        period: "YYYY-MM" — defaults to current month.
        """
        now     = datetime.now(timezone.utc)
        period  = period or now.strftime("%Y-%m")
        cutoff  = (now - timedelta(days=30)).isoformat()

        with self._driver.session() as s:
            total_repos    = s.run(_Q_TOTAL_REPOS).single()["total"]
            new_repos      = (s.run(_Q_NEW_REPOS, since=cutoff).single() or {}).get("new_repos", 0)
            active_devs    = (s.run(_Q_ACTIVE_CONTRIBUTORS, since=cutoff).single() or {}).get("active_devs", 0)
            velocity_row   = s.run(_Q_INNOVATION_VELOCITY, cutoff=cutoff).single()
            compliance_row = s.run(_Q_COMPLIANCE_GAP).single()
            supply_row     = s.run(_Q_SUPPLY_CHAIN_RISK).single()
            gap_row        = s.run(_Q_REGULATORY_GAPS).single()
            top_dis        = (s.run(_Q_TOP_DISRUPTION).single() or {}).get("max_score", 0.0)
            tech_surge_recs = list(s.run(_Q_TECH_SURGES, cutoff_30d=cutoff))
            breakout_recs   = list(s.run(_Q_BREAKOUT_REPOS))
            acq_recs        = list(s.run(_Q_ACQUISITION_CANDIDATES))

        # Velocity
        avg_delta  = float(velocity_row["avg_delta"] or 0) if velocity_row else 0.0
        avg_base   = float(velocity_row["avg_base"]  or 33.0) if velocity_row else 33.0
        velocity   = compute_innovation_velocity(avg_delta, avg_base)

        # Compliance gap
        tot_pay    = int(compliance_row["total_payment"] or 0) if compliance_row else 0
        miss_bsa   = int(compliance_row["missing_bsa"]   or 0) if compliance_row else 0
        comp_gap   = compute_compliance_gap(tot_pay, miss_bsa)

        # Supply chain
        avg_vuln   = float(supply_row["avg_vuln"]     or 5.0) if supply_row else 5.0
        crit_deps  = int(supply_row["critical_deps"]  or 0)   if supply_row else 0
        top_dep    = str(supply_row["top_dep"]         or "")  if supply_row else ""
        sc_risk    = compute_supply_chain_risk(avg_vuln, crit_deps)

        # Regulatory gaps
        gap_count  = int(gap_row["gap_count"] or 0) if gap_row else 0

        # Emerging surges
        surges = rank_surges([
            TechSurge(
                tech_name      = r["tech_name"] or "Unknown",
                category       = r["category"]  or "",
                repo_count_now = int(r["repo_count_now"] or 0),
                repo_count_30d = int(r["repo_count_30d"] or 0),
                mom_pct        = float(r["mom_pct"] or 0),
            )
            for r in tech_surge_recs
        ])

        # Breakout predictions
        breakouts = [
            BreakoutPrediction(
                repo_id             = r["repo_id"],
                full_name           = r["full_name"]            or r["repo_id"],
                current_score       = float(r["current_score"]  or 0),
                predicted_score_90d = float(r["predicted_score_90d"] or 0),
                slope_per_week      = float(r["slope_per_week"] or 0),
                trajectory_class    = r["trajectory_class"]     or "BREAKOUT",
                external_signal_score = float(r["external_signal_score"] or 0),
                innovation_signal   = float(r["innovation_signal"] or 0),
            )
            for r in breakout_recs
        ]

        # Acquisition predictions
        acquisitions = [
            AcquisitionPrediction(
                repo_id          = r["repo_id"],
                full_name        = r["full_name"]         or r["repo_id"],
                disruption_score = float(r["disruption_score"] or 0),
                adoption_score   = float(r["adoption_score"]   or 0),
                contributor_orgs = int(r["contributor_orgs"]   or 0),
                rationale        = build_acquisition_rationale(
                    r["full_name"] or r["repo_id"],
                    float(r["disruption_score"] or 0),
                    float(r["adoption_score"]   or 0),
                    int(r["contributor_orgs"]   or 0),
                ),
            )
            for r in acq_recs
        ]

        # Narrative alerts
        supply_alert  = (
            f"{top_dep} maintainer activity low — supply-chain risk elevated"
            if sc_risk >= 6.5 and top_dep else ""
        )
        comp_alert    = (
            f"{comp_gap:.0f}% of tracked payment repos lack BSA/AML controls"
            if comp_gap >= 15 else ""
        )

        return GitKTIndex(
            period                   = period,
            published_at             = now,
            total_repos_tracked      = total_repos,
            innovation_velocity_30d  = velocity,
            compliance_coverage_gap  = comp_gap,
            supply_chain_risk_score  = sc_risk,
            new_repos_this_month     = new_repos,
            active_contributors_30d  = active_devs,
            regulatory_gaps_detected = gap_count,
            highest_disruption_score = float(top_dis or 0),
            top_supply_chain_dep     = top_dep,
            emerging_surges          = surges,
            predicted_breakout_repos = breakouts,
            predicted_acquisitions   = acquisitions,
            supply_chain_alert       = supply_alert,
            compliance_alert         = comp_alert,
        )

    def save(self, index: GitKTIndex) -> None:
        """Persist the index to Neo4j and link breakout/acquisition repos."""
        with self._driver.session() as s:
            s.run(
                _Q_SAVE_INDEX,
                period                   = index.period,
                published_at             = index.published_at.isoformat(),
                total_repos_tracked      = index.total_repos_tracked,
                innovation_velocity_30d  = index.innovation_velocity_30d,
                compliance_coverage_gap  = index.compliance_coverage_gap,
                supply_chain_risk_score  = index.supply_chain_risk_score,
                new_repos_this_month     = index.new_repos_this_month,
                active_contributors_30d  = index.active_contributors_30d,
                regulatory_gaps_detected = index.regulatory_gaps_detected,
                highest_disruption_score = index.highest_disruption_score,
                supply_chain_alert       = index.supply_chain_alert,
                compliance_alert         = index.compliance_alert,
                index_json               = json.dumps(index.to_dict()),
            )
            for repo in index.predicted_breakout_repos:
                s.run(_Q_LINK_BREAKOUT, period=index.period, repo_id=repo.repo_id)
            for repo in index.predicted_acquisitions:
                s.run(_Q_LINK_ACQUISITION, period=index.period, repo_id=repo.repo_id)
            for surge in index.emerging_surges:
                s.run(_Q_LINK_SURGE, period=index.period, tech_name=surge.tech_name)

        logger.info("GitKT Index %s saved (%d repos, velocity %+.1f%%)",
                    index.period, index.total_repos_tracked, index.innovation_velocity_30d)

    def get_historical(self, limit: int = 12) -> List[Dict[str, Any]]:
        """Return last N monthly index summaries for trend charts."""
        with self._driver.session() as s:
            return [dict(r) for r in s.run(_Q_HISTORICAL, limit=limit)]

    def run(self, period: Optional[str] = None) -> GitKTIndex:
        """Compute + save in one call (Celery task entrypoint)."""
        index = self.compute(period)
        self.save(index)
        return index
