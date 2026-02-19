"""
Notification Bridge - Entry point.

Listens to desktop notifications and forwards them to Central Context API.
Supports Linux (D-Bus) and Windows (WinRT).
"""

from notification_bridge.core import Settings
from notification_bridge.server import app

__all__ = ["app"]


def main() -> None:
    """Run the server."""
    import uvicorn

    settings = Settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
