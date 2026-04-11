# IRIS Data Dictionary

A local data catalog web application — similar to DataHub — for browsing and documenting **InterSystems IRIS** persistent class metadata.

Built with **Streamlit** and reads directly from `iris_data_dict.xlsx`.

---

## Features

| Feature | Description |
|---|---|
| **Browse** | Filter tables by module, name, tag, and certification status; EN description completeness progress bar per table |
| **Search** | Full-text search across table names, descriptions, field names/types, and Thai descriptions; **Advanced Filters** panel for power users |
| **Advanced Search** | Filter by certification status, tags, FK presence, completeness, field datatype, missing descriptions, and FK-only fields |
| **Schema view** | Columns with IRIS types, MS SQL equivalent types, descriptions, FK references, parameters & triggers |
| **FK Diagram** | Per-table ER diagram tab — shows outgoing and incoming FK links; choose **Mermaid (static)** or **Interactive (Cytoscape)** renderer |
| **Lineage** | Column-level lineage tab — exact field-to-field FK paths upstream and downstream |
| **Relationship graph** | Interactive network (pyvis) or Mermaid flowchart with module subgraphs; 1–2 hop depth |
| **SQL Builder** | Generate `SELECT` statements; IRIS arrow-syntax (`->`) examples for reference fields |
| **Thai descriptions** | Inline editor to add Thai field descriptions, saved locally to `translations.json` |
| **Table Tags** | Label tables with PII, financial, deprecated, master-data, staging, lookup, audit, critical |
| **Table Metadata** | Set data owner, steward, contact, certification status (Certified/Draft/Deprecated/Experimental), update frequency, and last refresh date per table |
| **Certification Status** | Four-level trust badge (Certified / Draft / Deprecated / Experimental) — shown as colour-coded badge on table header and filterable in Browse and Search |
| **Changelog** | Audit log of all tag changes, translation saves, and metadata saves, with filtering and table navigation |
| **Type mapping** | IRIS types (`%String`, `%Date`, …) automatically mapped to MS SQL Server equivalents |
| **Recently Viewed** | Last 10 visited tables shown on the Home page for quick re-access |
| **URL deep linking** | `?table=TABLE_NAME` in the URL opens any table directly — shareable across the network |
| **Export schema** | Download any table schema as CSV or multi-sheet Excel (columns with MSSQL types, FK, incoming refs, parameters, triggers) |
| **Analytics** | Module Dependency Map, Hub Tables, Orphan Tables, ER Diagram (multi-table scope; Mermaid or Interactive Cytoscape renderer) |
| **Usage Stats** | Track sessions, page views, table views, and searches; charts for sessions/day, feature usage, top tables, and top searches |
| **Dark / Light mode** | Toggle between dark and light themes from the sidebar |
| **Diagram export** | Download any Mermaid diagram (FK Diagram, ER Diagram, Graph, Module Dependency) as **SVG** or **PNG** |
| **Admin lock** | Changelog and Usage Stats pages are passcode-protected; admin mode unlocks them for the session |

---

## Navigation Guide

Quick reference for where to find every feature in the app:

