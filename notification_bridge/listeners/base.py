"""Base listener protocol definition."""

from typing import Awaitable, Callable, Protocol

from notification_bridge.core import NotificationPayload

# Type alias for notification callback
NotificationCallback = Callable[[NotificationPayload], Awaitable[None]]


class NotificationListener(Protocol):
    """Platform-agnostic notification listener interface."""

    async def start(self, callback: NotificationCallback) -> None:
        """Start listening for notifications.

        Args:
            callback: Async function to call when a notification is received.
        """
        ...

    async def stop(self) -> None:
        """Stop listening and clean up resources."""
        ...

    @property
    def is_running(self) -> bool:
        """Whether the listener is currently active."""
        ...
