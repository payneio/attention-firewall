"""Tests for core module (Settings, NotificationPayload, NotificationForwarder)."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# These imports will fail until we implement the modules
from notification_bridge.core import (
    NotificationForwarder,
    NotificationPayload,
    Settings,
)


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self):
        """Test default configuration values."""
        settings = Settings()
        assert settings.central_context_url == "http://localhost:9000"
        assert settings.bucket_name == "notifications"
        assert settings.port == 9001

    def test_settings_from_env(self, monkeypatch):
        """Test settings can be overridden via environment variables."""
        monkeypatch.setenv("CENTRAL_CONTEXT_URL", "http://example.com:8000")
        monkeypatch.setenv("BUCKET_NAME", "my-notifications")
        monkeypatch.setenv("PORT", "9999")

        settings = Settings()
        assert settings.central_context_url == "http://example.com:8000"
        assert settings.bucket_name == "my-notifications"
        assert settings.port == 9999


class TestNotificationPayload:
    """Tests for NotificationPayload model."""

    def test_create_payload(self):
        """Test creating a notification payload with all fields."""
        payload = NotificationPayload(
            app_name="TestApp",
            summary="Test Summary",
            body="Test body content",
            icon="test-icon",
            replaces_id=0,
            actions=["action1", "Action 1"],
            hints={"urgency": 1},
            timeout=-1,
            received_at="2026-02-12T21:00:00+00:00",
        )

        assert payload.app_name == "TestApp"
        assert payload.summary == "Test Summary"
        assert payload.body == "Test body content"
        assert payload.icon == "test-icon"
        assert payload.replaces_id == 0
        assert payload.actions == ["action1", "Action 1"]
        assert payload.hints == {"urgency": 1}
        assert payload.timeout == -1

    def test_payload_serialization(self):
        """Test that payload serializes to JSON correctly."""
        payload = NotificationPayload(
            app_name="TestApp",
            summary="Test",
            body="Body",
            icon="",
            replaces_id=0,
            actions=[],
            hints={},
            timeout=-1,
            received_at="2026-02-12T21:00:00+00:00",
        )

        data = json.loads(payload.model_dump_json())
        assert data["app_name"] == "TestApp"
        assert data["summary"] == "Test"
        assert data["body"] == "Body"

    def test_payload_with_complex_hints(self):
        """Test payload with various hint types."""
        payload = NotificationPayload(
            app_name="App",
            summary="Summary",
            body="Body",
            icon="icon",
            replaces_id=1,
            actions=["open", "Open", "dismiss", "Dismiss"],
            hints={
                "urgency": 2,
                "category": "email.arrived",
                "sender-pid": 12345,
                "desktop-entry": "thunderbird",
            },
            timeout=5000,
            received_at="2026-02-12T21:00:00+00:00",
        )

        assert payload.hints["urgency"] == 2
        assert payload.hints["category"] == "email.arrived"
        assert len(payload.actions) == 4


class TestNotificationForwarder:
    """Tests for NotificationForwarder."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            central_context_url="http://localhost:9000",
            bucket_name="test-notifications",
        )

    @pytest.fixture
    def mock_client(self):
        """Create a mock HTTP client."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.fixture
    def forwarder(self, mock_client, settings):
        """Create a NotificationForwarder instance."""
        return NotificationForwarder(client=mock_client, settings=settings)

    @pytest.fixture
    def sample_notification(self):
        """Create a sample notification payload."""
        return NotificationPayload(
            app_name="TestApp",
            summary="Test Summary",
            body="Test body",
            icon="test-icon",
            replaces_id=0,
            actions=[],
            hints={"urgency": 1},
            timeout=-1,
            received_at=datetime.now(timezone.utc).isoformat(),
        )

    @pytest.mark.asyncio
    async def test_forward_success(self, forwarder, mock_client, sample_notification):
        """Test successful notification forwarding."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response

        await forwarder.forward(sample_notification)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "http://localhost:9000/content" in call_args[0]
        assert call_args[1]["json"]["bucket"] == "test-notifications"
        assert call_args[1]["json"]["content_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_forward_includes_description(
        self, forwarder, mock_client, sample_notification
    ):
        """Test that forwarded notification includes description."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response

        await forwarder.forward(sample_notification)

        call_args = mock_client.post.call_args
        description = call_args[1]["json"]["description"]
        assert "TestApp" in description
        assert "Test Summary" in description

    @pytest.mark.asyncio
    async def test_forward_generates_unique_names(
        self, forwarder, mock_client, sample_notification
    ):
        """Test that each forwarded notification gets a unique name."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response

        await forwarder.forward(sample_notification)
        first_name = mock_client.post.call_args[1]["json"]["name"]

        await forwarder.forward(sample_notification)
        second_name = mock_client.post.call_args[1]["json"]["name"]

        assert first_name != second_name
        assert first_name.startswith("TestApp_")
        assert second_name.startswith("TestApp_")

    @pytest.mark.asyncio
    async def test_forward_sanitizes_app_name(self, forwarder, mock_client, settings):
        """Test that app names with special chars are sanitized."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response

        notification = NotificationPayload(
            app_name="My App (v2.0)",
            summary="Test",
            body="",
            icon="",
            replaces_id=0,
            actions=[],
            hints={},
            timeout=-1,
            received_at=datetime.now(timezone.utc).isoformat(),
        )

        await forwarder.forward(notification)

        name = mock_client.post.call_args[1]["json"]["name"]
        assert "(" not in name
        assert ")" not in name
        assert "." not in name
        assert " " not in name

    @pytest.mark.asyncio
    async def test_forward_handles_http_error(
        self, forwarder, mock_client, sample_notification
    ):
        """Test that HTTP errors are handled gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response

        # Should not raise, just log warning
        await forwarder.forward(sample_notification)
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_handles_network_error(
        self, forwarder, mock_client, sample_notification
    ):
        """Test that network errors are handled gracefully."""
        mock_client.post.side_effect = httpx.RequestError("Connection refused")

        # Should not raise, just log error
        await forwarder.forward(sample_notification)

    @pytest.mark.asyncio
    async def test_forward_content_is_valid_json(
        self, forwarder, mock_client, sample_notification
    ):
        """Test that the content field contains valid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post.return_value = mock_response

        await forwarder.forward(sample_notification)

        content = mock_client.post.call_args[1]["json"]["content"]
        # Should be parseable as JSON
        parsed = json.loads(content)
        assert parsed["app_name"] == "TestApp"
        assert parsed["summary"] == "Test Summary"


class TestOutputRedirect:
    """main() can run without a console (pythonw) by redirecting output."""

    def test_log_file_receives_output(self, tmp_path, monkeypatch):
        import sys

        from notification_bridge.main import _redirect_output

        monkeypatch.setattr(sys, "stdout", sys.stdout)
        monkeypatch.setattr(sys, "stderr", sys.stderr)
        log = tmp_path / "bridge.log"
        _redirect_output(str(log))
        print("hello")
        sys.stdout.close()
        assert log.read_text() == "hello\n"

    def test_missing_console_goes_to_devnull(self, monkeypatch):
        import sys

        from notification_bridge.main import _redirect_output

        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)
        _redirect_output(None)
        assert sys.stdout is not None and not sys.stdout.isatty()
        sys.stdout.close()

    def test_app_still_importable_from_main(self):
        from notification_bridge.main import app

        assert app.title == "Notification Bridge"


class TestWebhookForwarding:
    """With WEBHOOK_URL set, notifications go there instead of Central Context."""

    @pytest.mark.asyncio
    async def test_posts_payload_with_token(self):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(202, json={"id": 1})

        settings = Settings(
            webhook_url="https://hub.example/events", webhook_token="secret"
        )
        payload = NotificationPayload(
            app_name="Microsoft Teams",
            summary="Alice",
            body="Hi",
            icon="",
            replaces_id=0,
            actions=[],
            hints={},
            timeout=-1,
            received_at="2026-09-22T00:00:00+00:00",
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await NotificationForwarder(client, settings).forward(payload)

        [request] = seen
        assert str(request.url) == "https://hub.example/events"
        assert request.headers["authorization"] == "Bearer secret"
        assert request.headers["x-agent"]
        assert json.loads(request.content)["summary"] == "Alice"
