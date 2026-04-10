# IRIS Data Dictionary

A local data catalog web application — similar to DataHub — for browsing and documenting **InterSystems IRIS** persistent class metadata.

Built with **Streamlit** and reads directly from `iris_data_dict.xlsx`.

---

## Features

| Feature | Description |
|---|---|
| **Browse** | Filter tables by module and name; completeness progress bar per table |
| **Search** | Full-text search across table names, descriptions, and field names |
| **Schema view** | Columns with types, descriptions, FK references, parameters & triggers |
| **Relationship graph** | Interactive network (pyvis) or Mermaid flowchart with module subgraphs |
| **SQL Builder** | Generate `SELECT` statements with IRIS arrow-syntax examples |
| **Thai descriptions** | Inline editor to add Thai field descriptions, saved to `translations.json` |

## Requirements

```bash
pip install streamlit pandas pyvis openpyxl
```

## Running

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.  
To access from other machines on the network, see **Configuration** below.

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

## Configuration

Copy the example config and edit as needed:

```bash
cp .streamlit/config.toml.example .streamlit/config.toml
```

| Setting | Default | Description |
|---|---|---|
| `address` | `0.0.0.0` | Bind to all interfaces (use specific IP to restrict) |
| `port` | `8501` | Port to listen on |
| `headless` | `true` | Suppress auto-open browser prompt |

To allow access through Windows Firewall (run as Administrator):

```powershell
New-NetFirewallRule -DisplayName "Streamlit 8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
```

## Thai translations

Translations entered via the app are saved to `translations.json` (git-ignored — local to each deployment).

## Project structure

```
app.py                        # Streamlit application
Create_JSON.ipynb             # Notebook: xlsx → JSON export
iris_data_dict.xlsx           # Source data (5 sheets)
.streamlit/
  config.toml.example         # Server config template
  config.toml                 # Local config (git-ignored)
translations.json             # Thai descriptions (git-ignored, auto-created)
```
