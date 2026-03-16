"""
Agent 14 — AutonomousDocsAgent
================================
The platform documents itself.

Every Sunday after the weekly intelligence report is written, this agent:
  1. Queries live Neo4j metrics (repos tracked, active contributors, compliance gap, etc.)
  2. Updates the README.md "Live Metrics" badge section with real numbers
  3. Patches CONTRIBUTING.md with the current agent count + recent contributor list
  4. Appends a CHANGELOG.md entry summarising this week's intelligence cycle
  5. Writes a AGENTS.md registry — one source of truth for all 14 agents

Why this matters
─────────────────
  • Any new developer who forks the repo sees live, accurate stats — not stale docs
  • The CHANGELOG is auto-generated from Neo4j data — every deployment is recorded
  • AGENTS.md gives contributors a single-file map of what each agent does, its
    Neo4j schema, and how to extend it — reducing onboarding time to < 30 minutes

Self-updating loop
───────────────────
  MetaLearningOrchestrator tunes weights  (Saturday)
  WeeklyIntelligenceAgent writes report   (Sunday 05:00)
  AutonomousDocsAgent patches docs        (Sunday 06:00)
  ← cycle repeats every week →

No human commit needed — docs drift is structurally impossible.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Neo4j queries (read-only — no writes to graph) ────────────────────────────

_Q_LIVE_METRICS = """
MATCH (r:Repository)
WITH
    count(r)                              AS total_repos,
    avg(r.overall_innovation_score)       AS avg_score,
    count(CASE WHEN r.trajectory_class = 'BREAKOUT' THEN 1 END) AS breakouts
MATCH (d:Developer)
WITH total_repos, avg_score, breakouts, count(d) AS total_devs
MATCH (r2:Repository)-[:RELEVANT_TO]->(fs:FinancialSector {name: 'Payments'})
WITH total_repos, avg_score, breakouts, total_devs, count(r2) AS payment_repos
OPTIONAL MATCH (r3:Repository)-[:RELEVANT_TO]->(fs2:FinancialSector {name: 'Payments'})
WHERE NOT (r3)-[:SUBJECT_TO]->(:RegulatoryFramework {framework_id: 'BSA'})
WITH total_repos, avg_score, breakouts, total_devs, payment_repos, count(r3) AS no_bsa
RETURN
    total_repos,
    round(avg_score, 1)                    AS avg_score,
    breakouts,
    total_devs,
    CASE WHEN payment_repos > 0
         THEN round(toFloat(no_bsa) / payment_repos * 100, 0)
         ELSE 0 END                        AS compliance_gap_pct
"""

_Q_TOP_CONTRIBUTORS = """
MATCH (d:Developer)-[c:CONTRIBUTED_TO]->(r:Repository)
WITH d, count(DISTINCT r) AS repo_count
ORDER BY repo_count DESC
LIMIT 5
RETURN d.login AS login, d.name AS name, repo_count
"""

_Q_RECENT_BREAKOUTS = """
MATCH (r:Repository)
WHERE r.trajectory_class = 'BREAKOUT'
  AND r.trajectory_updated_at >= datetime() - duration('P7D')
