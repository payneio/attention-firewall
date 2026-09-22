"""Notification Bridge - D-Bus to Central Context API bridge."""


def __getattr__(name: str):
    # Lazy, so importing the package doesn't configure logging before main() runs
    if name == "app":
        from notification_bridge.server import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
