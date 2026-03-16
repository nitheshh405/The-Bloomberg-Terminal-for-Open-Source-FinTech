"""
Technology Classification Agent (Agent 2 of 10)

Uses NLP (transformer-based) to classify each repository into fintech domains,
identify implemented technologies, and enrich the knowledge graph with
Technology nodes and IMPLEMENTS relationships.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)

# ── Fintech domain taxonomy ───────────────────────────────────────────────────

FINTECH_DOMAINS: Dict[str, List[str]] = {
    "payments": [
        "payment", "transaction", "transfer", "remittance", "wallet", "checkout",
        "merchant", "acquiring", "issuing", "IBAN", "ACH", "wire", "SEPA",
        "real-time-payments", "RTP", "FedNow", "iso20022",
    ],
    "trading": [
        "trading", "execution", "order management", "FIX protocol", "market data",
        "exchange", "market maker", "liquidity", "algo trading", "HFT",
        "backtesting", "OHLCV", "tick data", "options", "futures",
    ],
    "risk_management": [
        "risk", "VaR", "CVA", "DVA", "credit risk", "market risk", "operational risk",
        "stress testing", "scenario analysis", "collateral", "margin", "Basel",
        "FRTB", "SA-CCR",
    ],
    "fraud_detection": [
        "fraud", "anomaly detection", "suspicious activity", "chargeback",
        "card not present", "synthetic identity", "transaction monitoring",
        "ML fraud", "neural network fraud",
    ],
    "aml_compliance": [
        "AML", "anti-money laundering", "KYC", "know your customer", "CDD",
        "EDD", "SAR", "CTR", "FinCEN", "FATF", "sanctions screening", "OFAC",
        "watchlist", "PEP", "adverse media",
    ],
    "lending": [
        "loan", "credit scoring", "underwriting", "origination", "LTV",
        "DSCR", "default probability", "FICO", "credit bureau", "decisioning",
        "mortgage", "HELOC", "SME lending",
    ],
    "digital_identity": [
        "identity verification", "KYC", "eID", "biometric", "liveness",
        "document verification", "face match", "digital ID", "SSI",
        "verifiable credentials", "decentralized identity", "DID",
    ],
    "blockchain_defi": [
        "blockchain", "smart contract", "DeFi", "cryptocurrency", "NFT",
        "staking", "AMM", "liquidity pool", "yield farming", "bridge",
        "CBDC", "stablecoin", "custody", "wallet", "EVM", "Solidity",
    ],
    "regtech": [
        "regulatory reporting", "MiFID", "EMIR", "Dodd-Frank reporting",
        "XBRL", "RegTech", "compliance automation", "audit trail",
        "regulatory change management", "policy engine",
    ],
    "wealth_management": [
        "portfolio", "robo-advisor", "asset allocation", "rebalancing",
        "ETF", "tax loss harvesting", "financial planning", "wealth",
        "ESG", "impact investing",
    ],
    "insurtech": [
        "insurance", "underwriting", "actuarial", "claims", "premium",
        "telematics", "parametric", "P&C", "life insurance", "InsurTech",
    ],
    "financial_data": [
        "market data", "financial data", "time series", "OHLC",
        "economic data", "alternative data", "ESG data", "earnings",
        "fundamental data", "data vendor",
    ],
}

TECH_KEYWORDS: Dict[str, List[str]] = {
    "zero_knowledge_proofs": ["zkp", "zk-snark", "zk-stark", "zero knowledge"],
    "homomorphic_encryption": ["homomorphic", "FHE", "CKKS", "BFV"],
    "federated_learning": ["federated learning", "FL", "differential privacy"],
    "graph_neural_networks": ["GNN", "graph neural", "node classification"],
    "transformer_models": ["transformer", "BERT", "attention mechanism", "LLM"],
    "iso20022": ["ISO 20022", "ISO20022", "MX message", "pain.001"],
    "fix_protocol": ["FIX protocol", "FIX 4.4", "FIX 5.0", "FIXML"],
    "open_banking_api": ["PSD2", "open banking", "Account Information Service", "AISP"],
    "cbdc": ["CBDC", "central bank digital currency", "digital dollar"],
    "rust_finance": ["Rust", "memory safe", "systems programming", "low latency"],
}

CLASSIFICATION_SYSTEM_PROMPT = """You are a fintech technology classifier.
Given a repository description, README snippet, and topic tags, return a JSON object with:
{
  "primary_domain": "<one of: payments|trading|risk_management|fraud_detection|aml_compliance|lending|digital_identity|blockchain_defi|regtech|wealth_management|insurtech|financial_data|infrastructure|other>",
  "secondary_domains": ["<domain>", ...],
  "technologies": ["<specific technology name>", ...],
  "financial_use_cases": ["<use case description>", ...],
  "is_fintech": true|false,
  "confidence": 0.0-1.0,
  "reasoning": "<brief explanation>"
}
Only return the JSON. No markdown, no explanation."""


class TechnologyClassificationAgent(BaseAgent):
    """Agent 2: Classifies repositories into fintech domains and technology categories."""

    def __init__(self, batch_size: int = 50, **kwargs):
        super().__init__(name="TechnologyClassificationAgent", **kwargs)
        self.batch_size = batch_size

    async def _run(self, result: AgentResult) -> AgentResult:
        # Fetch unclassified or stale repositories
        repos = await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.primary_sector IS NULL
               OR r.last_classified_at IS NULL
               OR r.last_classified_at < datetime() - duration({days: 7})
            RETURN r.id AS id, r.description AS description,
                   r.readme_snippet AS readme, r.topics AS topics,
                   r.language AS language
            ORDER BY r.stars DESC
            LIMIT 2000
        """)

        result.items_processed = len(repos)
        logger.info("[%s] Classifying %d repositories", self.name, len(repos))

        classified = 0
        for batch in self._chunk(repos, self.batch_size):
            tasks = [self._classify_repo(r) for r in batch]
            outcomes = await __import__("asyncio").gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    result.errors.append(str(outcome))
                else:
                    classified += 1

        result.items_updated = classified
        result.insights.append(f"Classified {classified} repositories into fintech domains")

        # Build Technology nodes for detected technologies
        await self._ensure_technology_nodes()
        return result

    async def _classify_repo(self, repo: Dict) -> None:
        repo_id = repo["id"]
        description = repo.get("description") or ""
        readme = repo.get("readme") or ""
        topics = repo.get("topics") or []
        language = repo.get("language") or ""

        # Rule-based fast classification
        domains, technologies = self._rule_based_classify(
            description + " " + readme[:500] + " " + " ".join(topics)
        )

        primary_domain = domains[0] if domains else "other"
        confidence = 0.75 if domains else 0.3

        # AI-enhanced classification for high-value repos (starred repos)
        if self._ai and len(description) > 50:
            ai_result = await self._ai_classify_repo(description, readme[:800], topics)
            if ai_result:
                primary_domain = ai_result.get("primary_domain", primary_domain)
                domains = list(set([primary_domain] + ai_result.get("secondary_domains", [])))
                technologies = list(set(technologies + ai_result.get("technologies", [])))
                confidence = ai_result.get("confidence", confidence)

        # Write classification back to graph
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.primary_sector = $primary_domain,
                r.fintech_domains = $domains,
                r.detected_technologies = $technologies,
                r.classification_confidence = $confidence,
                r.last_classified_at = datetime($now)
        """, {
            "id": repo_id,
            "primary_domain": primary_domain,
            "domains": domains,
            "technologies": technologies,
            "confidence": confidence,
            "now": now,
        })

        # Create IMPLEMENTS relationships to Technology nodes
        for tech in technologies:
            tech_id = f"tech:{tech.lower().replace(' ', '-')}"
            await self._neo4j_write("""
                MERGE (t:Technology {id: $tech_id})
                ON CREATE SET t.name = $tech_name, t.first_seen = datetime($now)
                WITH t
                MATCH (r:Repository {id: $repo_id})
                MERGE (r)-[rel:IMPLEMENTS]->(t)
                SET rel.confidence = $confidence, rel.updated_at = datetime($now)
            """, {
                "tech_id": tech_id,
                "tech_name": tech,
                "repo_id": repo_id,
                "confidence": confidence,
                "now": now,
            })

        # Link to FinancialSector nodes
        for domain in domains:
            sector_id = f"sector:{domain.replace('_', '-')}"
            await self._neo4j_write("""
                MATCH (r:Repository {id: $repo_id})
                MATCH (fs:FinancialSector {id: $sector_id})
                MERGE (r)-[rel:RELEVANT_TO]->(fs)
                SET rel.confidence = $confidence, rel.updated_at = datetime($now)
            """, {
                "repo_id": repo_id,
                "sector_id": sector_id,
                "confidence": confidence,
                "now": now,
            })

    def _rule_based_classify(self, text: str) -> Tuple[List[str], List[str]]:
        text_lower = text.lower()
        matched_domains: List[str] = []
        matched_techs: List[str] = []

        for domain, keywords in FINTECH_DOMAINS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score >= 2:
                matched_domains.append((domain, score))

        for tech, keywords in TECH_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                matched_techs.append(tech.replace("_", " ").title())

        matched_domains.sort(key=lambda x: x[1], reverse=True)
        return [d[0] for d in matched_domains[:3]], matched_techs

    async def _ai_classify_repo(
        self, description: str, readme: str, topics: List[str]
    ) -> Optional[Dict]:
        prompt = f"""Repository description: {description}

