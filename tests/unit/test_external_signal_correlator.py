"""
Unit tests — ExternalSignalCorrelator (Agent 12)
=================================================
Tests all four signal source scorers and the composite.
Uses mocks for all network calls — fully offline.
"""

from __future__ import annotations

import pytest

from ai_agents.signals.external_signal_correlator import (
    ArxivPaper,
    Patent,
    ExternalSignalProfile,
    SIGNAL_WEIGHTS,
    score_arxiv_signal,
    score_patent_signal,
    score_job_signal,
    score_sandbox_signal,
    check_sandbox_participation,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_paper(year: int = 2025, title: str = "FinTech ML paper") -> ArxivPaper:
    return ArxivPaper(
        title      = title,
        url        = f"https://arxiv.org/abs/2501.{year:04d}",
        published  = f"{year}-03-15",
        authors    = ["Alice Smith", "Bob Jones"],
        summary    = "Study of FinTech OSS ecosystem.",
        categories = ["q-fin.CP", "cs.CE"],
    )


def _make_patent(title: str = "Payment processing system") -> Patent:
    return Patent(
        patent_number = "US11234567",
        title         = title,
        assignee      = "JPMorgan Chase",
        grant_date    = "2025-01-15",
        url           = "https://patentsview.org/patents/US11234567",
    )


# ── Signal weights ────────────────────────────────────────────────────────────

class TestSignalWeights:
    def test_weights_sum_to_one(self):
        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_four_sources_present(self):
        assert "arxiv"   in SIGNAL_WEIGHTS
        assert "patent"  in SIGNAL_WEIGHTS
        assert "jobs"    in SIGNAL_WEIGHTS
        assert "sandbox" in SIGNAL_WEIGHTS

    def test_no_weight_is_zero(self):
        for k, v in SIGNAL_WEIGHTS.items():
            assert v > 0, f"Signal '{k}' has zero weight"


# ── arXiv signal scorer ───────────────────────────────────────────────────────

class TestArxivSignal:
    def test_no_papers_returns_zero(self):
        assert score_arxiv_signal([]) == 0.0

    def test_one_recent_paper_scores_above_zero(self):
        papers = [_make_paper(2025)]
        score  = score_arxiv_signal(papers)
        assert score > 0.0

    def test_more_recent_papers_score_higher(self):
        old_papers    = [_make_paper(2020)] * 3
        recent_papers = [_make_paper(2025)] * 3
        assert score_arxiv_signal(recent_papers) > score_arxiv_signal(old_papers)

    def test_many_recent_papers_caps_at_100(self):
        papers = [_make_paper(2025)] * 20
        assert score_arxiv_signal(papers) <= 100.0

    def test_score_bounded_0_to_100(self):
        for count in [0, 1, 5, 10, 50]:
            papers = [_make_paper(2025)] * count
            score  = score_arxiv_signal(papers)
            assert 0.0 <= score <= 100.0, f"Score {score} out of bounds for {count} papers"


# ── Patent signal scorer ──────────────────────────────────────────────────────

class TestPatentSignal:
    def test_no_patents_returns_zero(self):
        assert score_patent_signal([]) == 0.0

    def test_one_patent_scores_20(self):
        assert score_patent_signal([_make_patent()]) == 20.0

    def test_five_patents_scores_100(self):
        patents = [_make_patent()] * 5
        assert score_patent_signal(patents) == 100.0

    def test_many_patents_capped_at_100(self):
        patents = [_make_patent()] * 20
        assert score_patent_signal(patents) <= 100.0

    def test_score_increases_with_count(self):
        s1 = score_patent_signal([_make_patent()])
        s3 = score_patent_signal([_make_patent()] * 3)
        assert s3 > s1


# ── Job posting signal scorer ─────────────────────────────────────────────────

class TestJobSignal:
    def test_zero_jobs_returns_zero(self):
        assert score_job_signal(0) == 0.0

    def test_one_job_returns_non_zero(self):
        assert score_job_signal(1) > 0.0

    def test_score_increases_with_count(self):
        assert score_job_signal(10) > score_job_signal(5)
        assert score_job_signal(5)  > score_job_signal(1)

    def test_many_jobs_capped_at_100(self):
        assert score_job_signal(1000) <= 100.0

    def test_score_bounded_0_to_100(self):
        for count in [0, 1, 5, 25, 100, 500]:
            score = score_job_signal(count)
            assert 0.0 <= score <= 100.0


# ── Regulatory sandbox signal scorer ─────────────────────────────────────────

class TestSandboxSignal:
    def test_not_participant_returns_zero(self):
        assert score_sandbox_signal(False, []) == 0.0

    def test_participant_with_one_regulator_scores_above_40(self):
        score = score_sandbox_signal(True, ["FCA"])
        assert score >= 40.0

    def test_more_regulators_score_higher(self):
        s1 = score_sandbox_signal(True, ["FCA"])
        s3 = score_sandbox_signal(True, ["FCA", "SEC", "MAS"])
        assert s3 > s1

    def test_score_capped_at_100(self):
        regulators = ["FCA", "SEC", "MAS", "EBA", "FINRA", "OCC", "CFPB"]
        assert score_sandbox_signal(True, regulators) <= 100.0


# ── Sandbox curated list ──────────────────────────────────────────────────────

class TestCheckSandboxParticipation:
    def test_known_participant_detected(self):
        is_part, regulators = check_sandbox_participation("moov-io/ach")
        assert is_part is True
        assert len(regulators) > 0

    def test_unknown_repo_not_participant(self):
        is_part, regulators = check_sandbox_participation("unknown/random-repo")
        assert is_part is False
        assert regulators == []

    def test_finos_known_participant(self):
        is_part, regs = check_sandbox_participation("finos/common-domain-model")
        assert is_part is True
        assert "FCA" in regs or "SEC" in regs


# ── ExternalSignalProfile composite ──────────────────────────────────────────

class TestExternalSignalProfile:
    def _make_profile(
        self,
        arxiv_score=50.0,
        patent_score=30.0,
        job_score=40.0,
        sandbox_score=0.0,
    ) -> ExternalSignalProfile:
        p = ExternalSignalProfile(
            repo_id      = "github:org/repo",
            repo_name    = "org/repo",
            search_terms = ["moov", "ach", "payments"],
        )
        p.arxiv_signal_score   = arxiv_score
        p.patent_signal_score  = patent_score
        p.job_signal_score     = job_score
        p.sandbox_signal_score = sandbox_score
        return p

    def test_composite_uses_weights(self):
        p = self._make_profile(100.0, 0.0, 0.0, 0.0)
        composite = p.compute_composite()
        expected  = 100.0 * SIGNAL_WEIGHTS["arxiv"]
        assert abs(composite - expected) < 0.01

    def test_composite_bounded_0_to_100(self):
        p = self._make_profile(100.0, 100.0, 100.0, 100.0)
        assert p.compute_composite() <= 100.0

        p2 = self._make_profile(0.0, 0.0, 0.0, 0.0)
        assert p2.compute_composite() >= 0.0

    def test_sandbox_boosts_composite(self):
        no_sandbox   = self._make_profile(sandbox_score=0.0)
        with_sandbox = self._make_profile(sandbox_score=100.0)
        assert with_sandbox.compute_composite() > no_sandbox.compute_composite()

    def test_all_signals_contribute(self):
        """Every signal should increase the composite when raised."""
        base   = self._make_profile(0.0, 0.0, 0.0, 0.0)
        arxiv  = self._make_profile(100.0, 0.0, 0.0, 0.0)
        patent = self._make_profile(0.0, 100.0, 0.0, 0.0)
        jobs   = self._make_profile(0.0, 0.0, 100.0, 0.0)
        sandbox = self._make_profile(0.0, 0.0, 0.0, 100.0)

        for variant in [arxiv, patent, jobs, sandbox]:
            assert variant.compute_composite() > base.compute_composite()
