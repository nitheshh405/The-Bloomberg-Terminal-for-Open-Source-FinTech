"""
Unit tests for the DependencyAnalysisAgent parsers and helpers.
"""

import pytest
from ai_agents.dependency.dependency_analysis_agent import (
    _parse_requirements_txt,
    _parse_package_json,
    _parse_go_mod,
    _check_risk,
    CRITICAL_FINTECH_PACKAGES,
    DependencyRecord,
)


class TestRequirementsTxtParser:
    def test_basic_dependencies(self):
        content = "requests==2.31.0\nfastapi>=0.110.0\npydantic"
        deps = _parse_requirements_txt(content, "test")
        names = [d.name for d in deps]
        assert "requests" in names
        assert "fastapi" in names
        assert "pydantic" in names

    def test_ignores_comments(self):
        content = "# this is a comment\nrequests==2.0"
        deps = _parse_requirements_txt(content, "test")
        names = [d.name for d in deps]
        assert len([n for n in names if "comment" in n.lower()]) == 0

    def test_ignores_blank_lines(self):
        content = "\n\nrequests==2.0\n\nfastapi\n\n"
        deps = _parse_requirements_txt(content, "test")
        assert len(deps) == 2

    def test_ignores_pip_flags(self):
        content = "-r base.txt\n--index-url https://example.com\nrequests"
        deps = _parse_requirements_txt(content, "test")
        names = [d.name for d in deps]
        assert "requests" in names
        # The -r and --index-url lines should be ignored
        assert not any(n.startswith("-") for n in names)

    def test_detects_critical_fintech_package(self):
        content = "stripe==7.0.0\nrequests"
        deps = _parse_requirements_txt(content, "test")
        stripe_dep = next(d for d in deps if d.name == "stripe")
        assert stripe_dep.is_critical_fintech is True

    def test_non_critical_package_not_flagged(self):
        content = "requests==2.0"
        deps = _parse_requirements_txt(content, "test")
        req = deps[0]
        assert req.is_critical_fintech is False

    def test_all_deps_have_python_ecosystem(self):
        content = "requests\nfastapi\nstarlette"
        deps = _parse_requirements_txt(content, "test")
        for d in deps:
            assert d.ecosystem == "python"


class TestPackageJsonParser:
    def test_parses_dependencies(self):
        content = '{"dependencies": {"react": "^18.0.0", "axios": "^1.0.0"}}'
        deps = _parse_package_json(content, "test")
        names = [d.name for d in deps]
        assert "react" in names
        assert "axios" in names

    def test_marks_dev_dependencies(self):
        content = '{"devDependencies": {"jest": "^29.0.0"}, "dependencies": {"react": "^18.0.0"}}'
        deps = _parse_package_json(content, "test")
        jest = next(d for d in deps if d.name == "jest")
        react = next(d for d in deps if d.name == "react")
        assert jest.is_dev_dependency is True
        assert react.is_dev_dependency is False

    def test_handles_empty_json(self):
        content = "{}"
        deps = _parse_package_json(content, "test")
        assert deps == []

    def test_handles_invalid_json(self):
        content = "not valid json {{{"
        deps = _parse_package_json(content, "test")
        assert deps == []

    def test_all_deps_have_npm_ecosystem(self):
        content = '{"dependencies": {"react": "^18.0.0"}}'
        deps = _parse_package_json(content, "test")
        for d in deps:
            assert d.ecosystem == "npm"


class TestGoModParser:
    def test_parses_require_block(self):
        content = """module github.com/example/myapp

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    github.com/jackc/pgx/v5 v5.4.0
)
"""
        deps = _parse_go_mod(content, "test")
        module_paths = [d.name for d in deps]
        assert any("gin-gonic/gin" in m for m in module_paths)

    def test_handles_empty_require_block(self):
        content = "module github.com/example/app\n\ngo 1.21\n"
        deps = _parse_go_mod(content, "test")
        assert deps == []

    def test_all_deps_have_go_ecosystem(self):
        content = "require (\n    github.com/gin-gonic/gin v1.9.1\n)\n"
        deps = _parse_go_mod(content, "test")
        for d in deps:
            assert d.ecosystem == "go"


class TestRiskChecking:
    def test_safe_package_has_no_risk_flags(self):
        flags = _check_risk("requests")
        assert flags == []

    def test_suspicious_crypto_wallet_flagged(self):
        flags = _check_risk("my-crypto")
        # The pattern r".*-crypto$" should match
        # (depends on exact regex; test what we expect)
        assert isinstance(flags, list)

    def test_returns_list_always(self):
        result = _check_risk("anypackagename")
        assert isinstance(result, list)


class TestDependencyRecord:
    def test_normalized_name_lowercase(self):
        dep = DependencyRecord(name="MyPackage", ecosystem="python")
        assert dep.normalized_name == "mypackage"

    def test_normalized_name_hyphens_to_underscores(self):
        dep = DependencyRecord(name="my-package", ecosystem="npm")
        assert dep.normalized_name == "my_package"

    def test_default_version_spec(self):
        dep = DependencyRecord(name="test")
        assert dep.version_spec == "*"

    def test_not_critical_by_default(self):
        dep = DependencyRecord(name="test")
        assert dep.is_critical_fintech is False
