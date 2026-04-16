# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Two separate tools sharing the same data source (`iris_data_dict.xlsx`):

1. **`app.py`** — the primary product: a Streamlit web app (DataHub-like data catalog) for browsing InterSystems IRIS persistent class metadata.
2. **`Create_JSON.ipynb`** — a secondary utility that exports the xlsx data to `iris_data_dictionary_full.json` for use by external tools.

## Running the app

```bash
streamlit run app.py
```

Dependencies: `streamlit pandas openpyxl plotly sqlalchemy psycopg2-binary`
(The SQLAlchemy/psycopg2 packages are only used when `backend = "postgres"`.)

Server config lives in `.streamlit/config.toml` (git-ignored; copy from `.streamlit/config.toml.example`). Set `address = "0.0.0.0"` — not a specific IP — so both localhost and network access work.

Admin passcode lives in `.streamlit/secrets.toml` (git-ignored; copy from `.streamlit/secrets.toml.example`). Falls back to `"admin1234"` if not set.

## Configuration layer (`config.toml` + `config.py`)

All non-secret application parameters are centralised in `config.toml` (committed to git). `config.py` is a thin loader that reads it and exposes typed Python constants used by both `app.py` and `storage.py`.

### How it works

```
config.toml  ──►  config.py (_load + _get)  ──►  APP_NAME, PREDEFINED_TAGS, …
```

- `config.py` uses `tomllib` (Python ≥ 3.11 stdlib) or `tomli` (pip install; Python 3.8–3.10).
- If `config.toml` is missing or a key is absent, every constant falls back to a hardcoded default — the app always starts.
- **Never put secrets in `config.toml`** — use `.streamlit/secrets.toml` for `admin_passcode` and `database_url`.

### Sections in config.toml

| Section | Key constants | Purpose |
|---|---|---|
| `[app]` | `APP_NAME`, `APP_VERSION`, `APP_ENV`, `PAGE_TITLE`, `LOGO_FILE` | Banner identity, browser tab |
| `[app.links]` | `REQUEST_CHANGE_URL` | Banner → Request Change button |
| `[data]` | `EXCEL_FILE` | Source xlsx path |
| `[storage]` | `TRANSLATIONS_FILE`, `TAGS_FILE`, `CHANGELOG_FILE`, `METADATA_FILE`, `USAGE_LOG_FILE` | File backend paths |
| `[limits]` | `MAX_CHANGELOG_ENTRIES`, `MAX_USAGE_LOG_ENTRIES`, `MAX_RECENTLY_VIEWED`, `NOTIFICATION_WINDOW_DAYS`, `MAX_CUSTOM_TAG_CHARS` | Capacity + UI limits |
| `[ui.diagram]` | `FK_MAX_ENTITIES_DEFAULT/MAX/STEP`, `FK_MAX_FIELDS_DEFAULT`, `ER_MAX_FIELDS_DEFAULT`, `CYTOSCAPE_HEIGHT` | FK Diagram + ER Diagram slider defaults |
| `[ui.analytics]` | `HUB_TOP_N_DEFAULT`, `MODULE_TOP_N_DEFAULT`, `MIN_REFS_DEFAULT` | Analytics page slider defaults |
| `[ui.browse]` | `COMPLETENESS_LOW_THRESHOLD` | % threshold for "low completeness" flag |
| `[defaults]` | `DEFAULT_PAGE`, `DEFAULT_MODULE_FILTER`, `DEFAULT_THEME` | Session state initial values |
| `[tags]` | `PREDEFINED_TAGS` | Built-in tag list |
| `[metadata]` | `CERT_OPTIONS`, `UPDATE_FREQ_OPTIONS` | Dropdown option lists |
| `[admin]` | `LOCKED_PAGES`, `ADMIN_PASSCODE_FALLBACK` | Admin gate config |

### Adding a new config value

1. Add the key to `config.toml` under the appropriate section.
2. Add a constant in `config.py` using `_get("section.key", default)`.
3. Import the constant in `app.py` or `storage.py` and use it — never hardcode the value again.

## Storage layer (`storage.py`)

