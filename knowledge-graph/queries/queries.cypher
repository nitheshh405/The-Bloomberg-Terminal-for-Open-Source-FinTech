// ============================================================================
// GitKT — Prebuilt Cypher Query Library
// Knowledge Graph: FinTech OSINT Intelligence Platform
// Author: Nithesh Gudipuri
// ============================================================================
// Usage: Run individual queries in Neo4j Browser or via the Python loader.
// All queries use $params for parameterisation.
// ============================================================================


// ── 1. TOP INNOVATION LEADERBOARD ──────────────────────────────────────────
// Top N repositories by composite innovation score

MATCH (r:Repository)
WHERE r.innovation_score IS NOT NULL
RETURN r.full_name       AS repo,
       r.primary_sector  AS sector,
       r.innovation_score AS score,
       r.stars            AS stars,
       r.disruption_score AS disruption,
       r.startup_score    AS startup
ORDER BY r.innovation_score DESC
LIMIT $limit;


// ── 2. DISRUPTION RADAR ────────────────────────────────────────────────────
// Repositories most likely to become financial infrastructure

MATCH (r:Repository)
WHERE r.disruption_score >= $min_disruption
OPTIONAL MATCH (r)-[:IMPLEMENTS]->(t:Technology)
RETURN r.full_name           AS repo,
       r.disruption_score    AS disruption_score,
       r.infra_probability   AS infra_probability,
       r.primary_sector      AS sector,
       collect(t.name)[..5]  AS technologies
ORDER BY r.disruption_score DESC
LIMIT $limit;


// ── 3. STARTUP OPPORTUNITY MAP ─────────────────────────────────────────────
// Repositories with strong VC-attractable signals

MATCH (r:Repository)
WHERE r.startup_score >= $min_startup
RETURN r.full_name       AS repo,
       r.startup_score   AS startup_score,
       r.stars            AS stars,
       r.primary_sector  AS sector,
       r.fintech_domains AS domains,
       r.innovation_signal_score AS iss
ORDER BY r.startup_score DESC
LIMIT $limit;


// ── 4. REGULATORY EXPOSURE MAP ─────────────────────────────────────────────
// Which repositories are subject to which regulations?

MATCH (r:Repository)-[rel:SUBJECT_TO]->(rl:Regulation)
RETURN r.full_name        AS repo,
       rl.name            AS regulation,
       rl.full_name       AS regulation_full_name,
       rel.risk_level     AS risk_level,
       r.compliance_risk_score AS compliance_score
ORDER BY r.compliance_risk_score DESC
LIMIT $limit;


// ── 5. COMPLIANCE SUPPORTERS ───────────────────────────────────────────────
// Repositories that HELP with compliance (tools, libraries, frameworks)

MATCH (r:Repository)-[rel:SUPPORTS_COMPLIANCE]->(rl:Regulation)
RETURN r.full_name              AS repo,
       rl.name                  AS regulation,
       rel.capabilities         AS capabilities,
       r.regulatory_relevance_score AS relevance,
       r.stars                  AS stars
ORDER BY r.regulatory_relevance_score DESC
LIMIT $limit;


// ── 6. TECHNOLOGY ECOSYSTEM CLUSTERS ───────────────────────────────────────
// Most-implemented technologies with repo counts and top repositories

MATCH (t:Technology)<-[:IMPLEMENTS]-(r:Repository)
WITH t, count(r) AS repo_count, collect(r.full_name)[..5] AS sample_repos
ORDER BY repo_count DESC
LIMIT $limit
RETURN t.name        AS technology,
       t.category    AS category,
       repo_count,
       sample_repos;


// ── 7. CONTRIBUTOR INFLUENCE NETWORK ───────────────────────────────────────
// Top developers by influence score with institutional affiliations

MATCH (d:Developer)
WHERE d.influence_score IS NOT NULL
OPTIONAL MATCH (d)-[:AFFILIATED_WITH]->(inst:Institution)
RETURN d.github_login        AS login,
       d.display_name        AS name,
       d.influence_score     AS influence,
       d.fintech_repo_count  AS fintech_repos,
       d.institutional_affiliation AS institution,
       collect(inst.name)    AS institutions
ORDER BY d.influence_score DESC
LIMIT $limit;


// ── 8. INSTITUTIONAL CONTRIBUTION MAP ──────────────────────────────────────
// Which financial institutions are most active in open-source FinTech?

