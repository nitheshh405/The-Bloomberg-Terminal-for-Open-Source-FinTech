# Contributing to GitKT
> The Bloomberg Terminal for Open-Source FinTech — Built for the Dev Community

**Created and architected by [Nithesh Gudipuri](https://github.com/nitheshh405)**
Claude AI was used as a development accelerator. The concept, design, and methodology are entirely Nithesh's original work.

---

## Who Should Contribute?

| You are... | You can contribute... |
|---|---|
| **FinTech Developer** | New AI agents, scoring improvements, sector coverage |
| **Compliance Engineer** | New regulatory frameworks, citation validation logic |
| **Data Engineer** | Ingestion connectors, GraphQL optimisations, new data sources |
| **Frontend Developer** | Dashboard tabs, chart components, HITL review UI |
| **ML Engineer** | Disruption prediction models, embedding improvements |
| **Financial Institution** | Regulatory data, institutional adoption, pilot feedback |

---

## Quick Start (3 Commands)

```bash
# 1. Clone and enter
git clone https://github.com/nitheshh405/GitKT
cd GitKT

# 2. Start services (Neo4j + Redis + API + Dashboard)
docker compose up          # installs everything automatically

# 3. Verify — should see 153 tests passing
python3 -m pytest tests/unit/ -v
```

The dashboard opens at **http://localhost:3000**
The API docs open at **http://localhost:8000/api/docs**

---

## Repository Map

```
GitKT/
│
├── ai-agents/                  ← 10 autonomous AI agents (extend here)
│   ├── base/base_agent.py      ← BaseAgent — inherit this for any new agent
│   ├── discovery/              ← Agent 1: finds new FinTech repos
│   ├── classification/         ← Agent 2: assigns sectors & domains
│   ├── dependency/             ← Agent 3: supply chain graph
│   ├── network/                ← Agent 4: contributor influence network
│   ├── signals/                ← Agent 5: innovation velocity detection
│   ├── compliance/             ← Agent 6: regulatory framework mapping
│   ├── adoption/               ← Agent 7: sector adoption scoring
│   ├── reporting/              ← Agent 8: weekly intelligence reports
│   ├── prediction/             ← Agent 9: disruption prediction
│   └── prediction/             ← Agent 10: startup opportunity scoring
│
├── api/                        ← FastAPI backend
│   ├── main.py                 ← App entry point + router registration
│   ├── routers/                ← One file per API domain
│   │   ├── hitl_review.py      ← HITL compliance review endpoints (NEW)
│   │   └── ...
│   ├── schemas/
│   │   └── compliance_citation.py  ← Citation + HITL Pydantic schemas (NEW)
│   ├── auth/
│   │   ├── oidc.py             ← OIDC/JWT validation (NEW)
│   │   └── rbac.py             ← Role-based access control (NEW)
│   └── services/neo4j_service.py
│
├── compliance-analysis/        ← Regulatory frameworks & regulator registry
│   ├── frameworks/frameworks.py  ← 9 frameworks (BSA, DORA, MiCA, PCI-DSS…)
│   └── regulators/regulators.py ← 13 regulators (SEC, FINRA, FCA, MAS…)
│
├── data-ingestion/             ← Data pipeline
│   ├── github/
│   │   ├── token_pool.py       ← Multi-PAT rotation (NEW — fixes rate limits)
│   │   └── graphql_client.py   ← 1 GraphQL call replaces 6 REST calls (NEW)
│   ├── queue/
│   │   ├── celery_app.py       ← Distributed task queue (NEW)
│   │   └── ingestion_tasks.py  ← Celery tasks + retry logic (NEW)
│   └── metadata-collector/     ← GitHub metadata enrichment
│
├── knowledge-graph/
│   ├── graph.py                ← Neo4j schema definitions
│   ├── queries/queries.cypher  ← 20 prebuilt Cypher queries
│   └── hitl/hitl_queue.py      ← HITL queue manager (NEW)
│
├── dashboard/src/              ← React 18 + Vite + TypeScript + Tailwind
│   ├── App.tsx                 ← Main app, TanStack Query hooks
│   └── services/api.ts         ← Typed API client
│
├── innovation-scoring/         ← 8-dimension innovation scoring engine
├── disruption-prediction/      ← Disruption potential model
├── startup-opportunity-detection/
│
├── tests/
│   ├── unit/                   ← 153 unit tests (run without any services)
│   └── integration/            ← Requires live FastAPI instance
│
└── docs/architecture/SYSTEM_ARCHITECTURE.md  ← Full architecture + ADRs
```

---

## Adding a New AI Agent (Step-by-Step)

Every agent inherits from `BaseAgent`. Here is the minimum viable agent:

```python
# ai-agents/my_domain/my_agent.py
from __future__ import annotations
from ai_agents.base.base_agent import BaseAgent, AgentResult

class MyFinTechAgent(BaseAgent):
    """
    What this agent does in one sentence.
    Which FinTech problem it solves.
    """
    agent_id   = "my_fintech_agent"
    agent_name = "My FinTech Agent"
    version    = "1.0.0"

    async def run(self, context: dict) -> AgentResult:
        # 1. Fetch data (GitHub, Neo4j, Elasticsearch)
        repos = await self._neo4j_query("MATCH (r:Repository) RETURN r LIMIT 10")

        # 2. Use Claude for intelligence extraction (with citations!)
        analysis = await self._claude_extract(
            prompt="Analyse these repos for X pattern",
            tool_schema=MY_EXTRACTION_TOOL,   # always use tool_use for structured output
            data=repos,
        )

        # 3. Write results to knowledge graph
        await self._neo4j_write(
            "MERGE (r:Repository {id: $id}) SET r.my_score = $score",
            params={"id": "github:org/repo", "score": 85.0},
        )

        return AgentResult(agent_id=self.agent_id, records_processed=len(repos))
```

**Rules for new agents:**
1. Always use `tool_use` (structured JSON) — never freeform prose from Claude
2. Every compliance claim **must** include a `CodeCitation` with `exact_quote` + `evidence_url`
3. Claims with `confidence_score < 0.8` are automatically queued for HITL review
4. Write to Neo4j using the existing node/relationship schema in `knowledge-graph/graph.py`
5. Add at least 15 unit tests in `tests/unit/test_<agent_name>.py`

---

## Adding a New Regulatory Framework

```python
# compliance-analysis/frameworks/frameworks.py
# Add to the FRAMEWORKS list:

RegulatoryFramework(
    id="my_framework",
    short_name="MF-2026",
    full_name="My Financial Framework 2026",
    jurisdiction="US",
    regulator_ids=["sec", "finra"],
    oss_relevance="high",
    technical_requirements=[
        TechnicalRequirement(
            id="MF-001",
            description="All transaction logs must be immutable",
            technology_tags=["audit-log", "immutability", "blockchain"],
            mandatory=True,
            penalty_risk="high",
        ),
    ],
)
```

---

## Enterprise Auth Setup

**For local development** (no IdP needed):
```bash
AUTH_ENABLED=false   # in .env — all requests run as synthetic admin
```

**For production with Azure AD:**
```bash
AUTH_ENABLED=true
OIDC_ISSUER_URL=https://login.microsoftonline.com/{your-tenant-id}/v2.0
OIDC_AUDIENCE=api://gitkt-platform
```

Then create App Roles in Azure AD → App Registrations → GitKT → App roles:
- `GitKT.Admin` → maps to role `admin`
- `GitKT.ComplianceOfficer` → maps to role `compliance_officer`
- `GitKT.Analyst` → maps to role `analyst`

To protect an endpoint:
```python
from api.auth.rbac import require_compliance_officer

@router.post("/sensitive")
async def do_sensitive_thing(
    user = Depends(require_compliance_officer)
):
    audit_log(user, "sensitive_action", "resource_id")
    ...
```

---

## GitHub Rate Limits — Token Pool Setup

For large-scale ingestion (> 5k repos), add multiple GitHub PATs:

```bash
# .env
GITHUB_TOKEN=ghp_primary_token
GITHUB_TOKEN_1=ghp_second_token
GITHUB_TOKEN_2=ghp_third_token
# Add up to GITHUB_TOKEN_9
# Each adds 5,000 req/hr → 5 tokens = 25,000 req/hr
```

The `GitHubTokenPool` rotates automatically and sleeps until the reset window
when all tokens are exhausted.

---

## Running the Celery Worker

```bash
# Terminal 1 — Redis broker
docker run -p 6379:6379 redis:7-alpine

# Terminal 2 — Celery worker (4 concurrent slots)
celery -A data_ingestion.queue.celery_app worker --loglevel=info --concurrency=4

# Terminal 3 — Celery beat (periodic tasks)
celery -A data_ingestion.queue.celery_app beat --loglevel=info

# Manually trigger a full ingestion sweep:
python3 -c "
from data_ingestion.queue.ingestion_tasks import ingest_repo
ingest_repo.delay('finos', 'common-domain-model')
"
```

---

## Pull Request Checklist

Before opening a PR:

- [ ] `python3 -m pytest tests/unit/ -v` passes (all 153+ tests)
- [ ] New agent: `tests/unit/test_<agent>.py` with ≥ 15 tests
- [ ] New compliance claim: uses `ComplianceClaim` schema with `CodeCitation`
- [ ] New endpoint: has RBAC guard via `Depends(require_role(...))`
- [ ] `SYSTEM_ARCHITECTURE.md` updated if new component added
- [ ] No secrets committed (use `.env` — already in `.gitignore`)

---

## FinTech Domain Primer

New to FinTech regulations? Here is what the platform tracks:

| Term | Meaning | Relevant Agent |
|---|---|---|
| **BSA** | Bank Secrecy Act — AML transaction monitoring | ComplianceAgent |
| **Dodd-Frank** | Post-2008 derivatives & systemic risk rules | ComplianceAgent |
| **DORA** | EU Digital Operational Resilience Act (2025) | InnovationSignalAgent |
| **MiCA** | EU Markets in Crypto-Assets Regulation | ComplianceAgent |
| **PCI-DSS** | Payment Card Industry Data Security Standard | DependencyAnalysisAgent |
| **T+1** | SEC rule: equity trades settle in 1 business day (2024) | InnovationSignalAgent |
| **FedNow** | Fed real-time payment rail (launched 2023) | DiscoveryAgent |
| **PSD2/3** | EU open banking directives | AdoptionOpportunityAgent |
| **FRTB** | Fundamental Review of Trading Book — Basel IV market risk | ComplianceAgent |

---

## Community & Support

- **GitHub Discussions** — architecture questions, agent ideas
- **Issues** — bug reports, new framework requests
- **Roadmap** — see [Projects tab](https://github.com/nitheshh405/GitKT/projects)

> *"This platform is built for the developer community and financial institutions — every contribution makes the FinTech ecosystem more transparent, accessible, and intelligent."*
> — Nithesh Gudipuri, Creator
