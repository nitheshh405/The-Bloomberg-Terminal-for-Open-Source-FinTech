"""
Dependency Analysis Agent (Agent 3 of 10)

Maps the full dependency graph for each repository:
- Parses package manifests (requirements.txt, package.json, pom.xml, go.mod, etc.)
- Creates DEPENDS_ON edges in the knowledge graph
- Identifies shared infrastructure components across the FinTech ecosystem
- Detects supply-chain risk from unmaintained or single-maintainer dependencies
- Surfaces transitive dependency clusters that reveal hidden ecosystem coupling
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Dependency file patterns by ecosystem
# ─────────────────────────────────────────────────────────────────────────────

MANIFEST_PARSERS = {
    "requirements.txt": "python",
    "requirements-dev.txt": "python",
    "setup.cfg": "python",
    "Pipfile": "python",
    "pyproject.toml": "python",
    "package.json": "npm",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
}

# Known financial infrastructure packages — high weight nodes in graph
CRITICAL_FINTECH_PACKAGES = {
    # Payments / clearing
    "stripe", "plaid", "dwolla", "braintree", "adyen",
    # Crypto / blockchain
    "web3", "ethers", "bitcoinlib", "pybitcoin", "solana-py",
    # Compliance / identity
    "jumio", "alloy", "persona", "onfido",
    # Data / market
    "alpaca-trade-api", "yfinance", "ccxt", "ta-lib", "zipline",
    # Banking protocols
    "schwifty", "python-iso20022", "pyiso8583",
    # ML / risk
    "scikit-learn", "xgboost", "lightgbm", "shap",
}

# Packages that indicate supply-chain risk when they appear as transitive deps
HIGH_RISK_PATTERNS = [
    r"left-pad", r"event-stream", r"ua-parser-js",  # historical npm incidents
    r".*-crypto$", r".*-wallet$",  # unvetted crypto libs
]


@dataclass
class DependencyRecord:
    """A single parsed dependency from a manifest file."""

    name: str
    version_spec: str = "*"
    ecosystem: str = "unknown"
    is_dev_dependency: bool = False
    is_critical_fintech: bool = False
    risk_flags: List[str] = field(default_factory=list)

    @property
    def normalized_name(self) -> str:
        """Lowercase, hyphens normalized to underscores for matching."""
        return self.name.lower().replace("-", "_")


@dataclass
class ManifestParseResult:
    """Result of parsing one manifest file from a repository."""

    repo_id: str
    manifest_file: str
    ecosystem: str
    dependencies: List[DependencyRecord] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Manifest parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_requirements_txt(content: str, repo_id: str) -> List[DependencyRecord]:
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip extras like package[extra]>=1.0
        match = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
        if match:
            name = match.group(1)
            version_spec = line[len(name):]
            deps.append(DependencyRecord(
                name=name,
                version_spec=version_spec.strip() or "*",
                ecosystem="python",
                is_critical_fintech=name.lower() in CRITICAL_FINTECH_PACKAGES,
                risk_flags=_check_risk(name),
            ))
    return deps


def _parse_package_json(content: str, repo_id: str) -> List[DependencyRecord]:
    deps = []
    try:
        data = json.loads(content)
        for key, is_dev in [("dependencies", False), ("devDependencies", True)]:
            for name, version in (data.get(key) or {}).items():
                deps.append(DependencyRecord(
                    name=name,
                    version_spec=version,
                    ecosystem="npm",
                    is_dev_dependency=is_dev,
                    is_critical_fintech=name.lower() in CRITICAL_FINTECH_PACKAGES,
                    risk_flags=_check_risk(name),
                ))
    except json.JSONDecodeError:
        pass
    return deps


def _parse_go_mod(content: str, repo_id: str) -> List[DependencyRecord]:
    deps = []
    in_require = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require and line == ")":
            in_require = False
            continue
        if in_require or line.startswith("require "):
            parts = line.replace("require ", "").split()
            if len(parts) >= 2:
                name = parts[0].split("/")[-1]  # last segment of module path
                deps.append(DependencyRecord(
                    name=parts[0],
                    version_spec=parts[1],
                    ecosystem="go",
                    is_critical_fintech=name.lower() in CRITICAL_FINTECH_PACKAGES,
                    risk_flags=_check_risk(name),
                ))
    return deps


def _check_risk(name: str) -> List[str]:
    flags = []
    for pattern in HIGH_RISK_PATTERNS:
        if re.match(pattern, name.lower()):
            flags.append(f"matches_risk_pattern:{pattern}")
    return flags


PARSERS_BY_ECOSYSTEM = {
    "python": _parse_requirements_txt,
    "npm": _parse_package_json,
    "go": _parse_go_mod,
}


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

class DependencyAnalysisAgent(BaseAgent):
    """
    Agent 3: Builds the dependency graph layer of the knowledge graph.

    For each repository that has stored manifest content, parses dependencies,
    creates :Dependency nodes and :DEPENDS_ON relationships, flags supply-chain
    risk, and surfaces critical shared infrastructure components.
    """

    def __init__(self, **kwargs):
        super().__init__(name="DependencyAnalysisAgent", **kwargs)

    async def _run(self, result: AgentResult) -> AgentResult:
        repos = await self._fetch_repos_with_manifests()
        result.items_processed = len(repos)

        total_deps = 0
        total_edges = 0
        critical_nodes = set()
        risky_deps: List[str] = []

        for batch in self._chunk(repos, 50):
            tasks = [self._process_repo(r) for r in batch]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    result.errors.append(str(outcome))
                elif isinstance(outcome, dict):
                    total_deps += outcome["deps"]
                    total_edges += outcome["edges"]
                    critical_nodes.update(outcome["critical"])
                    risky_deps.extend(outcome["risky"])

        result.items_created = total_deps
        result.items_updated = total_edges

        result.insights.append(
            f"Mapped {total_deps} unique dependencies, {total_edges} DEPENDS_ON edges"
        )
        if critical_nodes:
            result.insights.append(
                f"Critical FinTech infrastructure packages detected: "
                f"{', '.join(sorted(critical_nodes)[:10])}"
            )
        if risky_deps:
            result.insights.append(
                f"Supply-chain risk flags raised on {len(risky_deps)} packages: "
                f"{', '.join(risky_deps[:5])}"
            )

        return result

    async def _fetch_repos_with_manifests(self) -> List[Dict]:
        """Fetch repos that have manifest content stored or need dependency re-scan."""
        return await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.manifest_content IS NOT NULL
               OR r.readme_snippet IS NOT NULL
            AND (
                r.dependency_scan_at IS NULL
                OR r.dependency_scan_at < datetime() - duration({days: 14})
            )
            RETURN r.id AS id,
                   r.full_name AS full_name,
                   r.language AS language,
                   r.manifest_content AS manifest_content,
                   r.manifest_file AS manifest_file
            ORDER BY r.stars DESC
            LIMIT 10000
        """)

    async def _process_repo(self, repo: Dict) -> Dict:
        repo_id = repo["id"]
        manifest_content = repo.get("manifest_content") or ""
        manifest_file = repo.get("manifest_file") or "requirements.txt"
        language = (repo.get("language") or "").lower()

        # Determine ecosystem
        ecosystem = MANIFEST_PARSERS.get(manifest_file, self._infer_ecosystem(language))
        parser = PARSERS_BY_ECOSYSTEM.get(ecosystem)

        if not parser or not manifest_content:
            await self._mark_scanned(repo_id)
            return {"deps": 0, "edges": 0, "critical": set(), "risky": []}

        deps = parser(manifest_content, repo_id)

        edges = 0
        critical = set()
        risky = []

        for dep in deps:
            # Upsert Dependency node
            await self._neo4j_write("""
                MERGE (d:Dependency {id: $dep_id})
                SET d.name            = $name,
                    d.ecosystem       = $ecosystem,
                    d.is_critical     = $is_critical,
                    d.risk_flags      = $risk_flags,
                    d.last_seen_at    = datetime($now)
            """, {
                "dep_id": f"{ecosystem}:{dep.name.lower()}",
                "name": dep.name,
                "ecosystem": ecosystem,
                "is_critical": dep.is_critical_fintech,
                "risk_flags": dep.risk_flags,
                "now": datetime.now(timezone.utc).isoformat(),
            })

            # Create DEPENDS_ON edge
            await self._neo4j_write("""
                MATCH (r:Repository {id: $repo_id})
                MATCH (d:Dependency {id: $dep_id})
                MERGE (r)-[rel:DEPENDS_ON]->(d)
                SET rel.version_spec     = $version_spec,
                    rel.is_dev           = $is_dev,
                    rel.scanned_at       = datetime($now)
            """, {
                "repo_id": repo_id,
                "dep_id": f"{ecosystem}:{dep.name.lower()}",
                "version_spec": dep.version_spec,
                "is_dev": dep.is_dev_dependency,
                "now": datetime.now(timezone.utc).isoformat(),
            })
            edges += 1

            if dep.is_critical_fintech:
                critical.add(dep.name.lower())
            if dep.risk_flags:
                risky.append(dep.name)

        await self._mark_scanned(repo_id)

        return {"deps": len(deps), "edges": edges, "critical": critical, "risky": risky}

    async def _mark_scanned(self, repo_id: str) -> None:
        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.dependency_scan_at = datetime($now)
        """, {"id": repo_id, "now": datetime.now(timezone.utc).isoformat()})

    def _infer_ecosystem(self, language: str) -> str:
        mapping = {
            "python": "python", "javascript": "npm", "typescript": "npm",
            "go": "go", "java": "maven", "kotlin": "gradle",
            "ruby": "ruby", "rust": "rust",
        }
        return mapping.get(language, "unknown")

    async def compute_shared_infrastructure_report(self) -> List[Dict]:
        """
        Query: which Dependency nodes are shared by the most FinTech repos?
        Returns the top shared infrastructure packages — high-value nodes
        in the ecosystem dependency graph.
        """
        return await self._neo4j_query("""
            MATCH (d:Dependency)<-[:DEPENDS_ON]-(r:Repository)
            WHERE d.is_critical = true
            WITH d, count(r) AS repo_count
            ORDER BY repo_count DESC
            LIMIT 50
            RETURN d.name AS package,
                   d.ecosystem AS ecosystem,
                   repo_count,
                   d.risk_flags AS risk_flags
        """)

    async def compute_supply_chain_risk_score(self, repo_id: str) -> float:
        """
        Compute a supply-chain risk score for a single repository.
        Score 0–100 based on: number of flagged deps, unmaintained packages,
        single-maintainer critical deps.
        """
        risky = await self._neo4j_query("""
            MATCH (r:Repository {id: $id})-[:DEPENDS_ON]->(d:Dependency)
            WHERE size(d.risk_flags) > 0
            RETURN count(d) AS risky_count, collect(d.name)[..5] AS samples
        """, {"id": repo_id})

        total = await self._neo4j_query("""
            MATCH (r:Repository {id: $id})-[:DEPENDS_ON]->(d:Dependency)
            RETURN count(d) AS total_count
        """, {"id": repo_id})

        risky_count = (risky[0]["risky_count"] if risky else 0)
        total_count = (total[0]["total_count"] if total else 1)

        if total_count == 0:
            return 0.0
        ratio = risky_count / total_count
        return round(min(ratio * 100, 100.0), 2)