| Feature | Where to find it |
|---|---|
| 🏠 Home | Sidebar → **Home** (Recently Viewed tables shown here) |
| 🔍 Search | Sidebar → **Search** (searches table names, EN descriptions, field names/types, and Thai descriptions) |
| 🔍 Advanced Search | Sidebar → **Search** → expand **🔍 Advanced Filters** panel |
| 📁 Browse | Sidebar → **Browse** (filter by module, name, tag, and certification; click any row to open detail) |
| 🕸️ Graph | Sidebar → **Graph** (interactive network or Mermaid flowchart, 1–2 hops) |
| 📊 Analytics | Sidebar → **Analytics** (Module Dependency Map, Hub Tables, Orphan Tables, ER Diagram) |
| 📋 Changelog | Sidebar → **Changelog** 🔒 *(requires admin passcode)* |
| 📈 Usage Stats | Sidebar → **Usage Stats** 🔒 *(requires admin passcode)* |
| 🏷️ Tags | Browse → click a table → detail header → **🏷️ Manage Tags** expander |
| 📊 Metadata | Browse → click a table → detail header → **📊 Manage Metadata** expander |
| 📋 Schema | Browse → click a table → **1st tab "📋 Schema"** (IRIS type, MS SQL type, FK references) |
| ⚙️ SQL Builder | Browse → click a table → **2nd tab "⚙️ SQL Builder"** |
| 🇹🇭 Thai Desc | Browse → click a table → **3rd tab "🇹🇭 Thai Descriptions"** |
| 📐 FK Diagram | Browse → click a table → **4th tab "📐 FK Diagram"** (slider for entity limit; Split view for side-by-side) |
| 🔗 Lineage | Browse → click a table → **5th tab "🔗 Lineage"** (column-level upstream/downstream FK paths) |
| ☀️ / 🌙 Theme | Bottom of sidebar → **Light Mode / Dark Mode** toggle |

---

## Requirements

```bash
pip install -r requirements.txt
```

Or individually:

```bash
pip install streamlit pandas pyvis openpyxl plotly
```

---

## Running

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Network access (other machines)

By default the app binds to all interfaces (`0.0.0.0`). To reach it from other machines on the network you also need to open the port in Windows Firewall.

**Option A — Command Prompt (run as Administrator):**
```cmd
netsh advfirewall firewall add rule name="Streamlit 8501" dir=in action=allow protocol=TCP localport=8501
```

**Option B — PowerShell (run as Administrator):**
```powershell
New-NetFirewallRule -DisplayName "Streamlit 8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
```

Verify the rule was added:
```cmd
netsh advfirewall firewall show rule name="Streamlit 8501"
```

Once the firewall rule is in place, the app is reachable at `http://<YOUR_IP>:8501`.  
Find your IP with `ipconfig` — look for **IPv4 Address** under your active network adapter.

> **Note:** Always bind to `0.0.0.0` (not a specific IP) so both `localhost` and the network IP work simultaneously.

---

## URL deep linking

Append `?table=TABLE_NAME` to the server URL to open a specific table directly:

```
http://xx.xx.xx.xx:8501/?table=APC_Vendor
```

The URL bar updates automatically as you browse — copy it from the browser to share with colleagues.

---

## Table detail tabs

Each table detail page has five tabs:

