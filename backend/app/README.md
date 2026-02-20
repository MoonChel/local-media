# Backend Architecture

The backend is organized into modular packages for better maintainability and flexibility.

## Structure

```
backend/app/
├── core/                   # Shared core utilities
│   ├── config.py          # Configuration management
│   ├── db.py              # Database connection
│   ├── db_utils.py        # Database utilities
│   ├── dependencies.py    # FastAPI dependencies
│   └── models.py          # SQLAlchemy models
│
├── modules/               # Feature modules (can be enabled/disabled)
│   ├── library/          # Video library management (core, always enabled)
│   │   ├── router.py     # API endpoints
│   │   ├── service.py    # Business logic
│   │   └── transcoding.py # FFmpeg transcoding
│   │
│   ├── torrents/         # Torrent downloads (optional)
│   │   ├── router.py     # API endpoints
│   │   └── service.py    # Torrent management
│   │
│   ├── youtube/          # YouTube downloads (optional)
│   │   ├── router.py     # API endpoints
│   │   └── service.py    # YouTube download logic
│   │
│   ├── pastebin/         # Text sharing (optional)
│   │   └── router.py     # API endpoints
│   │
│   └── settings/         # Application settings (core, always enabled)
│       ├── router.py     # API endpoints
│       └── service.py    # Settings management
│
└── main.py               # FastAPI application entry point
```

## Module System

Modules can be enabled/disabled via `config.yaml`:

```yaml
modules:
  torrents: true   # Enable/disable torrent downloads
  youtube: true    # Enable/disable YouTube downloads
  pastebin: true   # Enable/disable pastebin
```

### Core Modules (Always Enabled)
- **library**: Video file management, streaming, transcoding
- **settings**: Application configuration

### Optional Modules
- **torrents**: Download videos via torrent
- **youtube**: Download videos from YouTube
- **pastebin**: Share text snippets

## Adding a New Module

1. Create a new directory under `modules/`
2. Add `__init__.py`, `router.py`, and optionally `service.py`
3. Register the router in `main.py`
4. Add enable/disable flag to `config.yaml`
5. Update frontend to conditionally show menu item

## Shared Resources

All modules share:
- Database connection (via `core.db`)
- Configuration (via `core.config`)
- Authentication (via `core.dependencies`)
- Models (via `core.models`)
