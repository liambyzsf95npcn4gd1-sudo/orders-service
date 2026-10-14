"""Integration tests for FastAPI endpoints with mocked upstream responses."""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.client import UpstreamDataError, UpstreamError, UpstreamTimeoutError
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestApiEndpoints:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @patch("app.main.fetch_upstream_orders", new_callable=AsyncMock)
    def test_get_root_success_contract(self, mock_fetch, client, sample_upstream_orders):
        mock_fetch.return_value = sample_upstream_orders

        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

        data = resp.json()

        # Check top-level keys
        assert set(data.keys()) == {"clients", "stats"}

        # Check stats keys and invariant
        stats = data["stats"]
        assert set(stats.keys()) == {"received", "unique", "duplicates_merged", "invalid_dropped"}
        assert stats["received"] == 17
        assert stats["unique"] == 8
        assert stats["duplicates_merged"] == 5
        assert stats["invalid_dropped"] == 4
        assert stats["received"] == stats["unique"] + stats["duplicates_merged"] + stats["invalid_dropped"]

        # Check clients schema
        clients = data["clients"]
        assert len(clients) == 8
        for c in clients:
            assert set(c.keys()) == {"name", "phone", "email", "amount"}
            assert isinstance(c["name"], str)
            assert isinstance(c["phone"], str)
            assert isinstance(c["email"], str)
            assert isinstance(c["amount"], (int, float))
            assert len(c["phone"]) == 11
            assert c["phone"].startswith("7")

        # Check ordering
        phones = [c["phone"] for c in clients]
        assert phones == sorted(phones)

    @patch("app.main.fetch_upstream_orders", new_callable=AsyncMock)
    def test_repeated_calls_deterministic_idempotent(self, mock_fetch, client, sample_upstream_orders):
        mock_fetch.return_value = sample_upstream_orders

        resp1 = client.get("/")
        resp2 = client.get("/")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()

    @patch("app.main.fetch_upstream_orders", new_callable=AsyncMock)
    def test_upstream_timeout_error(self, mock_fetch, client):
        mock_fetch.side_effect = UpstreamTimeoutError("Upstream timeout")

        resp = client.get("/")
        assert resp.status_code == 504
        data = resp.json()
        assert "Upstream timeout" in data["detail"]
        assert data["error"] == "UpstreamServiceError"

    @patch("app.main.fetch_upstream_orders", new_callable=AsyncMock)
    def test_upstream_http_500_error(self, mock_fetch, client):
        mock_fetch.side_effect = UpstreamError("Upstream returned HTTP 500", status_code=502)

        resp = client.get("/")
        assert resp.status_code == 502
        data = resp.json()
        assert "Upstream returned HTTP 500" in data["detail"]

    @patch("app.main.fetch_upstream_orders", new_callable=AsyncMock)
    def test_upstream_malformed_json_error(self, mock_fetch, client):
        mock_fetch.side_effect = UpstreamDataError("Failed to parse upstream response as JSON")

        resp = client.get("/")
        assert resp.status_code == 502
        data = resp.json()
        assert "Failed to parse" in data["detail"]

    @patch("app.main.fetch_upstream_orders", new_callable=AsyncMock)
    def test_upstream_not_a_list_error(self, mock_fetch, client):
        mock_fetch.side_effect = UpstreamDataError("Upstream JSON root must be an array of orders")

        resp = client.get("/")
        assert resp.status_code == 502
        data = resp.json()
        assert "must be an array" in data["detail"]
