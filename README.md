# Notification Bridge

A cross-platform service that listens to desktop notifications and forwards them to an HTTP API.

## Overview

Notification Bridge monitors desktop notifications and forwards them as JSON to a configurable HTTP endpoint.

| Platform | API | Status |
|----------|-----|--------|
| Linux | D-Bus (freedesktop.org spec) | Supported |
| Windows | WinRT UserNotificationListener | Supported |
| macOS | - | Not yet supported |

## Installation

```bash
cd notification-bridge

# Linux
uv sync --extra linux

# Windows
uv sync --extra windows
```

## Usage

```bash
# Start the bridge
uv run notification-bridge

# Server runs on port 9001 by default
```

### Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CENTRAL_CONTEXT_URL` | `http://localhost:9000` | Target API base URL |
| `BUCKET_NAME` | `notifications` | Bucket for stored notifications |
| `PORT` | `9001` | Server port |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with listener status |
| `/status` | GET | Bridge configuration and state |
| `/docs` | GET | OpenAPI documentation |

## Notification Data

Each captured notification is forwarded as JSON:

```json
{
  "app_name": "Firefox",
  "summary": "Download Complete",
  "body": "example.pdf has finished downloading",
  "icon": "firefox",
  "replaces_id": 0,
  "actions": ["open", "Open", "dismiss", "Dismiss"],
  "hints": {
    "urgency": 1,
    "category": "transfer.complete"
  },
  "timeout": -1,
  "received_at": "2026-02-12T21:52:37.303418+00:00"
}
```

## Running as a Service

### Linux (systemd)

See `examples/notification-bridge.service`:

```bash
cp examples/notification-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now notification-bridge
```

### Windows

Create a scheduled task to run at login, or use a service wrapper.

## Platform-Specific Notes

### Linux: D-Bus Permissions

On some systems, you may need to allow D-Bus eavesdropping. Create `/etc/dbus-1/session.d/notification-bridge.conf`:

```xml
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy context="default">
    <allow eavesdrop="true"/>
  </policy>
</busconfig>
```

### Windows: Notification Access

On first run, Windows will prompt you to grant notification access. You can also enable it manually:

**Settings > Privacy & Security > Notifications > Notification access**

## Architecture

```
notification_bridge/
├── core.py              # Settings, NotificationPayload, Forwarder
├── server.py            # FastAPI app and endpoints
├── main.py              # Entry point
└── listeners/
    ├── base.py          # NotificationListener protocol
    ├── linux.py         # D-Bus implementation
    └── windows.py       # WinRT implementation
```

## Development

```bash
# Install with dev dependencies
uv sync --extra linux  # or --extra windows

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=notification_bridge

# Format and lint
uv run ruff format .
uv run ruff check .
```

## License

MIT
