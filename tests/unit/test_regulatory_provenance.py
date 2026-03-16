"""Unit tests for regulatory mapping provenance safeguards."""

from ai_agents.compliance.regulatory_analysis_agent import RegulatoryAnalysisAgent


def _agent() -> RegulatoryAnalysisAgent:
    return RegulatoryAnalysisAgent(
        neo4j_uri="bolt://localhost:7687",
        neo4j_auth=("neo4j", "password"),
    )


def test_build_regulation_provenance_contains_evidence_fields():
    agent = _agent()
    text = "transaction monitoring sanctions OFAC KYC identity verification"
    p = agent._build_regulation_provenance("regulation:bsa", text)

    assert p["method"] == "rule_based_v1"
    assert p["signal_count"] >= 2
    assert isinstance(p["signals"], list)
    assert len(p["hash"]) == 16
    assert 0.0 <= p["confidence"] <= 1.0


def test_match_regulations_uses_minimum_signal_threshold():
    agent = _agent()
    # One weak mention should not pass threshold
    matched = agent._match_regulations("only mentions sanctions once")
    assert "regulation:bsa" not in matched
