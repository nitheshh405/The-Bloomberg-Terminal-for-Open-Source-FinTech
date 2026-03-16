# GitKT
### The Bloomberg Terminal for Open-Source FinTech — Built for the Dev Community

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-blue.svg)](https://neo4j.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)
[![Built with Claude](https://img.shields.io/badge/built%20with-Claude%20AI-blueviolet)](https://claude.ai)
[![Agents](https://img.shields.io/badge/AI%20agents-14%20active-brightgreen)](#)
[![Tests](https://img.shields.io/badge/tests-266%20passing-brightgreen)](#)

---

## 📊 Live Platform Metrics
> *Auto-updated every Sunday by [AutonomousDocsAgent](ai-agents/orchestration/autonomous_docs_agent.py)*

| Metric | Value |
|--------|-------|
<!-- LIVE_METRICS_START -->
| 🏦 Repositories Tracked | **–** |
| 📈 Avg Innovation Score | **–** |
| 🚀 Breakout Repos (live) | **–** |
| 👥 Developer Network | **–** |
| 🟡 Compliance Gap | **–** |
| 🔄 Updated this week | **–** |
<!-- LIVE_METRICS_END -->

---

## The Vision

> *"Every financial institution, regulator, and startup deserves to see what's coming — before it arrives."*
>
> — **Nithesh Gudipuri**, Creator & Architect

The global financial system is being rewritten in open source. Thousands of developers are quietly building the infrastructure, tooling, and protocols that will power the next generation of banking, payments, compliance, and capital markets — and almost nobody is watching.

**GitKT** is my answer to that problem.

I built this platform to do one thing: **map the knowledge hidden inside every public Git repository** — and turn it into actionable intelligence for the people who shape financial markets.

This is not a GitHub analytics tool. This is a **real-time intelligence operation** — autonomous AI agents continuously scanning the global open-source ecosystem, scoring repositories across 8 innovation dimensions, mapping them against regulatory frameworks, predicting which projects will become financial infrastructure, and surfacing the startup opportunities that institutional money hasn't found yet.

---

## What This Is

**GitKT** is a next-generation autonomous AI intelligence platform that:

- Continuously mines GitHub, GitLab, and Bitbucket for emerging FinTech repositories
- Builds a living knowledge graph connecting repositories, developers, organizations, technologies, regulators, and regulations
- Scores every repository across 8 innovation dimensions — from velocity and ecosystem influence to disruption probability and regulatory exposure
- Maps open-source projects to SEC, FINRA, OCC, CFTC, CFPB, and FinCEN compliance frameworks
- Predicts which open-source projects are on a trajectory to become financial infrastructure in 3–5 years
- Detects startup-worthy open-source clusters before venture capital does
- Publishes weekly intelligence reports, automatically, every Monday

---

## Core Capabilities

| Capability | Description |
|---|---|
| Repository Discovery | Scans GitHub, GitLab, Bitbucket for fintech repositories |
| Knowledge Graph | Neo4j graph connecting repos, devs, orgs, technologies, and regulations |
| Innovation Scoring | 8-dimensional scoring engine per repository |
| AI Agent System | 10 autonomous agents from discovery to reporting |
| Compliance Analysis | Maps repos to SEC, FINRA, OCC, CFTC, CFPB, FinCEN frameworks |
| Disruption Prediction | ML model estimating infrastructure probability over 3–5 years |
| Startup Signals | Detects VC-attractable open-source clusters before they're funded |
| Weekly Intelligence | Auto-generated reports committed to Git every Monday at 06:00 UTC |
| Conversational AI | Natural language queries over the full knowledge graph |
| Interactive Dashboard | React + D3.js visualizations, compliance maps, geographic heat maps |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitKT Platform                          │
├─────────────┬──────────────────┬──────────────────┬─────────────┤
│  Data Layer │   AI Agent Layer │  Analysis Layer  │  API Layer  │
├─────────────┼──────────────────┼──────────────────┼─────────────┤
│ GitHub API  │ Discovery Agent  │ Innovation Score │ FastAPI     │
│ GitLab API  │ Classification   │ Compliance Score │ REST        │
│ Bitbucket   │ Dependency Agent │ Disruption Model │ WebSocket   │
│ Fed Register│ Contributor Net  │ Startup Score    │             │
│ SEC EDGAR   │ Innovation Sig.  │ Adoption Analysis│             │
│ Regulatory  │ Regulatory Agent │                  │             │
│   Feeds     │ Adoption Agent   │                  │             │
│             │ Disruption Agent │                  │             │
│             │ Startup Agent    │                  │             │
│             │ Weekly Intel.    │                  │             │
├─────────────┴──────────────────┴──────────────────┴─────────────┤
│                    Knowledge Graph (Neo4j)                       │
│  Repositories · Developers · Organizations · Technologies       │
│  Financial Sectors · Regulations · Regulators · Geo Regions     │
├──────────────────────────────────────────────────────────────────┤
│              Search (Elasticsearch) + ML Pipeline                │
├──────────────────────────────────────────────────────────────────┤
│          React Dashboard + D3.js + Conversational AI            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
GitKT/
├── data-ingestion/
│   ├── repository-discovery/    # GitHub/GitLab/Bitbucket scrapers
│   ├── metadata-collector/      # Repo stats, commit history, topics
│   └── regulatory-feeds/        # Federal Register, SEC, regulatory APIs
├── knowledge-graph/
│   ├── schema/                  # Cypher schema definitions
│   ├── loaders/                 # ETL into Neo4j
│   └── queries/                 # Prebuilt Cypher query library
├── ai-agents/
│   ├── base/                    # Abstract base agent
│   ├── discovery/               # Repository discovery agent
│   ├── classification/          # Technology classification agent
│   ├── compliance/              # Regulatory analysis agent
│   ├── prediction/              # Disruption + startup agents
│   └── reporting/               # Weekly intelligence agent
├── innovation-scoring/          # 8-dimensional scoring engine
├── adoption-analysis/           # Financial sector adoption mapping
├── compliance-analysis/         # Regulator and framework mapping
├── disruption-prediction/       # ML disruption probability model
├── startup-opportunity-detection/
├── api/
│   ├── routers/                 # FastAPI route handlers
│   ├── models/                  # Pydantic schemas
│   └── services/                # Business logic services
├── dashboard/
│   └── src/
│       ├── components/          # React components
│       ├── pages/               # Dashboard pages
│       └── services/            # API client services
├── automation/
│   ├── workflows/               # GitHub Actions pipelines
│   ├── scripts/                 # Scheduled pipeline scripts
│   └── reports/                 # Generated weekly intelligence reports
├── deploy/
│   ├── docker/                  # Dockerfiles + docker-compose
│   └── kubernetes/              # K8s manifests
├── config/                      # Configuration and environment templates
├── tests/                       # Unit and integration tests
└── docs/                        # Architecture and API documentation
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/nitheshh405/The-Bloomberg-Terminal-for-Open-Source-FinTech.git
cd GitKT

# 2. Configure environment
cp config/env.example .env
# Fill in your API keys: GitHub, Anthropic, Neo4j credentials

# 3. Start infrastructure
docker-compose -f deploy/docker/docker-compose.yml up -d

# 4. Initialize the knowledge graph
python knowledge-graph/loaders/init_schema.py

# 5. Start the API
.venv/bin/python3 -m uvicorn api.main:app --reload --port 8000

# 6. Start the dashboard
cd dashboard && npm install && npm run dev

# 7. Run the first discovery cycle
python automation/scripts/run_pipeline.py
```

API docs available at: `http://localhost:8000/api/docs`
Dashboard available at: `http://localhost:3000`

---

## Weekly Intelligence Reports

Every Monday at 06:00 UTC, the platform automatically:

1. Runs the full discovery and scoring pipeline
2. Generates a Markdown intelligence report via Claude AI
3. Commits the report to `automation/reports/YYYY-MM-DD-weekly-intelligence.md`

---

## About

**Created and architected by [Nithesh Gudipuri](https://github.com/nitheshh405).**

The concept, product vision, system design, and intelligence methodology behind GitKT are entirely my own. Claude AI was used as a development accelerator to implement the architecture I specified — translating my vision into working code at speed.

This project is an expression of a core belief: *the most valuable financial intelligence isn't locked behind Bloomberg terminals or hedge fund research desks — it's hiding in plain sight on GitHub, waiting for someone to map it.*

---

## License

MIT — See [LICENSE](LICENSE)

Copyright (c) 2026 Nithesh Gudipuri
