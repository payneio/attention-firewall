"""FastAPI server module."""

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI

from notification_bridge.core import (
    NotificationForwarder,
    NotificationPayload,
    Settings,
)
from notification_bridge.listeners import get_listener
from notification_bridge.listeners.base import NotificationListener

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
settings = Settings()
listener: NotificationListener | None = None
forwarder: NotificationForwarder | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global listener, forwarder

    async with httpx.AsyncClient() as client:
        forwarder = NotificationForwarder(client=client, settings=settings)
        listener = get_listener()

        # Define callback that forwards notifications
        async def on_notification(notification: NotificationPayload) -> None:
            if forwarder:
                await forwarder.forward(notification)

        await listener.start(on_notification)
        yield
        await listener.stop()


app = FastAPI(
    title="Notification Bridge",
    description="Listens to desktop notifications and forwards them to Central Context API.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "listener_running": str(listener is not None and listener.is_running),
    }


@app.get("/status")
async def status() -> dict[str, Any]:
    """Get bridge status."""
    return {
        "running": listener is not None and listener.is_running,
        "target_url": settings.central_context_url,
        "bucket": settings.bucket_name,
    }
