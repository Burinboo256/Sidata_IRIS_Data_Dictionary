# Feature Documentation Plan

## Objective

Create complete, maintainable documentation for every user-facing feature and supporting technical feature in the IRIS Data Dictionary app.

The documentation should help two audiences:

- Users and data stewards who need to understand how to use each feature.
- Developers and maintainers who need to know where the feature lives in code, what data it depends on, and how to verify it.

## Current Documentation Baseline

| Existing file | Current role | Next action |
|---|---|---|
| `README.md` | User-facing overview, navigation guide, setup, and feature summary. | Keep as entry point. Link new per-feature docs from it after docs are created. |
| `doc/ARCHITECTURE_SUMMARY.md` | High-level architecture and module summary. | Keep as system overview. Add links to feature docs later. |
| `doc/APP_PY_ANALYSIS.md` | Technical analysis of `app.py` and page composition. | Use as source material for feature docs. |
| `doc/LINEAGE_FINDER_PLAN.md` | Existing planning notes for Lineage Finder. | Keep as historical implementation plan unless superseded. |
| `doc/LINEAGE_FINDER_STACK.md` | Detailed Lineage Finder stack with file/line references. | Treat as the model format for other technical feature docs. |

## Documentation Set To Create

Use one markdown file per major feature. Keep filenames stable and grouped under `doc/`.

| Priority | Feature area | Proposed doc file | Status |
|---|---|---|---|
| P0 | App navigation, banner, sidebar, theme, admin lock | `doc/APP_SHELL_STACK.md` | Done |
| P0 | Data loading, configuration, storage backends | `doc/DATA_STORAGE_STACK.md` | Done |
| P0 | Home page and recently viewed | `doc/HOME_STACK.md` | Done |
| P0 | Search and advanced filters | `doc/SEARCH_STACK.md` | Done |
| P0 | Browse tables | `doc/BROWSE_STACK.md` | Done |
| P0 | Table detail overview and header metadata | `doc/TABLE_DETAIL_STACK.md` | Done |
| P0 | Schema tab and schema export | `doc/SCHEMA_EXPORT_STACK.md` | Done |
| P0 | SQL Builder tab | `doc/SQL_BUILDER_STACK.md` | Done |
| P0 | Thai descriptions editor | `doc/THAI_DESCRIPTIONS_STACK.md` | Done |
| P0 | Table tags, metadata, certification status | `doc/GOVERNANCE_METADATA_STACK.md` | Done |
| P0 | Per-table FK Diagram tab | `doc/FK_DIAGRAM_STACK.md` | Done |
| P0 | Per-table column-level Lineage tab | `doc/COLUMN_LINEAGE_STACK.md` | Done |
| P0 | Standalone Lineage Finder page | `doc/LINEAGE_FINDER_STACK.md` | Done, keep updated |
| P1 | Analytics page: module dependency, hub tables, orphan tables, ER diagram | `doc/ANALYTICS_STACK.md` | Done |
| P1 | Usage Stats page | `doc/USAGE_STATS_STACK.md` | Done |
| P1 | Changelog page | `doc/CHANGELOG_STACK.md` | Done |
| P1 | Diagram rendering and export utilities | `doc/DIAGRAM_RENDERING_STACK.md` | Done |
| P1 | URL deep linking and navigation state | `doc/NAVIGATION_STATE_STACK.md` | Done |
| P2 | PostgreSQL import workflow | `doc/IMPORT_XLSX_STACK.md` | Done |
| P2 | Config reference | `doc/CONFIG_REFERENCE.md` | Done |
| P2 | Manual verification guide | `doc/MANUAL_VERIFICATION_GUIDE.md` | Done |

## Standard Doc Template

Every `*_STACK.md` feature doc should follow this structure:

~~~markdown
# <Feature Name> Stack

## Purpose

Short explanation of what the feature does and who uses it.

## High Level Stack

| Layer | Responsibility | Source |
|---|---|---|
| UI | ... | `app.py:start-end` |
| Domain logic | ... | `app.py:start-end` or helper file |
| Storage | ... | `storage.py:start-end` |

