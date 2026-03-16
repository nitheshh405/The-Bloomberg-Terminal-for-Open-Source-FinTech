"""
Full pipeline runner — executes all 10 agents in dependency order.
Can be run locally or invoked by GitHub Actions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


def _agent_kwargs() -> Dict[str, Any]:
    return {
        "neo4j_uri": settings.neo4j.uri,
        "neo4j_auth": (settings.neo4j.username, settings.neo4j.password),
        "neo4j_database": settings.neo4j.database,
        "es_hosts": settings.elasticsearch.hosts,
        "anthropic_api_key": settings.anthropic.api_key,
    }


async def run_full_pipeline(dry_run: bool = False) -> Dict[str, Any]:
    from ai_agents.discovery.repository_discovery_agent import RepositoryDiscoveryAgent
    from ai_agents.classification.technology_classification_agent import TechnologyClassificationAgent
    from ai_agents.compliance.regulatory_analysis_agent import RegulatoryAnalysisAgent
    from ai_agents.prediction.disruption_prediction_agent import DisruptionPredictionAgent
    from ai_agents.reporting.weekly_intelligence_agent import WeeklyIntelligenceAgent

    pipeline_start = datetime.now(timezone.utc)
    results: Dict[str, Any] = {}

    agents = [
        ("discovery", RepositoryDiscoveryAgent(
            github_token=settings.github.token,
            gitlab_token=settings.gitlab.token,
            **_agent_kwargs(),
        )),
        ("classification", TechnologyClassificationAgent(**_agent_kwargs())),
        ("compliance", RegulatoryAnalysisAgent(**_agent_kwargs())),
        ("prediction", DisruptionPredictionAgent(**_agent_kwargs())),
        ("weekly_intelligence", WeeklyIntelligenceAgent(**_agent_kwargs())),
    ]

    for agent_name, agent in agents:
        logger.info("═══ Running agent: %s ═══", agent_name)
        try:
            await agent.setup()
            if dry_run:
                logger.info("[DRY RUN] Skipping %s execution", agent_name)
                results[agent_name] = {"status": "skipped (dry_run)"}
            else:
                result = await agent.run()
                results[agent_name] = {
                    "status": result.status,
                    "items_processed": result.items_processed,
                    "items_created": result.items_created,
                    "items_updated": result.items_updated,
                    "duration_seconds": result.duration_seconds,
                    "insights": result.insights,
                    "error_count": len(result.errors),
                    "metadata": result.metadata,
                }
        except Exception as exc:
            logger.exception("Agent %s failed: %s", agent_name, exc)
            results[agent_name] = {"status": "failed", "error": str(exc)}
        finally:
            try:
                await agent.teardown()
            except Exception:
                pass

    duration = (datetime.now(timezone.utc) - pipeline_start).total_seconds()
    results["pipeline"] = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_duration_seconds": duration,
        "dry_run": dry_run,
    }

    logger.info("Pipeline completed in %.1fs", duration)
    return results


async def run_single_agent(agent_name: str, output_json: str = "") -> Dict[str, Any]:
    """Run a specific agent by name."""
    from ai_agents.discovery.repository_discovery_agent import RepositoryDiscoveryAgent
    from ai_agents.classification.technology_classification_agent import TechnologyClassificationAgent
    from ai_agents.compliance.regulatory_analysis_agent import RegulatoryAnalysisAgent
    from ai_agents.prediction.disruption_prediction_agent import DisruptionPredictionAgent
    from ai_agents.reporting.weekly_intelligence_agent import WeeklyIntelligenceAgent

    AGENT_MAP = {
        "discovery": lambda: RepositoryDiscoveryAgent(
            github_token=settings.github.token,
            gitlab_token=settings.gitlab.token,
            **_agent_kwargs(),
        ),
        "classification": lambda: TechnologyClassificationAgent(**_agent_kwargs()),
        "compliance": lambda: RegulatoryAnalysisAgent(**_agent_kwargs()),
        "prediction": lambda: DisruptionPredictionAgent(**_agent_kwargs()),
        "weekly_intelligence": lambda: WeeklyIntelligenceAgent(**_agent_kwargs()),
    }

    if agent_name not in AGENT_MAP:
        raise ValueError(f"Unknown agent: {agent_name}. Choose from: {list(AGENT_MAP.keys())}")

    agent = AGENT_MAP[agent_name]()
    await agent.setup()
    result = await agent.run()
    await agent.teardown()

    result_dict = {
        "agent": agent_name,
        "status": result.status,
        "items_processed": result.items_processed,
        "items_created": result.items_created,
        "items_updated": result.items_updated,
        "duration_seconds": result.duration_seconds,
        "insights": result.insights,
        "errors": result.errors,
        "metadata": result.metadata,
    }

    if output_json:
        with open(output_json, "w") as f:
            json.dump(result_dict, f, indent=2, default=str)
        logger.info("Result written to %s", output_json)

    return result_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinTech Intelligence Terminal Pipeline Runner")
    parser.add_argument("--agent", help="Run a specific agent only")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default="", help="Save result to JSON file")
    args = parser.parse_args()

    if args.agent:
        result = asyncio.run(run_single_agent(args.agent, args.output_json))
    else:
        result = asyncio.run(run_full_pipeline(dry_run=args.dry_run))

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("pipeline", {}).get("status") != "failed" else 1)