All persistence is routed through `storage.py`. `app.py` never reads/writes files or databases directly — it only calls functions imported from `storage`.

### Backend switching

Set `backend` in `.streamlit/secrets.toml`:

```toml
backend = "file"      # default — flat JSON files, zero setup
backend = "postgres"  # PostgreSQL via SQLAlchemy
database_url = "postgresql://user:pass@host:5432/iris_dict"
```

`storage.BACKEND` is detected once at module import time. The sidebar shows `💾 Backend: file` (or `postgres`) so you can confirm which backend is active.

### File backend (default)

All mutable state lives in JSON files in the project root:

| File | Content |
|---|---|
| `translations.json` | Thai descriptions `{class_name: {field: text}}` |
| `tags.json` | Tags per table `{table_name: [tag, ...]}` |
| `metadata.json` | Governance metadata per table |
| `changelog.json` | Audit log list (capped at 1 000 entries) |
| `usage_log.json` | Usage events list (capped at 10 000 entries) |

These files are git-ignored (live state only). `iris_data_dict.xlsx` is the read-only data source and is committed.

### PostgreSQL backend

Requires `sqlalchemy>=2.0` and `psycopg2-binary>=2.9`. Tables are defined in `models.py` and created by calling `storage.init_db()` (done automatically by `import_xlsx.py`).

**Import data from xlsx:**

```bash
python import_xlsx.py --xlsx iris_data_dict.xlsx
# --db   override the connection URL (else reads secrets.toml / DATABASE_URL env var)
# --drop truncate all dict_* tables before import (clean re-import)
```

**Tables created:**

| Table | Purpose |
|---|---|
| `dict_tables` | Mirrors `sql_tables` sheet |
| `dict_fields` | Mirrors `sql_fields` sheet |
| `dict_fk` | Mirrors `fk_relationships` sheet |
| `dict_classes` | Mirrors `classes` sheet |
| `dict_members` | Mirrors `members` sheet |
| `translations` | Thai descriptions (composite PK `class_name, field_name`) |
| `table_tags` | Tags (composite PK `table_name, tag`) |
| `table_metadata` | Governance metadata (PK `table_name`) |
| `changelog` | Audit log (serial ID, capped in app) |
| `usage_log` | Usage events (serial ID, JSONB `details`, capped in app) |

### Adding a new persistence operation

1. Add `_file_*` and `_pg_*` implementations in `storage.py`.
2. Add a public dispatcher function that calls the right one based on `BACKEND`.
3. Import the public function in `app.py`.
4. Never call file I/O or SQLAlchemy directly from `app.py`.

## app.py architecture

The entire app is a single-file Streamlit app (~3000 lines). There is no routing framework — navigation is driven by `st.session_state.page`.

### Data loading

All five sheets from `iris_data_dict.xlsx` are loaded once via `@st.cache_data`:

```python
tables, fields, fk, classes, members = load_data()
```

Three derived globals are computed at startup (also cached):
- `COMPLETENESS` — `{class_name: pct}` EN description fill rate per table
- `HUB_DF`, `ORPHAN_DF`, `DEP_COUNTS` — analytics aggregates
- `MODULE_SUMMARY` — module list with table counts

The startup block wraps each computation in its own `try/except` so a failure in analytics does not prevent the rest of the app from loading. `load_data()` itself calls `st.stop()` on failure with a clear error message — never a raw traceback.

The `fk` dataframe has a `resolve_status` column; always filter `fk[fk["resolve_status"] == "resolved"]` before using FK data. Unresolved rows (missing `source_sql_field_name`) are noise.

### Navigation

```python
def nav(page: str, table: str = None): ...
```

`st.session_state.page` drives which page block renders. Valid values: `"home"`, `"search"`, `"browse"`, `"detail"`, `"analytics"`, `"changelog"`, `"usage"`. The `browse` and `detail` pages share one `elif` branch.

URL deep-linking is handled at the top of every render cycle via `st.query_params["table"]`.

### Admin access control

```python
LOCKED_PAGES = {"changelog", "usage"}
ADMIN_PASSCODE  # read from st.secrets["admin_passcode"], fallback "admin1234"
```