## High Level Flow

```text
User action
  -> app code location
  -> helper/storage code location
  -> rendered output or saved state
```

## Detail Level Stack

### 1. Entry Point

| Detail | Source |
|---|---|
| ... | `file.py:start-end` |

### 2. Data Inputs

| Data | Required fields | Usage | Source |
|---|---|---|---|
| ... | ... | ... | `file.py:start-end` |

### 3. Processing Logic

| Detail | Source |
|---|---|
| ... | `file.py:start-end` |

### 4. Output / UI

| Detail | Source |
|---|---|
| ... | `file.py:start-end` |

## Ownership

| Area | Owner file | Source |
|---|---|---|
| ... | `app.py` | `app.py:start-end` |

## Manual Verification

| Check | Steps | Expected result |
|---|---|---|
| ... | ... | ... |
~~~

## Source Mapping Inventory

Initial source locations found from `app.py` routing and existing docs:

| Area | Known source anchors |
|---|---|
| Imports and storage wiring | `app.py:25-40` |
| Cached data loading | `app.py:430-432`, `app.py:1456`, `storage.py:70-106` |
| Sidebar page map | `app.py:1590-1598` |
| Home page | `app.py:1646-1685` |
| Search page | `app.py:1686-1888` |
| Browse page | `app.py:1889-1970` |
| Detail page | `app.py:1971-2888` |
| Detail tabs | `app.py:2192-2888` |
| Schema tab | `app.py:2192-2441` |
| FK Diagram tab | `app.py:2442-2795` |
| Column-level Lineage tab | `app.py:2796-2878` |
| Lineage Finder page | `app.py:2894-3024`, `lineage_finder.py:36-326` |
| Analytics page | `app.py:3028-3445` |
| Usage Stats page | `app.py:3446-3592` |
| Changelog page | `app.py:3593-end` |
| Mermaid HTML wrapper | `app.py:601` |
| IRIS to MSSQL type mapping | `app.py:787` |

These anchors are starting points. Each feature doc should re-read the relevant code section and record exact line ranges at the time the doc is written.

## Work Plan

### Phase 1: Establish Core Technical Docs

Goal: document the app foundation and the main navigation routes first.

1. Create `APP_SHELL_STACK.md`.
   - Cover banner, sidebar, theme toggle, admin lock, page routing.
   - Include file/line references for `render_banner`, `nav`, page map, and locked page behavior.
2. Create `DATA_STORAGE_STACK.md`.
   - Cover config, Excel backend, PostgreSQL backend, JSON persistence, load/save helpers.
   - Include `storage.py`, `config.py`, `models.py`, and `import_xlsx.py` references where relevant.
3. Create `HOME_STACK.md`.
   - Cover module cards, recently viewed, summary metrics, navigation from cards.
4. Create `SEARCH_STACK.md`.
   - Cover text search, table results, field results, advanced filters, search logging.
5. Create `BROWSE_STACK.md`.
   - Cover module/name/tag/certification filters, table list, navigation into detail.

### Phase 2: Document Table Detail Features

Goal: document the highest-use workflows inside the selected table detail page.

1. Create `TABLE_DETAIL_STACK.md`.
   - Cover selected table state, header, metadata display, tags, certification, detail tabs.
2. Create `SCHEMA_EXPORT_STACK.md`.
   - Cover schema dataframe, type mapping, outgoing/incoming FK sections, CSV and Excel export.
3. Create `SQL_BUILDER_STACK.md`.
   - Cover generated SELECT statement, selected columns, IRIS reference syntax, ObjectScript examples.
4. Create `THAI_DESCRIPTIONS_STACK.md`.
   - Cover translation loading, inline editing, save behavior, completeness progress, changelog entry.
5. Create `GOVERNANCE_METADATA_STACK.md`.
   - Cover tags, custom tag normalization, owner/steward/contact, certification, update frequency, save behavior.
