# GitKT — System Architecture
> Created and architected by **Nithesh Gudipuri**

## 1. Full System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FINTECH OSINT PLATFORM                                │
│                "Bloomberg Terminal for Open-Source FinTech"                  │
└──────────────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════╗
║  LAYER 1: DATA SOURCES                                                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐ ║
║  │  GitHub API  │  │ GitLab API  │  │  Bitbucket  │  │  Regulatory APIs   │ ║
║  │  REST v3/v4  │  │  REST v4    │  │  REST 2.0   │  │  Federal Register  │ ║
║  │  GraphQL v4  │  │             │  │             │  │  SEC EDGAR         │ ║
║  │  Topics      │  │  Topics     │  │  Labels     │  │  CFPB              │ ║
║  │  Search API  │  │  Search     │  │  Search     │  │  FinCEN            │ ║
║  └──────┬───────┘  └──────┬──────┘  └──────┬──────┘  └────────┬───────────┘ ║
╚═════════╪════════════════╪═══════════════════╪══════════════════╪════════════╝
          │                │                   │                  │
╔═════════▼════════════════▼═══════════════════▼══════════════════▼════════════╗
║  LAYER 2: DATA INGESTION                                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌──────────────────────────┐  ┌───────────────────────────────────────────┐ ║
║  │  Repository Discovery     │  │  Regulatory Feed Ingester                │ ║
║  │  ├─ GitHub Scanner        │  │  ├─ Federal Register API                 │ ║
║  │  ├─ GitLab Scanner        │  │  ├─ SEC EDGAR API                        │ ║
║  │  └─ Bitbucket Scanner     │  │  └─ CFPB / FinCEN endpoints              │ ║
║  │                           │  │                                           │ ║
║  │  3 discovery strategies:  │  │  Fintech relevance tagging               │ ║
║  │  1. Topic tag search       │  │  Links regulations to technologies        │ ║
║  │  2. Keyword NLP search     │  └───────────────────────────────────────────┘ ║
║  │  3. Dev network traversal  │                                              ║
║  └──────────────────────────┘                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
          │
╔═════════▼════════════════════════════════════════════════════════════════════╗
║  LAYER 3: AI AGENT SYSTEM (10 Autonomous Agents)                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────────┐ ║
║  │  BaseAgent (async, Neo4j + ES + Anthropic)                              │ ║
║  └──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────┘ ║
║         │      │      │      │      │      │      │      │      │           ║
║  Agent 1│ Ag2  │ Ag3  │ Ag4  │ Ag5  │ Ag6  │ Ag7  │ Ag8  │ Ag9  │ Ag10     ║
║  Disc.  │Class.│ Dep. │Cont. │ Sig. │Comp. │Adopt.│Disr. │Start.│Weekly    ║
║  ─────  │─────.│ ─── │────  │ ─── │────  │─────.│────  │─────.│─────     ║
║  Scans  │ NLP  │Dep.  │Dev   │Detec │Reg.  │FI    │ML    │VC    │Report    ║
║  repos  │class.│graph │netw. │spike │map   │adopt │pred. │sig.  │generator ║
║         │      │anal. │maps  │detec.│anal. │opp.  │      │detec.│          ║
║         │      │      │      │      │      │      │      │      │          ║
║  All agents share state via ──────────────────────────────────────► Neo4j   ║
╚══════════════════════════════════════════════════════════════════════════════╝
          │
╔═════════▼════════════════════════════════════════════════════════════════════╗
║  LAYER 4: KNOWLEDGE GRAPH (Neo4j)                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  NODE TYPES                        RELATIONSHIP TYPES                       ║
║  ─────────────────────              ─────────────────────────────────────── ║
║  Repository (200k+)                  (r)-[:CONTRIBUTED_BY]->(d)             ║
║  Developer (500k+)                   (r)-[:IMPLEMENTS]->(t)                 ║
║  Organization (50k+)                 (r)-[:RELEVANT_TO]->(fs)               ║
║  Technology (5k+)                    (r)-[:SUBJECT_TO]->(rl)               ║
║  FinancialSector (20)                (r)-[:SUPPORTS_COMPLIANCE]->(rl)       ║
║  Regulation (50+)                    (r)-[:DEPENDS_ON]->(r2)               ║
║  Regulator (15)                      (d)-[:COLLABORATES_WITH]->(d2)         ║
║  GeographicRegion (200+)             (d)-[:MEMBER_OF]->(o)                  ║
║  StartupEcosystem (50)               (rl)-[:ENFORCED_BY]->(reg)             ║
║  IntelligenceReport (weekly)         (t)-[:RELATED_TO]->(t2)                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
          │
