// ═══════════════════════════════════════════════════════════════════════════
// FinTech OSINT Platform — Neo4j Knowledge Graph Schema
// Run this against your Neo4j instance to initialize all constraints and indexes
// ═══════════════════════════════════════════════════════════════════════════

// ── Constraints (enforce uniqueness + create implicit indexes) ───────────────

CREATE CONSTRAINT repository_id IF NOT EXISTS
  FOR (r:Repository) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT developer_login IF NOT EXISTS
  FOR (d:Developer) REQUIRE d.login IS UNIQUE;

CREATE CONSTRAINT organization_name IF NOT EXISTS
  FOR (o:Organization) REQUIRE o.name IS UNIQUE;

CREATE CONSTRAINT technology_id IF NOT EXISTS
  FOR (t:Technology) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT financial_sector_id IF NOT EXISTS
  FOR (fs:FinancialSector) REQUIRE fs.id IS UNIQUE;

CREATE CONSTRAINT regulator_id IF NOT EXISTS
  FOR (reg:Regulator) REQUIRE reg.id IS UNIQUE;

CREATE CONSTRAINT regulation_id IF NOT EXISTS
  FOR (rl:Regulation) REQUIRE rl.id IS UNIQUE;

CREATE CONSTRAINT geographic_region_id IF NOT EXISTS
  FOR (gr:GeographicRegion) REQUIRE gr.id IS UNIQUE;

CREATE CONSTRAINT startup_ecosystem_id IF NOT EXISTS
  FOR (se:StartupEcosystem) REQUIRE se.id IS UNIQUE;

CREATE CONSTRAINT intelligence_report_id IF NOT EXISTS
  FOR (ir:IntelligenceReport) REQUIRE ir.id IS UNIQUE;

// ── Full-text search indexes ──────────────────────────────────────────────────

CREATE FULLTEXT INDEX repository_text IF NOT EXISTS
  FOR (r:Repository) ON EACH [r.name, r.description, r.readme_snippet, r.topics_text];

CREATE FULLTEXT INDEX technology_text IF NOT EXISTS
  FOR (t:Technology) ON EACH [t.name, t.description, t.keywords_text];

CREATE FULLTEXT INDEX regulation_text IF NOT EXISTS
  FOR (rl:Regulation) ON EACH [rl.name, rl.full_name, rl.description];

// ── Regular indexes for frequent lookups ─────────────────────────────────────

CREATE INDEX repo_stars IF NOT EXISTS FOR (r:Repository) ON (r.stars);
CREATE INDEX repo_score IF NOT EXISTS FOR (r:Repository) ON (r.innovation_score);
CREATE INDEX repo_disruption IF NOT EXISTS FOR (r:Repository) ON (r.disruption_score);
CREATE INDEX repo_updated IF NOT EXISTS FOR (r:Repository) ON (r.updated_at);
CREATE INDEX repo_source IF NOT EXISTS FOR (r:Repository) ON (r.source);
CREATE INDEX repo_sector IF NOT EXISTS FOR (r:Repository) ON (r.primary_sector);

CREATE INDEX dev_reputation IF NOT EXISTS FOR (d:Developer) ON (d.reputation_score);
CREATE INDEX dev_location IF NOT EXISTS FOR (d:Developer) ON (d.location);

// ═══════════════════════════════════════════════════════════════════════════
// NODE DEFINITIONS (with property documentation as comments)
// ═══════════════════════════════════════════════════════════════════════════

// ── Repository Node ───────────────────────────────────────────────────────────
// Core entity representing a Git repository
//
// MERGE (r:Repository {id: $id})
// SET r += {
//   id:                    "github:owner/repo",
//   source:                "github" | "gitlab" | "bitbucket",
//   full_name:             "owner/repo",
//   url:                   "https://...",
//   description:           "...",
//   readme_snippet:        "first 2000 chars of README",
//   topics_text:           "space-separated topics for full-text index",
//   language:              "Python" | "TypeScript" | ...,
//   stars:                 12345,
//   forks:                 678,
//   watchers:              12345,
//   open_issues:           23,
//   contributors_count:    45,
//   commits_count:         1200,
//   created_at:            datetime(),
//   updated_at:            datetime(),
//   pushed_at:             datetime(),
//   license:               "MIT" | "Apache-2.0" | ...,
//   is_fork:               false,
//   is_archived:           false,
//   default_branch:        "main",
//   -- Computed scores (updated each weekly run) --
//   innovation_score:      0.0 - 100.0,
//   git_impression_score:  0.0 - 100.0,
//   velocity_score:        0.0 - 100.0,
//   maturity_score:        0.0 - 100.0,
//   ecosystem_score:       0.0 - 100.0,
//   sector_relevance_score:0.0 - 100.0,
//   adoption_potential:    0.0 - 100.0,
//   startup_score:         0.0 - 100.0,
//   disruption_score:      0.0 - 100.0,
//   compliance_risk_score: 0.0 - 100.0,
//   auditability_score:    0.0 - 100.0,
//   -- Classification --
//   primary_sector:        "payments" | "trading" | "risk" | ...,
//   fintech_domains:       ["payments", "kyc"],
//   -- Discovery metadata --
//   discovery_signals:     ["topic:fintech", "keyword:AML"],
//   last_scored_at:        datetime(),
//   score_version:         "1.0.0"
// }

