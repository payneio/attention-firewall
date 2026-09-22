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

    @staticmethod
    def _extract_texts(notification) -> list[str]:
        """Return the text lines of a WinRT UserNotification, preferring ToastGeneric."""
        visual = notification.notification.visual if notification.notification else None
        if visual is None:
            return []
        bindings = list(visual.bindings)
        bindings.sort(key=lambda b: b.template != "ToastGeneric")
        for binding in bindings:
            texts = [t.text for t in binding.get_text_elements() if t.text]
            if texts:
                return texts
        return []

    def _convert_notification(self, notification) -> NotificationPayload | None:
        """Convert a WinRT notification to our payload format.

        Args:
            notification: The WinRT UserNotification object.

        Returns:
            NotificationPayload or None if conversion fails.
        """
        app_name = "Unknown"
        summary = ""
        body = ""

        # Try to get app name (may fail if ApplicationModel not available)
        try:
            if notification.app_info and notification.app_info.display_info:
                app_name = notification.app_info.display_info.display_name or "Unknown"
        except Exception as e:
            logger.debug(f"Could not get app info: {e}")

        # Extract text from the toast's visual binding. UserNotification exposes
        # a Notification (not a ToastNotification), so there is no XML content;
        # the text lives in visual.bindings -> get_text_elements().
        try:
            texts = self._extract_texts(notification)
            if len(texts) > 0:
                summary = texts[0]
            if len(texts) > 1:
                body = "\n".join(texts[1:])
        except Exception as e:
            logger.warning(f"Could not extract notification text: {e}")

        # Create payload even with minimal info
        try:
            return NotificationPayload(
                app_name=app_name,
                summary=summary,
                body=body,
                icon="",
                replaces_id=0,
                actions=[],
                hints={"windows_id": notification.id},
                timeout=-1,
                received_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error(f"Failed to create notification payload: {e}")
            return None
