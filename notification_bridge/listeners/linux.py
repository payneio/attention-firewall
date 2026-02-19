"""Linux D-Bus notification listener."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus

from notification_bridge.core import NotificationPayload
from notification_bridge.listeners.base import NotificationCallback

logger = logging.getLogger(__name__)


class LinuxListener:
    """Linux notification listener using D-Bus."""

    def __init__(self) -> None:
        self._bus: MessageBus | None = None
        self._running = False
        self._callback: NotificationCallback | None = None

    @property
    def is_running(self) -> bool:
        """Whether the listener is currently active."""
        return self._running

    async def start(self, callback: NotificationCallback) -> None:
        """Start listening for notifications on D-Bus."""
        self._callback = callback
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._running = True

        # Add match rule to eavesdrop on Notify method calls
        match_rule = (
            "type='method_call',"
            "interface='org.freedesktop.Notifications',"
            "member='Notify',"
            "eavesdrop=true"
        )

        # Request to add match rule
        assert self._bus is not None
        reply = await self._bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch",
                signature="s",
                body=[match_rule],
            )
        )

        if reply.message_type == MessageType.ERROR:
            logger.error(f"Failed to add match rule: {reply.body}")
            return

        logger.info("Successfully subscribed to D-Bus notifications")

        # Add message handler
        self._bus.add_message_handler(self._handle_message)

    async def stop(self) -> None:
        """Stop listening and disconnect from D-Bus."""
        self._running = False
        if self._bus:
            self._bus.disconnect()
            logger.info("Disconnected from D-Bus")

    def _handle_message(self, msg: Message) -> bool:
        """Handle incoming D-Bus messages."""
        if (
            msg.message_type == MessageType.METHOD_CALL
            and msg.interface == "org.freedesktop.Notifications"
            and msg.member == "Notify"
        ):
            # Schedule async processing
            asyncio.create_task(self._process_notification(msg))
        return False  # Don't consume the message

    async def _process_notification(self, msg: Message) -> None:
        """Process and forward a notification."""
        try:
            # Parse the Notify method arguments
            # Signature: susssasa{sv}i
            # app_name, replaces_id, icon, summary, body, actions, hints, timeout
            args = msg.body
            if len(args) < 8:
                logger.warning(f"Malformed notification message: {args}")
                return

            app_name, replaces_id, icon, summary, body, actions, hints, timeout = args[
                :8
            ]

            # Convert hints dict (may contain variant types)
            serializable_hints = {}
            for k, v in hints.items():
                try:
                    # dbus-fast Variant has .value attribute
                    val = v.value if hasattr(v, "value") else v
                    # Ensure JSON serializable
                    json.dumps(val)
                    serializable_hints[k] = val
                except (TypeError, ValueError):
                    serializable_hints[k] = str(v)

            notification = NotificationPayload(
                app_name=app_name,
                summary=summary,
                body=body,
                icon=icon,
                replaces_id=replaces_id,
                actions=list(actions) if actions else [],
                hints=serializable_hints,
                timeout=timeout,
                received_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(f"Received notification: [{app_name}] {summary}")

            # Invoke callback
            if self._callback:
                await self._callback(notification)

        except Exception as e:
            logger.exception(f"Error processing notification: {e}")
