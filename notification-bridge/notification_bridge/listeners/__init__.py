"""Platform-specific notification listeners."""

import sys

from notification_bridge.listeners.base import NotificationListener


def get_listener() -> NotificationListener:
    """Return the appropriate listener for the current platform."""
    if sys.platform == "linux":
        from notification_bridge.listeners.linux import LinuxListener

        return LinuxListener()
    elif sys.platform == "win32":
        from notification_bridge.listeners.windows import WindowsListener

        return WindowsListener()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")


__all__ = ["NotificationListener", "get_listener"]