╔═════════▼════════════════════════════════════════════════════════════════════╗
║  LAYER 5: ANALYSIS ENGINES                                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Innovation Scoring Engine (8 dimensions):                                  ║
║    Git Impression Score  →  Innovation Velocity Score  →  Maturity Score    ║
║    Ecosystem Influence  →  Sector Relevance  →  Adoption Potential          ║
║    Startup Score        →  Disruption Potential Score                        ║
║                                                                              ║
║  Compliance Scoring (4 dimensions):                                          ║
║    Compliance Risk  →  Regulatory Relevance  →  Auditability  →  Data Gov   ║
║                                                                              ║
║  Disruption Prediction (ML):                                                 ║
║    Feature engineering → Weighted linear + sigmoid → Infrastructure Prob    ║
║                                                                              ║
║  Startup Signal Detection:                                                   ║
║    Novelty + Community Growth + Enterprise Interest + Gap Analysis           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
          │
╔═════════▼════════════════════════════════════════════════════════════════════╗
║  LAYER 6: API LAYER (FastAPI)                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  GET  /api/v1/repositories         — List/filter repositories               ║
║  GET  /api/v1/repositories/{id}    — Repository details + all scores        ║
║  GET  /api/v1/repositories/leaderboard/disruption                           ║
║  GET  /api/v1/technologies         — Technology taxonomy                    ║
║  GET  /api/v1/regulations          — Regulation nodes                       ║
║  GET  /api/v1/graph/overview       — Graph visualization data               ║
║  GET  /api/v1/graph/stats          — Platform KPIs                          ║
║  GET  /api/v1/intelligence/reports — Weekly intelligence reports             ║
║  POST /api/v1/chat                 — Conversational AI (Claude)             ║
║  GET  /api/v1/search               — Full-text search (Elasticsearch)       ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
          │
╔═════════▼════════════════════════════════════════════════════════════════════╗
║  LAYER 7: PRESENTATION (React + D3.js)                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Dashboard Pages:                                                            ║
║  ├─ Overview           KPIs, top repos, sector distribution                 ║
║  ├─ Knowledge Graph    Interactive D3.js force-directed graph               ║
║  ├─ Innovation Radar   8-dimension bubble chart                             ║
║  ├─ Compliance Map     Regulation-technology matrix                         ║
║  ├─ Disruption Board   Leaderboard with prediction confidence               ║
║  ├─ Startup Signals    VC opportunity heatmap                               ║
║  ├─ Geographic Map     US fintech developer density map                     ║
║  ├─ Weekly Reports     Markdown report viewer                               ║
║  └─ AI Chat            Conversational interface (Claude-powered)            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. AI Agent Architecture

### Agent Dependency Graph

```
┌───────────────┐
│  Agent 1      │  Repository Discovery
│  Discovery    │  Scans GitHub/GitLab/Bitbucket
└───────┬───────┘
        │ writes Repository nodes
        ▼
┌───────────────┐  ┌────────────────────┐
│  Agent 2      │  │  Agent 3           │
│  Classification│  │  Dependency        │
│  NLP domains  │  │  Analysis          │  (parallel)
└───────┬───────┘  └────────┬───────────┘
        │                    │
        ├────────────────────┤ writes Technology links + DEPENDS_ON edges
        ▼                    ▼
┌───────────────┐  ┌─────────────────────┐
│  Agent 4      │  │  Agent 5            │
│  Contributor  │  │  Innovation Signal  │  (parallel)
│  Network      │  │  Spike Detector     │
└───────┬───────┘  └────────┬────────────┘
        │                    │
        ├────────────────────┤
        ▼                    ▼
┌───────────────┐  ┌─────────────────────┐
│  Agent 6      │  │  Agent 7            │
│  Regulatory   │  │  Adoption           │  (parallel)
│  Analysis     │  │  Opportunity        │
└───────┬───────┘  └────────┬────────────┘
        │                    │
        ├────────────────────┤
        ▼                    ▼
┌───────────────┐  ┌─────────────────────┐
│  Agent 8      │  │  Agent 9            │
│  Disruption   │  │  Startup            │  (parallel)
│  Prediction   │  │  Opportunity        │
└───────┬───────┘  └────────┬────────────┘
        │                    │
        └────────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │  Agent 10         │
        │  Weekly Intel.    │
        │  Report Generator │
        └───────────────────┘
```

### Communication Pattern
All agents communicate **exclusively through the shared Neo4j knowledge graph**.
No direct agent-to-agent API calls. This ensures:
- Agents can run in parallel safely
- Partial pipeline runs are resumable
- State is always consistent and queryable

---

## 3. Innovation Scoring Formula

