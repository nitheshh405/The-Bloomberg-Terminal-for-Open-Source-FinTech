"""
Regulator Definitions
Authoritative definitions of financial regulators monitored by the platform.
Maps regulator IDs to metadata, jurisdictions, and monitored domains.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Regulator:
    id: str
    name: str
    full_name: str
    jurisdiction: str          # country or region code
    website: str
    domains: List[str]         # regulated domains
    primary_focus: str
    feed_url: Optional[str] = None   # RSS/API feed for regulatory updates
    description: str = ""


REGULATORS: List[Regulator] = [
    Regulator(
        id="sec",
        name="SEC",
        full_name="U.S. Securities and Exchange Commission",
        jurisdiction="US",
        website="https://www.sec.gov",
        feed_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=&dateb=&owner=include&count=40&search_text=&action=getcompany",
        domains=["securities", "capital_markets", "investment_management",
                 "broker_dealer", "market_data", "derivatives"],
        primary_focus="Investor protection and market integrity",
        description="Primary regulator for US securities markets, broker-dealers, "
                    "investment advisers, and public companies.",
    ),
    Regulator(
        id="finra",
        name="FINRA",
        full_name="Financial Industry Regulatory Authority",
        jurisdiction="US",
        website="https://www.finra.org",
        domains=["broker_dealer", "securities", "trading", "market_surveillance"],
        primary_focus="Broker-dealer regulation and investor protection",
        description="Self-regulatory organization overseeing broker-dealers and "
                    "exchange markets in the United States.",
    ),
    Regulator(
        id="fed",
        name="Federal Reserve",
        full_name="Board of Governors of the Federal Reserve System",
        jurisdiction="US",
        website="https://www.federalreserve.gov",
        feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
        domains=["banking", "monetary_policy", "payments", "systemic_risk",
                 "cbdc", "fintech"],
        primary_focus="Monetary policy, bank supervision, financial system stability",
        description="Central bank of the United States. Oversees bank holding companies, "
                    "state-chartered member banks, and systemically important institutions.",
    ),
    Regulator(
        id="occ",
        name="OCC",
        full_name="Office of the Comptroller of the Currency",
        jurisdiction="US",
        website="https://www.occ.gov",
        domains=["national_banks", "federal_savings", "fintech_charter",
                 "crypto", "lending"],
        primary_focus="National bank supervision and fintech chartering",
        description="Charters, regulates, and supervises all national banks and federal "
                    "savings associations. Grants special purpose national bank charters "
                    "to qualifying fintech companies.",
    ),
    Regulator(
        id="fdic",
        name="FDIC",
        full_name="Federal Deposit Insurance Corporation",
        jurisdiction="US",
        website="https://www.fdic.gov",
        domains=["deposit_insurance", "banking", "bank_failure", "systemic_risk"],
        primary_focus="Deposit insurance and bank resolution",
        description="Insures deposits, examines and supervises financial institutions "
                    "for safety and soundness.",
    ),
    Regulator(
        id="cftc",
        name="CFTC",
        full_name="Commodity Futures Trading Commission",
        jurisdiction="US",
        website="https://www.cftc.gov",
        feed_url="https://www.cftc.gov/rss/pressreleases.xml",
        domains=["derivatives", "futures", "swaps", "crypto", "commodities",
                 "clearing", "dodd_frank"],
        primary_focus="Derivatives markets and commodity futures",
        description="Regulates the US derivatives markets, including futures, swaps, "
                    "and certain kinds of options. Has jurisdiction over crypto assets "
                    "that are commodities.",
    ),
    Regulator(
        id="cfpb",
        name="CFPB",
        full_name="Consumer Financial Protection Bureau",
        jurisdiction="US",
        website="https://www.consumerfinance.gov",
        feed_url="https://www.consumerfinance.gov/about-us/newsroom/feed/",
        domains=["consumer_lending", "payments", "open_banking", "mortgage",
                 "student_loans", "credit_cards", "data_privacy"],
        primary_focus="Consumer financial protection and open banking",
        description="Protects consumers in the financial marketplace. Oversees open "
                    "banking rules (Section 1033) enabling consumer data portability.",
    ),
    Regulator(
        id="fincen",
        name="FinCEN",
        full_name="Financial Crimes Enforcement Network",
        jurisdiction="US",
        website="https://www.fincen.gov",
        domains=["aml", "kyc", "bsa", "crypto", "sanctions", "sar", "ctr",
                 "beneficial_ownership"],
        primary_focus="Anti-money laundering and financial crime prevention",
        description="Bureau of the US Treasury. Administers the Bank Secrecy Act, "
                    "combats money laundering, terrorist financing, and other financial crimes.",
    ),
    Regulator(
        id="eba",
        name="EBA",
        full_name="European Banking Authority",
        jurisdiction="EU",
        website="https://www.eba.europa.eu",
        feed_url="https://www.eba.europa.eu/rss.xml",
        domains=["banking", "fintech", "open_banking", "psd2", "aml", "crypto",
                 "mica", "dora"],
        primary_focus="EU banking regulation, PSD2, MiCA, DORA",
        description="EU authority ensuring effective and consistent prudential regulation "
                    "and supervision across the EU banking sector. Key role in PSD2, "
                    "MiCA, and DORA implementation.",
    ),
    Regulator(
        id="esma",
        name="ESMA",
        full_name="European Securities and Markets Authority",
        jurisdiction="EU",
        website="https://www.esma.europa.eu",
        domains=["securities", "mifid2", "emir", "crypto", "mica",
                 "capital_markets", "aifmd"],
        primary_focus="EU securities markets and MiFID II / MiCA",
        description="EU authority for securities markets. Implements MiFID II, EMIR, "
                    "and the Markets in Crypto-Assets Regulation (MiCA).",
    ),
    Regulator(
        id="fca",
        name="FCA",
        full_name="Financial Conduct Authority",
        jurisdiction="GB",
        website="https://www.fca.org.uk",
        feed_url="https://www.fca.org.uk/news/rss.xml",
        domains=["banking", "fintech", "crypto", "payments", "open_banking",
                 "consumer_duty", "aml"],
        primary_focus="UK financial conduct and fintech innovation",
        description="Conducts regulation in the UK. Runs the Global Financial Innovation "
                    "Network (GFIN) and one of the world's first regulatory sandboxes.",
    ),
    Regulator(
        id="mas",
        name="MAS",
        full_name="Monetary Authority of Singapore",
        jurisdiction="SG",
        website="https://www.mas.gov.sg",
        domains=["banking", "payments", "fintech", "crypto", "cbdc",
                 "aml", "capital_markets"],
        primary_focus="Singapore financial regulation and fintech hub",
        description="Central bank and financial regulator of Singapore. Leads Project "
                    "Ubin (CBDC) and the Global CBDC Challenge.",
    ),
    Regulator(
        id="bis",
        name="BIS",
        full_name="Bank for International Settlements",
        jurisdiction="INT",
        website="https://www.bis.org",
        domains=["basel", "cbdc", "crypto", "systemic_risk", "fintech",
                 "payments", "monetary_policy"],
        primary_focus="International banking standards and CBDC research",
        description="International organization for central banks. Issues Basel accords "
                    "and conducts influential research on CBDCs, stablecoins, and crypto.",
    ),
    Regulator(
        id="fatf",
        name="FATF",
        full_name="Financial Action Task Force",
        jurisdiction="INT",
        website="https://www.fatf-gafi.org",
        domains=["aml", "kyc", "crypto", "terrorist_financing",
                 "beneficial_ownership", "sanctions"],
        primary_focus="Global AML/CFT standards and crypto travel rule",
        description="Inter-governmental body setting global standards for AML/CFT. "
                    "Issued the Travel Rule for virtual assets (Recommendation 16).",
    ),
]

# Index by ID for fast lookup
REGULATORS_BY_ID: dict[str, Regulator] = {r.id: r for r in REGULATORS}


def get_regulator(regulator_id: str) -> Optional[Regulator]:
    return REGULATORS_BY_ID.get(regulator_id)


def get_regulators_for_domain(domain: str) -> List[Regulator]:
    """Return all regulators that oversee a given domain."""
    return [r for r in REGULATORS if domain in r.domains]


def get_regulators_for_jurisdiction(jurisdiction: str) -> List[Regulator]:
    """Return all regulators for a jurisdiction (e.g. 'US', 'EU', 'INT')."""
    return [r for r in REGULATORS if r.jurisdiction == jurisdiction]
