"""Table-to-table relationship and lineage helpers.

This module keeps FK graph traversal outside the Streamlit page code so the
lineage search can be tested without starting the app.
"""

from __future__ import annotations

from collections import defaultdict, deque
from html import escape
import re
from typing import Any

import pandas as pd


INVALID_VALUES = {"", "nan", "none", "null", "nat"}


def _clean(value: Any) -> str:
    text = str(value).strip()
    return "" if text.lower() in INVALID_VALUES else text


def _mermaid_id(name: str) -> str:
    ident = re.sub(r"[^0-9A-Za-z_]", "_", str(name))
    if not ident or ident[0].isdigit():
        ident = f"T_{ident}"
    return ident


def _edge_next_table(edge: dict) -> str:
    return edge.get("display_target_table") or edge.get("target_table", "")


def build_fk_graph(
    fk_df: pd.DataFrame,
    direction: str = "Downstream",
    same_module_only: bool = False,
    tables_df: pd.DataFrame | None = None,
) -> dict[str, list[dict]]:
    """Build an adjacency list from resolved FK rows.

    Downstream follows natural FK direction: source table -> referenced table.
    Upstream reverses each edge: referenced table -> source table.
    Both includes both edge directions.
    """
    graph: dict[str, list[dict]] = defaultdict(list)
    if fk_df is None or fk_df.empty:
        return graph

    required = {"source_sql_table_name", "target_sql_table_name"}
    if not required.issubset(set(fk_df.columns)):
        return graph

    resolved = fk_df.copy()
    if "resolve_status" in resolved.columns:
        resolved = resolved[resolved["resolve_status"].astype(str).str.lower() == "resolved"]

    module_by_table = {}
    if tables_df is not None and not tables_df.empty and {"sql_table_name", "module_name"}.issubset(tables_df.columns):
        module_by_table = tables_df.set_index("sql_table_name")["module_name"].astype(str).to_dict()

    include_downstream = direction in ("Downstream", "Both")
    include_upstream = direction in ("Upstream", "Both")

    for _, row in resolved.iterrows():
        source_table = _clean(row.get("source_sql_table_name", ""))
        target_table = _clean(row.get("target_sql_table_name", ""))
        if not source_table or not target_table:
            continue
        if source_table == target_table:
            continue
        if same_module_only and module_by_table:
            if module_by_table.get(source_table) != module_by_table.get(target_table):
                continue

        source_field = _clean(row.get("source_sql_field_name", "")) or _clean(row.get("source_member_name", ""))
        target_key = _clean(row.get("target_pk_fields", "")) or "ID"
        cardinality = _clean(row.get("relationship_cardinality", ""))
        evidence = _clean(row.get("evidence_source", ""))
        source_class = _clean(row.get("source_class_name", ""))

        base_edge = {
            "source_table": source_table,
            "source_class": source_class,
            "source_field": source_field,
            "target_table": target_table,
            "target_key": target_key,
            "cardinality": cardinality,
            "evidence_source": evidence,
        }

        if include_downstream:
            graph[source_table].append({
                **base_edge,
                "from_table": source_table,
                "to_table": target_table,
                "display_source_table": source_table,
                "display_target_table": target_table,
                "search_direction": "Downstream",
            })

        if include_upstream:
            graph[target_table].append({
                **base_edge,
                "from_table": target_table,
                "to_table": source_table,
                "display_source_table": source_table,
                "display_target_table": target_table,
                "search_direction": "Upstream",
            })

    for edges in graph.values():
        edges.sort(key=lambda e: (_edge_next_table(e).lower(), e.get("source_field", "").lower()))
    return graph


def find_table_paths(
    graph: dict[str, list[dict]],
    source_table: str,
    target_table: str,
    max_hops: int = 3,
    max_paths: int = 10,
) -> list[dict]:
    """Find shortest FK paths between two tables using BFS."""
    source_table = _clean(source_table)
    target_table = _clean(target_table)
    if not source_table or not target_table or source_table == target_table:
        return []

    max_hops = max(1, int(max_hops))
    max_paths = max(1, int(max_paths))
    results = []
    seen_result_chains = set()
    seen_queue_chains = {(source_table,)}
    queue = deque([(source_table, [], {source_table})])

    while queue and len(results) < max_paths:
        current_table, path, visited = queue.popleft()
        if len(path) >= max_hops:
            continue

        for edge in graph.get(current_table, []):
            next_table = _edge_next_table(edge)
            if not next_table or next_table in visited:
                continue

            next_edge = dict(edge)
            next_edge["step"] = len(path) + 1
            new_path = path + [next_edge]
            new_chain = tuple(_tables_for_path(source_table, new_path))

            if next_table == target_table:
                if new_chain in seen_result_chains:
                    continue
                seen_result_chains.add(new_chain)
                results.append({
                    "path_index": len(results) + 1,
                    "hop_count": len(new_path),
                    "tables": list(new_chain),
                    "edges": new_path,
                })
                if len(results) >= max_paths:
                    break
            else:
                if new_chain in seen_queue_chains:
                    continue
                seen_queue_chains.add(new_chain)
                queue.append((next_table, new_path, visited | {next_table}))

    return results


def _tables_for_path(source_table: str, edges: list[dict]) -> list[str]:
    tables = [source_table]
    for edge in edges:
        next_table = _edge_next_table(edge)
        if next_table:
            tables.append(next_table)
    return tables


