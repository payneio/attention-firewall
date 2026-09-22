"""
Notification Bridge - Entry point.

Listens to desktop notifications and forwards them to Central Context API.
Supports Linux (D-Bus) and Windows (WinRT).
"""

import os
import sys

from notification_bridge.core import Settings


def __getattr__(name: str):
    # Import the server lazily so main() can redirect output before logging is set up
    if name == "app":
        from notification_bridge.server import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _redirect_output(log_file: str | None) -> None:
    """Send stdout/stderr to log_file, or to devnull when there is no console (pythonw)."""
    if log_file:
        stream = open(log_file, "a", buffering=1, encoding="utf-8")
    elif sys.stdout is None or sys.stderr is None:
        stream = open(os.devnull, "w")
    else:
        return
    sys.stdout = sys.stderr = stream


def main() -> None:
    """Run the server."""
    import uvicorn

    settings = Settings()
    _redirect_output(settings.log_file)

    from notification_bridge.server import app

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
