"""
Contributor Network Agent (Agent 4 of 10)

Maps the human layer of the FinTech open-source ecosystem:
- Discovers developers contributing to fintech repositories
- Identifies cross-repo contributors (bridge nodes in the network)
- Detects institutional contributors (employees of banks, regulators, VC-backed fintechs)
- Builds CONTRIBUTED_TO, COLLABORATES_WITH, and EMPLOYED_BY edges
- Computes influence scores — who are the key connectors in the FinTech OSS graph?
- Surfaces "stealth builders": high-influence contributors working quietly on
  pre-commercial fintech infrastructure
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from ai_agents.base.base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Institutional affiliation patterns
# ─────────────────────────────────────────────────────────────────────────────

INSTITUTIONAL_PATTERNS: Dict[str, str] = {
    # Major banks
    r"jpmorgan|jpmchase|chase\.com": "JPMorgan Chase",
    r"goldmansachs|gs\.com": "Goldman Sachs",
    r"morganstanley|ms\.com": "Morgan Stanley",
    r"citi(group|bank)?|citi\.com": "Citigroup",
    r"bankofamerica|bofa\.com": "Bank of America",
    r"wellsfargo|wf\.com": "Wells Fargo",
    r"barclays\.com": "Barclays",
    r"hsbc\.com": "HSBC",
    r"deutschebank|db\.com": "Deutsche Bank",
    r"ubs\.com": "UBS",
    # Major fintechs
    r"stripe\.com": "Stripe",
    r"square|block\.xyz|block\.com": "Block (Square)",
    r"paypal|venmo|braintree": "PayPal",
    r"coinbase\.com": "Coinbase",
    r"ripple\.com": "Ripple",
    r"plaid\.com": "Plaid",
    r"robinhood\.com": "Robinhood",
    r"revolut\.com": "Revolut",
    r"nubank\.com\.br": "Nubank",
    r"chime\.com": "Chime",
    # Exchanges
    r"nasdaq\.com": "Nasdaq",
    r"nyse\.com": "NYSE",
    r"iex(group)?\.com": "IEX",
    r"cboe\.com": "CBOE",
    # Asset managers
    r"blackrock\.com": "BlackRock",
    r"vanguard\.com": "Vanguard",
    r"fidelity\.com": "Fidelity",
    r"twosigma\.com|two-sigma\.com": "Two Sigma",
    r"citadel\.com": "Citadel",
    r"janestreet\.com|jane-street\.com": "Jane Street",
    r"virtu\.com": "Virtu Financial",
    r"renaissance(tech)?\.com": "Renaissance Technologies",
    # Regulators
    r"sec\.gov": "SEC",
    r"finra\.org": "FINRA",
    r"federalreserve\.gov": "Federal Reserve",
    r"occ\.gov": "OCC",
    r"cftc\.gov": "CFTC",
    r"cfpb\.gov": "CFPB",
    # Consulting / Big4
    r"mckinsey\.com": "McKinsey",
    r"deloitte\.com": "Deloitte",
    r"pwc\.com|pricewaterhousecoopers": "PwC",
    r"ey\.com|ernst.?young": "EY",
    r"kpmg\.com": "KPMG",
    r"accenture\.com": "Accenture",
    # VC-backed FinTech
    r"a16z\.com|andreessen": "a16z",
    r"sequoia": "Sequoia Capital",
}


@dataclass
class ContributorRecord:
    """Represents a developer in the FinTech OSS ecosystem."""

    github_login: str
    display_name: str = ""
    email: str = ""
    company: str = ""
    location: str = ""
    bio: str = ""
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    institutional_affiliation: Optional[str] = None
    repo_contributions: List[str] = field(default_factory=list)  # repo IDs

    @property
    def id(self) -> str:
        return f"github:{self.github_login}"

    @property
    def influence_proxy(self) -> float:
        """Quick proxy for influence before graph centrality is computed."""
        return math.log1p(self.followers) * 2 + math.log1p(self.public_repos)


@dataclass
class NetworkEdge:
    """A COLLABORATES_WITH edge between two contributors."""

    contributor_a: str
    contributor_b: str
    shared_repos: List[str] = field(default_factory=list)
    collaboration_strength: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Affiliation detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_institutional_affiliation(
    company: str, email: str, bio: str
) -> Optional[str]:
    """
    Returns the institution name if the contributor appears to be affiliated
    with a known financial institution, regulator, or major FinTech company.
    """
    text = f"{company} {email} {bio}".lower()
    for pattern, institution in INSTITUTIONAL_PATTERNS.items():
        if re.search(pattern, text):
            return institution
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Influence scoring
# ─────────────────────────────────────────────────────────────────────────────

def compute_influence_score(
    contributor: ContributorRecord,
    repo_count: int,
    cross_repo_count: int,
    institutional: bool,
) -> float:
    """
    Influence score 0–100 for a contributor in the FinTech OSS graph.

    Components:
    - Reach (followers, public repos): 0–30
    - Cross-repo activity (bridge node signal): 0–35
    - Institutional affiliation (institutional backing): 0–20
    - Ecosystem depth (fintech-specific repos): 0–15
    """
    reach = min(math.log1p(contributor.followers) * 3 +
                math.log1p(contributor.public_repos) * 1.5, 30.0)
    bridge = min(cross_repo_count * 4, 35.0)
    affiliation = 20.0 if institutional else 0.0
    depth = min(repo_count * 2.5, 15.0)
    return round(reach + bridge + affiliation + depth, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

class ContributorNetworkAgent(BaseAgent):
    """
    Agent 4: Maps the human network layer of FinTech open-source.

    Builds :Developer nodes and relationship edges:
    - (Developer)-[:CONTRIBUTED_TO]->(Repository)
    - (Developer)-[:COLLABORATES_WITH]->(Developer)
    - (Developer)-[:EMPLOYED_BY]->(Organization)
    - (Developer)-[:AFFILIATED_WITH]->(Institution)
    """

    def __init__(self, github_token: str = "", **kwargs):
        super().__init__(name="ContributorNetworkAgent", **kwargs)
        self.github_token = github_token

    async def _run(self, result: AgentResult) -> AgentResult:
        repos = await self._fetch_repos_for_network_analysis()
        result.items_processed = len(repos)

        all_contributors: Dict[str, ContributorRecord] = {}
        total_edges = 0
        institutional_count = 0

        for batch in self._chunk(repos, 20):
            tasks = [self._process_repo_contributors(r) for r in batch]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for outcome in outcomes:
                if isinstance(outcome, Exception):
                    result.errors.append(str(outcome))
                elif isinstance(outcome, dict):
                    for login, contributor in outcome["contributors"].items():
                        if login not in all_contributors:
                            all_contributors[login] = contributor
                        else:
                            # Merge repo contributions
                            all_contributors[login].repo_contributions.extend(
                                [r for r in contributor.repo_contributions
                                 if r not in all_contributors[login].repo_contributions]
                            )
                    total_edges += outcome["edges"]
                    institutional_count += outcome["institutional"]

        # Upsert all discovered contributors
        upserted = 0
        for batch in self._chunk(list(all_contributors.values()), 100):
            tasks = [self._upsert_contributor(c) for c in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            upserted += len(batch)

        # Build collaboration edges (contributors who share repos)
        collab_edges = await self._build_collaboration_edges(all_contributors)

        result.items_created = upserted
        result.items_updated = total_edges + collab_edges
        result.metadata["institutional_contributors"] = institutional_count
        result.metadata["collaboration_edges"] = collab_edges

        result.insights.append(
            f"Mapped {upserted} contributors across {len(repos)} repositories"
        )
        if institutional_count > 0:
            result.insights.append(
                f"Institutional contributors detected: {institutional_count} "
                f"(banks, regulators, FinTech firms)"
            )

        # Surface top influencers
        top = sorted(
            all_contributors.values(),
            key=lambda c: c.influence_proxy,
            reverse=True,
        )[:5]
        if top:
            result.insights.append(
                f"Top FinTech OSS contributors: "
                f"{', '.join(c.github_login for c in top)}"
            )

        return result

    async def _fetch_repos_for_network_analysis(self) -> List[Dict]:
        return await self._neo4j_query("""
            MATCH (r:Repository)
            WHERE r.stars >= 100
              AND r.primary_sector IS NOT NULL
              AND (
                r.contributor_network_at IS NULL
                OR r.contributor_network_at < datetime() - duration({days: 30})
              )
            RETURN r.id AS id,
                   r.full_name AS full_name,
                   r.contributors_list AS contributors_list
            ORDER BY r.stars DESC
            LIMIT 2000
        """)

    async def _process_repo_contributors(self, repo: Dict) -> Dict:
        """Parse stored contributor list and build ContributorRecord objects."""
        repo_id = repo["id"]
        raw_contributors = repo.get("contributors_list") or []

        contributors: Dict[str, ContributorRecord] = {}
        edges = 0
        institutional = 0

        for raw in raw_contributors:
            if not isinstance(raw, dict):
                continue

            login = raw.get("login", "")
            if not login:
                continue

            company = raw.get("company", "") or ""
            email = raw.get("email", "") or ""
            bio = raw.get("bio", "") or ""

            affiliation = detect_institutional_affiliation(company, email, bio)

            contributor = ContributorRecord(
                github_login=login,
                display_name=raw.get("name", "") or login,
                email=email,
                company=company.strip("@"),
                location=raw.get("location", "") or "",
                bio=bio[:500],
                public_repos=raw.get("public_repos", 0) or 0,
                followers=raw.get("followers", 0) or 0,
                following=raw.get("following", 0) or 0,
                institutional_affiliation=affiliation,
                repo_contributions=[repo_id],
            )
            contributors[login] = contributor

            # Create CONTRIBUTED_TO edge
            await self._neo4j_write("""
                MERGE (d:Developer {id: $dev_id})
                SET d.github_login      = $login,
                    d.display_name      = $display_name,
                    d.company           = $company,
                    d.location          = $location,
                    d.bio               = $bio,
                    d.public_repos      = $public_repos,
                    d.followers         = $followers,
                    d.institutional_affiliation = $affiliation,
                    d.last_seen_at      = datetime($now)
                WITH d
                MATCH (r:Repository {id: $repo_id})
                MERGE (d)-[rel:CONTRIBUTED_TO]->(r)
                SET rel.last_seen_at = datetime($now)
            """, {
                "dev_id": contributor.id,
                "login": login,
                "display_name": contributor.display_name,
                "company": contributor.company,
                "location": contributor.location,
                "bio": contributor.bio,
                "public_repos": contributor.public_repos,
                "followers": contributor.followers,
                "affiliation": affiliation,
                "repo_id": repo_id,
                "now": datetime.now(timezone.utc).isoformat(),
            })
            edges += 1

            if affiliation:
                institutional += 1
                # Link to institution node
                await self._neo4j_write("""
                    MERGE (inst:Institution {name: $institution})
                    WITH inst
                    MATCH (d:Developer {id: $dev_id})
                    MERGE (d)-[:AFFILIATED_WITH]->(inst)
                """, {
                    "institution": affiliation,
                    "dev_id": contributor.id,
                })

        # Mark repo as processed
        await self._neo4j_write("""
            MATCH (r:Repository {id: $id})
            SET r.contributor_network_at = datetime($now)
        """, {"id": repo_id, "now": datetime.now(timezone.utc).isoformat()})

        return {"contributors": contributors, "edges": edges, "institutional": institutional}

    async def _upsert_contributor(self, contributor: ContributorRecord) -> None:
        """Compute and persist final influence score."""
        cross_repo_count = len(contributor.repo_contributions)
        influence = compute_influence_score(
            contributor,
            repo_count=cross_repo_count,
            cross_repo_count=max(0, cross_repo_count - 1),
            institutional=contributor.institutional_affiliation is not None,
        )
        await self._neo4j_write("""
            MATCH (d:Developer {id: $dev_id})
            SET d.influence_score     = $influence,
                d.cross_repo_count    = $cross_repo_count,
                d.fintech_repo_count  = $repo_count
        """, {
            "dev_id": contributor.id,
            "influence": influence,
            "cross_repo_count": max(0, cross_repo_count - 1),
            "repo_count": cross_repo_count,
        })

    async def _build_collaboration_edges(
        self, contributors: Dict[str, ContributorRecord]
    ) -> int:
        """
        For contributors who share 2+ repositories, create COLLABORATES_WITH edges
        with a collaboration strength score.
        """
        # Build repo→contributors inverted index
        repo_to_devs: Dict[str, List[str]] = {}
        for login, contributor in contributors.items():
            for repo_id in contributor.repo_contributions:
                if repo_id not in repo_to_devs:
                    repo_to_devs[repo_id] = []
                repo_to_devs[repo_id].append(login)

        # Find pairs that share repos
        pair_shared: Dict[Tuple[str, str], List[str]] = {}
        for repo_id, devs in repo_to_devs.items():
            for i in range(len(devs)):
                for j in range(i + 1, len(devs)):
                    pair = (min(devs[i], devs[j]), max(devs[i], devs[j]))
                    if pair not in pair_shared:
                        pair_shared[pair] = []
                    pair_shared[pair].append(repo_id)

        edges_created = 0
        for (login_a, login_b), shared in pair_shared.items():
            if len(shared) < 2:
                continue  # Only create edge for 2+ shared repos

            strength = min(math.log1p(len(shared)) * 20, 100.0)
            await self._neo4j_write("""
                MATCH (a:Developer {id: $id_a})
                MATCH (b:Developer {id: $id_b})
                MERGE (a)-[rel:COLLABORATES_WITH]-(b)
                SET rel.shared_repo_count      = $shared_count,
                    rel.collaboration_strength = $strength,
                    rel.updated_at             = datetime($now)
            """, {
                "id_a": f"github:{login_a}",
                "id_b": f"github:{login_b}",
                "shared_count": len(shared),
                "strength": round(strength, 2),
                "now": datetime.now(timezone.utc).isoformat(),
            })
            edges_created += 1

        return edges_created

    async def get_top_influencers(self, limit: int = 20) -> List[Dict]:
        """Query: top FinTech OSS contributors by influence score."""
        return await self._neo4j_query("""
            MATCH (d:Developer)
            WHERE d.influence_score IS NOT NULL
            OPTIONAL MATCH (d)-[:AFFILIATED_WITH]->(inst:Institution)
            RETURN d.github_login AS login,
                   d.display_name AS name,
                   d.influence_score AS influence,
                   d.fintech_repo_count AS repos,
                   d.institutional_affiliation AS affiliation,
                   collect(inst.name) AS institutions
            ORDER BY d.influence_score DESC
            LIMIT $limit
        """, {"limit": limit})

    async def get_institutional_contribution_map(self) -> List[Dict]:
        """
        Query: which financial institutions are most active in open-source FinTech?
        Returns institution → repo → contributor mappings.
        """
        return await self._neo4j_query("""
            MATCH (d:Developer)-[:AFFILIATED_WITH]->(inst:Institution)
            MATCH (d)-[:CONTRIBUTED_TO]->(r:Repository)
            WITH inst.name AS institution,
                 count(DISTINCT d) AS contributor_count,
                 count(DISTINCT r) AS repo_count,
                 collect(DISTINCT r.full_name)[..5] AS sample_repos
            ORDER BY contributor_count DESC
            RETURN institution, contributor_count, repo_count, sample_repos
        """)