// ── Developer Node ────────────────────────────────────────────────────────────
// MERGE (d:Developer {login: $login})
// SET d += {
//   login:              "username",
//   name:               "Full Name",
//   email:              "...",
//   location:           "San Francisco, CA",
//   company:            "@BigBank",
//   bio:                "...",
//   public_repos:       42,
//   followers:          1200,
//   following:          300,
//   hireable:           true,
//   reputation_score:   0.0 - 100.0,
//   influence_score:    0.0 - 100.0,
//   fintech_expertise:  ["payments", "blockchain"],
//   source:             "github"
// }

// ── Organization Node ─────────────────────────────────────────────────────────
// MERGE (o:Organization {name: $name})
// SET o += {
//   name:           "anthropic",
//   display_name:   "Anthropic",
//   url:            "https://github.com/anthropic",
//   org_type:       "startup" | "enterprise" | "financial_institution" | "regulator",
//   description:    "...",
//   location:       "San Francisco, CA",
//   member_count:   150,
//   public_repos:   45,
//   fintech_focus:  true
// }

// ── Technology Node ───────────────────────────────────────────────────────────
// MERGE (t:Technology {id: $id})
// SET t += {
//   id:              "tech:zero-knowledge-proofs",
//   name:            "Zero-Knowledge Proofs",
//   category:        "cryptography" | "messaging" | "infrastructure" | ...,
//   description:     "...",
//   keywords_text:   "zkp zk-snark zk-stark privacy proof",
//   maturity_level:  "emerging" | "growing" | "mature" | "legacy",
//   first_seen:      datetime(),
//   adoption_count:  123
// }

// ── Financial Sector Node ────────────────────────────────────────────────────
// MERGE (fs:FinancialSector {id: $id})
// SET fs += {
//   id:          "sector:payments",
//   name:        "Payments Infrastructure",
//   description: "...",
//   parent_id:   "sector:financial-services"
// }

// ── Regulator Node ────────────────────────────────────────────────────────────
// MERGE (reg:Regulator {id: $id})
// SET reg += {
//   id:           "regulator:sec",
//   name:         "SEC",
//   full_name:    "Securities and Exchange Commission",
//   jurisdiction: "US",
//   website:      "https://sec.gov",
//   focus_areas:  ["securities", "digital-assets", "broker-dealers"]
// }

// ── Regulation Node ───────────────────────────────────────────────────────────
// MERGE (rl:Regulation {id: $id})
// SET rl += {
//   id:              "regulation:dodd-frank",
//   name:            "Dodd-Frank",
//   full_name:       "Dodd-Frank Wall Street Reform and Consumer Protection Act",
//   description:     "...",
//   enacted_year:    2010,
//   jurisdiction:    "US",
//   status:          "active" | "proposed" | "repealed",
//   compliance_area: ["systemic-risk", "derivatives", "consumer-protection"]
// }

// ── Geographic Region Node ────────────────────────────────────────────────────
// MERGE (gr:GeographicRegion {id: $id})
// SET gr += {
//   id:           "region:us-san-francisco",
//   name:         "San Francisco Bay Area",
//   country:      "US",
//   region_type:  "city" | "state" | "country",
//   lat:          37.7749,
//   lon:          -122.4194,
//   hub_score:    0.0 - 100.0,
//   vc_density:   0.0 - 100.0
// }

// ═══════════════════════════════════════════════════════════════════════════
// RELATIONSHIP DEFINITIONS
// ═══════════════════════════════════════════════════════════════════════════

