"""Tests for listener protocol and platform detection."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notification_bridge.core import NotificationPayload


class TestListenerProtocol:
    """Tests for the NotificationListener protocol compliance."""

    def test_linux_listener_implements_protocol(self):
        """Test that LinuxListener implements the NotificationListener protocol."""
        from notification_bridge.listeners.linux import LinuxListener

        listener = LinuxListener()

        # Check protocol methods exist
        assert hasattr(listener, "start")
        assert hasattr(listener, "stop")
        assert hasattr(listener, "is_running")
        assert callable(listener.start)
        assert callable(listener.stop)

    def test_windows_listener_implements_protocol(self):
        """Test that WindowsListener implements the NotificationListener protocol."""
        from notification_bridge.listeners.windows import WindowsListener

        listener = WindowsListener()

        # Check protocol methods exist
        assert hasattr(listener, "start")
        assert hasattr(listener, "stop")
        assert hasattr(listener, "is_running")
        assert callable(listener.start)
        assert callable(listener.stop)


class TestPlatformDetection:
    """Tests for platform-specific listener selection."""

    def test_get_listener_linux(self):
        """Test that get_listener returns LinuxListener on Linux."""
        with patch.object(sys, "platform", "linux"):
            from notification_bridge.listeners.linux import LinuxListener

            # Need to reload to pick up patched platform
            import notification_bridge.listeners as listeners_module
            import importlib

            importlib.reload(listeners_module)

            listener = listeners_module.get_listener()
            assert isinstance(listener, LinuxListener)

    def test_get_listener_windows(self):
        """Test that get_listener returns WindowsListener on Windows."""
        with patch.object(sys, "platform", "win32"):
            from notification_bridge.listeners.windows import WindowsListener

            import notification_bridge.listeners as listeners_module
            import importlib

            importlib.reload(listeners_module)

            listener = listeners_module.get_listener()
            assert isinstance(listener, WindowsListener)

    def test_get_listener_unsupported_platform(self):
        """Test that get_listener raises on unsupported platforms."""
        with patch.object(sys, "platform", "freebsd"):
            import notification_bridge.listeners as listeners_module
            import importlib

            importlib.reload(listeners_module)

            with pytest.raises(RuntimeError, match="Unsupported platform"):
                listeners_module.get_listener()


class TestLinuxListener:
    """Tests for Linux D-Bus notification listener."""

    @pytest.fixture
    def mock_dbus(self):
        """Mock D-Bus components."""
        mock_bus = AsyncMock()
        mock_bus.call = AsyncMock(return_value=MagicMock(message_type=MagicMock()))
        mock_bus.add_message_handler = MagicMock()
        mock_bus.disconnect = MagicMock()

        mock_message_bus_class = MagicMock()
        mock_message_bus_instance = MagicMock()
        mock_message_bus_instance.connect = AsyncMock(return_value=mock_bus)
        mock_message_bus_class.return_value = mock_message_bus_instance

        return mock_message_bus_class, mock_bus

    @pytest.fixture
    def linux_listener(self):
        """Create a LinuxListener instance."""
        from notification_bridge.listeners.linux import LinuxListener

        return LinuxListener()

    def test_initial_state(self, linux_listener):
        """Test listener initial state."""
        assert linux_listener.is_running is False

    @pytest.mark.asyncio
    async def test_start_connects_to_dbus(self, linux_listener, mock_dbus):
        """Test that start() connects to D-Bus session bus."""
        mock_message_bus_class, mock_bus = mock_dbus
        callback = AsyncMock()

        with patch(
            "notification_bridge.listeners.linux.MessageBus", mock_message_bus_class
        ):
            await linux_listener.start(callback)

        mock_message_bus_class.return_value.connect.assert_called_once()
        assert linux_listener.is_running is True

    @pytest.mark.asyncio
    async def test_start_adds_match_rule(self, linux_listener, mock_dbus):
        """Test that start() adds D-Bus match rule for notifications."""
        mock_message_bus_class, mock_bus = mock_dbus
        callback = AsyncMock()

        with patch(
            "notification_bridge.listeners.linux.MessageBus", mock_message_bus_class
        ):
            await linux_listener.start(callback)

        # Verify AddMatch was called
        mock_bus.call.assert_called_once()
        call_args = mock_bus.call.call_args[0][0]
        assert call_args.member == "AddMatch"

    @pytest.mark.asyncio
    async def test_start_registers_message_handler(self, linux_listener, mock_dbus):
        """Test that start() registers a message handler."""
        mock_message_bus_class, mock_bus = mock_dbus
        callback = AsyncMock()

        with patch(
            "notification_bridge.listeners.linux.MessageBus", mock_message_bus_class
        ):
            await linux_listener.start(callback)

        mock_bus.add_message_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_disconnects(self, linux_listener, mock_dbus):
        """Test that stop() disconnects from D-Bus."""
        mock_message_bus_class, mock_bus = mock_dbus
        callback = AsyncMock()

        with patch(
            "notification_bridge.listeners.linux.MessageBus", mock_message_bus_class
        ):
            await linux_listener.start(callback)
            await linux_listener.stop()

        mock_bus.disconnect.assert_called_once()
        assert linux_listener.is_running is False

    @pytest.mark.asyncio
    async def test_callback_invoked_on_notification(self, linux_listener, mock_dbus):
        """Test that callback is invoked when notification is received."""
        mock_message_bus_class, mock_bus = mock_dbus
        callback = AsyncMock()
        captured_handler = None

        def capture_handler(handler):
            nonlocal captured_handler
            captured_handler = handler

        mock_bus.add_message_handler = capture_handler

        with patch(
            "notification_bridge.listeners.linux.MessageBus", mock_message_bus_class
        ):
            with patch(
                "notification_bridge.listeners.linux.MessageType"
            ) as mock_msg_type:
                mock_msg_type.METHOD_CALL = "method_call"

                await linux_listener.start(callback)

                # Simulate a notification message
                mock_msg = MagicMock()
                mock_msg.message_type = "method_call"
                mock_msg.interface = "org.freedesktop.Notifications"
                mock_msg.member = "Notify"
                mock_msg.body = [
                    "TestApp",  # app_name
                    0,  # replaces_id
                    "icon",  # icon
                    "Summary",  # summary
                    "Body",  # body
                    [],  # actions
                    {},  # hints
                    -1,  # timeout
                ]

                # Call the captured handler
                assert captured_handler is not None
                captured_handler(mock_msg)

                # Give async task time to run
                import asyncio

                await asyncio.sleep(0.1)

                # Callback should have been invoked with a NotificationPayload
                callback.assert_called_once()
                payload = callback.call_args[0][0]
                assert isinstance(payload, NotificationPayload)
                assert payload.app_name == "TestApp"
                assert payload.summary == "Summary"


class TestWindowsListener:
    """Tests for Windows WinRT notification listener."""

    @pytest.fixture
    def windows_listener(self):
        """Create a WindowsListener instance."""
        from notification_bridge.listeners.windows import WindowsListener

        return WindowsListener()

    def test_initial_state(self, windows_listener):
        """Test listener initial state."""
        assert windows_listener.is_running is False

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    async def test_start_requests_access(self, windows_listener):
        """Test that start() requests notification access."""
        callback = AsyncMock()

        mock_listener = MagicMock()
        mock_listener.request_access_async = AsyncMock(return_value=1)  # ALLOWED = 1
        mock_listener.get_notifications_async = AsyncMock(return_value=[])

        with patch(
            "notification_bridge.listeners.windows.UserNotificationListener"
        ) as mock_unl:
            mock_unl.current = mock_listener

            # Start will begin polling, so we need to stop it
            await windows_listener.start(callback)
            await windows_listener.stop()

        mock_listener.request_access_async.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    async def test_start_raises_on_denied_access(self, windows_listener):
        """Test that start() raises PermissionError if access denied."""
        callback = AsyncMock()

        mock_listener = MagicMock()
        mock_listener.request_access_async = AsyncMock(return_value=0)  # DENIED = 0

        with patch(
            "notification_bridge.listeners.windows.UserNotificationListener"
        ) as mock_unl:
            mock_unl.current = mock_listener

            with pytest.raises(PermissionError, match="denied"):
                await windows_listener.start(callback)

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    async def test_stop_sets_running_false(self, windows_listener):
        """Test that stop() sets is_running to False."""
        callback = AsyncMock()

        mock_listener = MagicMock()
        mock_listener.request_access_async = AsyncMock(return_value=1)
        mock_listener.get_notifications_async = AsyncMock(return_value=[])

        with patch(
            "notification_bridge.listeners.windows.UserNotificationListener"
        ) as mock_unl:
            mock_unl.current = mock_listener

            await windows_listener.start(callback)
            assert windows_listener.is_running is True

            await windows_listener.stop()
            assert windows_listener.is_running is False

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    async def test_callback_invoked_on_new_notification(self, windows_listener):
        """Test that callback is invoked for new notifications."""
        callback = AsyncMock()
        call_count = 0

        mock_notification = MagicMock()
        mock_notification.id = 123
        mock_notification.app_info.display_info.display_name = "TestApp"

        # Mock the notification content
        mock_text_elem = MagicMock()
        mock_text_elem.text = "Test notification body"
        mock_binding = MagicMock()
        mock_binding.get_text_elements.return_value = [mock_text_elem]
        mock_notification.notification.visual.get_binding.return_value = mock_binding

        mock_listener = MagicMock()
        mock_listener.request_access_async = AsyncMock(return_value=1)

        # Return notification on first call, empty on subsequent calls
        async def get_notifications(*args):
            nonlocal call_count
            call_count += 1
            # First call is the startup snapshot, which is skipped
            if call_count == 2:
                return [mock_notification]
            return []

        mock_listener.get_notifications_async = get_notifications

        with patch(
            "notification_bridge.listeners.windows.UserNotificationListener"
        ) as mock_unl:
            mock_unl.current = mock_listener

            await windows_listener.start(callback)

            # Give polling time to run
            import asyncio

            await asyncio.sleep(0.2)

            await windows_listener.stop()

        # Callback should have been invoked
        assert callback.called
        payload = callback.call_args[0][0]
        assert isinstance(payload, NotificationPayload)


class TestWindowsTextExtraction:
    """Text extraction from WinRT UserNotification, using stand-in objects."""

    @staticmethod
    def _user_notification(bindings):
        from types import SimpleNamespace as NS

        def binding(template, texts):
            elements = [NS(text=t) for t in texts]
            return NS(template=template, get_text_elements=lambda: elements)

        visual = NS(bindings=[binding(tpl, texts) for tpl, texts in bindings])
        display = NS(display_name="Microsoft Teams")
        return NS(
            id=42,
            app_info=NS(display_info=display),
            notification=NS(visual=visual),
        )

    def test_summary_and_body_from_toast_generic(self):
        from notification_bridge.listeners.windows import WindowsListener

        n = self._user_notification(
            [("Other", ["ignored"]), ("ToastGeneric", ["Alice", "Hi", "there"])]
        )
        payload = WindowsListener()._convert_notification(n)
        assert payload.app_name == "Microsoft Teams"
        assert payload.summary == "Alice"
        assert payload.body == "Hi\nthere"

    def test_no_visual_yields_empty_text(self):
        from types import SimpleNamespace as NS

        from notification_bridge.listeners.windows import WindowsListener

        n = NS(id=1, app_info=None, notification=None)
        payload = WindowsListener()._convert_notification(n)
        assert payload.summary == "" and payload.body == ""


class TestWindowsStartupSnapshot:
    """Notifications already present at startup are not re-forwarded."""

    @pytest.fixture
    def fake_winrt(self, monkeypatch):
        import types
        from types import SimpleNamespace as NS

        state = NS(calls=0, batches=[])

        async def request_access_async():
            return "ALLOWED"

        async def get_notifications_async(kind):
            batch = state.batches[min(state.calls, len(state.batches) - 1)]
            state.calls += 1
            return batch

        listener = NS(
            request_access_async=request_access_async,
            get_notifications_async=get_notifications_async,
        )
        notifications = types.ModuleType("winrt.windows.ui.notifications")
        notifications.NotificationKinds = NS(TOAST=1)
        management = types.ModuleType("winrt.windows.ui.notifications.management")
        management.UserNotificationListener = NS(current=listener)
        management.UserNotificationListenerAccessStatus = NS(ALLOWED="ALLOWED")
        for name in ("winrt", "winrt.windows", "winrt.windows.ui"):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        monkeypatch.setitem(sys.modules, notifications.__name__, notifications)
        monkeypatch.setitem(sys.modules, management.__name__, management)
        return state

    @pytest.mark.asyncio
    async def test_existing_notifications_skipped(self, fake_winrt):
        import asyncio
        from types import SimpleNamespace as NS

        from notification_bridge.listeners.windows import WindowsListener

        old = NS(id=1, app_info=None, notification=None)
        new = NS(id=2, app_info=None, notification=None)
        fake_winrt.batches = [[old], [old, new]]

        callback = AsyncMock()
        listener = WindowsListener()
        await listener.start(callback)
        await asyncio.sleep(0.1)
        await listener.stop()

        forwarded = [c.args[0].hints["windows_id"] for c in callback.call_args_list]
        assert forwarded == [2]
