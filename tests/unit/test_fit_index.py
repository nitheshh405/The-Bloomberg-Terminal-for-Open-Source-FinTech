"""
Unit tests — FinTech Intelligence Terminal OSS Index
======================================
Tests all pure-logic functions — no Neo4j, no HTTP, no filesystem.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from ai_agents.reporting.fit_index_agent import (
    FITIndex,
    TechSurge,
    BreakoutPrediction,
    AcquisitionPrediction,
    compute_innovation_velocity,
    compute_compliance_gap,
    compute_supply_chain_risk,
    build_acquisition_rationale,
    rank_surges,
)
from ai_agents.reporting.index_publisher import (
    render_latex,
    render_markdown,
    render_json,
    _latex_escape,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_index(
    velocity: float = 12.4,
    compliance_gap: float = 23.0,
    supply_risk: float = 6.8,
    breakouts: int = 2,
    acquisitions: int = 1,
    surges: int = 2,
) -> FITIndex:
    breakout_list = [
        BreakoutPrediction(
            repo_id             = f"repo-{i}",
            full_name           = f"org/repo-{i}",
            current_score       = 72.0 + i,
            predicted_score_90d = 85.0 + i,
            slope_per_week      = 5.2 + i,
            trajectory_class    = "BREAKOUT",
        )
        for i in range(breakouts)
    ]
    acq_list = [
        AcquisitionPrediction(
            repo_id          = f"acq-{i}",
            full_name        = f"bigorg/finrepo-{i}",
            disruption_score = 88.0,
            adoption_score   = 71.0,
            contributor_orgs = 3,
            rationale        = f"bigorg/finrepo-{i}: high disruption score (88/100)",
        )
        for i in range(acquisitions)
    ]
    surge_list = [
        TechSurge(
            tech_name      = f"ISO 2022{i} Parser",
            category       = "Payments",
            repo_count_now = 340 + i * 100,
            repo_count_30d = 100,
            mom_pct        = 240.0 + i * 100,
        )
        for i in range(surges)
    ]
    return FITIndex(
        period                   = "2026-03",
        published_at             = datetime(2026, 3, 1, 6, 0, tzinfo=timezone.utc),
        total_repos_tracked      = 47_832,
        innovation_velocity_30d  = velocity,
        compliance_coverage_gap  = compliance_gap,
        supply_chain_risk_score  = supply_risk,
        new_repos_this_month     = 1_203,
        active_contributors_30d  = 8_941,
        regulatory_gaps_detected = 412,
        highest_disruption_score = 91.0,
        top_supply_chain_dep     = "urllib3",
        emerging_surges          = surge_list,
        predicted_breakout_repos = breakout_list,
        predicted_acquisitions   = acq_list,
        supply_chain_alert       = "urllib3 maintainer activity low — supply-chain risk elevated",
        compliance_alert         = "23% of tracked payment repos lack BSA/AML controls",
    )


# ── compute_innovation_velocity ────────────────────────────────────────────────

class TestComputeInnovationVelocity:
    def test_standard_case(self):
        # avg_delta=4.1, avg_base=33.1 → ~12.4%
        v = compute_innovation_velocity(4.1, 33.1)
        assert abs(v - 12.4) < 0.2

    def test_zero_base_returns_zero(self):
        assert compute_innovation_velocity(5.0, 0.0) == 0.0

    def test_negative_velocity(self):
        v = compute_innovation_velocity(-3.0, 60.0)
        assert v < 0

    def test_positive_is_positive(self):
        assert compute_innovation_velocity(2.0, 40.0) > 0

    def test_symmetry(self):
        v_pos = compute_innovation_velocity(10.0, 100.0)
        v_neg = compute_innovation_velocity(-10.0, 100.0)
        assert abs(v_pos + v_neg) < 0.001   # +10% and -10%


# ── compute_compliance_gap ────────────────────────────────────────────────────

class TestComputeComplianceGap:
    def test_23_percent(self):
        gap = compute_compliance_gap(total_payment=100, missing_bsa=23)
        assert abs(gap - 23.0) < 0.1

    def test_zero_payment_repos(self):
        assert compute_compliance_gap(0, 0) == 0.0

    def test_all_missing(self):
        assert compute_compliance_gap(50, 50) == 100.0

    def test_none_missing(self):
        assert compute_compliance_gap(100, 0) == 0.0

    def test_rounded_to_one_decimal(self):
        gap = compute_compliance_gap(3, 1)
        assert isinstance(gap, float)
        assert str(gap).split(".")[-1] in ["0", "3", "7"]  # reasonable rounding


# ── compute_supply_chain_risk ─────────────────────────────────────────────────

class TestComputeSupplyChainRisk:
    def test_elevated_score(self):
        score = compute_supply_chain_risk(avg_vuln=6.0, critical_deps=10)
        assert score >= 6.0

    def test_capped_at_10(self):
        score = compute_supply_chain_risk(avg_vuln=9.5, critical_deps=1000)
        assert score == 10.0

    def test_low_risk(self):
        score = compute_supply_chain_risk(avg_vuln=2.0, critical_deps=2)
        assert score < 4.0

    def test_zero_deps(self):
        score = compute_supply_chain_risk(avg_vuln=5.0, critical_deps=0)
        assert score == 5.0

    def test_non_negative(self):
        score = compute_supply_chain_risk(avg_vuln=0.0, critical_deps=0)
        assert score >= 0.0


# ── build_acquisition_rationale ───────────────────────────────────────────────

class TestBuildAcquisitionRationale:
    def test_includes_repo_name(self):
        r = build_acquisition_rationale("myorg/myrepo", 90.0, 70.0, 3)
        assert "myorg/myrepo" in r

    def test_exceptional_disruption(self):
        r = build_acquisition_rationale("org/repo", 92.0, 50.0, 1)
        assert "exceptional" in r.lower() or "disruption" in r.lower()

    def test_multi_institutional(self):
        r = build_acquisition_rationale("org/repo", 85.0, 65.0, 4)
        assert "institutional" in r.lower() or "org" in r.lower()

    def test_returns_string(self):
        r = build_acquisition_rationale("x/y", 0.0, 0.0, 0)
        assert isinstance(r, str) and len(r) > 0


# ── rank_surges ───────────────────────────────────────────────────────────────

class TestRankSurges:
    def _surge(self, name: str, mom: float) -> TechSurge:
        return TechSurge(
            tech_name=name, category="FinTech",
            repo_count_now=int(mom) + 100, repo_count_30d=100, mom_pct=mom,
        )

    def test_filters_noise_below_50pct(self):
        surges = [self._surge("A", 30.0), self._surge("B", 340.0)]
        ranked = rank_surges(surges)
        assert all(s.mom_pct >= 50 for s in ranked)

    def test_ordered_descending(self):
        surges = [self._surge("Low", 80.0), self._surge("High", 340.0), self._surge("Mid", 150.0)]
        ranked = rank_surges(surges)
        for i in range(len(ranked) - 1):
            assert ranked[i].mom_pct >= ranked[i + 1].mom_pct

    def test_top_n_limit(self):
        surges = [self._surge(f"Tech{i}", 100.0 + i * 10) for i in range(10)]
        assert len(rank_surges(surges, top_n=3)) <= 3

    def test_empty_input(self):
        assert rank_surges([]) == []


# ── FITIndex dataclass ───────────────────────────────────────────────────────

class TestFITIndex:
    def test_headline_contains_key_fields(self):
        idx = _make_index()
        h   = idx.headline
        assert "47,832" in h
        assert "+12.4%" in h
        assert "23%" in h
        assert "6.8/10" in h

    def test_headline_elevated_label(self):
        idx = _make_index(supply_risk=7.0)
        assert "elevated" in idx.headline.lower()

    def test_to_dict_serializable(self):
        idx = _make_index()
        d   = idx.to_dict()
        # Must be JSON-serializable
        dumped = json.dumps(d)
        assert "2026-03" in dumped

    def test_to_dict_has_published_at_string(self):
        idx = _make_index()
        d   = idx.to_dict()
        assert isinstance(d["published_at"], str)

    def test_tech_surge_label(self):
        surge = TechSurge("ISO 20022 Parser", "Payments", 440, 100, 340.0)
        assert "340%" in surge.surge_label or "+340" in surge.surge_label


# ── render_latex ──────────────────────────────────────────────────────────────

class TestRenderLatex:
    def test_produces_documentclass(self):
        tex = render_latex(_make_index())
        assert r"\documentclass" in tex

    def test_period_in_title(self):
        tex = render_latex(_make_index())
        assert "2026-03" in tex

    def test_repo_count_in_tex(self):
        tex = render_latex(_make_index())
        assert "47" in tex   # 47,832

    def test_breakout_repos_appear(self):
        tex = render_latex(_make_index(breakouts=2))
        assert "org/repo" in tex

    def test_acquisition_repos_appear(self):
        tex = render_latex(_make_index(acquisitions=1))
        assert "bigorg/finrepo" in tex

    def test_methodology_section_present(self):
        tex = render_latex(_make_index())
        assert "Methodology" in tex

    def test_citation_section_present(self):
        tex = render_latex(_make_index())
        assert "How to Cite" in tex or "Citation" in tex

    def test_latex_escape_ampersand(self):
        result = _latex_escape("BSA & AML")
        assert r"\&" in result
        assert "&" not in result.replace(r"\&", "")


# ── render_markdown ───────────────────────────────────────────────────────────

class TestRenderMarkdown:
    def test_h1_contains_period(self):
        md = render_markdown(_make_index())
        assert "# " in md and "2026-03" in md

    def test_velocity_present(self):
        md = render_markdown(_make_index(velocity=12.4))
        assert "+12.4%" in md

    def test_compliance_gap_present(self):
        md = render_markdown(_make_index(compliance_gap=23.0))
        assert "23%" in md

    def test_supply_chain_alert_in_output(self):
        md = render_markdown(_make_index(supply_risk=7.0))
        assert "Alert" in md or "supply" in md.lower()

    def test_bibtex_block_present(self):
        md = render_markdown(_make_index())
        assert "```bibtex" in md

    def test_methodology_table_present(self):
        md = render_markdown(_make_index())
        assert "RepositoryDiscovery" in md or "Agent" in md

    def test_no_breakout_graceful(self):
        md = render_markdown(_make_index(breakouts=0))
        assert "No breakout signals" in md


# ── render_json ───────────────────────────────────────────────────────────────

class TestRenderJson:
    def test_valid_json(self):
        js = render_json(_make_index())
        parsed = json.loads(js)
        assert parsed["period"] == "2026-03"

    def test_all_headline_metrics_present(self):
        parsed = json.loads(render_json(_make_index()))
        for key in [
            "total_repos_tracked", "innovation_velocity_30d",
            "compliance_coverage_gap", "supply_chain_risk_score",
        ]:
            assert key in parsed

    def test_breakout_list_serialized(self):
        parsed = json.loads(render_json(_make_index(breakouts=2)))
        assert len(parsed["predicted_breakout_repos"]) == 2

    def test_acquisition_list_serialized(self):
        parsed = json.loads(render_json(_make_index(acquisitions=1)))
        assert len(parsed["predicted_acquisitions"]) == 1
