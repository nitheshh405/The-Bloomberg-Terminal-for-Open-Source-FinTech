"""
Unit tests — AutonomousDocsAgent
==================================
All pure-logic tests — no Neo4j, no filesystem writes (uses tmp_path fixture).
"""

from __future__ import annotations

import re
import pytest
from datetime import datetime, timezone
from pathlib import Path

from ai_agents.orchestration.autonomous_docs_agent import (
    LiveMetrics,
    AGENT_REGISTRY,
    _build_live_metrics_badge_block,
    _build_changelog_entry,
    _build_agents_md,
    _patch_section,
    AutonomousDocsAgent,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _metrics(
    total_repos: int = 47_832,
    avg_score: float = 68.4,
    breakouts: int = 5,
    total_devs: int = 8_941,
    compliance_gap: float = 23.0,
    repos_this_week: int = 1_203,
) -> LiveMetrics:
    return LiveMetrics(
        total_repos      = total_repos,
        avg_score        = avg_score,
        breakouts        = breakouts,
        total_devs       = total_devs,
        compliance_gap   = compliance_gap,
        repos_this_week  = repos_this_week,
        top_contributors = [],
        recent_breakouts = [
            {"full_name": "org/fintech-a", "slope": 7.2},
            {"full_name": "org/fintech-b", "slope": 5.8},
        ],
        agent_accuracies = [],
        computed_at      = datetime(2026, 3, 10, 6, 0, tzinfo=timezone.utc),
    )


# ── AGENT_REGISTRY ────────────────────────────────────────────────────────────

class TestAgentRegistry:
    def test_has_14_agents(self):
        assert len(AGENT_REGISTRY) == 14

    def test_all_have_required_keys(self):
        required = {"number", "name", "module", "schedule", "purpose", "writes", "extends"}
        for a in AGENT_REGISTRY:
            missing = required - set(a.keys())
            assert not missing, f"Agent {a.get('number')} missing keys: {missing}"

    def test_numbers_are_sequential(self):
        numbers = [a["number"] for a in AGENT_REGISTRY]
        assert numbers == list(range(1, 15))

    def test_all_modules_start_with_ai_agents(self):
        for a in AGENT_REGISTRY:
            assert a["module"].startswith("ai_agents"), \
                f"Agent {a['number']} module path wrong: {a['module']}"

    def test_last_agent_is_autonomous_docs(self):
        assert AGENT_REGISTRY[-1]["name"] == "AutonomousDocsAgent"

    def test_meta_learning_is_agent_12(self):
        ml = next(a for a in AGENT_REGISTRY if "MetaLearning" in a["name"])
        assert ml["number"] == 12

    def test_future_signal_is_agent_10(self):
        fs = next(a for a in AGENT_REGISTRY if "FutureSignal" in a["name"])
        assert fs["number"] == 10


# ── _build_live_metrics_badge_block ───────────────────────────────────────────

class TestBuildLiveMetricsBadgeBlock:
    def test_contains_repo_count(self):
        block = _build_live_metrics_badge_block(_metrics())
        assert "47,832" in block

    def test_contains_avg_score(self):
        block = _build_live_metrics_badge_block(_metrics())
        assert "68.4" in block

    def test_compliance_gap_red_when_high(self):
        block = _build_live_metrics_badge_block(_metrics(compliance_gap=30.0))
        assert "🔴" in block

    def test_compliance_gap_yellow_when_medium(self):
        block = _build_live_metrics_badge_block(_metrics(compliance_gap=15.0))
        assert "🟡" in block

    def test_compliance_gap_green_when_low(self):
        block = _build_live_metrics_badge_block(_metrics(compliance_gap=5.0))
        assert "🟢" in block

    def test_is_markdown_table(self):
        block = _build_live_metrics_badge_block(_metrics())
        assert "|" in block and "**" in block


# ── _build_changelog_entry ────────────────────────────────────────────────────

class TestBuildChangelogEntry:
    def test_contains_week_date(self):
        entry = _build_changelog_entry(_metrics(), "2026-03-10", ["org/repo-a"])
        assert "2026-03-10" in entry

    def test_contains_breakout_names(self):
        entry = _build_changelog_entry(_metrics(), "2026-03-10", ["org/repo-a", "org/repo-b"])
        assert "org/repo-a" in entry
        assert "org/repo-b" in entry

    def test_empty_breakouts_handled(self):
        entry = _build_changelog_entry(_metrics(), "2026-03-10", [])
        assert "None this week" in entry

    def test_contains_agent_attribution(self):
        entry = _build_changelog_entry(_metrics(), "2026-03-10", [])
        assert "AutonomousDocsAgent" in entry

    def test_contains_repo_count(self):
        entry = _build_changelog_entry(_metrics(), "2026-03-10", [])
        assert "47,832" in entry or "47832" in entry


# ── _build_agents_md ─────────────────────────────────────────────────────────

class TestBuildAgentsMd:
    def test_contains_all_14_agents(self):
        md = _build_agents_md(AGENT_REGISTRY)
        for a in AGENT_REGISTRY:
            assert a["name"] in md

    def test_has_do_not_edit_warning(self):
        md = _build_agents_md(AGENT_REGISTRY)
        assert "not edit manually" in md.lower() or "do not edit" in md.lower()

    def test_agent_count_in_header(self):
        md = _build_agents_md(AGENT_REGISTRY)
        assert "14" in md

    def test_module_paths_present(self):
        md = _build_agents_md(AGENT_REGISTRY)
        assert "ai_agents.orchestration.meta_learning_orchestrator" in md

    def test_each_agent_has_extend_guidance(self):
        md = _build_agents_md(AGENT_REGISTRY)
        # Each agent entry should have "How to extend"
        assert md.count("How to extend") == len(AGENT_REGISTRY)


# ── _patch_section ────────────────────────────────────────────────────────────

class TestPatchSection:
    def _doc(self) -> str:
        return (
            "# README\n\n"
            "Some content.\n\n"
            "<!-- LIVE_METRICS_START -->\n"
            "| Old | Data |\n"
            "<!-- LIVE_METRICS_END -->\n\n"
            "More content.\n"
        )

    def test_replaces_section(self):
        new_body = "| New | Metrics |"
        result = _patch_section(self._doc(), "LIVE_METRICS", new_body)
        assert "| New | Metrics |" in result
        assert "| Old | Data |" not in result

    def test_preserves_surrounding_content(self):
        new_body = "| New | Metrics |"
        result = _patch_section(self._doc(), "LIVE_METRICS", new_body)
        assert "# README" in result
        assert "More content." in result

    def test_sentinels_preserved_in_output(self):
        result = _patch_section(self._doc(), "LIVE_METRICS", "| x | y |")
        assert "<!-- LIVE_METRICS_START -->" in result
        assert "<!-- LIVE_METRICS_END -->" in result

    def test_missing_sentinel_returns_original(self):
        doc    = "# No sentinels here\n"
        result = _patch_section(doc, "LIVE_METRICS", "new body")
        assert result == doc


# ── AutonomousDocsAgent file operations ───────────────────────────────────────

class TestAutonomousDocsAgentFiles:
    """Tests that use tmp_path — no real repo writes."""

    def _setup_repo(self, tmp_path: Path, include_sentinels: bool = True) -> Path:
        readme_content = (
            "# FinTech Intelligence Terminal\n\n"
            "## Live Metrics\n\n"
            "| Metric | Value |\n"
            "|--------|-------|\n"
        )
        if include_sentinels:
            readme_content += (
                "<!-- LIVE_METRICS_START -->\n"
                "| 🏦 Old | **0** |\n"
                "<!-- LIVE_METRICS_END -->\n"
            )
        readme_content += "\nMore content here.\n"
        (tmp_path / "README.md").write_text(readme_content)
        (tmp_path / "CONTRIBUTING.md").write_text(
            "# Contributing\n\n**10** autonomous agents are running.\n| Agents | 10 |\n"
        )
        return tmp_path

    def _make_agent(self, tmp_path: Path) -> AutonomousDocsAgent:
        """Agent with no Neo4j driver — only tests file operations directly."""
        agent = object.__new__(AutonomousDocsAgent)
        agent._driver = None
        agent._root   = tmp_path
        return agent

    def test_update_readme_patches_live_metrics(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        files = []
        agent._update_readme(_metrics(), files)
        result = (tmp_path / "README.md").read_text()
        assert "47,832" in result

    def test_update_readme_preserves_rest_of_file(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._update_readme(_metrics(), [])
        result = (tmp_path / "README.md").read_text()
        assert "More content here." in result

    def test_update_contributing_patches_agent_count(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._update_contributing([])
        result = (tmp_path / "CONTRIBUTING.md").read_text()
        assert "**14**" in result or "| Agents | 14 |" in result

    def test_append_changelog_creates_file(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._append_changelog(_metrics(), [])
        assert (tmp_path / "CHANGELOG.md").exists()

    def test_append_changelog_contains_date(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._append_changelog(_metrics(), [])
        content = (tmp_path / "CHANGELOG.md").read_text()
        assert "2026-03-10" in content

    def test_append_changelog_no_duplicate(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._append_changelog(_metrics(), [])
        agent._append_changelog(_metrics(), [])
        content = (tmp_path / "CHANGELOG.md").read_text()
        # Heading "## [2026-03-10]" must appear exactly once even after two calls
        assert content.count("## [2026-03-10]") == 1

    def test_write_agents_md_creates_file(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._write_agents_md([])
        assert (tmp_path / "AGENTS.md").exists()

    def test_write_agents_md_contains_all_agents(self, tmp_path):
        self._setup_repo(tmp_path)
        agent = self._make_agent(tmp_path)
        agent._write_agents_md([])
        content = (tmp_path / "AGENTS.md").read_text()
        assert "FutureSignalAgent" in content
        assert "MetaLearningOrchestrator" in content
        assert "AutonomousDocsAgent" in content
