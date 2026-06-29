# Manual Verification Guide

## Purpose

This guide provides smoke-test steps for the documented feature set. Use it before committing changes that affect UI, storage, import, diagrams, or documentation line references.

## Setup

| Check | Command / Step | Expected result |
|---|---|---|
| Install dependencies | `pip install -r requirements.txt` | Dependencies install successfully. |
| Start app | `streamlit run app.py` | App opens without fatal data-load errors. |
| File backend | Run without postgres secrets. | Sidebar shows `Backend: file`. |
| PostgreSQL backend | Configure `backend = "postgres"` and `database_url` in `.streamlit/secrets.toml`. | Sidebar shows `Backend: postgres` and app loads data. |

## Core Navigation

| Feature | Steps | Expected result |
|---|---|---|
| App shell | Load app. | Top banner, sidebar, Home page, and metrics render. |
| Theme | Click theme toggle. | App switches between light and dark in the current session. |
| Home | Click Home. | Metrics, Modules section, and Recently Viewed behavior work. |
| Deep link | Open `/?table=<valid_table>`. | Detail opens for the table and URL remains synced. |
| Admin pages | Open Changelog or Usage Stats without admin mode. | Admin gate blocks page content. |

## Search and Browse

| Feature | Steps | Expected result |
|---|---|---|
| Search text | Search a known table/field term. | Tables and/or Fields tabs show results. |
| Search filters | Use certification/tag/FK/datatype filters. | Results respect selected filters. |
| Thai search | Search saved Thai text. | Matching field appears with TH Description. |
| Browse filters | Use module/name/tag/certification filters. | Table list narrows correctly. |
| Browse selection | Select a table row. | Detail page opens for that table. |

## Table Detail

| Feature | Steps | Expected result |
|---|---|---|
| Header | Open a table detail. | Table name, module badges, share hint, and class context render. |
| Governance tags | Add/remove a tag. | Badge updates, persists after rerun, changelog entry is written. |
| Governance metadata | Save owner/certification/frequency. | Header updates and Browse/Search filters can use the metadata. |
| Schema tab | Open Schema tab. | Columns, FK references, outgoing/incoming sections, parameters/triggers render when data exists. |
| CSV/Excel export | Click header download buttons. | Files download for selected table schema. |
| SQL Builder | Select fields and inspect generated SQL. | SQL updates and arrow examples appear for FK fields. |
| Thai Descriptions | Edit Thai text and save. | Progress updates, values persist, changelog entry is written. |
| FK Diagram | Test Mermaid, Cytoscape, filters, and split view. | Diagrams render or valid empty-state messages appear. |
| Column Lineage | Open Lineage tab. | Upstream/downstream FK rows and type reference render. |

## Standalone Lineage Finder

| Feature | Steps | Expected result |
|---|---|---|
| Table path search | Choose source/target tables and click Find Relationship. | Paths, metrics, details, and selected diagram renderer appear when paths exist. |
| Guards | Choose same source/target or disconnected tables. | Info/warning message appears. |
| Direction/filter controls | Change direction, hops, max paths, same-module flag. | Search results reflect selected controls. |

## Analytics, Usage, and Changelog

| Feature | Steps | Expected result |
|---|---|---|
| Analytics dependency | Open Module Dependency Map. | Heatmap, Mermaid flowchart, and dependency table render when data exists. |
| Analytics hubs | Open Hub Tables and select a row. | Chart/table render and row navigates to detail. |
| Analytics orphans | Filter orphan tables. | Chart/table update and row navigates to detail. |
| Analytics ER | Generate ER by module/table/custom selection. | Mermaid or Cytoscape diagram renders. |
| Usage Stats | Navigate, search, open tables, then view as admin. | Metrics/charts/recent activity include new events. |
| Changelog | Make tag/metadata/translation changes, then view as admin. | Changelog entries appear and filters work. |

## Operations

| Feature | Steps | Expected result |
|---|---|---|
| PostgreSQL import | Run `python import_xlsx.py --db <url> --drop` against disposable DB. | `dict_*` tables populate; runtime user tables are preserved. |
| Config changes | Change non-secret config in `config.toml` and restart. | App reflects new values. |
| Documentation line refs | After code changes, re-check docs that cite changed ranges. | `file:line` references still point to current behavior. |

