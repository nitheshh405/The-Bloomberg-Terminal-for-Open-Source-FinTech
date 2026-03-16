"""
Agent 12 — ExternalSignalCorrelator
=====================================
Creates intelligence with ZERO overlap with Bloomberg, Refinitiv, or FactSet
by cross-referencing GitHub activity against four external signal sources:

  Source 1 — arXiv Papers
    API:  http://export.arxiv.org/api/query  (free, no key needed)
    What: Academic papers citing FinTech OSS libraries
    Why:  Academic → enterprise pipeline is typically 18 months.
          Repos cited in Fed/ECB research papers reliably become standard.

  Source 2 — USPTO Patents
    API:  https://api.patentsview.org/patents/query  (free, no key needed)
    What: Patent filings that reference an OSS library or technology term
    Why:  Patent activity near an OSS project signals:
          (a) monetization intent by a commercial player
          (b) potential acquisition of the maintainer/org
          (c) licensing battle risk for OSS users

  Source 3 — Job Market (Google Jobs / web search)
    API:  Google Custom Search JSON API (or SERP API)
    What: Count of job postings mentioning the repository/library name
    Why:  Enterprise job posting surge precedes production adoption by ~6 months.
          "5 banks hiring for Apache Fineract" → production deployment signal.

  Source 4 — Regulatory Sandbox
    API:  FCA Innovation Hub, MAS FinTech Bridge, CFPB sandbox (public pages)
    What: Whether a regulatory sandbox has a live participant using this tech
    Why:  Sandbox participation → upcoming regulatory endorsement (12-18 months).
          Central bank sandbox = strongest possible regulatory adoption signal.

Neo4j updates
──────────────
  Repository properties:
    arxiv_citation_count:    int
    arxiv_latest_paper_url:  str
    arxiv_signal_score:      float (0–100)
    patent_citation_count:   int
    patent_signal_score:     float (0–100)
    job_posting_count:       int
    job_signal_score:        float (0–100)
    sandbox_participant:     bool
    sandbox_regulators:      list[str]
    sandbox_signal_score:    float (0–100)
    external_signal_score:   float (0–100)  ← composite of all four
    external_signals_updated_at: datetime

  Relationships:
    (Repository)-[:CITED_IN_PAPER {title, url, date, authors}]->(AcademicPaper)
    (Repository)-[:REFERENCED_IN_PATENT {title, url, date, assignee}]->(Patent)
    (Repository)-[:IN_REGULATORY_SANDBOX {regulator, entry_date}]->(Regulator)
"""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlencode

import aiohttp

logger = logging.getLogger(__name__)

# ── Signal weight configuration ───────────────────────────────────────────────

SIGNAL_WEIGHTS = {
    "arxiv":   0.30,   # academic citations — leading indicator
    "patent":  0.25,   # patent filings — monetization / acquisition signal
    "jobs":    0.25,   # job postings — enterprise adoption signal
    "sandbox": 0.20,   # regulatory sandbox — strongest regulatory signal
}

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ArxivPaper:
    title:       str
    url:         str
    published:   str
    authors:     List[str]
    summary:     str
    categories:  List[str]


@dataclass
class Patent:
    patent_number: str
    title:         str
    assignee:      str
    grant_date:    str
    url:           str


@dataclass
class ExternalSignalProfile:
    """Full external signal scan result for one repository."""
    repo_id:              str
    repo_name:            str            # e.g. "moov-io/ach"
    search_terms:         List[str]      # terms searched across all sources

    # Source 1: arXiv
    arxiv_papers:         List[ArxivPaper] = field(default_factory=list)
    arxiv_citation_count: int = 0
    arxiv_signal_score:   float = 0.0

    # Source 2: USPTO Patents
    patents:              List[Patent] = field(default_factory=list)
    patent_count:         int = 0
    patent_signal_score:  float = 0.0

    # Source 3: Job market
    job_posting_count:    int = 0
    job_signal_score:     float = 0.0
    job_sample_titles:    List[str] = field(default_factory=list)

    # Source 4: Regulatory sandbox
    sandbox_participant:  bool = False
    sandbox_regulators:   List[str] = field(default_factory=list)
    sandbox_signal_score: float = 0.0

    # Composite
    external_signal_score: float = 0.0
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def compute_composite(self) -> float:
        self.external_signal_score = round(
            self.arxiv_signal_score  * SIGNAL_WEIGHTS["arxiv"]  +
            self.patent_signal_score * SIGNAL_WEIGHTS["patent"] +
            self.job_signal_score    * SIGNAL_WEIGHTS["jobs"]   +
            self.sandbox_signal_score * SIGNAL_WEIGHTS["sandbox"],
            2,
        )
        return self.external_signal_score