`st.session_state.admin_authenticated` (bool) tracks whether the current session has passed the passcode check. `render_admin_gate(target_page)` renders the passcode form and calls `st.stop()` — insert it at the top of any locked page block before rendering content.

### Key helper functions

| Function | Purpose |
|---|---|
| `render_banner()` | Renders the fixed 60 px top banner (logo, title, badges, last-updated, Request Change, bell, Guest avatar) and injects sidebar toggle JS via `components.html`. |
| `_module_mermaid_html(mermaid_code)` | Wraps raw Mermaid code in the full HTML shell for the Module Dependency Map. Returns `html`. |
| `build_module_mermaid(dep_counts, direction, collapse_bidir, center_module)` | Builds Mermaid code + calls `_module_mermaid_html`. Returns `(html, code)`. |
| `build_er_mermaid(table_names, include_fields, max_fields, cross_module, direction)` | Mermaid `erDiagram` for the FK Diagram tab and Analytics → ER Diagram. Returns `(html, code)`. On failure returns `(error_html, "# error: ...")`. |
| `build_cytoscape_html(table_names, include_fields, max_fields, cross_module, center_table, height)` | Interactive Cytoscape.js ER diagram. Returns `html` string. Call sites wrap it in `try/except` → `_cytoscape_error_html()`. |
| `_cytoscape_error_html(err, height)` | Returns a self-contained error HTML page with a Refresh button. Used by Cytoscape call-site error handlers. |
| `render_admin_gate(target_page)` | Renders passcode form for locked pages. Sets `admin_authenticated` on success and calls `st.rerun()`. |
| `simplify_iris_type(type_str)` | Maps IRIS verbose types (`%String(...)`, `%Date`, `CTCompany`) to short ER labels (`string`, `date`, `ref`). |
| `schema_to_csv(...)` / `schema_to_excel(...)` | Export helpers for the Schema tab download buttons. |
| `compute_analytics(fk_df, tables_df)` | Returns `(hub_df, orphan_df, dep_counts)`. Cached. On failure returns empty DataFrames. |

### Cytoscape.js rendering (`build_cytoscape_html`)

`build_cytoscape_html` is the interactive alternative to `build_er_mermaid`. It loads Cytoscape.js 3.28 from CDN (no extra pip package) and returns a self-contained HTML string for `components.html()`.

Key design decisions:

- **Node SVG cards** — when `include_fields=True`, each node's background is set to an SVG data-URI (`data:image/svg+xml,...`) generated by the inner `_node_svg()` helper. The SVG draws the table header (module colour) + field rows (type, name, FK badge, alternating row fills). Cytoscape's own text label is suppressed with `'label': ''` and `'text-opacity': 0` via the `node[?has_svg]` stylesheet selector.
- **`has_svg` node data flag** — set to `True` when a node was given an SVG inline style. Used by the stylesheet to suppress the default text label only for those nodes.
- **Inline element styles** — SVG nodes set `width`, `height`, `shape: rectangle`, and `background-image` directly in the element's `style` dict (higher priority than the global stylesheet in Cytoscape).
- **Side panel** — stores `all_fields_list` (all fields, not just the truncated set shown in the SVG) in `node.data().fields` so the click handler can display the complete field list.
- **Layout tuning** — `idealEdgeLength` and `nodeRepulsion` scale up automatically when `include_fields=True` so the larger SVG cards don't overlap.
- **`_xe(s)`** — inner helper that XML-escapes strings for safe embedding inside SVG text elements.

### Top banner (`render_banner`)

`render_banner()` is called once at the top of the main render cycle (after session state init). It:

1. Emits CSS via `st.markdown(unsafe_allow_html=True)`:
   - Hides Streamlit's default header (`header[data-testid="stHeader"]`)
   - Pushes sidebar down to `top: 60px` so it never overlaps the banner
   - Defines all `.app-banner`, `.bn-*` classes
   - Sets `pointer-events: none` on the banner background so Streamlit's underlying toggle button remains clickable; re-enables `pointer-events: auto` on interactive children

2. Emits the banner HTML via `st.markdown` (string concatenation — never f-strings with user data; `html.escape()` on all variable content)