// Repository → Developer
// (r:Repository)-[:CONTRIBUTED_BY {commits: 42, role: "maintainer"}]->(d:Developer)
// (r:Repository)-[:OWNED_BY]->(d:Developer)
// (r:Repository)-[:MAINTAINED_BY]->(o:Organization)

// Repository → Technology
// (r:Repository)-[:IMPLEMENTS {confidence: 0.92}]->(t:Technology)
// (r:Repository)-[:DEPENDS_ON {version: "^4.0"}]->(r2:Repository)

// Repository → FinancialSector
// (r:Repository)-[:RELEVANT_TO {relevance_score: 0.85}]->(fs:FinancialSector)

// Repository → Regulation
// (r:Repository)-[:SUBJECT_TO {risk_level: "high"}]->(rl:Regulation)
// (r:Repository)-[:SUPPORTS_COMPLIANCE {capability: "audit-trail"}]->(rl:Regulation)

// Repository → GeographicRegion
// (r:Repository)-[:PRIMARILY_DEVELOPED_IN]->(gr:GeographicRegion)

// Developer → Organization
// (d:Developer)-[:MEMBER_OF {role: "engineer"}]->(o:Organization)
// (d:Developer)-[:LOCATED_IN]->(gr:GeographicRegion)

// Developer → Developer
// (d1:Developer)-[:COLLABORATES_WITH {shared_repos: 5}]->(d2:Developer)

// Organization → FinancialSector
// (o:Organization)-[:OPERATES_IN]->(fs:FinancialSector)

// Regulation → Regulator
// (rl:Regulation)-[:ENFORCED_BY]->(reg:Regulator)

// Technology → Technology
// (t1:Technology)-[:RELATED_TO {similarity: 0.78}]->(t2:Technology)
// (t1:Technology)-[:SUPERSEDES]->(t2:Technology)

// ── Seed Data: Regulators ─────────────────────────────────────────────────────

MERGE (sec:Regulator {id: "regulator:sec"})
SET sec += {name: "SEC", full_name: "Securities and Exchange Commission",
            jurisdiction: "US", website: "https://sec.gov",
            focus_areas: ["securities", "digital-assets", "broker-dealers", "investment-advisers"]};

MERGE (finra:Regulator {id: "regulator:finra"})
SET finra += {name: "FINRA", full_name: "Financial Industry Regulatory Authority",
              jurisdiction: "US", website: "https://finra.org",
              focus_areas: ["broker-dealers", "market-integrity", "investor-protection"]};

MERGE (fed:Regulator {id: "regulator:federal-reserve"})
SET fed += {name: "Federal Reserve", full_name: "Board of Governors of the Federal Reserve System",
            jurisdiction: "US", website: "https://federalreserve.gov",
            focus_areas: ["monetary-policy", "bank-supervision", "payments", "systemic-risk"]};

MERGE (occ:Regulator {id: "regulator:occ"})
SET occ += {name: "OCC", full_name: "Office of the Comptroller of the Currency",
            jurisdiction: "US", website: "https://occ.gov",
            focus_areas: ["national-banks", "federal-savings-associations", "fintech-charters"]};

MERGE (fdic:Regulator {id: "regulator:fdic"})
SET fdic += {name: "FDIC", full_name: "Federal Deposit Insurance Corporation",
             jurisdiction: "US", website: "https://fdic.gov",
             focus_areas: ["deposit-insurance", "bank-supervision", "resolution"]};

MERGE (cftc:Regulator {id: "regulator:cftc"})
SET cftc += {name: "CFTC", full_name: "Commodity Futures Trading Commission",
             jurisdiction: "US", website: "https://cftc.gov",
             focus_areas: ["derivatives", "futures", "swaps", "digital-assets"]};

MERGE (cfpb:Regulator {id: "regulator:cfpb"})
SET cfpb += {name: "CFPB", full_name: "Consumer Financial Protection Bureau",
             jurisdiction: "US", website: "https://cfpb.gov",
             focus_areas: ["consumer-protection", "mortgage", "credit-cards", "open-banking"]};

MERGE (fincen:Regulator {id: "regulator:fincen"})
SET fincen += {name: "FinCEN", full_name: "Financial Crimes Enforcement Network",
               jurisdiction: "US", website: "https://fincen.gov",
               focus_areas: ["aml", "bsa", "sanctions", "cryptocurrency"]};

// ── Seed Data: Key Regulations ────────────────────────────────────────────────

