# Lineage Finder Stack

## Purpose

Lineage Finder lets a user choose a source table and target table, then searches foreign-key relationships to find direct or indirect table paths. It is table-level lineage enriched with column, key, module, and type details.

## Runtime Stack

```text
Streamlit UI
  app.py
    Lineage Finder page
    Input controls
    Metrics, tables, Mermaid/ASCII rendering

Domain logic
  lineage_finder.py
    FK graph builder
    BFS path search
    Path enrichment
    DataFrame and diagram output helpers

Data layer
  storage.py
    load_data()
    file backend or PostgreSQL backend

Source data
  iris_data_dict.xlsx
  optional PostgreSQL dict_* tables
```

## Data Inputs

The feature uses already-loaded dataframes from the app:

| DataFrame | Required columns | Usage |
|---|---|---|
| `fk` | `source_sql_table_name`, `target_sql_table_name` | Builds FK edges |
| `fk` | `source_sql_field_name`, `source_member_name`, `target_pk_fields` | Labels each path step |
| `fk` | `resolve_status`, `relationship_cardinality`, `evidence_source` | Filters and explains relationships |
| `tables` | `sql_table_name`, `class_name`, `module_name` | Adds class/module context |
| `fields` | `class_name`, `sql_field_name`, `member_type`, `description` | Adds field type and descriptions |

## Call Flow

```text
User clicks Find Relationship
  -> app.py calls build_fk_graph(fk, direction, same_module_only, tables)
  -> app.py calls find_table_paths(graph, source_table, target_table, max_hops, max_paths)
  -> app.py calls enrich_lineage_paths(paths, fields, tables)
  -> app.py calls lineage_paths_to_dataframe(paths)
  -> app.py renders metrics, details, expanders, and diagram
```

## Search Logic

`build_fk_graph()` converts resolved FK rows into an adjacency list. Direction controls which edges are included:

- `Downstream`: source table to referenced target table.
- `Upstream`: referenced target table back to tables that point at it.
- `Both`: includes both directions.

`find_table_paths()` uses breadth-first search, so shorter paths are returned first. It prevents cycles with a visited-table set and limits output with `max_hops` and `max_paths`.

## Output Stack

| Output | Function | Rendered in |
|---|---|---|
| Summary metrics | `app.py` | Streamlit metrics |
| Flat path table | `lineage_paths_to_dataframe()` | `st.dataframe()` |
| Per-path details | `lineage_paths_to_dataframe([path])` | Streamlit expanders |
| Mermaid diagram | `build_lineage_mermaid()` | `components.html()` |
| ASCII diagram | `build_lineage_ascii()` | `st.code()` |

## Ownership

Keep graph traversal and path formatting in `lineage_finder.py`. Keep user controls, Streamlit layout, and renderer selection in `app.py`. If future work adds tests, target `lineage_finder.py` first because it is pure Python logic and does not require Streamlit to run.