3. Injects sidebar toggle JS via `components.html(height=1)` (runs in an iframe, uses `window.parent.document` to reach the main page):
   - Attaches a click handler to `#bn-toggle` (the ☰ hamburger button)
   - Creates `#bn-edge-strip` — a fixed 6 px left-edge strip that glows gold on hover and auto-opens the sidebar after 350 ms
   - `setInterval` every 800 ms re-attaches both after Streamlit reruns (which refresh the DOM)
   - `findToggleBtn()` searches for Streamlit's real toggle button: first by `data-testid`, then by position (left 25 % of viewport, top < 300 px)

**Important:** `<script>` tags inside `st.markdown()` do NOT execute — Streamlit uses `innerHTML` assignment which strips scripts. All JS must go through `components.html()`.

### Mermaid rendering

All Mermaid builders (`_module_mermaid_html`, `build_er_mermaid`) use the same pattern:

```javascript
mermaid.initialize({ startOnLoad: false, ... });
var _done = false;
var _svgStr = "";
async function _render() {
  if (_done) return;
  if (document.body.offsetWidth === 0) { setTimeout(_render, 150); return; }
  _done = true;
  var r = await mermaid.render("id", _code);
  _svgStr = r.svg;
  document.getElementById("diagram").innerHTML = _svgStr;
  document.getElementById("btn-bar").style.display = "block";
}
```

The `offsetWidth === 0` check defers rendering until the iframe is visible (Streamlit renders all tab content upfront with `display:none`). Each builder also injects **⬇ SVG** and **⬇ PNG** download buttons that become visible after render.

### Detail page tabs

Each table detail page has **five** tabs:
1. **📋 Schema** — fields, FK references, incoming refs, parameters, triggers
2. **⚙️ SQL Builder** — generate SELECT; IRIS arrow-syntax (`->`) examples for FK and `_DR` display fields
3. **🇹🇭 Thai Descriptions** — `st.data_editor` saving to `translations.json`
4. **📐 FK Diagram** — renderer toggle (`fk_renderer_{tbl_name}`): **Mermaid** (`build_er_mermaid`) or **Interactive** (`build_cytoscape_html`); entity limit slider up to 250 (default 25); three independent filters (module, FK field, table — see below); cross-module refs checkbox (Mermaid only); Split view (Mermaid only) shows Outgoing/Incoming side-by-side
5. **🔗 Lineage** — column-level upstream/downstream FK paths with MS SQL types

Tab selection is persisted across `st.rerun()` calls via a `localStorage` JS snippet injected after `st.tabs(...)`, keyed to the table name.

#### FK Diagram filter logic

Three filters are available. All session-state keys are scoped per table (`_{tbl_name}` suffix):

| Filter | Session key | Applied at |
|---|---|---|
| **Filter by module** (`fk_module_filter_{tbl_name}`) | multiselect | Render time — passed into `_apply_module_filter()` at every `build_er_mermaid` / `build_cytoscape_html` call |
| **Filter by FK field** (`fk_field_filter_{tbl_name}`) | multiselect | Pre-render — `_apply_fk_field_filter()` runs against the original `out_tbls`/`in_tbls` |
| **Filter by table** (`fk_table_filter_{tbl_name}`) | multiselect | Pre-render — `_apply_table_filter()` runs against the original `out_tbls`/`in_tbls` |

**FK field filter** and **table filter** run independently against the unfiltered neighbor sets; their results are **unioned** before the module filter is applied:

```python
_ff_out, _ff_in = _apply_fk_field_filter(out_tbls, in_tbls, fk_field_filter)
_tf_out, _tf_in = _apply_table_filter(out_tbls, in_tbls, fk_table_filter)

if fk_field_filter and fk_table_filter:
    out_tbls = sorted(set(_ff_out) | set(_tf_out))
    in_tbls  = sorted(set(_ff_in)  | set(_tf_in))
elif fk_field_filter:
    out_tbls, in_tbls = _ff_out, _ff_in
elif fk_table_filter:
    out_tbls, in_tbls = _tf_out, _tf_in
```

The caption below the filter row reflects the post-filter counts and labels active filters.