MERGE (df:Regulation {id: "regulation:dodd-frank"})
SET df += {name: "Dodd-Frank", full_name: "Dodd-Frank Wall Street Reform Act",
           enacted_year: 2010, jurisdiction: "US", status: "active",
           compliance_area: ["systemic-risk", "derivatives", "volcker-rule", "consumer-protection"]};

MERGE (sox:Regulation {id: "regulation:sox"})
SET sox += {name: "SOX", full_name: "Sarbanes-Oxley Act",
            enacted_year: 2002, jurisdiction: "US", status: "active",
            compliance_area: ["financial-reporting", "audit", "internal-controls"]};

MERGE (bsa:Regulation {id: "regulation:bsa"})
SET bsa += {name: "BSA", full_name: "Bank Secrecy Act",
            enacted_year: 1970, jurisdiction: "US", status: "active",
            compliance_area: ["aml", "ctr", "sar", "transaction-monitoring"]};

MERGE (glba:Regulation {id: "regulation:glba"})
SET glba += {name: "GLBA", full_name: "Gramm-Leach-Bliley Act",
             enacted_year: 1999, jurisdiction: "US", status: "active",
             compliance_area: ["data-privacy", "financial-privacy", "information-security"]};

MERGE (pci:Regulation {id: "regulation:pci-dss"})
SET pci += {name: "PCI-DSS", full_name: "Payment Card Industry Data Security Standard",
            jurisdiction: "Global", status: "active",
            compliance_area: ["payment-security", "card-data", "encryption"]};

MERGE (basel:Regulation {id: "regulation:basel-iii"})
SET basel += {name: "Basel III", full_name: "Basel III Capital Framework",
              jurisdiction: "Global", status: "active",
              compliance_area: ["capital-requirements", "liquidity", "leverage", "systemic-risk"]};

// ── Seed Data: Financial Sectors ──────────────────────────────────────────────

MERGE (pay:FinancialSector {id: "sector:payments"})
SET pay += {name: "Payments Infrastructure", description: "Payment processing, rails, gateways"};

MERGE (cap:FinancialSector {id: "sector:capital-markets"})
SET cap += {name: "Capital Markets", description: "Trading, clearing, settlement, market data"};

MERGE (risk:FinancialSector {id: "sector:risk-management"})
SET risk += {name: "Risk Management", description: "Credit, market, and operational risk systems"};

MERGE (fraud:FinancialSector {id: "sector:fraud-aml"})
SET fraud += {name: "Fraud & AML", description: "Fraud detection, AML, transaction monitoring"};

MERGE (lend:FinancialSector {id: "sector:lending"})
SET lend += {name: "Lending & Credit", description: "Loan origination, credit scoring, underwriting"};

MERGE (wealth:FinancialSector {id: "sector:wealth-management"})
SET wealth += {name: "Wealth Management", description: "Portfolio management, robo-advisory"};

MERGE (insure:FinancialSector {id: "sector:insurtech"})
SET insure += {name: "InsurTech", description: "Insurance technology and underwriting platforms"};

MERGE (identity:FinancialSector {id: "sector:identity"})
SET identity += {name: "Digital Identity & KYC", description: "Identity verification, KYC/AML onboarding"};

MERGE (reg:FinancialSector {id: "sector:regtech"})
SET reg += {name: "RegTech", description: "Regulatory reporting, compliance automation"};

MERGE (defi:FinancialSector {id: "sector:defi"})
SET defi += {name: "DeFi & Blockchain", description: "Decentralized finance, blockchain infrastructure"};

// ── Regulation → Regulator relationships ─────────────────────────────────────

MATCH (df:Regulation {id: "regulation:dodd-frank"}), (sec:Regulator {id: "regulator:sec"})
MERGE (df)-[:ENFORCED_BY]->(sec);

MATCH (df:Regulation {id: "regulation:dodd-frank"}), (cftc:Regulator {id: "regulator:cftc"})
MERGE (df)-[:ENFORCED_BY]->(cftc);

MATCH (bsa:Regulation {id: "regulation:bsa"}), (fincen:Regulator {id: "regulator:fincen"})
MERGE (bsa)-[:ENFORCED_BY]->(fincen);

MATCH (pci:Regulation {id: "regulation:pci-dss"}), (fed:Regulator {id: "regulator:federal-reserve"})
MERGE (pci)-[:MONITORED_BY]->(fed);
