"""
Unit tests for the compliance analysis framework definitions.
"""

import pytest
from compliance_analysis.frameworks.frameworks import (
    FRAMEWORKS,
    FRAMEWORKS_BY_ID,
    get_framework,
    get_frameworks_for_domain,
    get_frameworks_for_jurisdiction,
    get_technology_requirements,
)
from compliance_analysis.regulators.regulators import (
    REGULATORS,
    REGULATORS_BY_ID,
    get_regulator,
    get_regulators_for_domain,
    get_regulators_for_jurisdiction,
)


class TestFrameworks:
    def test_frameworks_list_not_empty(self):
        assert len(FRAMEWORKS) > 0

    def test_all_expected_frameworks_present(self):
        expected_ids = {"bsa", "dodd-frank", "sox", "glba", "pci-dss", "basel-iii", "dora", "mica", "psd2"}
        actual_ids = {f.id for f in FRAMEWORKS}
        assert expected_ids.issubset(actual_ids), f"Missing frameworks: {expected_ids - actual_ids}"

    def test_each_framework_has_required_fields(self):
        for f in FRAMEWORKS:
            assert f.id, f"Framework missing id"
            assert f.short_name, f"Framework {f.id} missing short_name"
            assert f.full_name, f"Framework {f.id} missing full_name"
            assert f.jurisdiction, f"Framework {f.id} missing jurisdiction"
            assert f.primary_domains, f"Framework {f.id} missing primary_domains"
            assert f.effective_date, f"Framework {f.id} missing effective_date"

    def test_get_framework_by_id(self):
        bsa = get_framework("bsa")
        assert bsa is not None
        assert bsa.short_name == "BSA"

    def test_get_nonexistent_framework_returns_none(self):
        assert get_framework("nonexistent_regulation") is None

    def test_frameworks_by_id_index_complete(self):
        for f in FRAMEWORKS:
            assert f.id in FRAMEWORKS_BY_ID

    def test_get_frameworks_for_domain_aml(self):
        aml_frameworks = get_frameworks_for_domain("aml")
        assert len(aml_frameworks) > 0
        framework_ids = {f.id for f in aml_frameworks}
        assert "bsa" in framework_ids

    def test_get_frameworks_for_jurisdiction_us(self):
        us_frameworks = get_frameworks_for_jurisdiction("US")
        assert len(us_frameworks) > 0
        for f in us_frameworks:
            assert f.jurisdiction in ("US", "INT")

    def test_get_frameworks_for_jurisdiction_eu(self):
        eu_frameworks = get_frameworks_for_jurisdiction("EU")
        assert len(eu_frameworks) > 0
        eu_ids = {f.id for f in eu_frameworks}
        assert "dora" in eu_ids or "mica" in eu_ids or "psd2" in eu_ids

    def test_bsa_has_technical_requirements(self):
        bsa = get_framework("bsa")
        assert bsa is not None
        assert len(bsa.technical_requirements) > 0

    def test_technical_requirements_have_technology_tags(self):
        for framework in FRAMEWORKS:
            for req in framework.technical_requirements:
                assert req.id, f"Requirement in {framework.id} missing id"
                assert req.description, f"Requirement {req.id} missing description"
                assert len(req.technology_tags) > 0, f"Requirement {req.id} has no technology tags"
                assert req.penalty_risk in ("low", "medium", "high", "critical")

    def test_get_technology_requirements_for_encryption(self):
        results = get_technology_requirements("encryption")
        assert len(results) > 0
        framework_ids = {r["framework_id"] for r in results}
        # Encryption is required by GLBA and PCI-DSS at minimum
        assert "glba" in framework_ids or "pci-dss" in framework_ids

    def test_get_technology_requirements_returns_correct_structure(self):
        results = get_technology_requirements("audit_log")
        for r in results:
            assert "framework_id" in r
            assert "framework_name" in r
            assert "requirement_id" in r
            assert "requirement" in r
            assert "mandatory" in r
            assert "penalty_risk" in r


class TestRegulators:
    def test_regulators_list_not_empty(self):
        assert len(REGULATORS) > 0

    def test_all_expected_regulators_present(self):
        expected_ids = {"sec", "finra", "fed", "occ", "fdic", "cftc", "cfpb", "fincen"}
        actual_ids = {r.id for r in REGULATORS}
        assert expected_ids.issubset(actual_ids), f"Missing regulators: {expected_ids - actual_ids}"

    def test_each_regulator_has_required_fields(self):
        for r in REGULATORS:
            assert r.id, f"Regulator missing id"
            assert r.name, f"Regulator {r.id} missing name"
            assert r.full_name, f"Regulator {r.id} missing full_name"
            assert r.jurisdiction, f"Regulator {r.id} missing jurisdiction"
            assert r.website, f"Regulator {r.id} missing website"
            assert len(r.domains) > 0, f"Regulator {r.id} has no domains"

    def test_get_regulator_by_id(self):
        sec = get_regulator("sec")
        assert sec is not None
        assert sec.name == "SEC"

    def test_get_nonexistent_regulator_returns_none(self):
        assert get_regulator("doesnotexist") is None

    def test_regulators_by_id_index_complete(self):
        for r in REGULATORS:
            assert r.id in REGULATORS_BY_ID

    def test_get_regulators_for_domain_aml(self):
        aml_regulators = get_regulators_for_domain("aml")
        assert len(aml_regulators) > 0
        regulator_ids = {r.id for r in aml_regulators}
        assert "fincen" in regulator_ids

    def test_get_regulators_for_jurisdiction_us(self):
        us_regulators = get_regulators_for_jurisdiction("US")
        assert len(us_regulators) >= 7  # sec, finra, fed, occ, fdic, cftc, cfpb, fincen

    def test_fincen_covers_crypto(self):
        fincen = get_regulator("fincen")
        assert fincen is not None
        assert "crypto" in fincen.domains or "aml" in fincen.domains