| Tab | Description |
|---|---|
| **📋 Schema** | Columns with IRIS type, MS SQL type, description, and FK reference (TargetTable.PK). Outgoing and incoming FK expandable sections. |
| **⚙️ SQL Builder** | Build `SELECT` statements; IRIS arrow-syntax examples for reference fields; ObjectScript access pattern |
| **🇹🇭 Thai Descriptions** | Inline editor for Thai field descriptions with per-table progress bar |
| **📐 FK Diagram** | ER diagram of FK connections; **Mermaid (static)** or **Interactive (Cytoscape)** renderer; adjustable entity limit (default 25); Outgoing / Incoming / Both / Split view; SVG + PNG export |
| **🔗 Lineage** | Column-level lineage: upstream (this table's FK fields → target table + PK) and downstream (which fields in other tables reference this table), both with MS SQL types |

### Table Tags

Each table can be labelled with one or more tags via the **🏷️ Manage Tags** expander in the detail header:

| Tag | Meaning |
|---|---|
| `PII` | Contains personally identifiable information |
| `financial` | Financial / accounting data |
| `deprecated` | No longer actively used |
| `master-data` | Reference / lookup data shared across modules |
| `staging` | Temporary or ETL staging table |
| `lookup` | Small code/value lookup table |
| `audit` | Audit trail or change-log table |
| `critical` | Business-critical — changes require approval |

Tags are saved to `tags.json` and filter in the Browse page. All tag changes are recorded in the Changelog.

### Table Metadata

Each table can have governance metadata set via the **📊 Manage Metadata** expander in the detail header:

| Field | Purpose |
|---|---|
| **Owner** | Team or person responsible for the data (e.g. "Finance Team") |
| **Steward** | Named data steward accountable for quality and definitions |
| **Contact** | Email or contact handle for questions about this table |
| **Certification Status** | Trust level — see below |
| **Update Frequency** | How often the data is refreshed (Real-time / Daily / Weekly / Monthly / Quarterly / Ad-hoc) |
| **Last Refresh Date** | Date the data was last refreshed (e.g. `2026-04-01`) |

Metadata is saved to `metadata.json`. Owner, steward, contact, frequency, and last refresh are displayed directly in the table header. All saves are recorded in the Changelog.

### Certification Status

A colour-coded trust badge shown on each table:

| Status | Colour | Meaning |
|---|---|---|
| `Certified` | Green | Data has been reviewed and validated — safe to use in production |
| `Draft` | Orange | Definition or quality not yet finalised — use with caution |
| `Deprecated` | Red | No longer maintained — do not use for new reports |
| `Experimental` | Purple | Under active development — subject to breaking changes |

The certification badge appears in the table header and is filterable in both the **Browse** page and the **Advanced Search** panel.

---

## Advanced Search

The **🔍 Advanced Filters** panel (expand on the Search page) lets you filter without typing a keyword:

| Filter | Applies to | Description |
|---|---|---|
| Certification status | Tables | Show only tables with the selected certification level(s) |
| Tags | Tables | Show only tables that have all selected tags |
| Has FK relationships | Tables | Show only tables with at least one resolved FK |
| No FK (orphan) | Tables | Show only tables with zero FK relationships |
| Low EN description (<50%) | Tables | Show tables where fewer than half of fields have English descriptions |
| Field datatype | Fields | Filter by simplified type (string, int, date, ref, …) |
| Missing EN description | Fields | Show only fields with no English description |
| FK fields only | Fields | Show only fields that are foreign keys |

Text search and advanced filters can be combined freely.

---

## Type mapping (IRIS → MS SQL)

The app converts IRIS persistent class types to the closest MS SQL Server equivalents:

| IRIS Type | MS SQL Type |
|---|---|
| `%String(MAXLEN=N)` | `NVARCHAR(N)` |
| `%String` | `NVARCHAR(255)` |
| `%Integer` | `INT` |
| `%Date` | `DATE` |
| `%Time` | `TIME` |
| `%TimeStamp` / `%DateTime` | `DATETIME2` |
| `%Boolean` | `BIT` |
| `%Float` / `%Double` | `FLOAT` |
| `%Decimal` / `%Numeric` | `DECIMAL(18,4)` |
| `%Currency` | `MONEY` |
| `%Binary` / `%Stream` | `VARBINARY(MAX)` |
| Object reference (FK) | `BIGINT` |
| List | `NVARCHAR(MAX)` |

MS SQL types appear in the Schema tab, the Lineage tab, and in CSV/Excel exports.

---

## FK Diagram (per-table)

Each table detail page has a **📐 FK Diagram** tab that renders an entity-relationship diagram showing:

- **Outgoing FK** — tables this table references, with the FK field name as the edge label
- **Incoming FK** — tables that reference this table
- Field boxes with correct IRIS types (`string`, `date`, `float`, `ref`, `list`, …) and `FK` markers

Controls:

| Control | Options | Notes |
|---|---|---|
| **Renderer** | Mermaid (static) · Interactive (Cytoscape) | See below |
| **Show** | Outgoing + Incoming · Outgoing only · Incoming only · **Split view** | Split view available in Mermaid mode only |
| **Show fields** | on / off | Toggle field list inside each entity box |
| **Max fields/table** | 3–30 (default 6) | Caps fields shown per entity when "Show fields" is on |
| **Layout** | LR · TB | Left-to-right or top-to-bottom (Mermaid only) |
| **Max entities per diagram** | 5–100 (default 25) | Raise to see more tables; lower for a cleaner view |

### Mermaid (static) renderer

Renders a clean, static SVG ER diagram. Supports **Split view** (Outgoing / Incoming side-by-side) and exports as **⬇ SVG** or **⬇ PNG**.

### Interactive (Cytoscape) renderer

Renders a fully interactive ER diagram via **Cytoscape.js** (loaded from CDN — no extra install needed):

| Feature | Detail |
|---|---|
| **Drag nodes** | Rearrange the layout freely |
| **Zoom / Pan** | Mouse wheel zoom, click-drag to pan |
| **Click node** | Side panel shows full field list (name, type, FK marker, description) |
| **Field cards** | When "Show fields" is on, each node renders as a mini table card — header coloured by module, rows showing type + field name + FK badge |
| **Highlight neighbourhood** | Clicking a node dims unrelated nodes and highlights its edges |
| **Layout switcher** | Force (CoSE), Breadth-first, Grid, Circle, Concentric |
| **Module legend** | Colour key for up to 14 modules shown in the side panel |
| **Download PNG** | 2× resolution PNG of the current diagram |

> **Split view** is only available in Mermaid mode. Use the entity limit slider to control how many tables appear in Interactive mode.

When the diagram exceeds the entity limit a warning guides you to raise the slider.

---

## Analytics page

| Tab | Description |
|---|---|
| **Module Dependency Map** | Mermaid flowchart of module-to-module FK references; Focus mode, Top-N slider, collapse bidirectional |
| **Hub Tables** | Tables ranked by incoming + outgoing FK count |
| **Orphan Tables** | Tables with no FK relationships at all |
| **ER Diagram** | Multi-table ER diagram — scope by module, 1-hop from a table, or custom selection (up to 20 tables); choose **Mermaid (static)** or **Interactive (Cytoscape)** renderer |

The **ER Diagram** tab has the same Renderer toggle as the FK Diagram tab — see [Interactive (Cytoscape) renderer](#interactive-cytoscape-renderer) above for full feature list.

> **Note — Mermaid rendering:** All Mermaid diagrams (ER Diagram, FK Diagram, Module Dependency Map, Graph) use `mermaid.render()` with `offsetWidth` polling to defer rendering until the tab is visible. This avoids a Streamlit hidden-tab issue where Mermaid fails to compute SVG geometry inside a `display:none` container. Diagrams render automatically as soon as their tab is opened.

> **Diagram export:** All Mermaid diagrams show **⬇ SVG** and **⬇ PNG** download buttons once rendered. SVG is lossless vector; PNG is 2× resolution raster. The Interactive Cytoscape renderer exports **⬇ PNG** (2× resolution) from the toolbar inside the diagram.

---

## Changelog

The **📋 Changelog** page records every change made through the app:

- Thai description saves (table name + count of fields saved)
- Tag additions and removals
- Metadata saves (certification, owner, update frequency)

Entries are stored in `changelog.json` (up to 1,000 most recent). The page supports filtering by action type, table name, and free-text search. Clicking a row navigates to the relevant table.

---

## Usage Stats

The **📈 Usage Stats** page records usage events automatically and displays them as charts.

| Event | When recorded |
|---|---|
| `session_start` | Each new browser session |
| `page_view` | Every time the user navigates to a page |
| `table_view` | Every time a table detail page is opened |
| `search` | Every time a keyword is entered in the Search box |

Charts shown:

| Chart | Description |
|---|---|
| **Sessions per Day** | Bar chart of daily session counts (last 30 days) |
| **Feature Usage** | Donut chart of page_view breakdown by feature |
| **Top Tables Viewed** | Top 15 most-opened tables |
| **Top Searches** | Top 15 most-entered search queries |
| **Recent Activity** | Last 50 events with timestamp, event type, and details |

Events are stored in `usage_log.json` (capped at 10,000 most recent entries).

---

## Error handling

The app is designed to degrade gracefully rather than crash:

| Failure point | Behaviour |
|---|---|
| `iris_data_dict.xlsx` missing or unreadable | Clear `st.error` message + `st.stop()` — no raw traceback |
| Corrupted JSON file (`translations.json`, `tags.json`, `metadata.json`, `changelog.json`, `usage_log.json`) | Returns an empty default (`{}` / `[]`) — existing data in memory is unaffected |
| Disk full / permission error on save | `st.warning(...)` shown — app continues running without crashing |
| Usage logging / changelog write failure | Silent pass — logging must never crash the app |
| Startup analytics / completeness computation fails | Returns empty DataFrames — app loads with reduced analytics |
| Network graph (`build_pyvis_html`) fails | Error message rendered inside the iframe with a **Refresh page** button |
| Mermaid diagram (`build_mermaid_html`, `build_er_mermaid`) fails | Error HTML returned; Mermaid JS itself also shows render errors inline |
| Cytoscape diagram call site fails | `_cytoscape_error_html()` rendered inside the iframe with a **Refresh page** button |

---

## Data source

The app reads five sheets from `iris_data_dict.xlsx`:

| Sheet | Contents |
|---|---|
| `sql_tables` | Table → class mapping, module, description |
| `sql_fields` | Field definitions per class |
| `fk_relationships` | Object-reference / FK relationships |
| `classes` | Full class declarations with IRIS metadata |
| `members` | Properties, parameters, triggers per class |

To regenerate `iris_data_dictionary_full.json` (used by external tools), run `Create_JSON.ipynb`.

---

## Admin access control

The **📋 Changelog** and **📈 Usage Stats** pages are passcode-protected. A 🔒 icon appears next to them in the sidebar until unlocked.

### Setting your passcode

Copy the example secrets file and set your own passcode:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
admin_passcode = "your_passcode_here"
```

`secrets.toml` is git-ignored — never commit it. If no `secrets.toml` exists the app falls back to the default passcode `admin1234`.

### Admin session behaviour

| Action | Result |
|---|---|
| Click 🔒 Changelog or Usage Stats | Passcode form shown instead of page content |
| Enter correct passcode | Admin mode active for the browser session; both pages unlocked |
| Click **🔒 Lock Admin** in sidebar | Admin mode revoked; navigates to Home if currently on a locked page |

---

## Configuration

Copy the example config and edit as needed:

```bash
cp .streamlit/config.toml.example .streamlit/config.toml
```

| Setting | Default | Description |
|---|---|---|
| `address` | `0.0.0.0` | Bind to all interfaces — do **not** set to a specific IP |
| `port` | `8501` | Port to listen on |
| `headless` | `true` | Suppress auto-open browser prompt |

---

## Local data files

These files are git-ignored and created automatically by the app:

| File | Created by | Contents |
|---|---|---|
| `translations.json` | Thai Descriptions tab | Thai field descriptions per table |
| `tags.json` | Manage Tags expander | Tag lists per table |
| `metadata.json` | Manage Metadata expander | Owner, steward, contact, certification, refresh info per table |
| `changelog.json` | Any save action | Audit log entries |
| `usage_log.json` | Auto (every navigation / search) | Session, page view, table view, search events |

---

## Project structure

```
app.py                        # Streamlit application (~3000 lines)
requirements.txt              # Python dependencies
Create_JSON.ipynb             # Notebook: xlsx → JSON export
iris_data_dict.xlsx           # Source data (5 sheets)
.streamlit/
  config.toml.example         # Server config template
  config.toml                 # Local config (git-ignored)
  secrets.toml.example        # Admin passcode template
  secrets.toml                # Admin passcode (git-ignored)
translations.json             # Thai descriptions (git-ignored, auto-created)
tags.json                     # Table tags (git-ignored, auto-created)
metadata.json                 # Table governance metadata (git-ignored, auto-created)
changelog.json                # Audit log (git-ignored, auto-created)
usage_log.json                # Usage events (git-ignored, auto-created)
```
