# IRIS Data Dictionary

A local data catalog web application — similar to DataHub — for browsing and documenting **InterSystems IRIS** persistent class metadata.

Built with **Streamlit** and reads directly from `iris_data_dict.xlsx`.

---

## Features

| Feature | Description |
|---|---|
| **Browse** | Filter tables by module and name; EN description completeness progress bar per table |
| **Search** | Full-text search across table names, descriptions, and field names/types |
| **Schema view** | Columns with types, descriptions, FK references, parameters & triggers |
| **FK Diagram** | Per-table ER diagram tab — shows outgoing and incoming FK links with field names as edge labels |
| **Relationship graph** | Interactive network (pyvis) or Mermaid flowchart with module subgraphs; 1–2 hop depth |
| **SQL Builder** | Generate `SELECT` statements; IRIS arrow-syntax (`->`) examples for reference fields |
| **Thai descriptions** | Inline editor to add Thai field descriptions, saved locally to `translations.json` |
| **Recently Viewed** | Last 10 visited tables shown on the Home page for quick re-access |
| **URL deep linking** | `?table=TABLE_NAME` in the URL opens any table directly — shareable across the network |
| **Export schema** | Download any table schema as CSV or multi-sheet Excel (columns, FK, incoming refs, parameters, triggers) |
| **Analytics** | Module Dependency Map, Hub Tables, Orphan Tables, ER Diagram (multi-table scope) |

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
http://10.78.9.107:8501/?table=APC_Vendor
```

The URL bar updates automatically as you browse — copy it from the browser to share with colleagues.

---

## FK Diagram (per-table)

Each table detail page has a **📐 FK Diagram** tab that renders an entity-relationship diagram showing:

- **Outgoing FK** — tables this table references, with the FK field name as the edge label
- **Incoming FK** — tables that reference this table
- Field boxes with correct IRIS types (`string`, `date`, `float`, `ref`, `list`, …) and `FK` markers

Controls: Outgoing+Incoming / Outgoing only / Incoming only · show/hide fields · LR or TB layout.

For hub tables with many connections the diagram is capped at 25 entities; switch to "Outgoing only" or "Incoming only" to see each side in full.

---

## Analytics page

| Tab | Description |
|---|---|
| **Module Dependency Map** | Mermaid flowchart of module-to-module FK references; Focus mode, Top-N slider, collapse bidirectional |
| **Hub Tables** | Tables ranked by incoming + outgoing FK count |
| **Orphan Tables** | Tables with no FK relationships at all |
| **ER Diagram** | Multi-table ER diagram — scope by module, 1-hop from a table, or custom selection (up to 20 tables) |

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

## Thai translations

Translations entered via the app are saved to `translations.json` (git-ignored — local to each deployment).  
Progress is shown per-table in the **Thai Descriptions** tab and as a total count in the sidebar.

---

## Project structure

```
app.py                        # Streamlit application
requirements.txt              # Python dependencies
Create_JSON.ipynb             # Notebook: xlsx → JSON export
iris_data_dict.xlsx           # Source data (5 sheets)
.streamlit/
  config.toml.example         # Server config template
  config.toml                 # Local config (git-ignored)
translations.json             # Thai descriptions (git-ignored, auto-created on first save)
```
