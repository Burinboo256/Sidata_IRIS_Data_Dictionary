# IRIS Data Dictionary Architecture Summary

## Overview

IRIS Data Dictionary is a local data catalog web application for browsing and documenting InterSystems IRIS persistent class metadata. It is built with Streamlit and uses `iris_data_dict.xlsx` as the main metadata source.

The system supports two storage backends:

- File backend: uses Excel and local JSON files
- PostgreSQL backend: uses PostgreSQL through SQLAlchemy

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web UI | Streamlit |
| Data Processing | pandas |
| Visualization | Plotly, Mermaid, Cytoscape.js |
| Excel Reader | openpyxl |
| Configuration | `config.toml`, `config.py` |
| File Storage | JSON files |
| Database Storage | PostgreSQL |
| ORM / DB Layer | SQLAlchemy |
| Source Data | `iris_data_dict.xlsx` |

---

## Main Modules

| File | Responsibility |
|---|---|
| `app.py` | Main Streamlit application, UI rendering, navigation, search, diagrams, analytics |
| `storage.py` | Unified storage layer for file backend and PostgreSQL backend |
| `config.py` | Loads configuration from `config.toml` and exposes constants |
| `models.py` | SQLAlchemy table definitions for PostgreSQL backend |
| `import_xlsx.py` | CLI script to import Excel metadata into PostgreSQL |
| `iris_data_dict.xlsx` | Main source metadata file |
| `config.toml` | Application configuration |
| `requirements.txt` | Python dependencies |

---

## High-Level Architecture

```mermaid
flowchart TB
  User[User / Browser] --> App[Streamlit App<br/>app.py]

  App --> UI[UI Pages<br/>Home, Search, Browse,<br/>Analytics, Table Detail]
  App --> Logic[Business Logic<br/>Search, FK, Lineage,<br/>Completeness, Export]
  App --> Viz[Visualization<br/>Plotly, Mermaid, Cytoscape.js]
  App --> Config[Config Loader<br/>config.py]
  App --> Storage[Storage Layer<br/>storage.py]

  Storage --> FileBackend[File Backend<br/>Excel + JSON]
  Storage --> PgBackend[PostgreSQL Backend<br/>SQLAlchemy]

  FileBackend --> XLSX[iris_data_dict.xlsx]
  FileBackend --> JSON[translations.json<br/>tags.json<br/>metadata.json<br/>changelog.json<br/>usage_log.json]

  PgBackend --> DB[(PostgreSQL)]

  Importer[import_xlsx.py] --> XLSX
  Importer --> DB
```

---

## Module Diagram

```mermaid
flowchart LR
  app[app.py<br/>Streamlit UI + feature logic]

  config[config.py<br/>Config loader]
  storage[storage.py<br/>Storage abstraction]
  models[models.py<br/>SQLAlchemy models]
  importer[import_xlsx.py<br/>Excel to PostgreSQL import]
  xlsx[iris_data_dict.xlsx]
  json[(Local JSON files)]
  pg[(PostgreSQL)]

  app --> config
  app --> storage

  storage --> config
  storage --> xlsx
  storage --> json
  storage --> pg
  storage --> models

  importer --> xlsx
  importer --> pg
  importer --> models
```

---

## Runtime Flow

```mermaid
sequenceDiagram
  participant User
  participant App as app.py
  participant Config as config.py
  participant Storage as storage.py
  participant Data as Excel / JSON / PostgreSQL
  participant Viz as Plotly / Mermaid / Cytoscape

  User->>App: Open Streamlit app
  App->>Config: Load configuration
  App->>Storage: Load dictionary and user data
  Storage->>Data: Read source data
  Data-->>Storage: Return data
  Storage-->>App: Return normalized DataFrames / dicts
  App->>Viz: Build charts and diagrams
  Viz-->>User: Render visual output

  User->>App: Edit tags / metadata / Thai descriptions
  App->>Storage: Save changes
  Storage->>Data: Persist data
```

---

## Layered Stack

```mermaid
flowchart TB
  L1[Presentation Layer<br/>Streamlit UI, sidebar, banner, tabs]
  L2[Feature Layer<br/>Search, Browse, Analytics,<br/>SQL Builder, FK Diagram, Lineage]
  L3[Domain Logic Layer<br/>Type mapping, FK graph,<br/>ER diagram, completeness, exports]
  L4[Storage API Layer<br/>storage.py]
  L5[Persistence Layer<br/>File backend or PostgreSQL backend]
  L6[Source Metadata<br/>Excel sheets or dict_* tables]

  L1 --> L2
  L2 --> L3
  L3 --> L4
  L4 --> L5
  L5 --> L6
```

---

## Data Sources

The main source file is `iris_data_dict.xlsx`, which contains five sheets:

| Sheet | Description |
|---|---|
| `sql_tables` | Table to class mapping, module, description |
| `sql_fields` | Field definitions per class |
| `fk_relationships` | FK / object-reference relationships |
| `classes` | IRIS class declarations and metadata |
| `members` | Properties, parameters, triggers |

---

## Storage Backends

### File Backend

Used by default for local development.

```mermaid
flowchart LR
  App[app.py] --> Storage[storage.py]
  Storage --> XLSX[iris_data_dict.xlsx]
  Storage --> Translations[translations.json]
  Storage --> Tags[tags.json]
  Storage --> Metadata[metadata.json]
  Storage --> Changelog[changelog.json]
  Storage --> Usage[usage_log.json]
```

### PostgreSQL Backend

Used for production or multi-user deployment.

```mermaid
flowchart LR
  App[app.py] --> Storage[storage.py]
  Storage --> DB[(PostgreSQL)]

  Import[import_xlsx.py] --> DB
  XLSX[iris_data_dict.xlsx] --> Import
```

PostgreSQL tables include:

| Table Group | Purpose |
|---|---|
| `dict_*` tables | Read-only imported dictionary metadata |
| `translations` | Thai field descriptions |
| `table_tags` | Table tags |
| `table_metadata` | Governance metadata |
| `changelog` | Audit log |
| `usage_log` | Usage tracking |

---

## Key Features

- Browse tables by module, name, tags, and certification status
- Full-text and advanced search
- Table schema view
- SQL Builder
- Thai description editor
- FK diagram
- Column-level lineage
- Analytics dashboard
- Module dependency map
- ER diagram
- Table tags and metadata
- Certification status
- Changelog
- Usage statistics
- File or PostgreSQL backend
- Mermaid and Cytoscape diagram rendering

---

## Summary

This project is a Streamlit-based data catalog application.

The main application logic lives in `app.py`, while `storage.py` abstracts persistence so the same UI can work with either local files or PostgreSQL.

The system is designed around a metadata source, `iris_data_dict.xlsx`, and adds user-managed annotations such as Thai descriptions, tags, governance metadata, changelog, and usage tracking.
