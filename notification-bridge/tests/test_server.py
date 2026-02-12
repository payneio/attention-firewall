"""Tests for FastAPI server module."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestServerEndpoints:
    """Tests for FastAPI server endpoints."""

    @pytest.fixture
    def mock_listener(self):
        """Create a mock notification listener."""
        listener = AsyncMock()
        listener.start = AsyncMock()
        listener.stop = AsyncMock()
        listener.is_running = True
        return listener

    @pytest.fixture
    def client(self, mock_listener):
        """Create a test client with mocked listener."""
        with patch(
            "notification_bridge.server.get_listener", return_value=mock_listener
        ):
            from notification_bridge.server import app

            with TestClient(app) as client:
                yield client

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_shows_listener_status(self, client):
        """Test that health endpoint shows listener connection status."""
        response = client.get("/health")
        data = response.json()
        assert "listener_running" in data

    def test_status_endpoint(self, client):
        """Test the status endpoint."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "target_url" in data
        assert "bucket" in data

    def test_status_shows_configuration(self, client):
        """Test that status endpoint shows current configuration."""
        response = client.get("/status")
        data = response.json()
        assert data["bucket"] == "notifications"
        assert "localhost:9000" in data["target_url"]

    def test_openapi_available(self, client):
        """Test that OpenAPI docs are available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Notification Bridge"

    def test_docs_endpoint(self, client):
        """Test that /docs endpoint is available."""
        response = client.get("/docs")
        assert response.status_code == 200


class TestServerLifespan:
    """Tests for server lifespan management."""

    @pytest.fixture
    def mock_listener(self):
        """Create a mock notification listener."""
        listener = AsyncMock()
        listener.start = AsyncMock()
        listener.stop = AsyncMock()
        listener.is_running = True
        return listener

    def test_lifespan_starts_listener(self, mock_listener):
        """Test that lifespan starts the notification listener."""
        with patch(
            "notification_bridge.server.get_listener", return_value=mock_listener
        ):
            from notification_bridge.server import app

            with TestClient(app):
                pass  # Enter and exit context

        mock_listener.start.assert_called_once()

    def test_lifespan_stops_listener_on_shutdown(self, mock_listener):
        """Test that lifespan stops the listener on shutdown."""
        with patch(
            "notification_bridge.server.get_listener", return_value=mock_listener
        ):
            from notification_bridge.server import app

            with TestClient(app):
                pass  # Enter and exit context

        mock_listener.stop.assert_called_once()

    def test_lifespan_connects_listener_to_forwarder(self, mock_listener):
        """Test that listener callback is connected to forwarder."""
        with patch(
            "notification_bridge.server.get_listener", return_value=mock_listener
        ):
            from notification_bridge.server import app

            with TestClient(app):
                # Check that start was called with a callback
                mock_listener.start.assert_called_once()
                callback = mock_listener.start.call_args[0][0]
                assert callable(callback)


class TestServerConfiguration:
    """Tests for server configuration."""

    def test_server_uses_settings(self):
        """Test that server respects Settings configuration."""
        from notification_bridge.core import Settings

        settings = Settings()
        assert settings.port == 9001
        assert settings.central_context_url == "http://localhost:9000"
        assert settings.bucket_name == "notifications"
