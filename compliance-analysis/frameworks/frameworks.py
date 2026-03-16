"""
Regulatory Framework Definitions
Detailed mapping of financial regulations to their technical requirements,
enforcement scope, and open-source technology implications.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TechnicalRequirement:
    """A specific technical requirement mandated by a regulation."""
    id: str
    description: str
    technology_tags: List[str]      # technology domains that address this
    mandatory: bool = True
    penalty_risk: str = "medium"    # low | medium | high | critical


@dataclass
class RegulatoryFramework:
    id: str
    short_name: str
    full_name: str
    jurisdiction: str
    regulator_ids: List[str]
    effective_date: str
    status: str                     # enacted | proposed | amended | superseded
    scope: str                      # who is subject to this regulation
    primary_domains: List[str]
    technical_requirements: List[TechnicalRequirement] = field(default_factory=list)
    description: str = ""
    oss_relevance: str = ""         # why this matters to open-source FinTech


FRAMEWORKS: List[RegulatoryFramework] = [
    RegulatoryFramework(
        id="bsa",
        short_name="BSA",
        full_name="Bank Secrecy Act",
        jurisdiction="US",
        regulator_ids=["fincen", "fed", "occ", "fdic"],
        effective_date="1970-10-26",
        status="enacted",
        scope="Banks, MSBs, crypto exchanges, and any business transmitting funds",
        primary_domains=["aml", "kyc", "transaction_monitoring", "reporting"],
        description="Foundation of US AML law. Requires financial institutions to "
                    "assist government agencies in detecting and preventing money laundering.",
        oss_relevance="Open-source AML/KYC tools, transaction monitoring engines, "
                       "and SAR filing systems are directly relevant.",
        technical_requirements=[
            TechnicalRequirement(
                id="bsa-tr-001",
                description="Customer Identification Program (CIP) — verify identity of customers",
                technology_tags=["identity_verification", "kyc", "document_check", "biometric"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="bsa-tr-002",
                description="Transaction monitoring for suspicious activity patterns",
                technology_tags=["transaction_monitoring", "rule_engine", "behavior_analytics"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="bsa-tr-003",
                description="Currency Transaction Reports (CTR) for transactions >$10,000",
                technology_tags=["regulatory_reporting", "threshold_detection"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="bsa-tr-004",
                description="Suspicious Activity Reports (SAR) filing system",
                technology_tags=["sar_filing", "case_management", "regulatory_reporting"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="bsa-tr-005",
                description="Record retention for transactions and customer data (5 years)",
                technology_tags=["audit_log", "data_retention", "immutable_storage"],
                mandatory=True, penalty_risk="medium",
            ),
        ],
    ),

    RegulatoryFramework(
        id="dodd-frank",
        short_name="Dodd-Frank",
        full_name="Dodd-Frank Wall Street Reform and Consumer Protection Act",
        jurisdiction="US",
        regulator_ids=["cftc", "sec", "fed", "fdic"],
        effective_date="2010-07-21",
        status="enacted",
        scope="Banks, swap dealers, major swap participants, hedge funds, "
              "systemically important financial institutions",
        primary_domains=["derivatives", "clearing", "reporting", "systemic_risk",
                         "consumer_protection"],
        description="Comprehensive financial reform in response to the 2008 financial crisis. "
                    "Mandates central clearing of standardized derivatives, trade reporting, "
                    "and enhanced oversight of systemically important firms.",
        oss_relevance="Open-source derivatives pricing, trade reporting (DTCC/CFTC), "
                       "clearing interfaces, and risk analytics tools are highly relevant.",
        technical_requirements=[
            TechnicalRequirement(
                id="df-tr-001",
                description="Central clearing of standardized OTC derivatives",
                technology_tags=["clearing_settlement", "derivatives_pricing", "ccp_connectivity"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="df-tr-002",
                description="Real-time trade reporting to Swap Data Repositories (SDR)",
                technology_tags=["trade_reporting", "regulatory_reporting", "api_integration"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="df-tr-003",
                description="Volcker Rule compliance — restrictions on proprietary trading",
                technology_tags=["trading_surveillance", "position_monitoring"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="df-tr-004",
                description="Stress testing (DFAST) for large bank holding companies",
                technology_tags=["stress_testing", "risk_analytics", "scenario_analysis"],
                mandatory=True, penalty_risk="high",
            ),
        ],
    ),

    RegulatoryFramework(
        id="sox",
        short_name="SOX",
        full_name="Sarbanes-Oxley Act",
        jurisdiction="US",
        regulator_ids=["sec"],
        effective_date="2002-07-30",
        status="enacted",
        scope="US public companies and their auditors",
        primary_domains=["audit", "financial_reporting", "internal_controls", "data_integrity"],
        description="Mandates internal controls, audit requirements, and personal accountability "
                    "for executives of public companies following Enron/WorldCom scandals.",
        oss_relevance="Open-source audit logging, immutable ledger, and internal control "
                       "automation tools are directly applicable to SOX Section 404.",
        technical_requirements=[
            TechnicalRequirement(
                id="sox-tr-001",
                description="Immutable audit trails for all financial transactions and system access",
                technology_tags=["audit_log", "immutable_storage", "tamper_evident", "event_sourcing"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="sox-tr-002",
                description="Access controls and identity management for financial systems",
                technology_tags=["access_control", "rbac", "identity_management", "mfa"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="sox-tr-003",
                description="Data integrity and change management controls",
                technology_tags=["data_integrity", "change_management", "version_control"],
                mandatory=True, penalty_risk="high",
            ),
        ],
    ),

    RegulatoryFramework(
        id="glba",
        short_name="GLBA",
        full_name="Gramm-Leach-Bliley Act",
        jurisdiction="US",
        regulator_ids=["fed", "occ", "fdic", "sec", "cfpb"],
        effective_date="1999-11-12",
        status="enacted",
        scope="Financial institutions collecting nonpublic personal information (NPI)",
        primary_domains=["data_privacy", "consumer_data", "encryption", "access_control"],
        description="Requires financial institutions to explain their data sharing practices "
                    "and protect sensitive customer data.",
        oss_relevance="Encryption libraries, data masking tools, and privacy-preserving "
                       "analytics are relevant to GLBA Safeguards Rule compliance.",
        technical_requirements=[
            TechnicalRequirement(
                id="glba-tr-001",
                description="Encryption of customer financial data at rest and in transit",
                technology_tags=["encryption", "tls", "aes", "key_management", "hsm"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="glba-tr-002",
                description="Multi-factor authentication for systems accessing NPI",
                technology_tags=["mfa", "identity_verification", "access_control"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="glba-tr-003",
                description="Data classification and access controls for NPI",
                technology_tags=["data_classification", "rbac", "data_governance"],
                mandatory=True, penalty_risk="medium",
            ),
        ],
    ),

    RegulatoryFramework(
        id="pci-dss",
        short_name="PCI-DSS",
        full_name="Payment Card Industry Data Security Standard",
        jurisdiction="INT",
        regulator_ids=[],  # governed by PCI SSC, not a government regulator
        effective_date="2004-12-15",
        status="enacted",
        scope="Any entity storing, processing, or transmitting cardholder data",
        primary_domains=["payments", "encryption", "access_control", "network_security"],
        description="Global security standard for organizations handling branded credit cards. "
                    "Currently at version 4.0 (2022). Mandates technical and operational controls.",
        oss_relevance="Payment processing libraries, tokenization tools, and network security "
                       "tooling must all align with PCI-DSS requirements.",
        technical_requirements=[
            TechnicalRequirement(
                id="pci-tr-001",
                description="Encryption of cardholder data in transit (TLS 1.2+)",
                technology_tags=["tls", "encryption", "certificate_management"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="pci-tr-002",
                description="Tokenization or encryption of stored cardholder data",
                technology_tags=["tokenization", "encryption", "vault", "key_management"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="pci-tr-003",
                description="Vulnerability scanning and penetration testing",
                technology_tags=["security_scanning", "penetration_testing", "sast", "dast"],
                mandatory=True, penalty_risk="high",
            ),
        ],
    ),

    RegulatoryFramework(
        id="basel-iii",
        short_name="Basel III",
        full_name="Basel III International Regulatory Framework for Banks",
        jurisdiction="INT",
        regulator_ids=["bis", "fed", "occ", "fdic", "eba"],
        effective_date="2013-01-01",
        status="enacted",
        scope="Internationally active banks",
        primary_domains=["capital_requirements", "liquidity", "risk_analytics",
                         "stress_testing", "reporting"],
        description="Post-2008 international banking standards covering capital adequacy, "
                    "stress testing, and market liquidity risk. Basel IV (finalization) "
                    "effective January 2025.",
        oss_relevance="Risk analytics engines, capital calculation tools, LCR/NSFR calculators, "
                       "and stress testing frameworks are core Basel III technology needs.",
        technical_requirements=[
            TechnicalRequirement(
                id="b3-tr-001",
                description="Capital adequacy calculation and reporting (RWA)",
                technology_tags=["risk_analytics", "capital_calculation", "risk_weighted_assets"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="b3-tr-002",
                description="Liquidity Coverage Ratio (LCR) and NSFR calculation",
                technology_tags=["liquidity_modeling", "balance_sheet_analytics"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="b3-tr-003",
                description="Counterparty credit risk management (SA-CCR)",
                technology_tags=["credit_risk", "derivatives_pricing", "counterparty_risk"],
                mandatory=True, penalty_risk="high",
            ),
        ],
    ),

    RegulatoryFramework(
        id="dora",
        short_name="DORA",
        full_name="Digital Operational Resilience Act",
        jurisdiction="EU",
        regulator_ids=["eba", "esma"],
        effective_date="2025-01-17",
        status="enacted",
        scope="EU financial entities and their critical ICT third-party service providers",
        primary_domains=["operational_resilience", "ict_risk", "incident_reporting",
                         "third_party_risk", "testing"],
        description="EU regulation requiring financial firms to manage digital operational "
                    "resilience — including ICT risk management, incident reporting, resilience "
                    "testing, and oversight of cloud/third-party providers.",
        oss_relevance="DORA is highly relevant to open-source tools used in financial "
                       "infrastructure. Third-party risk management tools, incident response "
                       "automation, and resilience testing frameworks are all in scope.",
        technical_requirements=[
            TechnicalRequirement(
                id="dora-tr-001",
                description="ICT risk management framework and governance",
                technology_tags=["risk_management", "governance", "policy_management"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="dora-tr-002",
                description="ICT-related incident classification and reporting",
                technology_tags=["incident_management", "siem", "monitoring", "alerting"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="dora-tr-003",
                description="Digital operational resilience testing (TLPT — threat-led pentesting)",
                technology_tags=["penetration_testing", "red_team", "chaos_engineering"],
                mandatory=True, penalty_risk="medium",
            ),
            TechnicalRequirement(
                id="dora-tr-004",
                description="Third-party ICT provider risk monitoring and register",
                technology_tags=["third_party_risk", "vendor_management", "supply_chain_security"],
                mandatory=True, penalty_risk="high",
            ),
        ],
    ),

    RegulatoryFramework(
        id="mica",
        short_name="MiCA",
        full_name="Markets in Crypto-Assets Regulation",
        jurisdiction="EU",
        regulator_ids=["esma", "eba"],
        effective_date="2024-12-30",
        status="enacted",
        scope="Crypto-asset service providers (CASPs) and issuers of ARTs/EMTs in the EU",
        primary_domains=["crypto", "stablecoins", "cbdc", "aml", "custody",
                         "disclosure", "market_abuse"],
        description="First comprehensive EU regulatory framework for crypto-assets. "
                    "Creates a harmonized regime for crypto-asset service providers, "
                    "stablecoin issuers, and utility tokens.",
        oss_relevance="Open-source crypto custody, stablecoin infrastructure, CASP "
                       "compliance tools, and disclosure automation are all in scope.",
        technical_requirements=[
            TechnicalRequirement(
                id="mica-tr-001",
                description="Secure custody and segregation of client crypto-assets",
                technology_tags=["crypto_custody", "key_management", "hsm", "mpc"],
                mandatory=True, penalty_risk="critical",
            ),
            TechnicalRequirement(
                id="mica-tr-002",
                description="White paper disclosure for asset-referenced tokens (ARTs)",
                technology_tags=["disclosure_automation", "document_generation"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="mica-tr-003",
                description="Travel Rule compliance for crypto transfers",
                technology_tags=["travel_rule", "vasp_data_sharing", "blockchain_analytics"],
                mandatory=True, penalty_risk="high",
            ),
        ],
    ),

    RegulatoryFramework(
        id="psd2",
        short_name="PSD2",
        full_name="Revised Payment Services Directive",
        jurisdiction="EU",
        regulator_ids=["eba"],
        effective_date="2018-01-13",
        status="enacted",
        scope="Payment service providers operating in the EU/EEA",
        primary_domains=["open_banking", "payments", "strong_authentication",
                         "api", "third_party_providers"],
        description="EU directive mandating open banking — banks must provide secure APIs "
                    "for licensed third-party providers (TPPs) to access account data "
                    "and initiate payments. PSD3 is currently in progress.",
        oss_relevance="Open Banking API libraries, Strong Customer Authentication (SCA) "
                       "implementations, and TPP integration toolkits are highly relevant.",
        technical_requirements=[
            TechnicalRequirement(
                id="psd2-tr-001",
                description="Open Banking APIs (XS2A) for account data and payment initiation",
                technology_tags=["open_banking", "api_gateway", "oauth2", "berlin_group"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="psd2-tr-002",
                description="Strong Customer Authentication (SCA) — two-factor for payments",
                technology_tags=["mfa", "strong_authentication", "fido2", "biometric"],
                mandatory=True, penalty_risk="high",
            ),
            TechnicalRequirement(
                id="psd2-tr-003",
                description="Transaction Risk Analysis (TRA) for SCA exemptions",
                technology_tags=["fraud_detection", "risk_scoring", "behavior_analytics"],
                mandatory=True, penalty_risk="medium",
            ),
        ],
    ),
]

# Index by ID for fast lookup
FRAMEWORKS_BY_ID: dict[str, RegulatoryFramework] = {f.id: f for f in FRAMEWORKS}


def get_framework(framework_id: str) -> Optional[RegulatoryFramework]:
    return FRAMEWORKS_BY_ID.get(framework_id)


def get_frameworks_for_domain(domain: str) -> List[RegulatoryFramework]:
    return [f for f in FRAMEWORKS if domain in f.primary_domains]


def get_frameworks_for_jurisdiction(jurisdiction: str) -> List[RegulatoryFramework]:
    return [f for f in FRAMEWORKS if f.jurisdiction in (jurisdiction, "INT")]


def get_technology_requirements(technology_tag: str) -> List[Dict]:
    """
    For a given technology tag, return all regulatory requirements that it addresses.
    Useful for: "this repo does 'tokenization' — which regulations does that satisfy?"
    """
    results = []
    for framework in FRAMEWORKS:
        for req in framework.technical_requirements:
            if technology_tag in req.technology_tags:
                results.append({
                    "framework_id": framework.id,
                    "framework_name": framework.short_name,
                    "requirement_id": req.id,
                    "requirement": req.description,
                    "mandatory": req.mandatory,
                    "penalty_risk": req.penalty_risk,
                })
    return results
