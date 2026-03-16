"""
GitKT FinTech OSS Index — Publisher
=====================================
Renders a computed GitKTIndex into three publishable formats:

  1. LaTeX  — arXiv-compatible .tex file (submittable to cs.IR / q-fin.CP)
  2. Markdown — GitHub README / blog post / SSRN abstract page
  3. JSON   — API payload, machine-readable archive

arXiv submission notes
───────────────────────
  Category : cs.IR (Information Retrieval) or q-fin.CP (Computational Finance)
  License  : CC BY 4.0
  Authors  : FinTech Intelligence Terminal; Nithesh Gudipuri
  Format   : PDFLaTeX — submit the .tex + no additional style files needed

SSRN submission notes
──────────────────────
  Upload the generated PDF (compile the .tex locally with pdflatex).
  Paste the Markdown abstract into the SSRN abstract field.
  Series: Finance / FinTech
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ai_agents.reporting.gitkt_index_agent import (
    GitKTIndex,
    BreakoutPrediction,
    AcquisitionPrediction,
    TechSurge,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _latex_escape(s: str) -> str:
    """Escape LaTeX special characters in plain strings."""
    replacements = [
        ("\\", r"\textbackslash{}"),   # MUST be first — backslash appears in all other replacements
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
    ]
    for ch, rep in replacements:
        s = s.replace(ch, rep)
    return s


def _risk_level(score: float) -> str:
    if score >= 7.5:
        return "\\textbf{Critical}"
    if score >= 6.0:
        return "\\textbf{Elevated}"
    if score >= 4.0:
        return "Moderate"
    return "Low"


def _velocity_arrow(v: float) -> str:
    if v > 5:
        return r"\textcolor{green!60!black}{$\uparrow\uparrow$}"
    if v > 0:
        return r"\textcolor{green!60!black}{$\uparrow$}"
    if v < -5:
        return r"\textcolor{red}{$\downarrow\downarrow$}"
    if v < 0:
        return r"\textcolor{red}{$\downarrow$}"
    return r"\textcolor{gray}{$\rightarrow$}"


# ── LaTeX renderer ─────────────────────────────────────────────────────────────

def render_latex(index: GitKTIndex) -> str:
    """
    Render a full arXiv-compatible LaTeX document for this index issue.
    Requires: pdflatex + standard CTAN packages (geometry, booktabs, xcolor, hyperref).
    """
    # Breakout table rows
    breakout_rows = ""
    for i, r in enumerate(index.predicted_breakout_repos, 1):
        name = _latex_escape(r.full_name)
        breakout_rows += (
            f"    {i} & {name} & "
            f"{r.current_score:.1f} & "
            f"{r.predicted_score_90d:.1f} & "
            f"{r.slope_per_week:+.1f} \\\\\n"
        )
    if not breakout_rows:
        breakout_rows = "    \\multicolumn{5}{c}{\\textit{No breakout signals this period}} \\\\\n"

    # Acquisition table rows
    acq_rows = ""
    for i, a in enumerate(index.predicted_acquisitions, 1):
        name = _latex_escape(a.full_name)
        rationale = _latex_escape(a.rationale.split(": ", 1)[-1][:80])
        acq_rows += (
            f"    {i} & {name} & "
            f"{a.disruption_score:.0f} & "
            f"{a.adoption_score:.0f} & "
            f"\\textit{{{rationale}}} \\\\\n"
        )
    if not acq_rows:
        acq_rows = "    \\multicolumn{5}{c}{\\textit{No acquisition-grade signals this period}} \\\\\n"

    # Technology surge rows
    surge_rows = ""
    for s in index.emerging_surges[:5]:
        name = _latex_escape(s.tech_name)
        cat  = _latex_escape(s.category)
        surge_rows += (
            f"    {name} & {cat} & "
            f"{s.repo_count_30d} & {s.repo_count_now} & "
            f"\\textbf{{+{s.mom_pct:.0f}\\%}} \\\\\n"
        )
    if not surge_rows:
        surge_rows = "    \\multicolumn{5}{c}{\\textit{No significant technology surges this period}} \\\\\n"

    # Supply chain alert
    sc_alert_tex = ""
    if index.supply_chain_alert:
        sc_alert_tex = (
            f"\\begin{{quote}}\\textbf{{Alert:}} "
            f"{_latex_escape(index.supply_chain_alert)}\\end{{quote}}"
        )

    comp_alert_tex = ""
    if index.compliance_alert:
        comp_alert_tex = (
            f"\\begin{{quote}}\\textbf{{Gap:}} "
            f"{_latex_escape(index.compliance_alert)}\\end{{quote}}"
        )

    velocity_arrow = _velocity_arrow(index.innovation_velocity_30d)
    risk_label     = _risk_level(index.supply_chain_risk_score)
    period_label   = _latex_escape(index.period)
    pub_date       = index.published_at.strftime("%B %d, %Y")

    return textwrap.dedent(rf"""
    \documentclass[11pt,a4paper]{{article}}
    \usepackage[margin=1in]{{geometry}}
    \usepackage{{booktabs}}
    \usepackage{{xcolor}}
    \usepackage{{hyperref}}
    \usepackage{{microtype}}
    \usepackage{{amsmath}}

    \hypersetup{{
        colorlinks=true,
        linkcolor=blue,
        urlcolor=blue,
        pdftitle={{GitKT FinTech OSS Index -- {period_label}}},
        pdfauthor={{FinTech Intelligence Terminal}},
    }}

    \title{{
        \textbf{{GitKT FinTech OSS Index}}\\[0.5em]
        \large Monthly Report -- {period_label}
    }}
    \author{{
        FinTech Intelligence Terminal\\
        \textit{{Autonomous AI Swarm Research Division}}\\[0.5em]
        \small Nithesh Gudipuri (Creator \& Lead Architect)\\
        \small \href{{https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech}}%
                    {{github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech}}
    }}
    \date{{{pub_date}}}

    \begin{{document}}
    \maketitle

    \begin{{abstract}}
    The \textbf{{GitKT FinTech OSS Index}} is a monthly benchmark quantifying the health,
    momentum, compliance posture, and acquisition potential of the global open-source
    FinTech ecosystem. For \textbf{{{period_label}}}, the index tracked
    \textbf{{{index.total_repos_tracked:,}}} repositories across payment infrastructure,
    DeFi, RegTech, InsurTech, and ISO 20022 tooling sectors.
    Innovation velocity stands at \textbf{{{index.innovation_velocity_30d:+.1f}\%}} (30-day),
    with a supply-chain risk score of \textbf{{{index.supply_chain_risk_score:.1f}/10}}
    ({risk_label}) and a compliance coverage gap of
    \textbf{{{index.compliance_coverage_gap:.0f}\%}} among payment repositories.
    The index identified \textbf{{{len(index.predicted_breakout_repos)}}} breakout
    repositories and \textbf{{{len(index.predicted_acquisitions)}}} acquisition-grade signals.
    \end{{abstract}}

    \tableofcontents
    \newpage

    %% ── Section 1: Headline Dashboard ─────────────────────────────────────────
    \section{{Headline Dashboard}}

    \begin{{center}}
    \begin{{tabular}}{{ll}}
    \toprule
    \textbf{{Metric}} & \textbf{{Value}} \\
    \midrule
    Total repositories tracked      & {index.total_repos_tracked:,} \\
    New repositories (30-day)       & +{index.new_repos_this_month:,} \\
    Active contributors (30-day)    & {index.active_contributors_30d:,} \\
    Innovation velocity (30-day)    & {velocity_arrow} {index.innovation_velocity_30d:+.1f}\% \\
    Compliance coverage gap         & {index.compliance_coverage_gap:.0f}\% of payment repos \\
    Supply-chain risk score         & {index.supply_chain_risk_score:.1f}/10 ({risk_label}) \\
    Regulatory gaps detected        & {index.regulatory_gaps_detected} repos without framework coverage \\
    Highest disruption score        & {index.highest_disruption_score:.0f}/100 \\
    \bottomrule
    \end{{tabular}}
    \end{{center}}

    %% ── Section 2: Compliance Posture ─────────────────────────────────────────
    \section{{Compliance Posture}}

    {comp_alert_tex}

    \textbf{{{index.compliance_coverage_gap:.0f}\%}} of tracked payment repositories
    lack BSA/AML control coverage, representing a structural gap in the open-source
    FinTech supply chain. Repositories with compliance scores below the 40th percentile
    were flagged for human-in-the-loop review via the GitKT HITL queue.

    %% ── Section 3: Supply-Chain Risk ──────────────────────────────────────────
    \section{{Supply-Chain Risk}}

    {sc_alert_tex}

    The weighted supply-chain risk score of \textbf{{{index.supply_chain_risk_score:.1f}/10}}
    is derived from vulnerability assessments of critical transitive dependencies
    across all tracked repositories. Scores $\geq 6.5$ trigger automated alerts
    to the dependency graph maintained by the DependencyAnalysisAgent (Agent 7).

    %% ── Section 4: Emerging Technology Surges ─────────────────────────────────
    \section{{Emerging Technology Surges}}

    The following technologies exhibited the strongest month-over-month growth
    in repository adoption. Surges are computed by comparing the count of
    repositories \texttt{{[:IMPLEMENTS]}} each technology node between this
    period and 30 days prior.

    \begin{{center}}
    \begin{{tabular}}{{lllrr}}
    \toprule
    \textbf{{Technology}} & \textbf{{Category}} &
    \textbf{{Repos (30d ago)}} & \textbf{{Repos (now)}} & \textbf{{MoM Growth}} \\
    \midrule
    {surge_rows}\bottomrule
    \end{{tabular}}
    \end{{center}}

    %% ── Section 5: Predicted Breakout Repositories ────────────────────────────
    \section{{Predicted Breakout Repositories}}

    Repositories classified as \texttt{{BREAKOUT}} or \texttt{{ACCELERATING}} by the
    FutureSignalAgent (Agent 11) based on a minimum slope of
    $\geq 5$ score-points/week over their historical snapshot trajectory.

    \begin{{center}}
    \begin{{tabular}}{{rlrrl}}
    \toprule
    \textbf{{\#}} & \textbf{{Repository}} & \textbf{{Score Now}} &
    \textbf{{Score (90d)}} & \textbf{{Slope (pts/wk)}} \\
    \midrule
    {breakout_rows}\bottomrule
    \end{{tabular}}
    \end{{center}}

    %% ── Section 6: Acquisition-Grade Signals ──────────────────────────────────
    \section{{Acquisition-Grade Signals}}

    Repositories meeting the acquisition-signal threshold:
    disruption score $\geq 80$, adoption score $\geq 60$, and
    $\geq 2$ institutional contributor organisations.

    \begin{{center}}
    \begin{{tabular}}{{rlrrp{{6cm}}}}
    \toprule
    \textbf{{\#}} & \textbf{{Repository}} & \textbf{{Disruption}} &
    \textbf{{Adoption}} & \textbf{{Rationale}} \\
    \midrule
    {acq_rows}\bottomrule
    \end{{tabular}}
    \end{{center}}

    %% ── Section 7: Methodology ────────────────────────────────────────────────
    \section{{Methodology}}

    \subsection{{Data Collection}}
    Repositories are discovered via GitHub and GitLab APIs and ingested
    through a fault-tolerant Celery pipeline using a rotating PAT token pool.
    Data is persisted in a Neo4j knowledge graph updated weekly.

    \subsection{{Scoring Agents}}
    Twelve specialised AI agents run autonomously:
    (1)~RepositoryDiscovery, (2)~TechnologyClassification,
    (3)~RegulatoryAnalysis, (4)~ContributorNetwork,
    (5)~AdoptionOpportunity, (6)~DisruptionPrediction,
    (7)~DependencyAnalysis, (8)~InnovationSignal,
    (9)~WeeklyIntelligence, (10)~FutureSignal,
    (11)~ExternalSignalCorrelator, (12)~MetaLearningOrchestrator.

    \subsection{{Index Computation}}
    The GitKTIndexAgent (Agent 13) aggregates outputs of all twelve agents
    into the headline metrics. Weight parameters are auto-tuned monthly by
    the MetaLearningOrchestrator based on observed prediction accuracy.

    \subsection{{Reproducibility}}
    All source code, Cypher queries, and agent prompts are publicly available at:\\
    \href{{https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech}}%
    {{https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech}}

    %% ── Section 8: Citation ───────────────────────────────────────────────────
    \section{{How to Cite}}

    \begin{{quote}}
    Gudipuri, N., \& FinTech Intelligence Terminal. ({index.published_at.year}).
    \textit{{GitKT FinTech OSS Index -- {period_label}}}.
    GitKT Research. \url{{https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech}}
    \end{{quote}}

    \vfill
    \hrule
    \small
    \textit{{Generated autonomously by the FinTech Intelligence Terminal.
    Data sourced from public GitHub/GitLab APIs, arXiv, USPTO PatentsView, and curated
    regulatory sandbox registries. This report is licensed under CC BY 4.0.}}

    \end{{document}}
    """).strip()


# ── Markdown renderer ──────────────────────────────────────────────────────────

def render_markdown(index: GitKTIndex) -> str:
    """
    Render the index as GitHub-flavoured Markdown.
    Suitable for: GitHub README, SSRN abstract, blog post, LinkedIn article.
    """
    pub_date = index.published_at.strftime("%B %d, %Y")

    velocity_icon = "📈" if index.innovation_velocity_30d > 0 else "📉"
    risk_icon     = "🔴" if index.supply_chain_risk_score >= 6.5 else "🟡" if index.supply_chain_risk_score >= 4 else "🟢"

    # Breakout repos list
    breakout_list = ""
    for r in index.predicted_breakout_repos:
        breakout_list += (
            f"| `{r.full_name}` | {r.current_score:.1f} | {r.predicted_score_90d:.1f} "
            f"| {r.slope_per_week:+.1f} pts/wk | {r.trajectory_class} |\n"
        )
    if not breakout_list:
        breakout_list = "| — | — | — | — | No breakout signals |\n"

    # Acquisition candidates list
    acq_list = ""
    for a in index.predicted_acquisitions:
        rationale = a.rationale.split(": ", 1)[-1][:100]
        acq_list += f"| `{a.full_name}` | {a.disruption_score:.0f} | {a.adoption_score:.0f} | {rationale} |\n"
    if not acq_list:
        acq_list = "| — | — | — | No acquisition signals |\n"

    # Technology surges
    surge_list = ""
    for s in index.emerging_surges[:5]:
        surge_list += f"| **{s.tech_name}** | {s.category} | {s.repo_count_30d} → {s.repo_count_now} | **+{s.mom_pct:.0f}% MoM** |\n"
    if not surge_list:
        surge_list = "| — | — | — | No significant surges |\n"

    alerts = ""
    if index.supply_chain_alert:
        alerts += f"\n> ⚠️ **Supply-Chain Alert:** {index.supply_chain_alert}\n"
    if index.compliance_alert:
        alerts += f"\n> ⚠️ **Compliance Gap:** {index.compliance_alert}\n"

    return f"""# 📊 GitKT FinTech OSS Index — {index.period}
> *The S&P 500 equivalent for open-source FinTech health — published monthly*
>
> Published: {pub_date} | [Source Code](https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech)

---

## Headline Metrics

| Metric | Value |
|--------|-------|
| 🏦 Total repositories tracked | **{index.total_repos_tracked:,}** |
| 🆕 New repositories (30-day) | +{index.new_repos_this_month:,} |
| 👥 Active contributors (30-day) | {index.active_contributors_30d:,} |
| {velocity_icon} Innovation velocity (30-day) | **{index.innovation_velocity_30d:+.1f}%** |
| 🛡️ Compliance coverage gap | **{index.compliance_coverage_gap:.0f}%** of payment repos |
| {risk_icon} Supply-chain risk score | **{index.supply_chain_risk_score:.1f}/10** |
| 🔍 Regulatory gaps detected | {index.regulatory_gaps_detected} repos without framework coverage |
| 💥 Highest disruption score | {index.highest_disruption_score:.0f}/100 |
{alerts}

---

## 🚀 Predicted Breakout Repositories

| Repository | Score Now | Score (90d) | Slope | Class |
|------------|-----------|-------------|-------|-------|
{breakout_list}
*Trajectory computed by FutureSignalAgent using linear regression over Neo4j score snapshots.*

---

## 🎯 Acquisition-Grade Signals

| Repository | Disruption | Adoption | Rationale |
|------------|-----------|---------|-----------|
{acq_list}
*Threshold: disruption ≥ 80, adoption ≥ 60, ≥ 2 institutional contributor orgs.*

---

## ⚡ Emerging Technology Surges

| Technology | Category | Repos (30d ago → now) | MoM Growth |
|-----------|---------|----------------------|------------|
{surge_list}

---

## Methodology

The GitKT FinTech OSS Index aggregates outputs from **12 autonomous AI agents** running
continuously on a Neo4j knowledge graph of open-source FinTech repositories:

| Agent | Function |
|-------|----------|
| 1. RepositoryDiscovery | GitHub/GitLab ingestion |
| 2. TechnologyClassification | Claude AI sector + tech tagging |
| 3. RegulatoryAnalysis | Compliance risk scoring |
| 4. ContributorNetwork | Developer graph + institutional mapping |
| 5. AdoptionOpportunity | Sector-specific adoption readiness |
| 6. DisruptionPrediction | ML-based disruption scoring |
| 7. DependencyAnalysis | Supply-chain + blast-radius mapping |
| 8. InnovationSignal | Velocity + concept clustering |
| 9. WeeklyIntelligence | Claude-generated narrative reports |
| 10. FutureSignalAgent | 30/90/180-day score forecasting |
| 11. ExternalSignalCorrelator | arXiv + USPTO + jobs + sandboxes |
| 12. MetaLearningOrchestrator | Autonomous weight tuning + accuracy tracking |

Weights are auto-tuned monthly by the MetaLearningOrchestrator based on observed
prediction accuracy. Full methodology and source code available at:
[github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech](https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech)

---

## How to Cite

```bibtex
@techreport{{gitkt-index-{index.period.replace("-", "")},
  author  = {{Gudipuri, Nithesh and {{FinTech Intelligence Terminal}}}},
  title   = {{GitKT FinTech OSS Index -- {index.period}}},
  year    = {{{index.published_at.year}}},
  month   = {{{index.published_at.month}}},
  url     = {{https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech}},
  note    = {{Generated autonomously by the GitKT AI swarm}}
}}
```

---
*Data sourced from public GitHub/GitLab APIs, arXiv, USPTO PatentsView, and curated
regulatory sandbox registries. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).*
"""


# ── JSON renderer ──────────────────────────────────────────────────────────────

def render_json(index: GitKTIndex, indent: int = 2) -> str:
    """Render the index as a clean JSON string (for API responses and archiving)."""
    return json.dumps(index.to_dict(), indent=indent, default=str)


# ── File writer ────────────────────────────────────────────────────────────────

class IndexPublisher:
    """
    Write all three formats to disk under a configurable output directory.

    Directory layout:
        {output_dir}/
            {period}/
                gitkt-index-{period}.tex      ← arXiv submission
                gitkt-index-{period}.md       ← GitHub / SSRN abstract
                gitkt-index-{period}.json     ← API archive

    Usage:
        pub = IndexPublisher("/path/to/reports")
        paths = pub.publish(index)
        print(paths["latex"])  # path to .tex file
    """

    def __init__(self, output_dir: str = "automation/index-reports") -> None:
        self.output_dir = Path(output_dir)

    def publish(self, index: GitKTIndex) -> dict:
        """Write all three formats. Returns dict of {format: path}."""
        issue_dir = self.output_dir / index.period
        issue_dir.mkdir(parents=True, exist_ok=True)

        stem  = f"gitkt-index-{index.period}"
        paths = {}

        # LaTeX
        tex_path = issue_dir / f"{stem}.tex"
        tex_path.write_text(render_latex(index), encoding="utf-8")
        paths["latex"] = str(tex_path)

        # Markdown
        md_path = issue_dir / f"{stem}.md"
        md_path.write_text(render_markdown(index), encoding="utf-8")
        paths["markdown"] = str(md_path)

        # JSON
        json_path = issue_dir / f"{stem}.json"
        json_path.write_text(render_json(index), encoding="utf-8")
        paths["json"] = str(json_path)

        return paths