### Analytics page tabs

1. **🗺️ Module Dependency Map** — `build_module_mermaid`; Focus mode or All-modules with Top-N slider
2. **🏆 Hub Tables** — ranked by total FK count (incoming + outgoing)
3. **🏝️ Orphan Tables** — tables with zero FK relationships
4. **📐 ER Diagram** — renderer toggle (`er_renderer`): **Mermaid** (`build_er_mermaid`) or **Interactive** (`build_cytoscape_html`); scope by module / 1-hop / custom selection (max 20 tables)

### Persistence helpers

All functions below are imported from `storage.py` (not defined inline in `app.py`):

| Function | Purpose |
|---|---|
| `load_translations()` / `save_translations(data)` | Thai field descriptions `{class_name: {field: text}}` |
| `load_tags()` / `save_tags(data)` | Tag lists per table `{table: [tag, ...]}` |
| `load_metadata()` / `save_metadata(data)` | Governance metadata per table (owner, steward, cert, etc.) |
| `load_changelog()` / `append_changelog(action, table, details)` | Audit log; capped at 1,000 entries |
| `clear_changelog()` | Delete all changelog entries (TRUNCATE for postgres, write `[]` for file) |
| `load_usage_log()` / `log_event(event, details)` | Usage events; capped at 10,000 entries |
| `load_data()` | Load all five xlsx/postgres sheets; returns `(tables, fields, fk, classes, members)` |
| `BACKEND` | String constant `"file"` or `"postgres"` — detected once at import |

**Error handling contract:**
- All `load_*` functions return an empty default on any read error — a corrupted file or DB failure never crashes the app.
- All `save_*` functions call `st.warning(...)` on error — surfaced to the user but never crashes the render cycle.
- `log_event` and `append_changelog` use a fully silent `except Exception: pass` — logging must never take the app down.

### Tags and metadata

- **Tags** (`PREDEFINED_TAGS`): PII, financial, deprecated, master-data, staging, lookup, audit, critical — selectable from dropdown. Users can also type any custom tag (normalised to lowercase + hyphens). All tags stored in `tags.json`, filterable in Browse.
- **Certification** (`CERT_OPTIONS`): Certified, Draft, Deprecated, Experimental — colour-coded badge on table header, filterable in Browse and Advanced Search.
- **Metadata fields**: owner, steward, contact, update_frequency, last_refresh — displayed inline in table header.
- All tag and metadata changes are recorded in `changelog.json` via `append_changelog()`.

### Arrow syntax (SQL Builder)

IRIS creates two SQL columns per object-reference property: `PropName` (ID) and `PropName_DR` (display value). `fk_map` only contains the base field. The SQL Builder detects `_DR` fields with:

```python
elif f.endswith("_DR") and f[:-3] in fk_map:
    base = f[:-3]
    ref_in_chosen.append((f, fk_map[base], base))
```

Use the base field name (not `_DR`) for the arrow traversal syntax.

### Translations

Thai descriptions are stored in `translations.json` as `{class_name: {sql_field_name: thai_text}}`. Loaded into `st.session_state.translations` on startup; written back by `save_translations()`.

## FK data structure

Key columns in the `fk_relationships` sheet:

| Column | Notes |
|---|---|
| `resolve_status` | `"resolved"` or `"unresolved"` — always filter for resolved |
| `source_sql_table_name` / `source_sql_field_name` | The FK field on the source side |
| `target_sql_table_name` | The referenced table |
| `relationship_cardinality` | `"children"` for parent-child; empty for plain object refs |
| `evidence_source` | `"des_ref"` (object reference property) or `"relationship"` |

The join key between `fk` and `fields`/`tables` is `class_name` (e.g. `User.APCVendCat.cls`) or `sql_table_name`.

## Create_JSON.ipynb

Reads the five `iris_data_dict-*.csv` files (exported from the xlsx) and writes `iris_data_dictionary_full.json`. Run via:

```bash
jupyter nbconvert --to notebook --execute Create_JSON.ipynb
```

The notebook's single cell also has an `if __name__ == "__main__"` guard so it can be run as a script. The output JSON is git-ignored.
