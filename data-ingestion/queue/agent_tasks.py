"""
Agent Intelligence Cycle — Celery Tasks
=========================================
Orchestrates the weekly autonomous intelligence cycle for all 13 GitKT agents.
Each task is independently retryable and idempotent.

Full weekly schedule (defined in celery_app.py beat_schedule):
─────────────────────────────────────────────────────────────
  Mon 02:00  Ingestion        — full GitHub/GitLab sweep (ingestion_tasks.py)
  Tue 03:00  Classification   — technology tagging + regulatory analysis (Agents 2, 3)
  Wed 03:00  Network/Adoption — contributor graph + sector scoring (Agents 4, 5)
  Thu 03:00  Disruption/Deps  — disruption prediction + supply chain (Agents 6, 7)
  Fri 03:00  Signals          — innovation signal + future trajectory + external (Agents 8, 10, 11)
  Sat 04:00  Meta-learning    — evaluate predictions + tune weights (Agent 12)
  Sun 05:00  Report           — Claude narrative weekly report (Agent 9)
  Sun 06:00  Docs update      — auto-update README/CONTRIBUTING/CHANGELOG (Agent 14)

  1st/month 06:00  Index — GitKT FinTech OSS Index publication (Agent 13)

Each task is independent — failure in one day does not block the others.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _driver():
    from neo4j import GraphDatabase
    uri  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    pw   = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, pw))


def _gh_token() -> str:
    return os.getenv("GITHUB_TOKEN", "")


try:
    from data_ingestion.queue.celery_app import app as celery_app

    # ── Tuesday: Classification + Regulatory ──────────────────────────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_classification_cycle",
        max_retries=3, default_retry_delay=300,
    )
    def run_classification_cycle(self) -> Dict[str, Any]:
        """
        Agents 2 + 3: technology classification and regulatory analysis
        for all repos ingested since last run.
        """
        driver = None
        try:
            driver = _driver()
            results: Dict[str, Any] = {}

            from ai_agents.classification.technology_classification_agent import TechnologyClassificationAgent
            agent2 = TechnologyClassificationAgent(neo4j_driver=driver)
            import asyncio
            r2 = asyncio.run(agent2.run())
            results["technology_classification"] = r2.summary if hasattr(r2, "summary") else str(r2)

            from ai_agents.compliance.regulatory_analysis_agent import RegulatoryAnalysisAgent
            agent3 = RegulatoryAnalysisAgent(neo4j_driver=driver)
            r3 = asyncio.run(agent3.run())
            results["regulatory_analysis"] = r3.summary if hasattr(r3, "summary") else str(r3)

            logger.info("Classification cycle complete: %s", results)
            return results

        except Exception as exc:
            logger.error("Classification cycle failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

    # ── Wednesday: Contributor Network + Adoption ─────────────────────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_network_adoption_cycle",
        max_retries=3, default_retry_delay=300,
    )
    def run_network_adoption_cycle(self) -> Dict[str, Any]:
        """Agents 4 + 5: contributor network mapping and sector adoption scoring."""
        driver = None
        try:
            driver = _driver()
            import asyncio
            results: Dict[str, Any] = {}

            from ai_agents.network.contributor_network_agent import ContributorNetworkAgent
            r4 = asyncio.run(ContributorNetworkAgent(github_token=_gh_token(), neo4j_driver=driver).run())
            results["contributor_network"] = r4.summary if hasattr(r4, "summary") else str(r4)

            from ai_agents.adoption.adoption_opportunity_agent import AdoptionOpportunityAgent
            r5 = asyncio.run(AdoptionOpportunityAgent(neo4j_driver=driver).run())
            results["adoption_opportunity"] = r5.summary if hasattr(r5, "summary") else str(r5)

            logger.info("Network/adoption cycle complete: %s", results)
            return results

        except Exception as exc:
            logger.error("Network/adoption cycle failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

    # ── Thursday: Disruption + Dependency ────────────────────────────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_disruption_dependency_cycle",
        max_retries=3, default_retry_delay=300,
    )
    def run_disruption_dependency_cycle(self) -> Dict[str, Any]:
        """Agents 6 + 7: disruption prediction and supply-chain dependency analysis."""
        driver = None
        try:
            driver = _driver()
            import asyncio
            results: Dict[str, Any] = {}

            from ai_agents.prediction.disruption_prediction_agent import DisruptionPredictionAgent
            r6 = asyncio.run(DisruptionPredictionAgent(neo4j_driver=driver).run())
            results["disruption_prediction"] = r6.summary if hasattr(r6, "summary") else str(r6)

            from ai_agents.dependency.dependency_analysis_agent import DependencyAnalysisAgent
            r7 = asyncio.run(DependencyAnalysisAgent(neo4j_driver=driver).run())
            results["dependency_analysis"] = r7.summary if hasattr(r7, "summary") else str(r7)

            logger.info("Disruption/dependency cycle complete: %s", results)
            return results

        except Exception as exc:
            logger.error("Disruption/dependency cycle failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

    # ── Friday: Innovation Signals + Future Trajectory + External ─────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_signals_cycle",
        max_retries=3, default_retry_delay=300,
    )
    def run_signals_cycle(self) -> Dict[str, Any]:
        """Agents 8 + 10 + 11: innovation signal, future trajectory, external correlator."""
        driver = None
        try:
            driver = _driver()
            import asyncio
            results: Dict[str, Any] = {}

            from ai_agents.signals.innovation_signal_agent import InnovationSignalAgent
            r8 = asyncio.run(InnovationSignalAgent(neo4j_driver=driver).run())
            results["innovation_signal"] = r8.summary if hasattr(r8, "summary") else str(r8)

            from ai_agents.signals.future_signal_agent import FutureSignalAgent
            r10 = FutureSignalAgent(driver).run()
            results["future_signal"] = {
                "processed": r10.get("processed", 0),
                "breakouts": r10.get("breakouts", 0),
                "alerts":    r10.get("alerts", 0),
            }

            from ai_agents.signals.external_signal_correlator import ExternalSignalCorrelator
            r11 = asyncio.run(ExternalSignalCorrelator(driver).run_batch())
            results["external_correlator"] = r11

            logger.info("Signals cycle complete: %s", results)
            return results

        except Exception as exc:
            logger.error("Signals cycle failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

    # ── Saturday: Meta-learning ───────────────────────────────────────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_meta_learning_cycle",
        max_retries=3, default_retry_delay=300,
    )
    def run_meta_learning_cycle(self) -> Dict[str, Any]:
        """
        Agent 12: MetaLearningOrchestrator.
        Evaluates due predictions, computes accuracy, tunes weights.
        The swarm gets smarter every week.
        """
        driver = None
        try:
            driver = _driver()
            from ai_agents.orchestration.meta_learning_orchestrator import MetaLearningOrchestrator
            result = MetaLearningOrchestrator(driver).run_weekly_cycle()
            logger.info("Meta-learning cycle complete: %s", result)
            return result
        except Exception as exc:
            logger.error("Meta-learning cycle failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

    # ── Sunday 05:00: Weekly intelligence report ──────────────────────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_weekly_report",
        max_retries=2, default_retry_delay=600,
    )
    def run_weekly_report(self) -> Dict[str, Any]:
        """
        Agent 9: WeeklyIntelligenceAgent.
        Claude-generated narrative report — sent to report_dir on disk.
        """
        driver = None
        try:
            driver = _driver()
            import asyncio
            from ai_agents.reporting.weekly_intelligence_agent import WeeklyIntelligenceAgent
            report_dir = os.getenv("REPORT_DIR", "automation/reports")
            r9 = asyncio.run(WeeklyIntelligenceAgent(
                report_dir=report_dir, neo4j_driver=driver
            ).run())
            result = r9.summary if hasattr(r9, "summary") else str(r9)
            logger.info("Weekly report complete: %s", result)
            return {"weekly_report": result}
        except Exception as exc:
            logger.error("Weekly report failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

    # ── Sunday 06:00: Autonomous docs update ─────────────────────────────────

    @celery_app.task(
        bind=True,
        name="data_ingestion.queue.agent_tasks.run_autonomous_docs_update",
        max_retries=2, default_retry_delay=300,
    )
    def run_autonomous_docs_update(self) -> Dict[str, Any]:
        """
        Agent 14: AutonomousDocsAgent.
        Updates README live-metric badges, CONTRIBUTING agent count,
        CHANGELOG with this week's highlights.
        No human needed — the platform documents itself.
        """
        driver = None
        try:
            driver = _driver()
            from ai_agents.orchestration.autonomous_docs_agent import AutonomousDocsAgent
            result = AutonomousDocsAgent(driver).run()
            logger.info("Docs update complete: %s", result)
            return result
        except Exception as exc:
            logger.error("Docs update failed: %s", exc)
            raise self.retry(exc=exc)
        finally:
            if driver:
                driver.close()

except ImportError:
    # Celery not installed — stubs for direct testing / CLI use
    logger.warning("Celery not installed; agent_tasks running as plain functions")

    def run_classification_cycle() -> Dict[str, Any]:          # type: ignore[misc]
        return {"status": "stub — install celery"}
    def run_network_adoption_cycle() -> Dict[str, Any]:        # type: ignore[misc]
        return {"status": "stub — install celery"}
    def run_disruption_dependency_cycle() -> Dict[str, Any]:   # type: ignore[misc]
        return {"status": "stub — install celery"}
    def run_signals_cycle() -> Dict[str, Any]:                 # type: ignore[misc]
        return {"status": "stub — install celery"}
    def run_meta_learning_cycle() -> Dict[str, Any]:           # type: ignore[misc]
        return {"status": "stub — install celery"}
    def run_weekly_report() -> Dict[str, Any]:                 # type: ignore[misc]
        return {"status": "stub — install celery"}
    def run_autonomous_docs_update() -> Dict[str, Any]:        # type: ignore[misc]
        return {"status": "stub — install celery"}
