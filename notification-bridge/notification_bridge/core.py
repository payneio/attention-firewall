"""Core module: Settings, NotificationPayload, and NotificationForwarder."""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    central_context_url: str = "http://localhost:9000"
    bucket_name: str = "notifications"
    port: int = 9001

    model_config = {"env_file": ".env", "extra": "ignore"}


class NotificationPayload(BaseModel):
    """Structured notification data."""

    app_name: str
    summary: str
    body: str
    icon: str
    replaces_id: int
    actions: list[str]
    hints: dict[str, Any]
    timeout: int
    received_at: str


class NotificationForwarder:
    """Forwards notifications to Central Context API."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def forward(self, notification: NotificationPayload) -> None:
        """Send notification to Central Context API."""
        # Create a unique name for the notification
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_app_name = "".join(
            c if c.isalnum() else "_" for c in notification.app_name
        )
        name = f"{safe_app_name}_{timestamp}"

        payload = {
            "content": notification.model_dump_json(),
            "bucket": self.settings.bucket_name,
            "name": name,
            "content_type": "application/json",
            "description": f"Notification from {notification.app_name}: {notification.summary}",
        }

        try:
            response = await self.client.post(
                f"{self.settings.central_context_url}/content",
                json=payload,
            )
            if response.status_code == 201:
                logger.info(f"Forwarded notification: {name}")
            else:
                logger.warning(
                    f"Failed to forward notification: {response.status_code} - {response.text}"
                )
        except httpx.RequestError as e:
            logger.error(f"HTTP error forwarding notification: {e}")