def enrich_lineage_paths(paths: list[dict], fields_df: pd.DataFrame, tables_df: pd.DataFrame) -> list[dict]:
    """Add module, field type, target key type, and descriptions to path edges."""
    if not paths:
        return []

    class_by_table = {}
    module_by_table = {}
    if tables_df is not None and not tables_df.empty:
        if {"sql_table_name", "class_name"}.issubset(tables_df.columns):
            class_by_table = tables_df.set_index("sql_table_name")["class_name"].astype(str).to_dict()
        if {"sql_table_name", "module_name"}.issubset(tables_df.columns):
            module_by_table = tables_df.set_index("sql_table_name")["module_name"].astype(str).to_dict()

    field_lookup = {}
    if fields_df is not None and not fields_df.empty:
        for _, row in fields_df.iterrows():
            key = (_clean(row.get("class_name", "")), _clean(row.get("sql_field_name", "")))
            if key[0] and key[1]:
                field_lookup[key] = row

    enriched = []
    for path in paths:
        new_edges = []
        for edge in path.get("edges", []):
            source_table = edge.get("source_table", "")
            target_table = edge.get("target_table", "")
            source_class = edge.get("source_class") or class_by_table.get(source_table, "")
            target_class = class_by_table.get(target_table, "")
            source_field = edge.get("source_field", "")
            target_key = edge.get("target_key", "") or "ID"

            source_field_row = field_lookup.get((source_class, source_field))
            target_key_row = field_lookup.get((target_class, target_key))

            new_edge = dict(edge)
            new_edge.update({
                "source_module": module_by_table.get(source_table, ""),
                "target_module": module_by_table.get(target_table, ""),
                "source_field_type": _clean(source_field_row.get("member_type", "")) if source_field_row is not None else "",
                "source_description": _clean(source_field_row.get("description", "")) if source_field_row is not None else "",
                "target_key_type": _clean(target_key_row.get("member_type", "")) if target_key_row is not None else "",
                "target_key_description": _clean(target_key_row.get("description", "")) if target_key_row is not None else "",
            })
            new_edges.append(new_edge)

        enriched.append({**path, "edges": new_edges})
    return enriched


def lineage_paths_to_dataframe(paths: list[dict]) -> pd.DataFrame:
    """Flatten lineage paths into a display-friendly DataFrame."""
    rows = []
    for path in paths:
        for edge in path.get("edges", []):
            rows.append({
                "Path": path.get("path_index", ""),
                "Step": edge.get("step", ""),
                "Search Direction": edge.get("search_direction", ""),
                "Source Table": edge.get("source_table", ""),
                "Source Module": edge.get("source_module", ""),
                "Source Field / FK": edge.get("source_field", ""),
                "Source Type": edge.get("source_field_type", ""),
                "Target Table": edge.get("target_table", ""),
                "Target Module": edge.get("target_module", ""),
                "Target Key / PK": edge.get("target_key", ""),
                "Target Key Type": edge.get("target_key_type", ""),
                "Cardinality": edge.get("cardinality", ""),
                "Evidence": edge.get("evidence_source", ""),
            })
    return pd.DataFrame(rows)


def build_lineage_mermaid(paths: list[dict], source_table: str, target_table: str) -> str:
    """Build a Mermaid flowchart for found lineage paths."""
    lines = ["flowchart LR"]
    nodes = set()
    edge_lines = []

    for path in paths:
        for edge in path.get("edges", []):
            src = edge.get("display_source_table") or edge.get("source_table", "")
            tgt = edge.get("display_target_table") or edge.get("target_table", "")
            if not src or not tgt:
                continue
            nodes.add(src)
            nodes.add(tgt)
            field = edge.get("source_field", "") or "FK"
            target_key = edge.get("target_key", "") or "ID"
            label = f"{field} -> {target_key}"
            edge_lines.append(f'  {_mermaid_id(src)} -->|"{escape(label)}"| {_mermaid_id(tgt)}')

    for node in sorted(nodes):
        lines.append(f'  {_mermaid_id(node)}["{escape(node)}"]')

    seen_edges = set()
    for edge_line in edge_lines:
        if edge_line not in seen_edges:
            seen_edges.add(edge_line)
            lines.append(edge_line)

    source_id = _mermaid_id(source_table)
    target_id = _mermaid_id(target_table)
    if source_table in nodes:
        lines.append(f"  class {source_id} sourceNode")
    if target_table in nodes:
        lines.append(f"  class {target_id} targetNode")
    lines.append("  classDef sourceNode fill:#d0f0e0,stroke:#1a7040,stroke-width:2px,color:#1a1a1a")
    lines.append("  classDef targetNode fill:#ffe0e0,stroke:#c00000,stroke-width:2px,color:#1a1a1a")
    return "\n".join(lines)


def build_lineage_ascii(paths: list[dict]) -> str:
    """Build a plain-text ASCII diagram for found lineage paths."""
    if not paths:
        return ""

    blocks = []
    for path in paths:
        lines = [
            f"Path {path.get('path_index', '')} ({path.get('hop_count', '')} hop(s))",
            "",
        ]
        edges = path.get("edges", [])
        if not edges:
            lines.append("  No edges")
            blocks.append("\n".join(lines))
            continue

        first_table = edges[0].get("display_source_table") or edges[0].get("source_table", "")
        lines.append(f"  [{first_table}]")
        for edge in edges:
            source_field = edge.get("source_field", "") or "FK"
            target_key = edge.get("target_key", "") or "ID"
            target_table = edge.get("display_target_table") or edge.get("target_table", "")
            search_direction = edge.get("search_direction", "")
            direction_note = f" ({search_direction})" if search_direction else ""
            lines.append(f"      |-- {source_field} -> {target_key}{direction_note}")
            lines.append(f"      v")
            lines.append(f"  [{target_table}]")

        blocks.append("\n".join(lines))

    return "\n\n" + ("-" * 72 + "\n\n").join(blocks)
