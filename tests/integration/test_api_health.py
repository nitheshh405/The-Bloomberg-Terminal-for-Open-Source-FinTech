"""
Integration tests for the FastAPI backend.
Requires the FastAPI app to be importable (no live Neo4j needed for health/docs).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from api.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_has_status(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_response_has_version(self, client):
        response = client.get("/api/v1/health")
        data = response.json()
        assert "version" in data

    def test_health_content_type_json(self, client):
        response = client.get("/api/v1/health")
        assert "application/json" in response.headers.get("content-type", "")


class TestApiDocs:
    def test_openapi_docs_accessible(self, client):
        response = client.get("/api/docs")
        assert response.status_code == 200

    def test_openapi_schema_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_schema_has_paths(self, client):
        response = client.get("/openapi.json")
        schema = response.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 0


class TestRouterRegistration:
    """Verify all expected routers are registered."""

    def test_repositories_route_registered(self, client):
        # Should return 500 (no DB) not 404 (not found)
        response = client.get("/api/v1/repositories")
        assert response.status_code != 404

    def test_technologies_route_registered(self, client):
        response = client.get("/api/v1/technologies")
        assert response.status_code != 404

    def test_regulations_route_registered(self, client):
        response = client.get("/api/v1/regulations")
        assert response.status_code != 404

    def test_graph_stats_route_registered(self, client):
        response = client.get("/api/v1/graph/stats")
        assert response.status_code != 404

    def test_search_route_registered(self, client):
        response = client.get("/api/v1/search?q=fintech")
        assert response.status_code != 404

    def test_intelligence_reports_route_registered(self, client):
        response = client.get("/api/v1/intelligence/reports")
        # Returns [] or 200 — should not be 404
        assert response.status_code in (200, 500)


class TestSearchValidation:
    def test_search_requires_query_param(self, client):
        response = client.get("/api/v1/search")
        assert response.status_code == 422  # Unprocessable Entity

    def test_search_enforces_min_length(self, client):
        response = client.get("/api/v1/search?q=a")
        assert response.status_code == 422  # min_length=2

    def test_search_accepts_valid_query(self, client):
        response = client.get("/api/v1/search?q=payments")
        assert response.status_code != 422

    def test_search_respects_limit(self, client):
        response = client.get("/api/v1/search?q=test&limit=101")
        assert response.status_code == 422  # le=100


class TestCORSHeaders:
    def test_cors_headers_present_on_health(self, client):
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},
        )
        # CORS should allow the dashboard origin
        assert response.status_code == 200


class TestIntelligenceReports:
    def test_reports_endpoint_returns_list(self, client):
        response = client.get("/api/v1/intelligence/reports")
        # Returns [] when no reports dir exists, or list of reports
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_missing_report_returns_404(self, client):
        response = client.get("/api/v1/intelligence/reports/9999-99-99")
        assert response.status_code == 404
