"""
Weekly Intelligence Agent (Agent 10 of 10)

Generates automated weekly intelligence reports by:
1. Querying the knowledge graph for top signals
2. Using Claude to synthesize insights
3. Generating a Markdown report
4. Committing the report to the Git repository
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)

REPORT_DIR = Path("automation/reports")

REPORT_GENERATION_PROMPT = """You are an expert fintech intelligence analyst.
Based on the data below from our open-source fintech intelligence platform,
write a professional weekly intelligence report in Markdown format.

The report should include:
1. Executive Summary (3-5 key insights)
2. Top Emerging Repositories (ranked by innovation score)
3. Fastest Growing Technologies
4. New Developer Innovation Clusters
5. RegTech Developments & Compliance Signals
6. High-Disruption-Potential Repositories
7. Startup Opportunity Signals
8. Geographic Innovation Hotspots
9. Recommended Actions for Financial Institutions

Use professional, data-driven language. Be specific about metrics.
Format with clear headings, bullet points, and tables where appropriate.

DATA:
{data}"""


class WeeklyIntelligenceAgent(BaseAgent):
    """Agent 10: Generates and commits weekly fintech intelligence reports."""

    def __init__(self, report_dir: str = "automation/reports", **kwargs):
        super().__init__(name="WeeklyIntelligenceAgent", **kwargs)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    async def _run(self, result: AgentResult) -> AgentResult:
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        # ── Gather intelligence data ──────────────────────────────────────────
        logger.info("[%s] Gathering intelligence data", self.name)
        intel = await self._gather_intelligence()

        # ── Generate report ───────────────────────────────────────────────────
        logger.info("[%s] Generating report", self.name)
        if self._ai:
            report_content = await self._generate_ai_report(intel, date_str)
        else:
            report_content = self._generate_template_report(intel, date_str)

        # ── Save report ───────────────────────────────────────────────────────
        report_path = self.report_dir / f"{date_str}-weekly-intelligence.md"
        report_path.write_text(report_content, encoding="utf-8")
        logger.info("[%s] Report saved: %s", self.name, report_path)

        # ── Commit to Git ─────────────────────────────────────────────────────
        committed = self._commit_report(report_path, date_str)

        result.items_processed = 1
        result.items_created = 1 if committed else 0
        result.insights.append(f"Weekly intelligence report generated: {report_path.name}")
        result.metadata["report_path"] = str(report_path)
        result.metadata["git_committed"] = committed
        return result

    # ── Intelligence data gathering ───────────────────────────────────────────

    async def _gather_intelligence(self) -> Dict:
        intel = {}

        intel["top_repos"] = await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.innovation_score IS NOT NULL
            RETURN r.full_name AS name, r.innovation_score AS score,
                   r.primary_sector AS sector, r.stars AS stars,
                   r.disruption_score AS disruption,
                   r.startup_score AS startup,
                   r.description AS description
            ORDER BY r.innovation_score DESC
            LIMIT 20
        """)

        intel["high_disruption"] = await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.disruption_score >= 70
            RETURN r.full_name AS name, r.disruption_score AS score,
                   r.primary_sector AS sector, r.stars AS stars
            ORDER BY r.disruption_score DESC
            LIMIT 10
        """)

        intel["top_startup_opportunities"] = await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.startup_score >= 65
            RETURN r.full_name AS name, r.startup_score AS score,
                   r.primary_sector AS sector, r.stars AS stars,
                   r.fintech_domains AS domains
            ORDER BY r.startup_score DESC
            LIMIT 10
        """)

        intel["growing_technologies"] = await self._neo4j_query("""
            MATCH (t:Technology)<-[:IMPLEMENTS]-(r:Repository)
            RETURN t.name AS technology, t.category AS category,
                   count(r) AS repo_count,
                   avg(r.innovation_score) AS avg_score
            ORDER BY repo_count DESC
            LIMIT 15
        """)

        intel["sector_distribution"] = await self._neo4j_query("""
            MATCH (r:Repository)-[:RELEVANT_TO]->(fs:FinancialSector)
            RETURN fs.name AS sector, count(r) AS repo_count,
                   avg(r.innovation_score) AS avg_innovation_score
            ORDER BY repo_count DESC
        """)

        intel["regtech_signals"] = await self._neo4j_query("""
            MATCH (r:Repository)-[:SUPPORTS_COMPLIANCE]->(rl:Regulation)
            WHERE r.regulatory_relevance_score >= 60
            RETURN r.full_name AS repo, rl.name AS regulation,
                   r.regulatory_relevance_score AS relevance_score
            ORDER BY r.regulatory_relevance_score DESC
            LIMIT 15
        """)

        intel["contributor_hotspots"] = await self._neo4j_query("""
            MATCH (d:Developer)-[:CONTRIBUTED_TO]->(r:Repository)
            WHERE d.location IS NOT NULL AND d.location <> ""
            WITH d.location AS location, count(distinct r) AS repo_count,
                 avg(r.innovation_score) AS avg_score
            WHERE repo_count >= 3
            RETURN location, repo_count, avg_score
            ORDER BY repo_count DESC
            LIMIT 15
        """)

        intel["new_repos_this_week"] = await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.last_ingested_at >= datetime() - duration({days: 7})
            RETURN count(r) AS count
        """)

        intel["platform_stats"] = await self._neo4j_query("""
            MATCH (r:Repository) WITH count(r) AS total_repos
            MATCH (d:Developer) WITH total_repos, count(d) AS total_devs
            MATCH (t:Technology) WITH total_repos, total_devs, count(t) AS total_techs
            RETURN total_repos, total_devs, total_techs
        """)

        return intel

    # ── AI-powered report generation ──────────────────────────────────────────

    async def _generate_ai_report(self, intel: Dict, date_str: str) -> str:
        data_summary = self._format_intel_for_prompt(intel)

        try:
            message = await self._ai.messages.create(
                model="claude-opus-4-6",
                max_tokens=4000,
                system="You are an expert fintech intelligence analyst writing professional weekly reports.",
                messages=[{
                    "role": "user",
                    "content": REPORT_GENERATION_PROMPT.format(data=data_summary),
                }],
            )
            ai_content = message.content[0].text if message.content else ""
            header = self._report_header(date_str, intel)
            return f"{header}\n\n{ai_content}\n\n---\n*Generated by FinTech Intelligence Terminal — {date_str}*"
        except Exception as exc:
            logger.error("[%s] AI report generation failed: %s", self.name, exc)
            return self._generate_template_report(intel, date_str)

    def _generate_template_report(self, intel: Dict, date_str: str) -> str:
        """Fallback template-based report when AI is unavailable."""
        stats = intel.get("platform_stats", [{}])[0] if intel.get("platform_stats") else {}
        new_repos = intel.get("new_repos_this_week", [{}])[0] if intel.get("new_repos_this_week") else {}

        lines = [
            self._report_header(date_str, intel),
            "",
            "## Executive Summary",
            "",
            f"This week's scan covered **{stats.get('total_repos', 0):,} repositories**, "
            f"**{stats.get('total_devs', 0):,} developers**, and "
            f"**{stats.get('total_techs', 0):,} distinct technologies**.",
            f"**{new_repos.get('count', 0):,} new repositories** were ingested this week.",
            "",
            "## Top Emerging Repositories",
            "",
            "| Repository | Sector | Stars | Innovation Score | Disruption Score |",
            "|---|---|---|---|---|",
        ]

        for r in intel.get("top_repos", [])[:10]:
            lines.append(
                f"| [{r.get('name','')}] | {r.get('sector','')} | "
                f"{r.get('stars',0):,} | {r.get('score',0):.1f} | {r.get('disruption',0):.1f} |"
            )

        lines += [
            "",
            "## High Disruption Potential",
            "",
            "| Repository | Sector | Disruption Score |",
            "|---|---|---|",
        ]

        for r in intel.get("high_disruption", []):
            lines.append(
                f"| {r.get('name','')} | {r.get('sector','')} | **{r.get('score',0):.1f}** |"
            )

        lines += [
            "",
            "## Startup Opportunity Signals",
            "",
            "| Repository | Sector | Startup Score |",
            "|---|---|---|",
        ]

        for r in intel.get("top_startup_opportunities", []):
            lines.append(
                f"| {r.get('name','')} | {r.get('sector','')} | {r.get('score',0):.1f} |"
            )

        lines += [
            "",
            "## Growing Technologies",
            "",
            "| Technology | Category | Repositories | Avg Score |",
            "|---|---|---|---|",
        ]

        for t in intel.get("growing_technologies", []):
            lines.append(
                f"| {t.get('technology','')} | {t.get('category','')} | "
                f"{t.get('repo_count',0)} | {t.get('avg_score',0):.1f} |"
            )

        lines += [
            "",
            "## RegTech Compliance Signals",
            "",
            "| Repository | Regulation | Relevance Score |",
            "|---|---|---|",
        ]

        for r in intel.get("regtech_signals", []):
            lines.append(
                f"| {r.get('repo','')} | {r.get('regulation','')} | {r.get('relevance_score',0):.1f} |"
            )

        lines += [
            "",
            "---",
            f"*Generated by FinTech Intelligence Terminal — {date_str}*",
        ]

        return "\n".join(lines)

    def _report_header(self, date_str: str, intel: Dict) -> str:
        return f"""# FinTech Intelligence Terminal — Weekly Report