MATCH (d:Developer)-[:AFFILIATED_WITH]->(inst:Institution)
MATCH (d)-[:CONTRIBUTED_TO]->(r:Repository)
WITH inst.name AS institution,
     count(DISTINCT d) AS contributor_count,
     count(DISTINCT r) AS repo_count,
     collect(DISTINCT r.full_name)[..5] AS sample_repos
ORDER BY contributor_count DESC
RETURN institution, contributor_count, repo_count, sample_repos
LIMIT $limit;


// ── 9. DEPENDENCY GRAPH — CRITICAL INFRASTRUCTURE ──────────────────────────
// Most-shared packages in the FinTech OSS dependency graph

MATCH (d:Dependency)<-[:DEPENDS_ON]-(r:Repository)
WITH d, count(r) AS repo_count
ORDER BY repo_count DESC
LIMIT $limit
RETURN d.name      AS package,
       d.ecosystem  AS ecosystem,
       repo_count,
       d.is_critical AS is_critical_fintech,
       d.risk_flags  AS risk_flags;


// ── 10. SUPPLY CHAIN RISK REPORT ───────────────────────────────────────────
// Repositories with flagged supply-chain dependencies

MATCH (r:Repository)-[:DEPENDS_ON]->(d:Dependency)
WHERE size(d.risk_flags) > 0
WITH r, collect(d.name) AS risky_deps, count(d) AS risky_count
ORDER BY risky_count DESC
LIMIT $limit
RETURN r.full_name  AS repo,
       risky_count,
       risky_deps[..5] AS sample_risky_deps,
       r.stars        AS stars;


// ── 11. INNOVATION SIGNAL — WEEKLY TOP SIGNALS ─────────────────────────────
// Highest Innovation Signal Scores updated in the last 7 days

MATCH (r:Repository)
WHERE r.innovation_signal_score IS NOT NULL
  AND r.innovation_signal_at >= datetime() - duration({days: 7})
RETURN r.full_name               AS repo,
       r.innovation_signal_score AS iss,
       r.fired_signals           AS signals,
       r.pre_viral_score         AS pre_viral,
       r.cross_pollination_score AS cross_pol,
       r.regulatory_anticipation_score AS reg_anticipation,
       r.stars                   AS stars,
       r.primary_sector          AS sector
ORDER BY r.innovation_signal_score DESC
LIMIT $limit;


// ── 12. SECTOR ADOPTION LEADERBOARD ────────────────────────────────────────
// Best adoption opportunities for a given financial sector

MATCH (s:FinancialSector {name: $sector})-[opp:HAS_ADOPTION_OPPORTUNITY]->(r:Repository)
RETURN r.full_name             AS repo,
       opp.composite_score     AS adoption_score,
       opp.adoption_stage      AS stage,
       opp.technical_maturity  AS technical_maturity,
       opp.compliance_fit      AS compliance_fit,
       opp.blocking_gaps       AS gaps,
       r.stars                 AS stars
ORDER BY opp.composite_score DESC
LIMIT $limit;


// ── 13. CROSS-SECTOR TECHNOLOGY FLOW ───────────────────────────────────────
// Technologies being adopted across multiple financial sectors

MATCH (r:Repository)-[:IMPLEMENTS]->(t:Technology)
MATCH (r)-[:RELEVANT_TO]->(fs:FinancialSector)
WITH t.name AS technology,
     collect(DISTINCT fs.name) AS sectors,
     count(DISTINCT r) AS repo_count
WHERE size(sectors) >= 2
ORDER BY size(sectors) DESC, repo_count DESC
RETURN technology, sectors, repo_count
LIMIT $limit;


// ── 14. GEOGRAPHIC INNOVATION MAP ──────────────────────────────────────────
// Repository and developer concentration by geographic region

MATCH (r:Repository)-[:LOCATED_IN]->(g:GeographicRegion)
WITH g.name AS region,
     count(r) AS repo_count,
     avg(r.innovation_score) AS avg_score
ORDER BY repo_count DESC
RETURN region, repo_count, round(avg_score, 2) AS avg_innovation_score
LIMIT $limit;


// ── 15. REGULATOR ACTIVITY MONITOR ─────────────────────────────────────────
// Recent regulatory documents and their technology impact

MATCH (rd:RegulatoryDocument)-[:AFFECTS_TECHNOLOGY]->(t:Technology)
WHERE rd.published_date >= datetime() - duration({days: $days_back})
RETURN rd.title         AS document,
       rd.regulator     AS regulator,
       rd.published_date AS published,
       collect(t.name)  AS affected_technologies
