# Local media player

FastAPI + Vue + Tailwind + Plyr app for local playback of movies/shows/videos.
Torrent is optional and only used to download into one selected media folder.

## Features

- Playback-first UI: pick item and play
- Dynamic media folders from config (multiple folders per type supported)
- Settings UI to add/update/delete folder mappings at runtime
- Option to create missing media folder while adding mapping
- Stable URL per video (`/watch/<id>`) based on `source_id + relative_path`
- Continue watching (SQLite on volume)
- File watcher auto-reindex + periodic full rescan fallback
- Optional basic auth
- Optional torrent ingest (`magnet` + `.torrent`) to chosen folder

## Dev (2 containers)

```bash
make dev
```

Open [http://localhost:5173](http://localhost:5173).

Stop:

```bash
make down
```

## Prod (single container)

```bash
make prod
```

Open [http://localhost:8080](http://localhost:8080).

## Volumes

- `./config` -> `/config` (`config.yaml`, `state.db`)
- `./media` -> `/media`

Use subfolders under `./media` as sources (`/media/movies`, `/media/shows`, etc).
This allows deleting mapped folders from inside the app.

## Settings

Open `/settings` in the app:

- Add mapping to existing folder
- Add mapping and create folder if missing
- Edit mapping (same `id`)
- Delete mapping

All changes persist to `/config/config.yaml` and are applied immediately (rescan + watcher reload).

## Config

You can still edit `/config/config.yaml` directly for advanced/manual changes:

- `library.sources`
- `downloads.enabled`
- `auth` / `extensions` / scan settings

Auth env overrides:

- `AUTH_ENABLED=true|false`
- `APP_USER=<username>`
- `APP_PASSWORD=<password>`

## API

- `GET /api/health`
- `GET /api/sources`
- `GET /api/videos`
- `GET /api/stream/{id}`
- `GET /api/progress/{id}`
- `PUT /api/progress/{id}`
- `POST /api/rescan`
- `GET /api/torrents/meta`
- `GET /api/torrents`
- `POST /api/torrents/magnet` with `{ magnet, source_id }`
- `POST /api/torrents/upload` multipart with `source_id`, `torrent_file`

## Notes / TODO

- Re-check Video.js v10 preview migration later:
  - Docs: https://v10.videojs.org/
  - Install guide: https://v10.videojs.org/docs/framework/react/style/css/how-to/installation
  - Try when preview packages (`@videojs/html-preview` / `@videojs/react-preview`) are reliably available and stable.