```
Innovation Score = Σ(dimension_score × weight)

Dimension              Weight   Description
─────────────────────  ──────   ────────────────────────────────────────────
Git Impression         0.10     Stars, forks, contributors (log-normalized)
Innovation Velocity    0.20     Growth rate, commit frequency, issue activity
Technology Maturity    0.10     Age, license, documentation quality
Ecosystem Influence    0.18     Dependent repos, fork ratio, org backing
Sector Relevance       0.17     Domain match confidence × regulatory score
Adoption Potential     0.12     License permissiveness, language, maturity
Startup Opportunity    0.06     (from Agent 9)
Disruption Potential   0.07     (from Agent 8)
```

---

## 4. Data Flow

```
GitHub/GitLab APIs
      │
      ▼ (async HTTP, rate-limited)
Repository Discovery Agent
      │
      ▼ (batch upsert, 100 repos/batch)
Neo4j: Repository + Organization nodes
      │
      ▼ (parallel classification)
Technology Classification Agent
      │ NLP rules + Claude AI
      ▼
Neo4j: IMPLEMENTS edges, Technology nodes, RELEVANT_TO sector edges
      │
      ▼
Regulatory Analysis Agent
      │ Signal matching + regulation mapping
      ▼
Neo4j: SUBJECT_TO + SUPPORTS_COMPLIANCE edges, compliance scores
      │
      ▼
Innovation Scoring Pipeline
      │ 8-dimensional scoring
      ▼
Neo4j: innovation_score, disruption_score, startup_score per Repository
      │
      ▼
Weekly Intelligence Agent
      │ Claude-powered synthesis
      ▼
automation/reports/YYYY-MM-DD-weekly-intelligence.md
      │
      ▼ git commit
GitHub repository (automation/reports/)
```

---

## 5. Deployment Topology

### Local Development
```
localhost:7474  →  Neo4j Browser
localhost:7687  →  Neo4j Bolt (API)
localhost:9200  →  Elasticsearch
localhost:8000  →  FastAPI Backend
localhost:3000  →  React Dashboard
```

### Production (Kubernetes)
```
                    ┌─────────────────┐
Internet ──► Ingress│  NGINX Ingress  │
                    └────────┬────────┘
                    /        │        \api
                   ▼         │         ▼
          Dashboard Pod   ───┘    API Pod (3x replicas)
          (nginx:alpine)          (uvicorn workers)
                                       │
                    ┌──────────────────┤
                    │                  │
                    ▼                  ▼
               Neo4j Pod        Elasticsearch Pod
               (StatefulSet)    (StatefulSet)
                    │
                    ▼
            Persistent Volume (graph data)
```

---

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Graph DB | Neo4j | Native graph queries, APOC plugins, GDS for ML |
| Search | Elasticsearch | Full-text search across README content |
| Agent Communication | Shared Neo4j | No message broker needed; all state is queryable |
| AI Model | Claude (Anthropic) | Best at nuanced financial domain classification |
| Disruption Model | Heuristic → ML | Start fast with domain expertise; train with labels over time |
| Pipeline Trigger | GitHub Actions | Zero infrastructure, auto-runs on schedule |
| Frontend | React + D3.js | Maximum flexibility for custom graph visualizations |
| API Framework | FastAPI | Async, auto-docs, Pydantic validation |
| Task Queue | Celery + Redis | Distributed ingestion, automatic rate-limit retry |
| Auth | OIDC + JWT (python-jose) | Enterprise SSO (Azure AD / Okta) without custom auth |

---

## 11. Enterprise Risk Mitigations (Production-Grade)

### 11.1 Data Provenance — Eliminating AI Hallucinations

**Problem:** AI compliance claims without citations can mislead compliance officers and expose institutions to regulatory liability.

**Architecture:**

```
Claude (tool_use) ─────► ComplianceClaim (Pydantic strict schema)
                                │
                    ┌───────────▼────────────┐
                    │  CodeCitation (required) │
                    │  • file_path             │
                    │  • line_start / line_end │
                    │  • exact_quote (≥10 ch.) │  ← verbatim, no paraphrasing
                    │  • evidence_url          │  ← GitHub permalink
                    │  • confidence_score      │  ← 0.0 – 1.0
                    └───────────┬─────────────┘
                                │
              confidence ≥ 0.8 ?
              ┌─────────────────┴──────────────────┐
             YES                                    NO
              │                                     │
    hitl_status = "auto"              hitl_status = "pending"
    → Neo4j COMPLIES_WITH             → HITL queue (compliance officer review)
      verified = true                   GET /api/v1/hitl/pending
                                        POST /{repo_id}/approve | /reject
```

**Key files:**
- `api/schemas/compliance_citation.py` — Pydantic models + Claude tool schema
- `knowledge-graph/hitl/hitl_queue.py` — Neo4j HITL queue manager
- `api/routers/hitl_review.py` — REST endpoints for dashboard review panel

**Neo4j relationship:**
```cypher
(Repository)-[:COMPLIES_WITH {
    confidence:   0.72,
    hitl_status:  "pending",
    exact_quote:  "aml_check(transaction)",
    evidence_url: "https://github.com/org/repo/blob/SHA/file#L42",
    reviewed_by:  null
}]->(RegulatoryFramework)
```