ORDER BY rd.published_date DESC
LIMIT $limit;


// ── 16. COLLABORATION NETWORK BRIDGES ──────────────────────────────────────
// Developers who bridge multiple fintech project communities

MATCH (d:Developer)-[c:COLLABORATES_WITH]->(d2:Developer)
WHERE c.shared_repo_count >= 3
RETURN d.github_login              AS developer,
       d.influence_score           AS influence,
       d.institutional_affiliation AS affiliation,
       count(c)                    AS bridge_connections,
       avg(c.collaboration_strength) AS avg_strength
ORDER BY bridge_connections DESC
LIMIT $limit;


// ── 17. VELOCITY LEADERS — FASTEST GROWING ─────────────────────────────────
// Repositories with the highest star/contributor growth rates

MATCH (r:Repository)
WHERE r.star_growth_rate IS NOT NULL
  AND r.star_growth_rate > 0
RETURN r.full_name          AS repo,
       r.star_growth_rate   AS star_growth,
       r.fork_growth_rate   AS fork_growth,
       r.contributor_growth_rate AS contrib_growth,
       r.stars              AS current_stars,
       r.primary_sector     AS sector,
       r.fired_signals      AS signals
ORDER BY r.star_growth_rate DESC
LIMIT $limit;


// ── 18. FULL KNOWLEDGE GRAPH STATS ─────────────────────────────────────────
// Platform-wide node and relationship counts

CALL {
    MATCH (r:Repository) RETURN count(r) AS repositories
}
CALL {
    MATCH (d:Developer) RETURN count(d) AS developers
}
CALL {
    MATCH (o:Organization) RETURN count(o) AS organizations
}
CALL {
    MATCH (t:Technology) RETURN count(t) AS technologies
}
CALL {
    MATCH (dep:Dependency) RETURN count(dep) AS dependencies
}
CALL {
    MATCH (fs:FinancialSector) RETURN count(fs) AS sectors
}
CALL {
    MATCH (rl:Regulation) RETURN count(rl) AS regulations
}
CALL {
    MATCH (inst:Institution) RETURN count(inst) AS institutions
}
CALL {
    MATCH ()-[rel]->() RETURN count(rel) AS total_relationships
}
RETURN repositories, developers, organizations, technologies,
       dependencies, sectors, regulations, institutions,
       total_relationships;


// ── 19. REPO DEEP DIVE ─────────────────────────────────────────────────────
// Full intelligence profile for a single repository

MATCH (r:Repository {id: $repo_id})
OPTIONAL MATCH (r)-[:IMPLEMENTS]->(t:Technology)
OPTIONAL MATCH (r)-[:SUBJECT_TO]->(rl:Regulation)
OPTIONAL MATCH (r)-[:SUPPORTS_COMPLIANCE]->(rl2:Regulation)
OPTIONAL MATCH (r)-[:MAINTAINED_BY]->(o:Organization)
OPTIONAL MATCH (r)-[:DEPENDS_ON]->(dep:Dependency)
RETURN r,
       collect(DISTINCT t.name)   AS technologies,
       collect(DISTINCT rl.name)  AS subject_to_regulations,
       collect(DISTINCT rl2.name) AS supports_compliance_for,
       o.name                     AS organization,
       count(DISTINCT dep)        AS dependency_count;


// ── 20. WEEKLY INTELLIGENCE SUMMARY ────────────────────────────────────────
// All key metrics for the weekly intelligence report generation

CALL {
    MATCH (r:Repository) RETURN count(r) AS total_repos
}
CALL {
    MATCH (r:Repository) WHERE r.disruption_score >= 70
    RETURN count(r) AS high_disruption
}
CALL {
    MATCH (r:Repository) WHERE r.startup_score >= 65
    RETURN count(r) AS startup_signals
}
CALL {
    MATCH (r:Repository)
    WHERE r.last_ingested_at >= datetime() - duration({days: 7})
    RETURN count(r) AS new_repos_this_week
}
CALL {
    MATCH (r:Repository)
    WHERE r.innovation_signal_score >= 60
      AND r.innovation_signal_at >= datetime() - duration({days: 7})
    RETURN count(r) AS high_iss_this_week
}
CALL {
    MATCH (r:Repository) RETURN round(avg(r.innovation_score), 2) AS avg_score
}
RETURN total_repos, high_disruption, startup_signals,
       new_repos_this_week, high_iss_this_week, avg_score;