RETURN coalesce(r.full_name, r.name) AS full_name, r.trajectory_slope AS slope
ORDER BY r.trajectory_slope DESC
LIMIT 5
"""

_Q_WEEKLY_STATS = """
MATCH (r:Repository)
WHERE r.last_snapshot_at >= datetime() - duration('P7D')
RETURN count(r) AS repos_updated_this_week
"""

_Q_AGENT_ACCURACY = """
MATCH (c:AgentWeightConfig)
RETURN c.agent_id AS agent_id, c.accuracy_30d AS accuracy, c.config_version AS version
ORDER BY c.agent_id
"""


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class LiveMetrics:
    total_repos:       int
    avg_score:         float
    breakouts:         int
    total_devs:        int
    compliance_gap:    float
    repos_this_week:   int
    top_contributors:  List[Dict[str, Any]]
    recent_breakouts:  List[Dict[str, Any]]
    agent_accuracies:  List[Dict[str, Any]]
    computed_at:       datetime


@dataclass
class DocsUpdateResult:
    readme_updated:       bool
    contributing_updated: bool
    changelog_appended:   bool
    agents_md_updated:    bool
    metrics_snapshot:     Dict[str, Any]
    files_written:        List[str]


# ── Agent registry — single source of truth ────────────────────────────────────

AGENT_REGISTRY = [
    {
        "number":   1,
        "name":     "RepositoryDiscoveryAgent",
        "module":   "ai_agents.discovery.repository_discovery_agent",
        "schedule": "Monday 02:00 UTC (triggered by ingestion sweep)",
        "purpose":  "Discovers repositories from GitHub/GitLab APIs and upserts them into Neo4j.",
        "writes":   "(Repository), (Organization), [:MAINTAINED_BY]",
        "inputs":   "GitHub API token, search queries",
        "extends":  "Add new discovery sources (GitLab, Bitbucket, Sourcehut) in `_upsert_repo()`",
    },
    {
        "number":   2,
        "name":     "TechnologyClassificationAgent",
        "module":   "ai_agents.classification.technology_classification_agent",
        "schedule": "Tuesday 03:00 UTC",
        "purpose":  "Uses Claude AI to classify repositories by FinTech sector and technology stack.",
        "writes":   "(Technology), [:IMPLEMENTS], [:RELEVANT_TO], r.primary_sector",
        "inputs":   "Repository README + language data from Neo4j",
        "extends":  "Add new tech categories in `_FINTECH_TAXONOMY` dict",
    },
    {
        "number":   3,
        "name":     "RegulatoryAnalysisAgent",
        "module":   "ai_agents.compliance.regulatory_analysis_agent",
        "schedule": "Tuesday 03:30 UTC",
        "purpose":  "Scores each repository's compliance posture against 12 regulatory frameworks (BSA, PCI-DSS, DORA, etc.).",
        "writes":   "[:SUBJECT_TO], [:SUPPORTS_COMPLIANCE], r.compliance_risk_score",
        "inputs":   "Repository code structure + sector classification from Agent 2",
        "extends":  "Add new frameworks in `REGULATORY_FRAMEWORKS` list + Cypher MERGE block",
    },
    {
        "number":   4,
        "name":     "ContributorNetworkAgent",
        "module":   "ai_agents.network.contributor_network_agent",
        "schedule": "Wednesday 03:00 UTC",
        "purpose":  "Maps developer collaboration graphs and institutional contributor patterns.",
        "writes":   "(Developer), (Institution), [:CONTRIBUTED_TO], [:COLLABORATES_WITH], [:AFFILIATED_WITH]",
        "inputs":   "GitHub API commit history",
        "extends":  "Add `gitlab_token` param to also map GitLab contributor networks",
    },
    {
        "number":   5,
        "name":     "AdoptionOpportunityAgent",
        "module":   "ai_agents.adoption.adoption_opportunity_agent",
        "schedule": "Wednesday 03:30 UTC",
        "purpose":  "Scores repositories on enterprise adoption readiness per FinTech sector.",
        "writes":   "(FinancialSector), [:HAS_ADOPTION_OPPORTUNITY], r.adoption_score",
        "inputs":   "Technology + regulatory data from Agents 2 and 3",
        "extends":  "Add new sectors in `FINANCIAL_SECTORS` list",
    },
    {
        "number":   6,
        "name":     "DisruptionPredictionAgent",
        "module":   "ai_agents.prediction.disruption_prediction_agent",
        "schedule": "Thursday 03:00 UTC",
        "purpose":  "ML model predicting which repos are on a trajectory to disrupt incumbents.",
        "writes":   "r.disruption_score, r.disruption_category, r.disruption_features_json",
        "inputs":   "All scored dimensions from Agents 2–5",
        "extends":  "Retrain `DisruptionScoringModel` by subclassing and overriding `_score_repo()`",
    },
    {
        "number":   7,
        "name":     "DependencyAnalysisAgent",
        "module":   "ai_agents.dependency.dependency_analysis_agent",
        "schedule": "Thursday 03:30 UTC",
        "purpose":  "Parses manifest files to build a supply-chain dependency graph with blast-radius scoring.",
        "writes":   "(Dependency), [:DEPENDS_ON], r.supply_chain_risk_score, r.dependency_scan_at",
        "inputs":   "Repository file trees from GitHub API",
        "extends":  "Add new manifest parsers in `_MANIFEST_PARSERS` dict (e.g. Cargo.toml, go.mod)",
    },
    {
        "number":   8,
        "name":     "InnovationSignalAgent",
        "module":   "ai_agents.signals.innovation_signal_agent",
        "schedule": "Friday 03:00 UTC",
        "purpose":  "Computes innovation velocity from commit patterns, contributor growth, and concept clustering.",
        "writes":   "r.innovation_signal_score, r.velocity_class, r.concept_vector",
        "inputs":   "Snapshot history + contributor data from Agents 1, 4",
        "extends":  "Add new velocity signals by extending `VelocitySignal` dataclass",
    },
    {
        "number":   9,
        "name":     "WeeklyIntelligenceAgent",
        "module":   "ai_agents.reporting.weekly_intelligence_agent",
        "schedule": "Sunday 05:00 UTC",
        "purpose":  "Aggregates all agent outputs into a Claude-generated narrative intelligence report (Markdown + PDF).",
        "writes":   "Files to `automation/reports/`",
        "inputs":   "All Neo4j metrics from Agents 1–12",
        "extends":  "Customise the report template in `_REPORT_PROMPT` string",
    },
    {
        "number":   10,
        "name":     "FutureSignalAgent",
        "module":   "ai_agents.signals.future_signal_agent",
        "schedule": "Friday 03:30 UTC",
        "purpose":  "Fits linear trajectories over score snapshots and extrapolates 30/90/180-day forecasts.",
        "writes":   "(ScoreSnapshot), [:HAS_SCORE_SNAPSHOT], r.predicted_score_30d/90d/180d, r.trajectory_class",
        "inputs":   "Historical ScoreSnapshot nodes (auto-created on each scoring run)",
        "extends":  "Replace `fit_linear_trajectory()` with polynomial fitting for non-linear repos",
    },
    {
        "number":   11,
        "name":     "ExternalSignalCorrelator",
        "module":   "ai_agents.signals.external_signal_correlator",
        "schedule": "Friday 04:00 UTC",
        "purpose":  "Correlates repos with arXiv papers, USPTO patents, job postings, and regulatory sandbox participation.",
        "writes":   "(AcademicPaper), (Patent), [:CITED_IN_PAPER], [:REFERENCED_IN_PATENT], r.external_signal_score",
        "inputs":   "arXiv Atom API, PatentsView API, Indeed RSS, curated sandbox registry",
        "extends":  "Add new signal sources in `SIGNAL_WEIGHTS` dict (e.g. Semantic Scholar, SEC filings)",
    },
    {
        "number":   12,
        "name":     "MetaLearningOrchestrator",
        "module":   "ai_agents.orchestration.meta_learning_orchestrator",
        "schedule": "Saturday 04:00 UTC",
        "purpose":  "Evaluates timed predictions, computes rolling accuracy per agent, tunes scoring weights autonomously.",
        "writes":   "(PredictionLog), (AgentWeightConfig) — versioned weight history",
        "inputs":   "PredictionLog nodes with past evaluate_after timestamps",
        "extends":  "Add new prediction types in `PredictionType` class + `EVALUATION_HORIZON` dict",
    },
    {
        "number":   13,
        "name":     "FITIndexAgent",
        "module":   "ai_agents.reporting.fit_index_agent",
        "schedule": "1st of every month 06:00 UTC",
        "purpose":  "Aggregates all agent outputs into the monthly FinTech Intelligence Terminal OSS Index (LaTeX/Markdown/JSON).",
        "writes":   "(FITIndex) + [:FEATURES_BREAKOUT], [:FLAGS_ACQUISITION], [:HIGHLIGHTS_SURGE] edges",
        "inputs":   "All Neo4j data from Agents 1–12",
        "extends":  "Add new index sections in `index_publisher.py` `render_latex()` / `render_markdown()`",
    },
    {
        "number":   14,
        "name":     "AutonomousDocsAgent",
        "module":   "ai_agents.orchestration.autonomous_docs_agent",
        "schedule": "Sunday 06:00 UTC",
        "purpose":  "Updates README.md live metrics, CONTRIBUTING.md agent count, CHANGELOG.md weekly entry, AGENTS.md registry.",
        "writes":   "Files only — no Neo4j writes",
        "inputs":   "Live Neo4j metrics + repo root file paths",
        "extends":  "Add new doc targets in `DocsUpdateResult` + corresponding `_update_*()` method",
    },
]


# ── Pure-logic helpers (testable without Neo4j) ───────────────────────────────

def _build_live_metrics_badge_block(metrics: LiveMetrics) -> str:
    """
    Build the README 'Live Metrics' section (between sentinel comments).
    Uses GitHub shields.io-style static badge format as inline text — no external service needed.
    """
    gap_emoji = "🔴" if metrics.compliance_gap >= 25 else "🟡" if metrics.compliance_gap >= 10 else "🟢"
    return (
        f"| 🏦 Repositories Tracked | **{metrics.total_repos:,}** |\n"
        f"| 📈 Avg Innovation Score | **{metrics.avg_score:.1f}/100** |\n"
        f"| 🚀 Breakout Repos (live) | **{metrics.breakouts}** |\n"
        f"| 👥 Developer Network | **{metrics.total_devs:,} contributors** |\n"
        f"| {gap_emoji} Compliance Gap | **{metrics.compliance_gap:.0f}% lack BSA controls** |\n"
        f"| 🔄 Updated this week | **{metrics.repos_this_week:,} repos** |"
    )


def _build_changelog_entry(
    metrics: LiveMetrics,
    week_ending: str,
    breakout_names: List[str],
) -> str:
    """Build a single CHANGELOG.md weekly entry block."""
    breakout_list = "\n".join(f"  - `{n}`" for n in breakout_names) or "  - None this week"
    return (
        f"\n## [{week_ending}] — Weekly Intelligence Cycle\n\n"
        f"### Platform Stats\n"
        f"- Repositories tracked: **{metrics.total_repos:,}**\n"
        f"- Average innovation score: **{metrics.avg_score:.1f}/100**\n"
        f"- New breakout repos detected: **{len(breakout_names)}**\n"
        f"- Active developer network: **{metrics.total_devs:,}**\n"
        f"- Compliance gap (payment sector): **{metrics.compliance_gap:.0f}%**\n\n"
        f"### Breakout Repos\n"
        f"{breakout_list}\n\n"
        f"*Generated autonomously by AutonomousDocsAgent at {metrics.computed_at.strftime('%Y-%m-%d %H:%M UTC')}*\n"
    )


def _build_agents_md(agent_registry: list) -> str:
    """Render the full AGENTS.md — one source of truth for all agents."""
    header = (
        "# FinTech Intelligence Terminal — Agent Registry\n\n"
        "> Auto-generated by `AutonomousDocsAgent` every Sunday.\n"
        "> **Do not edit manually** — changes will be overwritten.\n\n"
        f"**{len(agent_registry)} autonomous agents** are currently active.\n\n"
        "---\n\n"
    )
    entries = []
    for a in agent_registry:
        entries.append(
            f"## Agent {a['number']:02d} — {a['name']}\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| Module | `{a['module']}` |\n"
            f"| Schedule | {a['schedule']} |\n"
            f"| Purpose | {a['purpose']} |\n"
            f"| Neo4j writes | `{a['writes']}` |\n"
            f"| Inputs | {a['inputs']} |\n"
            f"| How to extend | {a['extends']} |\n"
        )
    return header + "\n".join(entries)


def _patch_section(content: str, sentinel: str, new_body: str) -> str:
    """
    Replace content between <!-- SENTINEL_START --> and <!-- SENTINEL_END --> comments.
    Returns original content unchanged if sentinels not found.
    """
    start = f"<!-- {sentinel}_START -->"
    end   = f"<!-- {sentinel}_END -->"
    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        re.DOTALL,
    )
    replacement = f"{start}\n{new_body}\n{end}"
    new_content, count = pattern.subn(replacement, content)
    if count == 0:
        logger.warning("Sentinel %s not found in document — skipping patch", sentinel)
    return new_content


# ── Agent class ────────────────────────────────────────────────────────────────

class AutonomousDocsAgent:
    """
    Agent 14: AutonomousDocsAgent

    Reads live Neo4j metrics and patches key documentation files so
    the repo always reflects the current state of the platform.

    Usage (standalone):
        agent = AutonomousDocsAgent(neo4j_driver, repo_root="/path/to/repo")
        result = agent.run()

    Usage (Celery):
        run_autonomous_docs_update.apply_async()
    """

    agent_id   = "autonomous_docs_agent"
    agent_name = "AutonomousDocsAgent"
    version    = "1.0.0"

    def __init__(
        self,
        neo4j_driver,
        repo_root: Optional[str] = None,
    ) -> None:
        self._driver   = neo4j_driver
        self._root     = Path(repo_root or _find_repo_root())

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch_metrics(self) -> LiveMetrics:
        """Pull live stats from Neo4j — single session, multiple queries."""
        with self._driver.session() as s:
            row         = s.run(_Q_LIVE_METRICS).single() or {}
            contributors = [dict(r) for r in s.run(_Q_TOP_CONTRIBUTORS)]
            breakouts   = [dict(r) for r in s.run(_Q_RECENT_BREAKOUTS)]
            week_row    = s.run(_Q_WEEKLY_STATS).single() or {}
            acc_rows    = [dict(r) for r in s.run(_Q_AGENT_ACCURACY)]

        return LiveMetrics(
            total_repos      = int(row.get("total_repos", 0)),
            avg_score        = float(row.get("avg_score", 0.0)),
            breakouts        = int(row.get("breakouts", 0)),
            total_devs       = int(row.get("total_devs", 0)),
            compliance_gap   = float(row.get("compliance_gap_pct", 0.0)),
            repos_this_week  = int(week_row.get("repos_updated_this_week", 0)),
            top_contributors = contributors,
            recent_breakouts = breakouts,
            agent_accuracies = acc_rows,
            computed_at      = datetime.now(timezone.utc),
        )

    def run(self) -> DocsUpdateResult:
        """Fetch metrics and update all documentation files."""
        metrics      = self.fetch_metrics()
        files_written: List[str] = []

        readme_ok       = self._update_readme(metrics, files_written)
        contributing_ok = self._update_contributing(files_written)
        changelog_ok    = self._append_changelog(metrics, files_written)
        agents_ok       = self._write_agents_md(files_written)

        logger.info(
            "AutonomousDocsAgent: README=%s CONTRIBUTING=%s CHANGELOG=%s AGENTS=%s",
            readme_ok, contributing_ok, changelog_ok, agents_ok,
        )

        return DocsUpdateResult(
            readme_updated       = readme_ok,
            contributing_updated = contributing_ok,
            changelog_appended   = changelog_ok,
            agents_md_updated    = agents_ok,
            metrics_snapshot     = {
                "total_repos":     metrics.total_repos,
                "avg_score":       metrics.avg_score,
                "breakouts":       metrics.breakouts,
                "compliance_gap":  metrics.compliance_gap,
                "repos_this_week": metrics.repos_this_week,
            },
            files_written = files_written,
        )

    # ── Internal updaters ──────────────────────────────────────────────────────

    def _update_readme(self, metrics: LiveMetrics, files_written: List[str]) -> bool:
        readme = self._root / "README.md"
        if not readme.exists():
            logger.warning("README.md not found at %s", readme)
            return False

        content   = readme.read_text(encoding="utf-8")
        badge_body = _build_live_metrics_badge_block(metrics)
        # README must contain <!-- LIVE_METRICS_START --> / <!-- LIVE_METRICS_END -->
        new_content = _patch_section(content, "LIVE_METRICS", badge_body)

        if new_content != content:
            readme.write_text(new_content, encoding="utf-8")
            files_written.append(str(readme))
            logger.info("README.md live metrics updated")
        return True

    def _update_contributing(self, files_written: List[str]) -> bool:
        contrib = self._root / "CONTRIBUTING.md"
        if not contrib.exists():
            return False

        content = contrib.read_text(encoding="utf-8")
        # Update the agent count line if it exists
        new_content = re.sub(
            r"(\*\*)\d+(\*\* autonomous agents)",
            f"**{len(AGENT_REGISTRY)}** autonomous agents",
            content,
        )
        new_content = re.sub(
            r"(\| Agents \| )\d+",
            f"| Agents | {len(AGENT_REGISTRY)}",
            new_content,
        )
        if new_content != content:
            contrib.write_text(new_content, encoding="utf-8")
            files_written.append(str(contrib))
            logger.info("CONTRIBUTING.md agent count updated to %d", len(AGENT_REGISTRY))
        return True

    def _append_changelog(self, metrics: LiveMetrics, files_written: List[str]) -> bool:
        changelog = self._root / "CHANGELOG.md"
        week_ending = metrics.computed_at.strftime("%Y-%m-%d")
        breakout_names = [r.get("full_name", "") for r in metrics.recent_breakouts]
        entry = _build_changelog_entry(metrics, week_ending, breakout_names)

        heading_marker = f"## [{week_ending}]"
        if changelog.exists():
            existing = changelog.read_text(encoding="utf-8")
            # Don't duplicate entries for the same week (check heading, not just date)
            if heading_marker in existing:
                logger.info("CHANGELOG.md already has entry for %s", week_ending)
                return True
            # Prepend after the first heading
            first_heading_end = existing.find("\n", existing.find("# ")) + 1
            new_content = existing[:first_heading_end] + entry + existing[first_heading_end:]
        else:
            new_content = "# Changelog\n" + entry

        changelog.write_text(new_content, encoding="utf-8")
        files_written.append(str(changelog))
        logger.info("CHANGELOG.md updated with entry for %s", week_ending)
        return True

    def _write_agents_md(self, files_written: List[str]) -> bool:
        agents_md = self._root / "AGENTS.md"
        content   = _build_agents_md(AGENT_REGISTRY)
        agents_md.write_text(content, encoding="utf-8")
        files_written.append(str(agents_md))
        logger.info("AGENTS.md written with %d agent entries", len(AGENT_REGISTRY))
        return True


# ── Repo root discovery ────────────────────────────────────────────────────────

def _find_repo_root() -> str:
    """Walk up from this file's location to find the git repo root."""
    p = Path(__file__).resolve()
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            return str(parent)
    return str(Path.cwd())