---

### 11.2 Ingestion Scalability — GitHub Rate Limit Architecture

**Problem:** GitHub REST API: 5,000 req/hr/token. Scanning 50k repos exhausts this in minutes.

**Solution stack:**

```
┌──────────────────────────────────────────────────────────┐
│  GitHubTokenPool  (data-ingestion/github/token_pool.py)  │
│  • Holds N PATs (GITHUB_TOKEN, GITHUB_TOKEN_1…9)         │
│  • Round-robin rotation per request                       │
│  • Auto-sleep until X-RateLimit-Reset on exhaustion       │
│  • Effective limit: N × 5,000 req/hr                      │
└────────────────────────┬─────────────────────────────────┘
                         │ provides headers to
┌────────────────────────▼─────────────────────────────────┐
│  GitHubGraphQLClient  (data-ingestion/github/graphql_client.py) │
│  • 1 GraphQL request = metadata + commits + contributors  │
│    + releases + directory listing  (was 6 REST calls)     │
│  • Concurrency: asyncio.Semaphore(10) — polite batching   │
└────────────────────────┬─────────────────────────────────┘
                         │ results queued via
┌────────────────────────▼─────────────────────────────────┐
│  Celery Tasks  (data-ingestion/queue/)                    │
│  • celery_app.py  — broker=Redis, beat schedule           │
│  • ingestion_tasks.py:                                    │
│    - ingest_repo(owner, name)   → GraphQL → Neo4j         │
│    - run_full_ingestion_sweep() → Monday 02:00 UTC        │
│    - refresh_active_repos()     → every 6 hours           │
│    - rescan_rejected_repos()    → after HITL reject        │
│  • Rate-limit retry: self.retry(countdown=reset_time)     │
└──────────────────────────────────────────────────────────┘
```

**Start workers:**
```bash
docker run -p 6379:6379 redis:7-alpine
celery -A data_ingestion.queue.celery_app worker --concurrency=4
celery -A data_ingestion.queue.celery_app beat
```

---

### 11.3 Enterprise Integration — OIDC / RBAC

**Problem:** Financial institutions require SSO via Azure AD / Okta / Ping. Username/password systems are blocked by IT security policy.

**OIDC Flow:**

```
Browser                 Azure AD / Okta              FastAPI
   │                         │                          │
   │── login redirect ───────►│                          │
   │◄── access_token JWT ─────│                          │
   │                         │                          │
   │── GET /api/v1/hitl/pending ─────────────────────────►│
   │   Authorization: Bearer <JWT>                        │
   │                                                      │
   │                              ┌─── get_current_user() │
   │                              │    fetch JWKS (cached)│
   │                              │    verify RS256 sig   │
   │                              │    decode claims      │
   │                              └──► AuthenticatedUser  │
   │                                   .sub / .email      │
   │                                   .roles: ["compliance_officer"]
   │                                         │
   │                              require_role("compliance_officer")
   │                              _effective_level ≥ 2 ? → 200 OK
   │◄── 200 pending queue ─────────────────────────────────│
```

**Role mapping (Azure AD App Roles):**

| Azure AD App Role | GitKT Role | Permissions |
|---|---|---|
| `GitKT.Admin` | `admin` | Full access |
| `GitKT.ComplianceOfficer` | `compliance_officer` | HITL approve/reject + all reads |
| `GitKT.Analyst` | `analyst` | Read-only (repos, scores, reports) |
| `GitKT.Developer` | `developer` | API pipeline access |

**Key files:**
- `api/auth/oidc.py` — JWKS discovery, JWT validation, `get_current_user()`
- `api/auth/rbac.py` — `require_role(min_role)` dependency factory + audit log

**Environment variables:**
```bash
AUTH_ENABLED=true
OIDC_ISSUER_URL=https://login.microsoftonline.com/{tenant}/v2.0
OIDC_AUDIENCE=api://gitkt-platform
```

---

## 12. Test Coverage Map

| File | Tests | Covers |
|---|---|---|
| `test_innovation_scoring.py` | 14 | InnovationScores dataclass, ScoringEngine |
| `test_compliance_frameworks.py` | 21 | 9 frameworks, domain/jurisdiction lookups |
| `test_dependency_analysis.py` | 20 | Manifest parsers, supply-chain risk |
| `test_innovation_signal.py` | 20 | ISS velocity, pre-viral, cross-pollination |
| `test_adoption_opportunity.py` | 24 | 6-dimension readiness, sector affinity |
| `test_enterprise_risks.py` | 37 | Citation schema, token pool, RBAC levels |
| `test_api_health.py` | 17 | FastAPI routing, CORS, search validation |
| **Total** | **153** | |