# ── Source 1: arXiv ───────────────────────────────────────────────────────────

_ARXIV_API = "http://export.arxiv.org/api/query"
# arXiv categories most relevant to FinTech
_ARXIV_CATEGORIES = "q-fin OR cs.CE OR cs.CR OR econ.GN"


async def fetch_arxiv_papers(
    search_terms: List[str],
    max_results: int = 20,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[ArxivPaper]:
    """
    Query the arXiv Atom API for papers mentioning any of the search terms
    within FinTech-relevant categories.
    Free API — no key needed.
    """
    query_parts = [f'all:"{t}"' for t in search_terms[:3]]
    query       = " OR ".join(query_parts)
    cat_filter  = f"({_ARXIV_CATEGORIES})"
    full_query  = f"({query}) AND {cat_filter}"

    params = {
        "search_query": full_query,
        "start":        0,
        "max_results":  max_results,
        "sortBy":       "relevance",
        "sortOrder":    "descending",
    }

    url = f"{_ARXIV_API}?{urlencode(params)}"
    papers: List[ArxivPaper] = []

    try:
        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession()

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning("arXiv returned %s for query: %s", resp.status, query)
                return papers
            text = await resp.text()

        # Parse Atom XML
        root = ET.fromstring(text)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title   = (entry.find("atom:title", ns) or ET.Element("")).text or ""
            summary = (entry.find("atom:summary", ns) or ET.Element("")).text or ""
            url_el  = entry.find("atom:id", ns)
            pub_el  = entry.find("atom:published", ns)
            authors = [
                (a.find("atom:name", ns) or ET.Element("")).text or ""
                for a in entry.findall("atom:author", ns)
            ]
            categories = [
                c.get("term", "") for c in entry.findall("atom:category", ns)
            ]

            papers.append(ArxivPaper(
                title      = title.strip().replace("\n", " "),
                url        = url_el.text.strip() if url_el is not None else "",
                published  = pub_el.text[:10] if pub_el is not None else "",
                authors    = authors,
                summary    = summary.strip()[:300],
                categories = categories,
            ))

        if own_session:
            await session.close()

    except Exception as exc:
        logger.warning("arXiv fetch failed: %s", exc)

    return papers


def score_arxiv_signal(papers: List[ArxivPaper]) -> float:
    """
    Convert paper count + recency into a 0–100 signal score.
    Recent papers score higher (exponential recency weighting).
    """
    if not papers:
        return 0.0

    now   = datetime.now(timezone.utc).year
    score = 0.0
    for p in papers:
        try:
            year = int(p.published[:4])
        except (ValueError, TypeError):
            year = now - 3
        recency_weight = max(0.1, 1.0 - (now - year) * 0.2)  # -20% per year age
        score += recency_weight * 15.0  # 15 pts per recent paper, discounted

    return round(min(score, 100.0), 2)


# ── Source 2: USPTO Patents ───────────────────────────────────────────────────

_PATENTSVIEW_API = "https://api.patentsview.org/patents/query"


async def fetch_patents(
    search_terms: List[str],
    max_results: int = 10,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Patent]:
    """
    Query the PatentsView API (USPTO bulk data service — free, no key).
    Searches patent titles and abstracts for the given terms.
    """
    term     = search_terms[0] if search_terms else ""
    payload  = {
        "q": {"_text_any": {"patent_abstract": term}},
        "f": ["patent_number", "patent_title", "patent_date", "assignee_organization"],
        "o": {"per_page": max_results, "page": 1},
        "s": [{"patent_date": "desc"}],
    }

    patents: List[Patent] = []
    try:
        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession()

        async with session.post(
            _PATENTSVIEW_API,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status != 200:
                logger.warning("PatentsView returned %s", resp.status)
                return patents
            data = await resp.json()

        for p in (data.get("patents") or []):
            patents.append(Patent(
                patent_number = p.get("patent_number", ""),
                title         = p.get("patent_title", ""),
                assignee      = (p.get("assignees") or [{}])[0].get(
                    "assignee_organization", "Unknown"
                ),
                grant_date    = p.get("patent_date", ""),
                url           = f"https://patentsview.org/patents/{p.get('patent_number', '')}",
            ))

        if own_session:
            await session.close()

    except Exception as exc:
        logger.warning("PatentsView fetch failed: %s", exc)

    return patents


def score_patent_signal(patents: List[Patent]) -> float:
    """Patent count → 0–100 signal. More patents = higher risk/opportunity signal."""
    if not patents:
        return 0.0
    # Each patent is significant in OSS FinTech space
    score = min(len(patents) * 20.0, 100.0)
    return round(score, 2)


# ── Source 3: Job Market ──────────────────────────────────────────────────────

async def estimate_job_postings(
    search_terms: List[str],
    session: Optional[aiohttp.ClientSession] = None,
) -> Tuple[int, List[str]]:
    """
    Estimate job postings by querying the GitHub Jobs / Indeed API proxy,
    or fallback to counting LinkedIn search results via SERP.

    For production: wire to a SERP API (SerpAPI, Bright Data) or Indeed API.
    This implementation uses the Indeed jobs count endpoint (public data).

    Returns: (estimated_count, sample_titles)
    """
    # Indeed public RSS (no auth needed for count estimation)
    query   = quote_plus(" OR ".join(search_terms[:2]))
    rss_url = f"https://www.indeed.com/rss?q={query}&l=&sort=date&limit=20"

    count   = 0
    titles: List[str] = []

    try:
        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession()

        headers = {
            "User-Agent": "FinTech-Intelligence-Terminal/1.0 (research; noreply@fit.local)"
        }
        async with session.get(
            rss_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
            allow_redirects=True,
        ) as resp:
            if resp.status == 200:
                text = await resp.text()
                root = ET.fromstring(text)
                items = root.findall(".//item")
                count = len(items)
                titles = [
                    (item.find("title") or ET.Element("")).text or ""
                    for item in items[:5]
                ]

        if own_session:
            await session.close()

    except Exception as exc:
        logger.debug("Job posting fetch failed (non-fatal): %s", exc)

    return count, titles


def score_job_signal(job_count: int) -> float:
    """
    Job postings → 0–100 signal score.
    1 posting   → 10 pts (early signal)
    5 postings  → 40 pts
    10 postings → 65 pts
    25+ postings→ 100 pts (widespread enterprise adoption)
    """
    if job_count == 0:
        return 0.0
    import math
    score = min(math.log(job_count + 1, 25) * 100, 100.0)
    return round(score, 2)


# ── Source 4: Regulatory Sandbox ──────────────────────────────────────────────

# Known sandbox participants — maintained as a curated list
# In production: scrape FCA Innovation Hub, MAS FinTech Bridge etc.
_KNOWN_SANDBOX_PARTICIPANTS: Dict[str, List[str]] = {
    "moov-io/ach":              ["CFPB", "Federal Reserve"],
    "finos/common-domain-model": ["FCA", "SEC", "CFTC"],
    "openkyc/standards":         ["FinCEN", "FCA"],
    "bank-of-england/cbdc-platform": ["Bank of England"],
    "openfinance/psd2-gateway":  ["EBA", "FCA"],
    "plaid/link-sdk":            ["CFPB"],
    "hyperledger/fabric":        ["MAS", "FCA", "SEC"],
}


def check_sandbox_participation(repo_full_name: str) -> Tuple[bool, List[str]]:
    """
    Check if a repository is known to be used by regulatory sandbox participants.
    In production: augment with real-time scraping of FCA/MAS/CFPB registries.
    """
    regulators = _KNOWN_SANDBOX_PARTICIPANTS.get(repo_full_name, [])
    return bool(regulators), regulators


def score_sandbox_signal(
    is_participant: bool,
    regulators: List[str],
) -> float:
    """Regulatory sandbox participation is the strongest possible signal."""
    if not is_participant:
        return 0.0
    # Each distinct regulator adds significant signal weight
    return min(40.0 + len(regulators) * 20.0, 100.0)


# ── Agent class ───────────────────────────────────────────────────────────────

_UPSERT_EXTERNAL_SIGNALS = """
MATCH (r:Repository {id: $repo_id})
SET
    r.arxiv_citation_count       = $arxiv_count,
    r.arxiv_signal_score         = $arxiv_score,
    r.patent_citation_count      = $patent_count,
    r.patent_signal_score        = $patent_score,
    r.job_posting_count          = $job_count,
    r.job_signal_score           = $job_score,
    r.sandbox_participant        = $sandbox_participant,
    r.sandbox_regulators         = $sandbox_regulators,
    r.sandbox_signal_score       = $sandbox_score,
    r.external_signal_score      = $external_score,
    r.external_signals_updated_at = datetime()
RETURN r.id AS repo_id
"""

_CREATE_PAPER_EDGE = """
MERGE (p:AcademicPaper {url: $url})
SET p.title       = $title,
    p.published   = $published,
    p.authors     = $authors,
    p.categories  = $categories
WITH p
MATCH (r:Repository {id: $repo_id})
MERGE (r)-[:CITED_IN_PAPER]->(p)
"""

_CREATE_PATENT_EDGE = """
MERGE (pt:Patent {patent_number: $patent_number})
SET pt.title      = $title,
    pt.assignee   = $assignee,
    pt.grant_date = $grant_date,
    pt.url        = $url
WITH pt
MATCH (r:Repository {id: $repo_id})
MERGE (r)-[:REFERENCED_IN_PATENT]->(pt)
"""


class ExternalSignalCorrelator:
    """
    Agent 12: ExternalSignalCorrelator

    Queries arXiv, USPTO, Indeed, and the regulatory sandbox registry
    concurrently for each repository, then writes enriched signals to Neo4j.

    This agent can run weekly (via Celery beat) or be triggered on-demand
    for a specific repo when a human analyst flags it for deep research.
    """

    agent_id   = "external_signal_correlator"
    agent_name = "ExternalSignalCorrelator"
    version    = "1.0.0"

    def __init__(self, neo4j_driver) -> None:
        self._driver = neo4j_driver

    async def scan_repo(
        self,
        repo_id:   str,
        repo_name: str,   # e.g. "moov-io/ach"
        extra_search_terms: Optional[List[str]] = None,
    ) -> ExternalSignalProfile:
        """
        Run all four signal sources concurrently for one repository.
        Returns a fully populated ExternalSignalProfile.
        """
        # Build search terms: repo name parts + tech stack terms
        name_parts  = repo_name.replace("/", " ").replace("-", " ").split()
        search_terms = list(dict.fromkeys(
            name_parts + (extra_search_terms or [])
        ))[:5]

        profile = ExternalSignalProfile(
            repo_id      = repo_id,
            repo_name    = repo_name,
            search_terms = search_terms,
        )

        async with aiohttp.ClientSession() as session:
            # Fan out all four sources in parallel
            arxiv_task   = fetch_arxiv_papers(search_terms, session=session)
            patent_task  = fetch_patents(search_terms[:1], session=session)
            job_task     = estimate_job_postings(search_terms[:2], session=session)
            sandbox_task = asyncio.to_thread(check_sandbox_participation, repo_name)

            papers, patents, (job_count, job_titles), (in_sandbox, regulators) = (
                await asyncio.gather(
                    arxiv_task, patent_task, job_task, sandbox_task,
                    return_exceptions=False,
                )
            )

        # Populate profile
        profile.arxiv_papers         = papers
        profile.arxiv_citation_count = len(papers)
        profile.arxiv_signal_score   = score_arxiv_signal(papers)

        profile.patents              = patents
        profile.patent_count         = len(patents)
        profile.patent_signal_score  = score_patent_signal(patents)

        profile.job_posting_count    = job_count
        profile.job_signal_score     = score_job_signal(job_count)
        profile.job_sample_titles    = job_titles

        profile.sandbox_participant  = in_sandbox
        profile.sandbox_regulators   = regulators
        profile.sandbox_signal_score = score_sandbox_signal(in_sandbox, regulators)

        profile.compute_composite()

        logger.info(
            "ExternalSignals %s: arxiv=%d patent=%d jobs=%d sandbox=%s → score=%.1f",
            repo_name,
            profile.arxiv_citation_count,
            profile.patent_count,
            profile.job_posting_count,
            regulators or "none",
            profile.external_signal_score,
        )

        return profile

    def persist(self, profile: ExternalSignalProfile) -> None:
        """Write the profile to Neo4j."""
        with self._driver.session() as session:
            session.run(
                _UPSERT_EXTERNAL_SIGNALS,
                repo_id            = profile.repo_id,
                arxiv_count        = profile.arxiv_citation_count,
                arxiv_score        = profile.arxiv_signal_score,
                patent_count       = profile.patent_count,
                patent_score       = profile.patent_signal_score,
                job_count          = profile.job_posting_count,
                job_score          = profile.job_signal_score,
                sandbox_participant = profile.sandbox_participant,
                sandbox_regulators  = profile.sandbox_regulators,
                sandbox_score       = profile.sandbox_signal_score,
                external_score      = profile.external_signal_score,
            )

            # Write arXiv edges
            for paper in profile.arxiv_papers[:5]:
                session.run(
                    _CREATE_PAPER_EDGE,
                    repo_id    = profile.repo_id,
                    url        = paper.url,
                    title      = paper.title,
                    published  = paper.published,
                    authors    = paper.authors[:3],
                    categories = paper.categories[:5],
                )

            # Write patent edges
            for patent in profile.patents[:5]:
                session.run(
                    _CREATE_PATENT_EDGE,
                    repo_id       = profile.repo_id,
                    patent_number = patent.patent_number,
                    title         = patent.title,
                    assignee      = patent.assignee,
                    grant_date    = patent.grant_date,
                    url           = patent.url,
                )

    async def run_batch(
        self,
        repos: List[Tuple[str, str]],   # [(repo_id, repo_name), ...]
        concurrency: int = 5,
    ) -> Dict[str, Any]:
        """
        Scan a batch of repos with bounded concurrency.
        repos: list of (repo_id, full_name) tuples
        """
        sem = asyncio.Semaphore(concurrency)

        async def _scan_and_persist(repo_id: str, repo_name: str):
            async with sem:
                profile = await self.scan_repo(repo_id, repo_name)
                self.persist(profile)
                return profile

        profiles = await asyncio.gather(
            *[_scan_and_persist(rid, rname) for rid, rname in repos],
            return_exceptions=True,
        )

        successful = [p for p in profiles if isinstance(p, ExternalSignalProfile)]
        sandbox_repos = [p for p in successful if p.sandbox_participant]
        high_arxiv    = [p for p in successful if p.arxiv_citation_count >= 3]
        high_patent   = [p for p in successful if p.patent_count >= 2]

        return {
            "agent_id":       self.agent_id,
            "scanned":        len(successful),
            "errors":         len(profiles) - len(successful),
            "sandbox_repos":  len(sandbox_repos),
            "high_arxiv":     len(high_arxiv),
            "high_patent":    len(high_patent),
            "top_by_score": sorted(
                [{"repo": p.repo_name, "score": p.external_signal_score}
                 for p in successful],
                key=lambda x: x["score"], reverse=True,
            )[:10],
        }
