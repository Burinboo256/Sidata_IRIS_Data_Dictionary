# Config Reference

## Purpose

This reference documents committed app configuration in `config.toml`, typed defaults exposed by `config.py`, and secret settings that belong in `.streamlit/secrets.toml`.

## High Level Stack

| Layer | Responsibility | Source |
|---|---|---|
| Committed config | `config.toml` stores non-secret app settings. | `config.toml:1-78` |
| Config loader | `config.py` loads TOML and falls back to defaults. | `config.py:19-52` |
| Constants | `config.py` exposes app identity, file paths, limits, UI defaults, tags, metadata options, and admin defaults. | `config.py:55-119` |
| Secret config | `.streamlit/secrets.toml` stores admin passcode, backend, and database URL. | `config.py:11-12`, `storage.py:34-42`, `storage.py:52-56`, `app.py:54-57` |
| App consumers | `app.py` and `storage.py` import config constants. | `app.py:11-23`, `storage.py:23-32` |

## Detail Level Stack

### 1. Loader Behavior

| Detail | Source |
|---|---|
| `config.py` states that secrets should not be stored in committed config. | `config.py:1-13` |
| Loader uses `tomllib` on Python 3.11+ or `tomli` fallback. | `config.py:19-26` |
| Config path is project-root `config.toml` beside `config.py`. | `config.py:28` |
| Missing config or loader failure returns empty dict. | `config.py:31-38` |
| `_get()` resolves dot-notation keys and returns default when missing. | `config.py:44-52` |

### 2. `config.toml` Sections

| Section | Keys | Source |
|---|---|---|
| `[app]` | `name`, `version`, `environment`, `page_title`, `page_icon`, `logo_file` | `config.toml:5-11` |
| `[app.links]` | `request_change_url` | `config.toml:13-14` |
| `[data]` | `excel_file` | `config.toml:17-18` |
| `[storage]` | runtime JSON file names | `config.toml:21-26` |
| `[limits]` | changelog/usage/recent/notification/custom-tag limits | `config.toml:29-34` |
| `[ui.diagram]` | FK/ER diagram defaults and Cytoscape height | `config.toml:37-43` |
| `[ui.analytics]` | hub top N, module top N, min refs | `config.toml:46-49` |
| `[ui.browse]` | low completeness threshold | `config.toml:52-53` |
| `[defaults]` | default page, module filter, theme | `config.toml:56-59` |
| `[tags]` | predefined tag list | `config.toml:62-66` |
| `[metadata]` | certification and update frequency options | `config.toml:69-73` |
| `[admin]` | locked pages and passcode fallback | `config.toml:76-78` |

### 3. Exposed Constants

| Constant group | Source |
|---|---|
| App identity and request-change URL | `config.py:55-63` |
| Source workbook path | `config.py:65-66` |
| Runtime JSON file paths | `config.py:68-73` |
| Capacity limits | `config.py:75-80` |
| Diagram UI defaults | `config.py:82-88` |
| Analytics defaults | `config.py:90-93` |
| Browse threshold | `config.py:95-96` |
| Session defaults | `config.py:98-101` |
| Tags and metadata option lists | `config.py:103-115` |
| Admin locked pages and fallback passcode | `config.py:117-119` |

### 4. Secret Settings

| Secret | Usage | Source |
|---|---|---|
| `admin_passcode` | Overrides admin fallback passcode for locked pages. | `app.py:54-57` |
| `backend` | Selects `file` or `postgres` storage backend. | `storage.py:34-42` |
| `database_url` | SQLAlchemy PostgreSQL connection URL. | `storage.py:52-56`, `import_xlsx.py:57-62` |

## Manual Verification

| Check | Steps | Expected result |
|---|---|---|
| Missing config fallback | Temporarily move `config.toml` in disposable copy and start app. | App starts with defaults. |
| App identity | Change non-secret app name/version in `config.toml`. | Banner reflects updated values on restart. |
| Limits | Change `max_recently_viewed`. | Home recent list caps at new value. |
| Admin secret | Set `admin_passcode` in `.streamlit/secrets.toml`. | Locked pages require the secret passcode. |
| Backend secret | Set `backend = "postgres"` and `database_url`. | Sidebar backend changes and app reads PostgreSQL data. |

