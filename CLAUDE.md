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

Dependencies: `streamlit pandas pyvis openpyxl plotly`

Server config lives in `.streamlit/config.toml` (git-ignored; copy from `.streamlit/config.toml.example`). Set `address = "0.0.0.0"` — not a specific IP — so both localhost and network access work.

Admin passcode lives in `.streamlit/secrets.toml` (git-ignored; copy from `.streamlit/secrets.toml.example`). Falls back to `"admin1234"` if not set.

## app.py architecture

The entire app is a single-file Streamlit app (~2700 lines). There is no routing framework — navigation is driven by `st.session_state.page`.

### Data loading

All five sheets from `iris_data_dict.xlsx` are loaded once via `@st.cache_data`:

```python
tables, fields, fk, classes, members = load_data()
```

Three derived globals are computed at startup (also cached):
- `COMPLETENESS` — `{class_name: pct}` EN description fill rate per table
- `HUB_DF`, `ORPHAN_DF`, `DEP_COUNTS` — analytics aggregates
- `MODULE_SUMMARY` — module list with table counts

The `fk` dataframe has a `resolve_status` column; always filter `fk[fk["resolve_status"] == "resolved"]` before using FK data. Unresolved rows (missing `source_sql_field_name`) are noise.

### Navigation

```python
def nav(page: str, table: str = None): ...
```

`st.session_state.page` drives which page block renders. Valid values: `"home"`, `"search"`, `"browse"`, `"detail"`, `"graph"`, `"analytics"`, `"changelog"`, `"usage"`. The `browse` and `detail` pages share one `elif` branch.

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
| `collect_graph_data(center, depth, fk_df, tables_df)` | BFS over resolved FKs → `(nodes_dict, edges_list)`. Cached. Shared by pyvis and Mermaid graph renderers. |
| `build_pyvis_html(center, nodes_dict, edges)` | Renders pyvis network to HTML string via a temp file. |
| `build_mermaid_html(center, nodes_dict, edges, direction, group_modules)` | Mermaid flowchart for the Graph page. Returns `(html, code)`. |
| `_module_mermaid_html(mermaid_code)` | Wraps raw Mermaid code in the full HTML shell for the Module Dependency Map. Returns `html`. |
| `build_module_mermaid(dep_counts, direction, collapse_bidir, center_module)` | Builds Mermaid code + calls `_module_mermaid_html`. Returns `(html, code)`. |
| `build_er_mermaid(table_names, include_fields, max_fields, cross_module, direction)` | Mermaid `erDiagram` for the FK Diagram tab and Analytics → ER Diagram. Returns `(html, code)`. |
| `render_admin_gate(target_page)` | Renders passcode form for locked pages. Sets `admin_authenticated` on success and calls `st.rerun()`. |
| `simplify_iris_type(type_str)` | Maps IRIS verbose types (`%String(...)`, `%Date`, `CTCompany`) to short ER labels (`string`, `date`, `ref`). |
| `schema_to_csv(...)` / `schema_to_excel(...)` | Export helpers for the Schema tab download buttons. |
| `compute_analytics(fk_df, tables_df)` | Returns `(hub_df, orphan_df, dep_counts)`. Cached. |

### Mermaid rendering

All three HTML builders (`build_mermaid_html`, `_module_mermaid_html`, `build_er_mermaid`) use the same pattern:

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
4. **📐 FK Diagram** — `build_er_mermaid` for 1-hop FK connections; adjustable entity limit slider (default 25); Split view shows Outgoing/Incoming side-by-side
5. **🔗 Lineage** — column-level upstream/downstream FK paths with MS SQL types

Tab selection is persisted across `st.rerun()` calls via a `localStorage` JS snippet injected after `st.tabs(...)`, keyed to the table name.

### Analytics page tabs

1. **🗺️ Module Dependency Map** — `build_module_mermaid`; Focus mode or All-modules with Top-N slider
2. **🏆 Hub Tables** — ranked by total FK count (incoming + outgoing)
3. **🏝️ Orphan Tables** — tables with zero FK relationships
4. **📐 ER Diagram** — `build_er_mermaid`; scope by module / 1-hop / custom selection (max 20 tables)

### Persistence helpers

| Function | File | Purpose |
|---|---|---|
| `load_translations()` / `save_translations(data)` | `translations.json` | Thai field descriptions `{class_name: {field: text}}` |
| `load_tags()` / `save_tags(data)` | `tags.json` | Tag lists per table `{table: [tag, ...]}` |
| `load_metadata()` / `save_metadata(data)` | `metadata.json` | Governance metadata per table (owner, steward, cert, etc.) |
| `load_changelog()` / `append_changelog(action, table, details)` | `changelog.json` | Audit log; capped at 1,000 entries |
| `load_usage_log()` / `log_event(event, details)` | `usage_log.json` | Usage events; capped at 10,000 entries |

### Tags and metadata

- **Tags** (`PREDEFINED_TAGS`): PII, financial, deprecated, master-data, staging, lookup, audit, critical — stored in `tags.json`, filterable in Browse.
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
