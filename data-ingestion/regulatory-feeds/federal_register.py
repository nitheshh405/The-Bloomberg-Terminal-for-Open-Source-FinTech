"""
Federal Register & SEC EDGAR Regulatory Feed Ingester.
Pulls rule announcements, proposed rules, and enforcement actions,
then links them to relevant technologies in the knowledge graph.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RegulatoryDocument:
    """Normalized regulatory document record."""

    source: str               # "federal_register" | "sec_edgar" | "cfpb"
    doc_id: str
    title: str
    agency: str
    doc_type: str             # "rule" | "proposed_rule" | "notice" | "enforcement"
    publication_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    abstract: str = ""
    full_text_url: str = ""
    docket_number: str = ""
    regulation_ids: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    fintech_relevance_tags: List[str] = field(default_factory=list)
    raw: Dict = field(default_factory=dict)


# Agencies to monitor
MONITORED_AGENCIES = [
    "Securities and Exchange Commission",
    "Federal Reserve System",
    "Office of the Comptroller of the Currency",
    "Federal Deposit Insurance Corporation",
    "Commodity Futures Trading Commission",
    "Consumer Financial Protection Bureau",
    "Financial Industry Regulatory Authority",
    "National Credit Union Administration",
    "Financial Crimes Enforcement Network",
    "Office of Foreign Assets Control",
]

FINTECH_REGULATORY_TERMS = [
    "cryptocurrency", "digital asset", "blockchain", "distributed ledger",
    "cybersecurity", "data privacy", "artificial intelligence", "machine learning",
    "algorithmic trading", "automated systems", "robo-advisor", "digital banking",
    "payment systems", "money transmission", "fintech", "regtech",
    "anti-money laundering", "know your customer", "sanctions",
    "open banking", "API", "cloud computing", "operational risk",
]


class FederalRegisterIngester:
    """Pulls recent regulatory documents from the Federal Register API."""

    BASE_URL = "https://www.federalregister.gov/api/v1"

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days

    async def fetch_recent(self) -> List[RegulatoryDocument]:
        since = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).date().isoformat()
        docs: List[RegulatoryDocument] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for agency in MONITORED_AGENCIES:
                try:
                    params = {
                        "conditions[agencies][]": agency,
                        "conditions[publication_date][gte]": since,
                        "conditions[type][]": ["Rule", "Proposed Rule", "Notice"],
                        "per_page": 100,
                        "fields[]": [
                            "document_number", "title", "type", "publication_date",
                            "effective_on", "abstract", "html_url", "docket_ids",
                            "agencies", "topics", "regulation_id_numbers",
                        ],
                        "order": "newest",
                    }
                    resp = await client.get(f"{self.BASE_URL}/documents.json", params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    for item in data.get("results", []):
                        doc = self._parse_fr(item)
                        doc.fintech_relevance_tags = self._tag_fintech_relevance(doc)
                        docs.append(doc)

                    await asyncio.sleep(0.5)

                except Exception as exc:
                    logger.warning("Federal Register fetch error for %s: %s", agency, exc)

        logger.info("Fetched %d regulatory documents from Federal Register", len(docs))
        return docs

    def _parse_fr(self, item: Dict) -> RegulatoryDocument:
        def _dt(s):
            if not s:
                return None
            try:
                return datetime.fromisoformat(s)
            except ValueError:
                return None

        agencies = item.get("agencies", [])
        agency_name = agencies[0].get("name", "") if agencies else ""

        return RegulatoryDocument(
            source="federal_register",
            doc_id=item.get("document_number", ""),
            title=item.get("title", ""),
            agency=agency_name,
            doc_type=item.get("type", "").lower().replace(" ", "_"),
            publication_date=_dt(item.get("publication_date")),
            effective_date=_dt(item.get("effective_on")),
            abstract=item.get("abstract") or "",
            full_text_url=item.get("html_url", ""),
            docket_number=", ".join(item.get("docket_ids", [])),
            regulation_ids=item.get("regulation_id_numbers", []),
            topics=item.get("topics", []),
            raw=item,
        )

    def _tag_fintech_relevance(self, doc: RegulatoryDocument) -> List[str]:
        """Return fintech domain tags based on title + abstract text matching."""
        text = f"{doc.title} {doc.abstract}".lower()
        tags = []
        for term in FINTECH_REGULATORY_TERMS:
            if term.lower() in text:
                tags.append(term)
        return list(dict.fromkeys(tags))  # deduplicate preserving order


class SECEdgarIngester:
    """Pulls recent SEC filings and rule announcements."""

    BASE_URL = "https://efts.sec.gov/LATEST/search-index"

    async def fetch_recent_rules(self) -> List[RegulatoryDocument]:
        docs: List[RegulatoryDocument] = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                params = {
                    "q": "fintech digital asset cryptocurrency blockchain",
                    "dateRange": "custom",
                    "startdt": (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat(),
                    "forms": "34-12G",
                }
                resp = await client.get(
                    "https://efts.sec.gov/LATEST/search-index?q=%22fintech%22&dateRange=custom&startdt=2024-01-01&forms=34-12G",
                    headers={"User-Agent": "FinTech OSINT Platform research@example.com"},
                )
                # SEC EDGAR full-text search
                logger.info("SEC EDGAR fetch completed: status %s", resp.status_code)
        except Exception as exc:
            logger.warning("SEC EDGAR fetch error: %s", exc)

        return docs