README excerpt: {readme[:600]}

Topics: {', '.join(topics)}

Classify this repository."""

        try:
            response = await self._ai_classify(prompt, CLASSIFICATION_SYSTEM_PROMPT)
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as exc:
            logger.debug("AI classification failed: %s", exc)
        return None

    async def _ensure_technology_nodes(self) -> None:
        """Create Technology nodes for all known fintech technologies."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        known_techs = [
            ("tech:iso20022", "ISO 20022", "messaging", "mature"),
            ("tech:fix-protocol", "FIX Protocol", "messaging", "mature"),
            ("tech:zero-knowledge-proofs", "Zero-Knowledge Proofs", "cryptography", "emerging"),
            ("tech:federated-learning", "Federated Learning", "ml", "growing"),
            ("tech:cbdc", "Central Bank Digital Currency", "digital-money", "emerging"),
            ("tech:open-banking-api", "Open Banking API", "infrastructure", "growing"),
            ("tech:homomorphic-encryption", "Homomorphic Encryption", "cryptography", "emerging"),
        ]

        for tech_id, name, category, maturity in known_techs:
            await self._neo4j_write("""
                MERGE (t:Technology {id: $id})
                ON CREATE SET t.name = $name, t.category = $category,
                              t.maturity_level = $maturity, t.first_seen = datetime($now)
            """, {"id": tech_id, "name": name, "category": category,
                  "maturity": maturity, "now": now})