6. Create `FK_DIAGRAM_STACK.md`.
   - Cover per-table ER diagram, Mermaid/Cytoscape renderers, direction/split view filters, diagram export.
7. Create `COLUMN_LINEAGE_STACK.md`.
   - Cover upstream/downstream column-level lineage inside table detail.

### Phase 3: Document Cross-Table and Admin Features

Goal: complete the standalone pages and observability features.

1. Review and maintain `LINEAGE_FINDER_STACK.md`.
   - Confirm line references still match after any code changes.
2. Create `ANALYTICS_STACK.md`.
   - Cover module dependency map, hub tables, orphan tables, and multi-table ER diagram.
3. Create `USAGE_STATS_STACK.md`.
   - Cover session/page/table/search logging, charts, top tables, top searches, recent activity.
4. Create `CHANGELOG_STACK.md`.
   - Cover changelog storage, filters, admin access, navigation from changelog rows.
5. Create `DIAGRAM_RENDERING_STACK.md`.
   - Cover Mermaid, Cytoscape, SVG/PNG export, shared diagram helpers, fallback behavior.
6. Create `NAVIGATION_STATE_STACK.md`.
   - Cover session state, URL deep link, selected table, recently viewed, rerun behavior.

### Phase 4: Document Operations and Verification

Goal: document setup, import, config, and manual QA after feature changes.

1. Create `IMPORT_XLSX_STACK.md`.
   - Cover CLI options, PostgreSQL init, drop behavior, imported tables.
2. Create `CONFIG_REFERENCE.md`.
   - Cover `config.toml`, `config.py`, `.streamlit/secrets.toml`, and environment-specific settings.
3. Create `MANUAL_VERIFICATION_GUIDE.md`.
   - Cover smoke test steps for each page and detail tab.
4. Update `README.md`.
   - Done. Added a documentation index linking all new docs.
5. Update `doc/ARCHITECTURE_SUMMARY.md`.
   - Done. Added links from system layers to detailed feature docs.

## Per-Feature Documentation Checklist

Use this checklist before marking any feature doc done:

| Check | Required |
|---|---|
| Purpose is clear for users and maintainers. | Yes |
| High-level stack exists. | Yes |
| Detail-level stack exists. | Yes |
| Every major behavior has `file:line` or `file:start-end`. | Yes |
| Data inputs and outputs are documented. | Yes |
| Storage reads/writes are documented if the feature persists data. | Yes |
| Manual verification steps exist. | Yes |
| Related files are linked from README or architecture docs. | Yes |

## Recommended Execution Order

1. `DATA_STORAGE_STACK.md`
2. `APP_SHELL_STACK.md`
3. `SEARCH_STACK.md`
4. `BROWSE_STACK.md`
5. `TABLE_DETAIL_STACK.md`
6. `SCHEMA_EXPORT_STACK.md`
7. `THAI_DESCRIPTIONS_STACK.md`
8. `GOVERNANCE_METADATA_STACK.md`
9. `FK_DIAGRAM_STACK.md`
10. `COLUMN_LINEAGE_STACK.md`
11. `ANALYTICS_STACK.md`
12. `USAGE_STATS_STACK.md`
13. `CHANGELOG_STACK.md`
14. `DIAGRAM_RENDERING_STACK.md`
15. `NAVIGATION_STATE_STACK.md`
16. `IMPORT_XLSX_STACK.md`
17. `CONFIG_REFERENCE.md`
18. `MANUAL_VERIFICATION_GUIDE.md`
19. README and architecture index updates

This order starts with shared foundations, then documents user workflows, then finishes with operations and cross-cutting references.

## Maintenance Rules

- Re-check line numbers whenever code changes near a documented feature.
- Prefer `file:start-end` ranges over single lines for multi-line behavior.
- Keep user-facing instructions separate from implementation details when a doc becomes long.
- Do not duplicate large chunks of README text; link back to README for general usage.
- When a feature is refactored out of `app.py`, update the feature doc ownership table immediately.
