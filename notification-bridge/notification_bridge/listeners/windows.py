"""Windows WinRT notification listener."""

import asyncio
import logging
from datetime import datetime, timezone

from notification_bridge.core import NotificationPayload
from notification_bridge.listeners.base import NotificationCallback

logger = logging.getLogger(__name__)

# Windows-specific imports are done lazily to avoid import errors on Linux
UserNotificationListener = None


class WindowsListener:
    """Windows notification listener using WinRT UserNotificationListener."""

    def __init__(self) -> None:
        self._running = False
        self._callback: NotificationCallback | None = None
        self._poll_task: asyncio.Task | None = None
        self._seen_ids: set[int] = set()

    @property
    def is_running(self) -> bool:
        """Whether the listener is currently active."""
        return self._running

    async def start(self, callback: NotificationCallback) -> None:
        """Start listening for notifications.

        Args:
            callback: Async function to call when a notification is received.

        Raises:
            PermissionError: If notification access is denied by the user.
        """
        # Import WinRT modules
        try:
            from winrt.windows.ui.notifications.management import (
                UserNotificationListener as UNL,
            )
            from winrt.windows.ui.notifications.management import (
                UserNotificationListenerAccessStatus,
            )
        except ImportError as e:
            raise RuntimeError(
                "Windows notification support requires winrt packages. "
                "Install with: uv sync --extra windows"
            ) from e

        self._callback = callback

        # Request access to notifications
        listener = UNL.current
        access = await listener.request_access_async()

        # Check access status (0 = Denied, 1 = Allowed)
        if access != UserNotificationListenerAccessStatus.ALLOWED:
            raise PermissionError(
                "Notification access denied. Please enable notification access "
                "in Windows Settings > Privacy > Notifications."
            )

        self._running = True
        logger.info("Successfully obtained notification listener access")

        # Start polling for notifications
        self._poll_task = asyncio.create_task(self._poll_notifications(listener))

    async def stop(self) -> None:
        """Stop listening for notifications."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.info("Stopped Windows notification listener")

    async def _poll_notifications(self, listener) -> None:
        """Poll for new notifications.

        Args:
            listener: The UserNotificationListener instance.
        """
        try:
            from winrt.windows.ui.notifications import NotificationKinds
        except ImportError:
            logger.error("Failed to import NotificationKinds")
            return

        while self._running:
            try:
                # Get current notifications
                notifications = await listener.get_notifications_async(
                    NotificationKinds.TOAST
                )

                for notification in notifications:
                    if notification.id not in self._seen_ids:
                        self._seen_ids.add(notification.id)
                        payload = self._convert_notification(notification)
                        if payload and self._callback:
                            await self._callback(payload)

                # Clean up old IDs to prevent memory growth
                if len(self._seen_ids) > 1000:
                    # Keep only the most recent IDs
                    current_ids = {n.id for n in notifications}
                    self._seen_ids = current_ids

            except Exception as e:
                logger.error(f"Error polling notifications: {e}")

            await asyncio.sleep(0.5)

    def _convert_notification(self, notification) -> NotificationPayload | None:
        """Convert a WinRT notification to our payload format.

        Args:
            notification: The WinRT UserNotification object.

        Returns:
            NotificationPayload or None if conversion fails.
        """
        try:
            # Get app info
            app_name = "Unknown"
            if notification.app_info and notification.app_info.display_info:
                app_name = notification.app_info.display_info.display_name or "Unknown"

            # Get notification content
            summary = ""
            body = ""

            try:
                # Try to get text elements from the notification visual
                visual = notification.notification.visual
                if visual:
                    # Get the toast binding
                    binding = visual.get_binding(
                        "Windows.UI.Notifications.ToastTemplateType.ToastText02"
                    )
                    if not binding:
                        # Try generic binding
                        bindings = visual.bindings
                        if bindings and len(bindings) > 0:
                            binding = bindings[0]

                    if binding:
                        text_elements = list(binding.get_text_elements())
                        if len(text_elements) > 0:
                            summary = text_elements[0].text or ""
                        if len(text_elements) > 1:
                            body = text_elements[1].text or ""
            except Exception as e:
                logger.debug(f"Could not extract notification text: {e}")

            return NotificationPayload(
                app_name=app_name,
                summary=summary,
                body=body,
                icon="",  # WinRT doesn't easily expose icon path
                replaces_id=0,
                actions=[],  # Would need more complex parsing
                hints={"windows_id": notification.id},
                timeout=-1,
                received_at=datetime.now(timezone.utc).isoformat(),
            )

        except Exception as e:
            logger.error(f"Failed to convert notification: {e}")
            return None