**Date:** {date_str}
**Classification:** Open Intelligence

---"""

    def _format_intel_for_prompt(self, intel: Dict) -> str:
        import json
        # Truncate for prompt efficiency
        summary = {
            "top_repos": intel.get("top_repos", [])[:10],
            "high_disruption": intel.get("high_disruption", []),
            "startup_opportunities": intel.get("top_startup_opportunities", []),
            "growing_technologies": intel.get("growing_technologies", [])[:10],
            "regtech_signals": intel.get("regtech_signals", [])[:8],
            "platform_stats": intel.get("platform_stats", []),
        }
        return json.dumps(summary, indent=2, default=str)

    # ── Git commit ────────────────────────────────────────────────────────────

    def _commit_report(self, report_path: Path, date_str: str) -> bool:
        try:
            subprocess.run(["git", "add", str(report_path)], check=True, capture_output=True)
            msg = f"Weekly FinTech Intelligence Update — {date_str}"
            subprocess.run(
                ["git", "commit", "-m", msg, "--allow-empty"],
                check=True, capture_output=True
            )
            logger.info("[%s] Report committed to git", self.name)
            return True
        except subprocess.CalledProcessError as exc:
            logger.warning("[%s] Git commit failed: %s", self.name, exc.stderr.decode())
            return False
