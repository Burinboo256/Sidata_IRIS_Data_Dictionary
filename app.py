import json
import os
import re
import tempfile

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="IRIS Data Dictionary",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0f1117; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

div[data-testid="column"] .stButton button {
    background: #1e2130; border: 1px solid #2e3250; border-radius: 8px;
    text-align: left; padding: 12px; color: #e0e0e0;
    white-space: pre-line; min-height: 80px;
}
div[data-testid="column"] .stButton button:hover {
    border-color: #4c6ef5; background: #252a40;
}
[data-testid="metric-container"] {
    background: #1e2130; border: 1px solid #2e3250;
    border-radius: 8px; padding: 16px;
}
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 12px; font-weight: 600;
    background: #1a3a5c; color: #7eb8f7; margin-right: 6px;
}
.badge-purple { background: #2d1a5c; color: #b27ef7; }
.badge-green  { background: #1a3a28; color: #6fcf97; }
.badge-orange { background: #3a2a1a; color: #f7a96f; }
hr { border-color: #2e3250; }
h2, h3 { color: #c5cae9; }
.graph-legend span {
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    font-size: 12px; margin-right: 8px; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ─── Constants ────────────────────────────────────────────────────────────────

EXCEL_PATH = "iris_data_dict.xlsx"
TRANSLATIONS_PATH = "translations.json"
MAX_GRAPH_NODES = 60

# ─── Data loading ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading data dictionary…")
def load_data():
    xl = pd.ExcelFile(EXCEL_PATH)
    tables  = xl.parse("sql_tables").fillna("")
    fields  = xl.parse("sql_fields").fillna("")
    fk      = xl.parse("fk_relationships").fillna("")
    classes = xl.parse("classes").fillna("")
    members = xl.parse("members").fillna("")
    return tables, fields, fk, classes, members


@st.cache_data(show_spinner=False)
def compute_completeness(_fields_df):
    """% of fields per class_name that have a non-empty EN description."""
    result = {}
    for class_name, grp in _fields_df.groupby("class_name"):
        total = len(grp)
        filled = (grp["description"].astype(str).str.strip() != "").sum()
        result[class_name] = round(filled / total * 100) if total > 0 else 0
    return result


@st.cache_data(show_spinner="Collecting graph data…")
def collect_graph_data(center_table: str, depth: int, _fk_df, _tables_df) -> tuple:
    """Return (nodes_dict, edges_list).
    nodes_dict : {table_name: 'center'|'out'|'in'}
    edges_list : [(src_table, tgt_table, field_label)]
    """
    resolved = _fk_df[_fk_df["resolve_status"] == "resolved"]
    nodes: dict = {center_table: "center"}
    edges: list = []
    edges_seen: set = set()
    frontier = {center_table}

    for _ in range(depth):
        next_frontier: set = set()
        for current in list(frontier):
            # Outgoing
            for _, r in resolved[resolved["source_sql_table_name"] == current].iterrows():
                target = str(r["target_sql_table_name"])
                if not target or target == "nan" or len(nodes) >= MAX_GRAPH_NODES:
                    continue
                if target not in nodes:
                    nodes[target] = "out"
                    next_frontier.add(target)
                field = str(r["source_sql_field_name"])
                if field in ("", "nan"):
                    field = str(r["source_member_name"])
                key = (current, target, field[:30])
                if key not in edges_seen:
                    edges_seen.add(key)
                    edges.append((current, target, field))

            # Incoming
            for _, r in resolved[resolved["target_sql_table_name"] == current].iterrows():
                src_tbl = str(r["source_sql_table_name"])
                if not src_tbl or src_tbl == "nan" or len(nodes) >= MAX_GRAPH_NODES:
                    continue
                if src_tbl not in nodes:
                    nodes[src_tbl] = "in"
                    next_frontier.add(src_tbl)
                field = str(r["source_sql_field_name"])
                if field in ("", "nan"):
                    field = str(r["source_member_name"])
                key = (src_tbl, current, field[:30])
                if key not in edges_seen:
                    edges_seen.add(key)
                    edges.append((src_tbl, current, field))

            if len(nodes) >= MAX_GRAPH_NODES:
                break
        frontier = next_frontier
        if not frontier:
            break

    return nodes, edges


def build_pyvis_html(center_table: str, nodes_dict: dict, edges: list) -> str:
    """Render collected graph data as an interactive pyvis network."""
    net = Network(
        height="560px", width="100%", directed=True,
        bgcolor="#1e2130", font_color="#e0e0e0",
    )
    COLORS = {"center": "#4c6ef5", "out": "#6fcf97", "in": "#f7a96f"}
    SIZES  = {"center": 40, "out": 22, "in": 22}

    for name, role in nodes_dict.items():
        net.add_node(
            name, label=name,
            color=COLORS[role], size=SIZES[role],
            title=f"<b>{name}</b>",
            font={"size": 11, "color": "#e0e0e0", "strokeWidth": 3, "strokeColor": "#1e2130"},
        )

    added_edges: set = set()
    for src, tgt, label in edges:
        key = (src, tgt, label[:30])
        if key in added_edges:
            continue
        added_edges.add(key)
        net.add_edge(
            src, tgt,
            title=label,
            label=label if len(label) <= 22 else "",
            color={"color": "#5a6278", "highlight": "#4c6ef5"},
            arrows="to",
            font={"size": 9, "strokeWidth": 2, "strokeColor": "#1e2130"},
        )

    net.set_options("""{
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000, "centralGravity": 0.3,
          "springLength": 130, "springConstant": 0.04, "damping": 0.09
        }
      },
      "nodes": {"borderWidth": 2, "shape": "dot"},
      "edges": {"smooth": {"type": "curvedCW", "roundness": 0.1}},
      "interaction": {"hover": true, "tooltipDelay": 80}
    }""")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, "graph.html")
        net.save_graph(tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            html = f.read()
    return html


def mermaid_id(name: str) -> str:
    """Sanitize a table name to a valid Mermaid node ID."""
    return re.sub(r"[^a-zA-Z0-9]", "_", str(name))


def build_mermaid_html(
    center_table: str,
    nodes_dict: dict,
    edges: list,
    direction: str = "LR",
    group_modules: bool = True,
) -> tuple:
    """Render collected graph data as a Mermaid flowchart.
    Returns (html_string, raw_mermaid_code).
    """
    tbl_to_module = tables.set_index("sql_table_name")["module_name"].to_dict()
    tbl_to_prefix = tables.set_index("sql_table_name")["module_prefix"].to_dict()

    lines = [f"flowchart {direction}"]

    if group_modules:
        groups: dict = {}
        for tname in nodes_dict:
            mod = tbl_to_module.get(tname, "Unknown")
            groups.setdefault(mod, []).append(tname)

        for mod_name in sorted(groups):
            mod_id = mermaid_id(mod_name)
            prefix = tbl_to_prefix.get(groups[mod_name][0], "")
            lines.append(f'    subgraph {mod_id}["{prefix} · {mod_name}"]')
            for tname in sorted(groups[mod_name]):
                nid = mermaid_id(tname)
                lines.append(f'        {nid}["{tname}"]')
            lines.append("    end")
    else:
        for tname in sorted(nodes_dict):
            nid = mermaid_id(tname)
            lines.append(f'    {nid}["{tname}"]')

    # Edges — deduplicated
    seen_edges: set = set()
    for src, tgt, label in edges:
        sid, tid = mermaid_id(src), mermaid_id(tgt)
        lbl = label[:26] + "…" if len(label) > 26 else label
        key = (sid, tid, lbl)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        if lbl:
            lines.append(f'    {sid} -->|"{lbl}"| {tid}')
        else:
            lines.append(f'    {sid} --> {tid}')

    # Highlight center
    lines.append(
        f"    style {mermaid_id(center_table)} "
        "fill:#4c6ef5,color:#fff,stroke:#7eb8f7,stroke-width:3px"
    )

    mermaid_code = "\n".join(lines)

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body {{
    margin: 0; padding: 14px;
    background: #1e2130; overflow: auto;
    font-family: 'Segoe UI', sans-serif;
  }}
  .mermaid {{ min-height: 420px; }}
  .mermaid svg {{ max-width: 100% !important; height: auto; }}
</style>
</head>
<body>
<pre class="mermaid">{mermaid_code}</pre>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: "dark",
  flowchart: {{
    useMaxWidth: false,
    htmlLabels: true,
    curve: "basis",
    padding: 20
  }},
  securityLevel: "loose"
}});
</script>
</body></html>"""

    return html, mermaid_code


def extract_storage(class_decl: str) -> str:
    m = re.search(r"StorageStrategy\s*=\s*([a-zA-Z0-9_]+)", class_decl)
    return m.group(1) if m else "Default"


def load_translations() -> dict:
    if os.path.exists(TRANSLATIONS_PATH):
        with open(TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_translations(data: dict):
    with open(TRANSLATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── Export helpers ───────────────────────────────────────────────────────────

@st.cache_data
def schema_to_csv(_fields_df, _fk_df, tbl_name: str, class_name: str) -> bytes:
    """Return UTF-8 CSV bytes of the table schema (columns + reference target)."""
    tbl_f = _fields_df[_fields_df["class_name"] == class_name].sort_values("member_order")
    fk_res = _fk_df[
        (_fk_df["source_class_name"] == class_name) & (_fk_df["resolve_status"] == "resolved")
    ]
    fk_map = (
        fk_res[fk_res["source_sql_field_name"] != ""]
        .set_index("source_sql_field_name")["target_sql_table_name"]
        .to_dict()
    )
    rows = [
        {
            "Table": tbl_name,
            "Field": str(r["sql_field_name"]),
            "Type": str(r["member_type"]),
            "Description (EN)": str(r["description"]),
            "Description (TH)": "",
            "Reference →": fk_map.get(str(r["sql_field_name"]), ""),
        }
        for _, r in tbl_f.iterrows()
    ]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


@st.cache_data
def schema_to_excel(
    _fields_df, _fk_df, _members_df, _tables_df,
    tbl_name: str, class_name: str,
) -> bytes:
    """Return Excel bytes with sheets: Columns, Outgoing FK, Incoming Refs, Parameters, Triggers."""
    import io

    tbl_f     = _fields_df[_fields_df["class_name"] == class_name].sort_values("member_order")
    fk_out    = _fk_df[(_fk_df["source_class_name"] == class_name) & (_fk_df["resolve_status"] == "resolved")]
    fk_in     = _fk_df[(_fk_df["target_sql_table_name"] == tbl_name) & (_fk_df["resolve_status"] == "resolved")]
    cls_mem   = _members_df[_members_df["class_name"] == class_name]

    fk_map = (
        fk_out[fk_out["source_sql_field_name"] != ""]
        .set_index("source_sql_field_name")["target_sql_table_name"]
        .to_dict()
    )

    col_rows = [
        {
            "Field": str(r["sql_field_name"]),
            "Type": str(r["member_type"]),
            "Description (EN)": str(r["description"]),
            "Description (TH)": "",
            "Reference →": fk_map.get(str(r["sql_field_name"]), ""),
        }
        for _, r in tbl_f.iterrows()
    ]

    rel_rows = []
    for _, r in fk_out.iterrows():
        fn = str(r["source_sql_field_name"]) if str(r["source_sql_field_name"]) not in ("", "nan") else str(r["source_member_name"])
        rel_rows.append({"Field": fn, "Kind": str(r["evidence_source"]),
                         "Target Table": str(r["target_sql_table_name"]), "Target PK": str(r["target_pk_fields"])})

    inc_rows = []
    for _, r in fk_in.iterrows():
        src_row = _tables_df[_tables_df["class_name"] == r["source_class_name"]]
        src_name = src_row.iloc[0]["sql_table_name"] if not src_row.empty else str(r["source_class_name"])
        inc_rows.append({"Source Table": src_name, "Via Field": str(r["source_sql_field_name"]), "Kind": str(r["evidence_source"])})

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(col_rows).to_excel(writer, sheet_name="Columns", index=False)
        if rel_rows:
            pd.DataFrame(rel_rows).to_excel(writer, sheet_name="Outgoing FK", index=False)
        if inc_rows:
            pd.DataFrame(inc_rows).to_excel(writer, sheet_name="Incoming Refs", index=False)
        params = cls_mem[cls_mem["member_kind"] == "parameter"]
        if not params.empty:
            params[["member_name", "member_type", "description"]].rename(
                columns={"member_name": "Name", "member_type": "Value", "description": "Description"}
            ).to_excel(writer, sheet_name="Parameters", index=False)
        triggers = cls_mem[cls_mem["member_kind"] == "trigger"]
        if not triggers.empty:
            triggers[["member_name", "member_decl", "description"]].rename(
                columns={"member_name": "Name", "member_decl": "Declaration", "description": "Description"}
            ).to_excel(writer, sheet_name="Triggers", index=False)
    return buf.getvalue()


# ─── Analytics helpers ────────────────────────────────────────────────────────

@st.cache_data
def compute_analytics(_fk_df, _tables_df) -> tuple:
    """Return (hub_df, orphan_df, dep_counts).
    hub_df    : every table with incoming/outgoing FK counts
    orphan_df : tables with zero relationships in both directions
    dep_counts: cross-module reference counts (source_module, target_module, count)
    """
    resolved = _fk_df[_fk_df["resolve_status"] == "resolved"]

    inc = resolved.groupby("target_sql_table_name").size().reset_index(name="incoming")
    out = (
        resolved[resolved["source_sql_table_name"] != ""]
        .groupby("source_sql_table_name").size()
        .reset_index(name="outgoing")
    )

    hub = _tables_df[["sql_table_name", "module_name", "module_prefix", "class_description"]].copy()
    hub = hub.merge(inc, left_on="sql_table_name", right_on="target_sql_table_name", how="left")
    hub = hub.merge(out, left_on="sql_table_name", right_on="source_sql_table_name", how="left")
    hub["incoming"] = hub["incoming"].fillna(0).astype(int)
    hub["outgoing"] = hub["outgoing"].fillna(0).astype(int)
    hub["total"]    = hub["incoming"] + hub["outgoing"]

    orphan = hub[(hub["incoming"] == 0) & (hub["outgoing"] == 0)].copy()

    # Cross-module dependency counts (exclude self-references)
    tbl_mod = _tables_df.set_index("sql_table_name")["module_name"].to_dict()
    fk_mod  = resolved.copy()
    fk_mod["src_mod"] = fk_mod["source_sql_table_name"].map(tbl_mod)
    fk_mod["tgt_mod"] = fk_mod["target_sql_table_name"].map(tbl_mod)
    cross = fk_mod[
        fk_mod["src_mod"].notna() & fk_mod["tgt_mod"].notna()
        & (fk_mod["src_mod"] != fk_mod["tgt_mod"])
    ]
    dep_counts = (
        cross.groupby(["src_mod", "tgt_mod"]).size()
        .reset_index(name="count")
        .rename(columns={"src_mod": "source_module", "tgt_mod": "target_module"})
    )

    return hub, orphan, dep_counts


def _module_mermaid_html(mermaid_code: str) -> str:
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body {{ margin:0; padding:14px; background:#1e2130; overflow:auto;
         font-family:'Segoe UI',sans-serif; }}
  .mermaid {{ min-height:400px; }}
  .mermaid svg {{ max-width:100% !important; height:auto; }}
</style></head><body>
<pre class="mermaid">{mermaid_code}</pre>
<script>
mermaid.initialize({{
  startOnLoad:true, theme:"dark",
  flowchart:{{ useMaxWidth:false, htmlLabels:true, curve:"basis", padding:24 }},
  securityLevel:"loose"
}});
</script></body></html>"""


def build_module_mermaid(
    dep_counts: pd.DataFrame,
    direction: str = "LR",
    collapse_bidir: bool = True,
    center_module: str = None,
) -> tuple:
    """Render pre-filtered dep_counts as a Mermaid module flowchart.

    Args:
        dep_counts     : already-filtered DataFrame (source_module, target_module, count)
        direction      : Mermaid direction — "LR" or "TD"
        collapse_bidir : merge A→B + B→A into a single A↔B edge
        center_module  : highlight this module node (e.g. focus mode)

    Returns (html_string, raw_mermaid_code).
    """
    if dep_counts.empty:
        code = f"flowchart {direction}\n    empty[\"No data to show\"]"
        return _module_mermaid_html(code), code

    mod_prefix = tables.groupby("module_name")["module_prefix"].first().to_dict()
    mod_count  = tables.groupby("module_name").size().to_dict()

    lines = [f"flowchart {direction}"]

    # ── Build edges (optionally collapse bidirectional pairs) ──
    edges: list[tuple] = []   # (src, tgt, label, is_bidir)
    seen_pairs: set = set()

    for _, r in dep_counts.sort_values("count", ascending=False).iterrows():
        src, tgt, cnt = r["source_module"], r["target_module"], int(r["count"])
        fwd_key = (src, tgt)
        rev_key = (tgt, src)
        if fwd_key in seen_pairs or rev_key in seen_pairs:
            continue

        if collapse_bidir:
            rev = dep_counts[
                (dep_counts["source_module"] == tgt) & (dep_counts["target_module"] == src)
            ]
            if not rev.empty:
                rev_cnt = int(rev.iloc[0]["count"])
                edges.append((src, tgt, f"→ {cnt}  ← {rev_cnt}", True))
                seen_pairs.add(fwd_key)
                seen_pairs.add(rev_key)
                continue

        edges.append((src, tgt, f"{cnt} refs", False))
        seen_pairs.add(fwd_key)

    # ── Nodes ──
    mods_in_graph = sorted(
        {src for src, _, _, _ in edges} | {tgt for _, tgt, _, _ in edges}
    )
    for mod in mods_in_graph:
        mid    = mermaid_id(mod)
        prefix = mod_prefix.get(mod, "")
        cnt    = mod_count.get(mod, 0)
        lines.append(f'    {mid}["{prefix} · {mod}\\n({cnt} tables)"]')

    # ── Edges ──
    for src, tgt, label, is_bidir in edges:
        sid, tid = mermaid_id(src), mermaid_id(tgt)
        arrow = "<-->" if is_bidir else "-->"
        lines.append(f'    {sid} {arrow}|"{label}"| {tid}')

    # ── Highlight center module ──
    if center_module and center_module in mods_in_graph:
        lines.append(
            f"    style {mermaid_id(center_module)} "
            "fill:#4c6ef5,color:#fff,stroke:#7eb8f7,stroke-width:3px"
        )

    mermaid_code = "\n".join(lines)
    return _module_mermaid_html(mermaid_code), mermaid_code


# ─── ER diagram helpers ───────────────────────────────────────────────────────

def simplify_iris_type(type_str: str) -> str:
    """Map a verbose IRIS type declaration to a short ER-friendly label."""
    t = str(type_str).strip()
    if not t or t == "nan":
        return "string"
    if t.lower().startswith("list"):
        return "list"
    m = re.search(r"%(\w+)", t)
    if m:
        base = m.group(1).lower()
        return {
            "string": "string", "integer": "int", "date": "date",
            "time": "time", "datetime": "datetime", "boolean": "bool",
            "float": "float", "double": "float", "decimal": "decimal",
            "bigint": "bigint", "smallint": "int", "numeric": "numeric",
        }.get(base, base[:10])
    if "(" in t:
        return t.split("(")[0].strip().split(".")[-1][:10].lower()
    if "." in t or (t and t[0].isupper()):
        return "ref"
    return t[:10].lower()


def build_er_mermaid(
    table_names: list,
    include_fields: bool = True,
    max_fields: int = 8,
    cross_module: bool = False,
    direction: str = "TB",
) -> tuple:
    """Build a Mermaid erDiagram for the given table names.

    Args:
        table_names   : tables to include as primary entities
        include_fields: show field list inside each entity box
        max_fields    : cap fields per entity (appends a "…N more" note)
        cross_module  : also include tables that primary entities reference
        direction     : Mermaid er layoutDirection ("TB" or "LR")

    Returns (html_string, raw_mermaid_code).
    """
    resolved_er = fk[fk["resolve_status"] == "resolved"]
    primary     = set(table_names)

    # Optionally pull in cross-module referenced tables
    if cross_module:
        ext = resolved_er[
            resolved_er["source_sql_table_name"].isin(primary)
            & ~resolved_er["target_sql_table_name"].isin(primary)
            & (resolved_er["source_sql_field_name"] != "")
        ]["target_sql_table_name"].unique()
        all_tables = primary | set(ext)
    else:
        all_tables = primary

    # Only keep edges where both ends are in all_tables
    er_edges = resolved_er[
        resolved_er["source_sql_table_name"].isin(all_tables)
        & resolved_er["target_sql_table_name"].isin(all_tables)
        & (resolved_er["source_sql_field_name"] != "")
    ]

    tbl_class = tables.set_index("sql_table_name")["class_name"].to_dict()

    lines = ["erDiagram"]

    # ── Entity definitions ──
    for tbl in sorted(all_tables):
        cn = tbl_class.get(tbl, "")
        if not cn or not include_fields:
            lines.append(f"    {tbl} {{")
            lines.append("    }")
            continue

        tbl_f = fields[fields["class_name"] == cn].sort_values("member_order")
        fk_fields = set(
            er_edges[er_edges["source_sql_table_name"] == tbl]["source_sql_field_name"]
        )
        total = len(tbl_f)
        shown = tbl_f.head(max_fields)

        lines.append(f"    {tbl} {{")
        for _, fr in shown.iterrows():
            sf = re.sub(r"[^a-zA-Z0-9_]", "_", str(fr["sql_field_name"]))
            if not sf or sf == "nan":
                continue
            ftype  = simplify_iris_type(str(fr["member_type"]))
            marker = " FK" if fr["sql_field_name"] in fk_fields else ""
            desc   = str(fr["description"])[:28].replace('"', "'")
            comment = f' "{desc}"' if desc and desc != "nan" else ""
            lines.append(f"        {ftype} {sf}{marker}{comment}")
        if total > max_fields:
            lines.append(f'        string _and_{total - max_fields}_more "{total - max_fields} more fields"')
        lines.append("    }")

    # ── Relationships ──
    seen_rel: set = set()
    for _, r in er_edges.iterrows():
        src   = str(r["source_sql_table_name"])
        tgt   = str(r["target_sql_table_name"])
        field = str(r["source_sql_field_name"])
        card  = str(r.get("relationship_cardinality", ""))

        if src not in all_tables or tgt not in all_tables:
            continue
        key = (src, tgt, field[:20])
        if key in seen_rel:
            continue
        seen_rel.add(key)

        arrow = "||--o{" if card == "children" else "}o--||"
        label = field[:28].replace('"', "'") if field and field != "nan" else "ref"
        lines.append(f'    {src} {arrow} {tgt} : "{label}"')

    mermaid_code = "\n".join(lines)

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  body {{ margin:0; padding:14px; background:#1e2130; overflow:auto;
         font-family:'Segoe UI',sans-serif; }}
  .mermaid {{ min-height:500px; }}
  .mermaid svg {{ max-width:100% !important; height:auto; }}
</style></head><body>
<pre class="mermaid">{mermaid_code}</pre>
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: "dark",
  er: {{ useMaxWidth: false, layoutDirection: "{direction}", diagramPadding: 24, entityPadding: 12 }},
  securityLevel: "loose"
}});
</script></body></html>"""

    return html, mermaid_code


# ─── Load all data ────────────────────────────────────────────────────────────

tables, fields, fk, classes, members = load_data()
COMPLETENESS = compute_completeness(fields)
HUB_DF, ORPHAN_DF, DEP_COUNTS = compute_analytics(fk, tables)

MODULE_SUMMARY = (
    tables.groupby(["module_name", "module_prefix"])
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
    .reset_index(drop=True)
)

# ─── Session state ────────────────────────────────────────────────────────────

for key, default in [
    ("page", "home"),
    ("selected_table", None),
    ("browse_module", "All modules"),
    ("browse_filter", ""),
    ("graph_center", None),
    ("graph_depth", 1),
    ("recently_viewed", []),
    ("analytics_tab", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "translations" not in st.session_state:
    st.session_state.translations = load_translations()

# ─── URL deep linking ─────────────────────────────────────────────────────────
# On first load, honour ?table=TABLE_NAME in the URL.
_url_table = st.query_params.get("table", "")
if _url_table and st.session_state.page == "home":
    if _url_table in set(tables["sql_table_name"]):
        st.session_state.page = "detail"
        st.session_state.selected_table = _url_table
        rv = st.session_state.recently_viewed
        if _url_table in rv:
            rv.remove(_url_table)
        rv.insert(0, _url_table)
        st.session_state.recently_viewed = rv[:10]

# Keep the URL bar in sync with the current table.
if st.session_state.page == "detail" and st.session_state.selected_table:
    st.query_params["table"] = st.session_state.selected_table
elif "table" in st.query_params:
    del st.query_params["table"]


def nav(page: str, table: str = None):
    st.session_state.page = page
    if table is not None:
        st.session_state.selected_table = table
        if page == "detail":
            rv = st.session_state.recently_viewed
            if table in rv:
                rv.remove(table)
            rv.insert(0, table)
            st.session_state.recently_viewed = rv[:10]
    st.rerun()


# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🗂️ IRIS Data Dictionary")
    st.markdown("---")

    pages = {
        "home":      "🏠  Home",
        "search":    "🔍  Search",
        "browse":    "📁  Browse",
        "graph":     "🕸️  Graph",
        "analytics": "📊  Analytics",
    }
    for pid, label in pages.items():
        is_active = st.session_state.page == pid or (
            st.session_state.page == "detail" and pid == "browse"
        )
        if st.button(label, use_container_width=True, key=f"nav_{pid}",
                     type="primary" if is_active else "secondary"):
            nav(pid)

    st.markdown("---")
    st.caption(f"📊 **{len(tables):,}** tables")
    st.caption(f"🔗 **{len(fk):,}** relationships")
    st.caption(f"📦 **{MODULE_SUMMARY['module_name'].nunique()}** modules")

    # Overall EN completeness
    overall = round(sum(COMPLETENESS.values()) / len(COMPLETENESS)) if COMPLETENESS else 0
    st.markdown("---")
    st.caption("EN Description Coverage")
    st.progress(overall / 100, text=f"{overall}%")

    # TH translations progress
    trans_count = sum(len(v) for v in st.session_state.translations.values())
    total_fields = len(fields)
    st.caption(f"🇹🇭 TH Translations: **{trans_count:,}** / {total_fields:,} fields")

# ─── HOME ─────────────────────────────────────────────────────────────────────

if st.session_state.page == "home":
    st.title("IRIS Data Dictionary")
    st.markdown(
        "Browse and search IRIS persistent class metadata — tables, fields, "
        "types, and object-reference relationships."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tables", f"{len(tables):,}")
    c2.metric("Fields", f"{len(fields):,}")
    c3.metric("Relationships", f"{len(fk):,}")
    c4.metric("Modules", len(tables["module_name"].unique()))

    st.markdown("---")
    st.subheader("Modules")

    COLS = 4
    col_groups = [st.columns(COLS) for _ in range((len(MODULE_SUMMARY) + COLS - 1) // COLS)]
    for i, row in MODULE_SUMMARY.iterrows():
        with col_groups[i // COLS][i % COLS]:
            label = f"**{row['module_prefix']}**\n{row['module_name']}\n_{row['count']} tables_"
            if st.button(label, key=f"mod_{i}", use_container_width=True):
                st.session_state.browse_module = row["module_name"]
                nav("browse")

    # Recently Viewed
    if st.session_state.recently_viewed:
        st.markdown("---")
        st.subheader("Recently Viewed")
        rv_list = st.session_state.recently_viewed
        rv_cols = st.columns(min(len(rv_list), 5))
        for i, tbl in enumerate(rv_list):
            tbl_info = tables[tables["sql_table_name"] == tbl]
            prefix = tbl_info.iloc[0]["module_prefix"] if not tbl_info.empty else ""
            with rv_cols[i % 5]:
                if st.button(f"🗃️ {tbl}\n`{prefix}`", key=f"rv_{tbl}", use_container_width=True):
                    nav("detail", table=tbl)

# ─── SEARCH ───────────────────────────────────────────────────────────────────

elif st.session_state.page == "search":
    st.title("Search")
    query = st.text_input(
        "Search", placeholder="e.g. vendor, patient, diagnosis code",
        label_visibility="collapsed",
    )

    if query:
        q = query.strip().lower()
        t_mask = (
            tables["sql_table_name"].str.lower().str.contains(q, na=False)
            | tables["class_description"].str.lower().str.contains(q, na=False)
            | tables["module_name"].str.lower().str.contains(q, na=False)
        )
        matched_tables = tables[t_mask].copy()

        f_mask = (
            fields["sql_field_name"].str.lower().str.contains(q, na=False)
            | fields["description"].str.lower().str.contains(q, na=False)
            | fields["member_type"].str.lower().str.contains(q, na=False)
        )
        matched_fields = fields[f_mask].copy()

        st.markdown(f"**{len(matched_tables)}** tables · **{len(matched_fields)}** fields")

        tab_t, tab_f = st.tabs(
            [f"Tables ({len(matched_tables)})", f"Fields ({len(matched_fields)})"]
        )

        with tab_t:
            if matched_tables.empty:
                st.info("No tables matched.")
            else:
                disp = matched_tables[
                    ["sql_table_name", "module_prefix", "module_name", "class_description"]
                ].rename(columns={
                    "sql_table_name": "Table", "module_prefix": "Prefix",
                    "module_name": "Module", "class_description": "Description",
                }).copy()
                disp["Description"] = disp["Description"].str.replace("\n", " ").str[:120]
                evt = st.dataframe(disp, width="stretch", hide_index=True,
                                   selection_mode="single-row", on_select="rerun",
                                   key="search_t_sel")
                if evt.selection.rows:
                    nav("detail", table=matched_tables.iloc[evt.selection.rows[0]]["sql_table_name"])

        with tab_f:
            if matched_fields.empty:
                st.info("No fields matched.")
            else:
                tbl_map = tables.set_index("class_name")["sql_table_name"].to_dict()
                matched_fields = matched_fields.copy()
                matched_fields["Table"] = matched_fields["class_name"].map(tbl_map)
                disp = matched_fields[
                    ["sql_field_name", "Table", "description", "member_type"]
                ].rename(columns={
                    "sql_field_name": "Field", "description": "Description", "member_type": "Type",
                }).copy()
                disp["Type"] = disp["Type"].str[:60]
                evt = st.dataframe(disp, width="stretch", hide_index=True,
                                   selection_mode="single-row", on_select="rerun",
                                   key="search_f_sel")
                if evt.selection.rows:
                    tbl = matched_fields.iloc[evt.selection.rows[0]]["Table"]
                    if tbl:
                        nav("detail", table=tbl)

# ─── BROWSE / DETAIL ─────────────────────────────────────────────────────────

elif st.session_state.page in ("browse", "detail"):
    if st.session_state.page == "browse":
        st.title("Browse Tables")

    module_options = ["All modules"] + sorted(tables["module_name"].unique().tolist())
    default_mod_idx = (
        module_options.index(st.session_state.browse_module)
        if st.session_state.browse_module in module_options else 0
    )

    col_m, col_f = st.columns([2, 3])
    with col_m:
        sel_module = st.selectbox("Module", module_options, index=default_mod_idx, key="browse_mod_select")
        st.session_state.browse_module = sel_module
    with col_f:
        name_filter = st.text_input("Filter by table name", value=st.session_state.browse_filter,
                                    placeholder="e.g. vendor", key="browse_name_filter")
        st.session_state.browse_filter = name_filter

    filtered = tables.copy()
    if sel_module != "All modules":
        filtered = filtered[filtered["module_name"] == sel_module]
    if name_filter.strip():
        filtered = filtered[
            filtered["sql_table_name"].str.lower().str.contains(name_filter.strip().lower(), na=False)
        ]
    filtered = filtered.sort_values("sql_table_name").reset_index(drop=True)

    st.caption(f"{len(filtered):,} tables")

    disp = filtered[
        ["sql_table_name", "module_prefix", "module_name", "class_description", "class_name"]
    ].copy()
    disp["Completeness"] = disp["class_name"].map(COMPLETENESS).fillna(0).astype(int)
    disp = disp.drop(columns=["class_name"]).rename(columns={
        "sql_table_name": "Table", "module_prefix": "Prefix",
        "module_name": "Module", "class_description": "Description",
    })
    disp["Description"] = disp["Description"].str.replace("\n", " ").str[:100]

    evt = st.dataframe(
        disp,
        column_config={
            "Completeness": st.column_config.ProgressColumn(
                "EN Desc %", min_value=0, max_value=100, format="%d%%",
            )
        },
        width="stretch", hide_index=True,
        selection_mode="single-row", on_select="rerun",
        key="browse_table_sel", height=280,
    )

    if evt.selection.rows:
        st.session_state.selected_table = filtered.iloc[evt.selection.rows[0]]["sql_table_name"]
        st.session_state.page = "detail"

    # ── Table Detail ─────────────────────────────────────────────────────────

    if st.session_state.page == "detail" and st.session_state.selected_table:
        tbl_name = st.session_state.selected_table
        tbl_row_df = tables[tables["sql_table_name"] == tbl_name]

        if tbl_row_df.empty:
            st.error(f"Table '{tbl_name}' not found.")
        else:
            tbl_row = tbl_row_df.iloc[0]
            class_name = str(tbl_row["class_name"])

            st.markdown("---")

            # Header
            hcol1, hcol2, hcol3 = st.columns([5, 1, 1])
            with hcol1:
                st.markdown(f"## 🗃️ {tbl_name}")
                st.markdown(
                    f'<span class="badge badge-purple">{tbl_row["module_prefix"]}</span>'
                    f'<span class="badge">{tbl_row["module_name"]}</span>',
                    unsafe_allow_html=True,
                )
                st.caption(f"🔗 Share: `?table={tbl_name}`")
            with hcol2:
                score = COMPLETENESS.get(class_name, 0)
                st.metric("EN Desc", f"{score}%")
                if st.button("🕸️ Graph", key="goto_graph", use_container_width=True):
                    st.session_state.graph_center = tbl_name
                    nav("graph")
            with hcol3:
                st.markdown("<br>", unsafe_allow_html=True)
                csv_bytes = schema_to_csv(fields, fk, tbl_name, class_name)
                st.download_button(
                    "⬇️ CSV", csv_bytes,
                    file_name=f"{tbl_name}_schema.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"dl_csv_{tbl_name}",
                )
                xl_bytes = schema_to_excel(fields, fk, members, tables, tbl_name, class_name)
                st.download_button(
                    "⬇️ Excel", xl_bytes,
                    file_name=f"{tbl_name}_schema.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"dl_xl_{tbl_name}",
                )

            if tbl_row["class_description"]:
                st.info(str(tbl_row["class_description"]).replace("\n", "  \n"))

            class_info = classes[classes["class_name"] == class_name]
            if not class_info.empty:
                ci = class_info.iloc[0]
                storage = extract_storage(str(ci["class_decl"]))
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Class:** `{class_name}`")
                c2.markdown(f"**Storage:** `{storage}`")
                c3.markdown(f"**DB:** `{ci.get('db', '')}`")

            # Pre-build field data
            tbl_fields = fields[fields["class_name"] == class_name].sort_values("member_order")
            tbl_fk_src  = fk[fk["source_class_name"] == class_name]
            resolved_fk = tbl_fk_src[tbl_fk_src["resolve_status"] == "resolved"]
            incoming    = fk[(fk["target_sql_table_name"] == tbl_name) & (fk["resolve_status"] == "resolved")]
            cls_members = members[members["class_name"] == class_name]

            fk_map = (
                resolved_fk[resolved_fk["source_sql_field_name"] != ""]
                .set_index("source_sql_field_name")["target_sql_table_name"]
                .to_dict()
            )

            # ── Tabs ────────────────────────────────────────────────────────

            tab_schema, tab_sql, tab_translate = st.tabs(
                ["📋 Schema", "⚙️ SQL Builder", "🇹🇭 Thai Descriptions"]
            )

            # ── TAB 1: Schema ────────────────────────────────────────────────

            with tab_schema:
                st.subheader("Columns")
                if not tbl_fields.empty:
                    col_rows = []
                    for _, fr in tbl_fields.iterrows():
                        sf = str(fr["sql_field_name"])
                        ref = fk_map.get(sf, "")
                        col_rows.append({
                            "Field": sf,
                            "Type": str(fr["member_type"])[:80],
                            "Description": str(fr["description"]),
                            "Reference →": ref,
                        })
                    st.dataframe(pd.DataFrame(col_rows), width="stretch", hide_index=True)
                else:
                    st.info("No columns found.")

                if not resolved_fk.empty:
                    with st.expander(f"Outgoing relationships ({len(resolved_fk)})", expanded=True):
                        rel_rows = []
                        for _, r in resolved_fk.iterrows():
                            fn = str(r["source_sql_field_name"])
                            if fn in ("", "nan"):
                                fn = str(r["source_member_name"])
                            rel_rows.append({
                                "Field": fn,
                                "Kind": str(r["evidence_source"]),
                                "Target Table": str(r["target_sql_table_name"]),
                                "Target PK": str(r["target_pk_fields"]),
                            })
                        rel_evt = st.dataframe(
                            pd.DataFrame(rel_rows), width="stretch", hide_index=True,
                            selection_mode="single-row", on_select="rerun",
                            key=f"rel_{tbl_name}",
                        )
                        if rel_evt.selection.rows:
                            nav("detail", table=resolved_fk.iloc[rel_evt.selection.rows[0]]["target_sql_table_name"])

                if not incoming.empty:
                    with st.expander(f"Referenced by ({len(incoming)})", expanded=False):
                        inc_rows = []
                        for _, r in incoming.iterrows():
                            src_row = tables[tables["class_name"] == r["source_class_name"]]
                            src_name = src_row.iloc[0]["sql_table_name"] if not src_row.empty else str(r["source_class_name"])
                            inc_rows.append({
                                "Source Table": src_name,
                                "Via Field": str(r["source_sql_field_name"]),
                                "Kind": str(r["evidence_source"]),
                            })
                        inc_df = pd.DataFrame(inc_rows).drop_duplicates()
                        inc_evt = st.dataframe(
                            inc_df, width="stretch", hide_index=True,
                            selection_mode="single-row", on_select="rerun",
                            key=f"inc_{tbl_name}",
                        )
                        if inc_evt.selection.rows:
                            nav("detail", table=inc_df.iloc[inc_evt.selection.rows[0]]["Source Table"])

                params    = cls_members[cls_members["member_kind"] == "parameter"]
                triggers  = cls_members[cls_members["member_kind"] == "trigger"]
                if not params.empty or not triggers.empty:
                    with st.expander("Parameters & Triggers"):
                        if not params.empty:
                            st.markdown("**Parameters**")
                            st.dataframe(
                                params[["member_name", "member_type", "description"]].rename(
                                    columns={"member_name": "Name", "member_type": "Value", "description": "Description"}
                                ), width="stretch", hide_index=True,
                            )
                        if not triggers.empty:
                            st.markdown("**Triggers**")
                            st.dataframe(
                                triggers[["member_name", "member_decl", "description"]].rename(
                                    columns={"member_name": "Name", "member_decl": "Declaration", "description": "Description"}
                                ), width="stretch", hide_index=True,
                            )

            # ── TAB 2: SQL Builder ───────────────────────────────────────────

            with tab_sql:
                st.markdown("Select fields to build a SELECT statement for this table.")

                if tbl_fields.empty:
                    st.info("No fields available.")
                else:
                    all_fnames = tbl_fields["sql_field_name"].tolist()

                    ca, cb = st.columns([3, 1])
                    with ca:
                        chosen = st.multiselect(
                            "Fields to include",
                            options=all_fnames,
                            default=all_fnames,
                            key=f"sql_chosen_{tbl_name}",
                        )
                    with cb:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("Select all", key=f"sql_all_{tbl_name}", use_container_width=True):
                            chosen = all_fnames

                    if chosen:
                        lines = ["    " + f for f in chosen]
                        sql = "SELECT\n" + ",\n".join(lines) + f"\nFROM {tbl_name}"
                        st.code(sql, language="sql")

                        # Arrow syntax examples for reference fields
                        ref_in_chosen = [(f, fk_map[f]) for f in chosen if f in fk_map]
                        if ref_in_chosen:
                            with st.expander("Arrow syntax examples (reference fields)"):
                                st.markdown(
                                    "IRIS SQL lets you traverse object references directly "
                                    "using `->`. Click-to-copy examples below:"
                                )
                                for rf, target_tbl in ref_in_chosen[:10]:
                                    tgt_row = tables[tables["sql_table_name"] == target_tbl]
                                    if tgt_row.empty:
                                        continue
                                    tgt_class = tgt_row.iloc[0]["class_name"]
                                    tgt_fields = (
                                        fields[fields["class_name"] == tgt_class]["sql_field_name"]
                                        .head(4).tolist()
                                    )
                                    if tgt_fields:
                                        arrow_parts = ", ".join(f"{rf}->{tf}" for tf in tgt_fields)
                                        st.code(
                                            f"-- {rf} references {target_tbl}\n"
                                            f"SELECT {arrow_parts}\nFROM {tbl_name}",
                                            language="sql",
                                        )

                        # IRIS ObjectScript access hint
                        with st.expander("ObjectScript access pattern"):
                            clean_class = class_name.replace(".cls", "")
                            st.code(
                                f"// Open an object by ID\n"
                                f"Set obj = ##{{{clean_class}}}.%OpenId(id)\n\n"
                                f"// Read a property\n"
                                f"Write obj.PropertyName\n\n"
                                f"// SQL equivalent\n"
                                f"SELECT {chosen[0] if chosen else 'FieldName'} FROM {tbl_name} WHERE %ID = :id",
                                language="objectscript",
                            )

            # ── TAB 3: Thai Descriptions ─────────────────────────────────────

            with tab_translate:
                translations = st.session_state.translations
                table_trans  = translations.get(class_name, {})

                filled_count = sum(1 for f in tbl_fields["sql_field_name"] if table_trans.get(str(f), "").strip())
                total_count  = len(tbl_fields)
                st.markdown(
                    f"Thai descriptions filled: **{filled_count}** / {total_count} fields"
                )
                st.progress(filled_count / total_count if total_count else 0)
                st.markdown("")

                if tbl_fields.empty:
                    st.info("No fields available.")
                else:
                    edit_df = tbl_fields[["sql_field_name", "description"]].copy()
                    edit_df.columns = ["Field", "EN Description"]
                    edit_df["TH Description"] = edit_df["Field"].map(
                        lambda f: table_trans.get(str(f), "")
                    )

                    edited = st.data_editor(
                        edit_df,
                        column_config={
                            "Field":          st.column_config.TextColumn(disabled=True, width="medium"),
                            "EN Description": st.column_config.TextColumn(disabled=True, width="large"),
                            "TH Description": st.column_config.TextColumn(
                                "TH Description (แก้ไขได้)", width="large",
                            ),
                        },
                        width="stretch",
                        hide_index=True,
                        key=f"th_editor_{tbl_name}",
                        num_rows="fixed",
                    )

                    if st.button("💾 Save Thai descriptions", key=f"save_th_{tbl_name}", type="primary"):
                        new_trans = {
                            str(row["Field"]): str(row["TH Description"])
                            for _, row in edited.iterrows()
                            if str(row.get("TH Description", "")).strip()
                        }
                        translations[class_name] = new_trans
                        save_translations(translations)
                        st.session_state.translations = translations
                        st.success(f"Saved {len(new_trans)} Thai descriptions for **{tbl_name}**.")
                        st.rerun()

# ─── GRAPH ────────────────────────────────────────────────────────────────────

elif st.session_state.page == "graph":
    st.title("🕸️ Relationship Graph")

    all_table_names = sorted(tables["sql_table_name"].tolist())
    default_center = st.session_state.graph_center or (
        st.session_state.selected_table if st.session_state.selected_table else all_table_names[0]
    )
    default_idx = all_table_names.index(default_center) if default_center in all_table_names else 0

    # ── Controls
    gc1, gc2, gc3 = st.columns([3, 1, 2])
    with gc1:
        center = st.selectbox(
            "Center table", all_table_names, index=default_idx, key="graph_center_sel"
        )
        st.session_state.graph_center = center
    with gc2:
        depth = st.selectbox("Hops", [1, 2], index=st.session_state.graph_depth - 1, key="graph_depth_sel")
        st.session_state.graph_depth = depth
    with gc3:
        presentation = st.radio(
            "Presentation", ["🔵 Network", "📊 Mermaid"],
            horizontal=True, key="graph_presentation",
        )

    is_mermaid = presentation == "📊 Mermaid"

    # ── Mermaid-specific options
    if is_mermaid:
        mo1, mo2 = st.columns([2, 2])
        with mo1:
            dir_choice = st.radio(
                "Direction",
                ["Left → Right (LR)", "Top → Bottom (TD)"],
                horizontal=True, key="mermaid_dir",
            )
            mermaid_direction = "LR" if "LR" in dir_choice else "TD"
        with mo2:
            st.markdown("<br>", unsafe_allow_html=True)
            group_modules = st.checkbox(
                "Group by module (subgraphs)", value=True, key="mermaid_grp"
            )

    # ── Legend
    st.markdown(
        '<div class="graph-legend">'
        '<span style="background:#4c6ef5;color:#fff">⬤  Center</span>'
        '<span style="background:#6fcf97;color:#1e2130">⬤  Outgoing refs</span>'
        '<span style="background:#f7a96f;color:#1e2130">⬤  Incoming refs</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Max {MAX_GRAPH_NODES} nodes shown. Hover nodes/edges for details.")

    if center:
        nodes_dict, edges = collect_graph_data(center, depth, fk, tables)

        if len(nodes_dict) >= MAX_GRAPH_NODES:
            st.warning(
                f"Graph reached the {MAX_GRAPH_NODES}-node limit — "
                "not all connections are shown. Try reducing hops."
            )

        if is_mermaid:
            m_html, m_code = build_mermaid_html(
                center, nodes_dict, edges,
                direction=mermaid_direction,
                group_modules=group_modules,
            )
            components.html(m_html, height=640, scrolling=True)
            with st.expander("Raw Mermaid code  ·  paste into mermaid.live or Notion"):
                st.code(m_code, language="text")
        else:
            p_html = build_pyvis_html(center, nodes_dict, edges)
            components.html(p_html, height=580, scrolling=False)

        # Connected tables navigation
        connected = sorted(set(nodes_dict.keys()) - {center})
        if connected:
            st.markdown("---")
            st.subheader("Connected tables")
            st.caption("Click any table below to open its detail page.")
            NCOLS = 5
            cg = [st.columns(NCOLS) for _ in range((len(connected) + NCOLS - 1) // NCOLS)]
            for i, tbl in enumerate(connected):
                with cg[i // NCOLS][i % NCOLS]:
                    if st.button(tbl, key=f"gn_{tbl}", use_container_width=True):
                        nav("detail", table=tbl)

# ─── ANALYTICS ───────────────────────────────────────────────────────────────

elif st.session_state.page == "analytics":
    st.title("📊 Analytics")

    tab_dep, tab_hub, tab_orphan, tab_er = st.tabs([
        "🗺️ Module Dependency Map",
        "🏆 Hub Tables",
        "🏝️ Orphan Tables",
        "📐 ER Diagram",
    ])

    # ── TAB 1: Module Dependency Map ─────────────────────────────────────────

    with tab_dep:
        st.subheader("Cross-module FK References")
        st.markdown(
            "Each cell shows how many resolved FK relationships go **from** the row module "
            "**to** the column module. Self-references are excluded."
        )

        if DEP_COUNTS.empty:
            st.info("No cross-module relationships found.")
        else:
            # ── Heatmap
            dep_pivot = (
                DEP_COUNTS.pivot(index="source_module", columns="target_module", values="count")
                .fillna(0).astype(int)
            )
            fig_heat = px.imshow(
                dep_pivot,
                labels=dict(x="Target Module", y="Source Module", color="FK count"),
                color_continuous_scale="Blues",
                text_auto=True,
                aspect="auto",
            )
            fig_heat.update_layout(
                paper_bgcolor="#1e2130", plot_bgcolor="#1e2130",
                font=dict(color="#e0e0e0", size=11),
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis=dict(tickangle=-35),
                coloraxis_showscale=False,
            )
            fig_heat.update_traces(textfont=dict(size=10))
            st.plotly_chart(fig_heat, use_container_width=True)

            # ── Mermaid module diagram
            st.markdown("---")
            st.subheader("Module Dependency Flowchart")

            all_module_names = sorted(
                set(DEP_COUNTS["source_module"]) | set(DEP_COUNTS["target_module"])
            )

            # ── Row 1: mode + style options
            rc1, rc2, rc3, rc4 = st.columns([2, 2, 1, 1])
            with rc1:
                view_mode = st.radio(
                    "View mode", ["🌐 All modules", "🎯 Focus on module"],
                    horizontal=True, key="dep_mode",
                )
            with rc2:
                collapse_bidir = st.checkbox(
                    "Collapse bidirectional (A↔B)", value=True, key="dep_bidir",
                    help="Merge A→B and B→A into one double-headed arrow showing both counts."
                )
            with rc3:
                m_dir = st.radio("Direction", ["LR", "TD"], horizontal=True, key="dep_dir")
            with rc4:
                st.markdown("<br>", unsafe_allow_html=True)

            # ── Row 2: mode-specific controls
            is_focus = view_mode.startswith("🎯")
            center_mod = None

            if is_focus:
                fc1, fc2 = st.columns([2, 2])
                with fc1:
                    center_mod = st.selectbox(
                        "Center module", all_module_names, key="dep_focus_mod"
                    )
                with fc2:
                    focus_dir = st.radio(
                        "Show connections",
                        ["Both", "Outgoing →", "← Incoming"],
                        horizontal=True, key="dep_focus_dir",
                    )
                # Filter to only edges involving center_mod
                if focus_dir == "Outgoing →":
                    filtered_dep = DEP_COUNTS[DEP_COUNTS["source_module"] == center_mod]
                elif focus_dir == "← Incoming":
                    filtered_dep = DEP_COUNTS[DEP_COUNTS["target_module"] == center_mod]
                else:
                    filtered_dep = DEP_COUNTS[
                        (DEP_COUNTS["source_module"] == center_mod) |
                        (DEP_COUNTS["target_module"] == center_mod)
                    ]
            else:
                ac1, ac2 = st.columns([2, 2])
                with ac1:
                    min_refs = st.number_input(
                        "Min references per edge", min_value=1, value=3,
                        step=1, key="dep_min_refs",
                        help="Hide edges with fewer FK references than this threshold."
                    )
                with ac2:
                    total_mods = len(all_module_names)
                    top_n_mods = st.slider(
                        "Top N modules (by connectivity)", min_value=3,
                        max_value=total_mods, value=min(12, total_mods),
                        step=1, key="dep_top_n",
                        help="Keep only the N most-connected modules. Reduces clutter."
                    )
                # Apply top-N filter
                mod_totals = (
                    DEP_COUNTS.groupby("source_module")["count"].sum()
                    .add(DEP_COUNTS.groupby("target_module")["count"].sum(), fill_value=0)
                    .sort_values(ascending=False)
                )
                top_mods = set(mod_totals.head(top_n_mods).index)
                filtered_dep = DEP_COUNTS[
                    DEP_COUNTS["source_module"].isin(top_mods) &
                    DEP_COUNTS["target_module"].isin(top_mods) &
                    (DEP_COUNTS["count"] >= int(min_refs))
                ]

            # ── Render
            node_count = len(
                set(filtered_dep["source_module"]) | set(filtered_dep["target_module"])
            )
            edge_count = len(filtered_dep)
            st.caption(f"Showing **{node_count}** modules · **{edge_count}** relationships")

            m_html, m_code = build_module_mermaid(
                filtered_dep,
                direction=m_dir,
                collapse_bidir=collapse_bidir,
                center_module=center_mod,
            )
            components.html(m_html, height=560, scrolling=True)

            with st.expander("Raw Mermaid code  ·  paste into mermaid.live or Notion"):
                st.code(m_code, language="text")

            # ── Raw dependency table
            st.markdown("---")
            st.subheader("Reference counts by module pair")
            dep_disp = (
                DEP_COUNTS.rename(columns={
                    "source_module": "From Module",
                    "target_module": "To Module",
                    "count": "FK Count",
                })
                .sort_values("FK Count", ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(dep_disp, width="stretch", hide_index=True)

    # ── TAB 2: Hub Tables ────────────────────────────────────────────────────

    with tab_hub:
        st.subheader("Most Referenced Tables")
        st.markdown(
            "Tables ranked by **incoming** FK references — these are your master-data "
            "/ lookup tables that the rest of the system depends on."
        )

        top_n = st.slider("Show top N tables", min_value=10, max_value=50, value=20, step=5, key="hub_n")
        hub_top = HUB_DF.nlargest(top_n, "incoming").reset_index(drop=True)

        # Bar chart
        fig_hub = px.bar(
            hub_top,
            x="incoming", y="sql_table_name",
            orientation="h",
            color="module_name",
            hover_data={"outgoing": True, "total": True, "module_prefix": True},
            labels={
                "incoming": "Incoming References",
                "sql_table_name": "Table",
                "module_name": "Module",
            },
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig_hub.update_layout(
            paper_bgcolor="#1e2130", plot_bgcolor="#1e2130",
            font=dict(color="#e0e0e0"),
            yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=max(300, top_n * 22),
        )
        st.plotly_chart(fig_hub, use_container_width=True)

        # Clickable table
        st.markdown("---")
        hub_disp = hub_top[["sql_table_name", "module_prefix", "module_name", "incoming", "outgoing", "total"]].rename(
            columns={
                "sql_table_name": "Table", "module_prefix": "Prefix",
                "module_name": "Module", "incoming": "Incoming ↙",
                "outgoing": "Outgoing ↗", "total": "Total",
            }
        )
        hub_evt = st.dataframe(
            hub_disp, width="stretch", hide_index=True,
            selection_mode="single-row", on_select="rerun", key="hub_sel",
        )
        if hub_evt.selection.rows:
            nav("detail", table=hub_top.iloc[hub_evt.selection.rows[0]]["sql_table_name"])

    # ── TAB 3: Orphan Tables ─────────────────────────────────────────────────

    with tab_orphan:
        st.subheader("Orphan Tables")
        st.markdown(
            "Tables with **zero** resolved FK relationships in either direction — "
            "no outgoing references and nothing references them."
        )

        if ORPHAN_DF.empty:
            st.success("No orphan tables found.")
        else:
            oc1, oc2 = st.columns([2, 3])
            with oc1:
                orp_modules = ["All modules"] + sorted(ORPHAN_DF["module_name"].unique().tolist())
                orp_mod = st.selectbox("Filter by module", orp_modules, key="orp_mod")
            with oc2:
                orp_filter = st.text_input("Filter by name", placeholder="e.g. RV", key="orp_filter")

            orp_view = ORPHAN_DF.copy()
            if orp_mod != "All modules":
                orp_view = orp_view[orp_view["module_name"] == orp_mod]
            if orp_filter.strip():
                orp_view = orp_view[
                    orp_view["sql_table_name"].str.lower().str.contains(orp_filter.strip().lower(), na=False)
                ]
            orp_view = orp_view.sort_values("sql_table_name").reset_index(drop=True)

            # Summary by module
            orp_by_mod = (
                orp_view.groupby(["module_prefix", "module_name"]).size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
            fig_orp = px.bar(
                orp_by_mod, x="module_prefix", y="count",
                color="module_name",
                labels={"module_prefix": "Module", "count": "Orphan tables"},
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_orp.update_layout(
                paper_bgcolor="#1e2130", plot_bgcolor="#1e2130",
                font=dict(color="#e0e0e0"),
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                height=260,
            )
            st.plotly_chart(fig_orp, use_container_width=True)

            st.caption(f"{len(orp_view):,} orphan tables shown")
            orp_disp = orp_view[["sql_table_name", "module_prefix", "module_name", "class_description"]].rename(
                columns={
                    "sql_table_name": "Table", "module_prefix": "Prefix",
                    "module_name": "Module", "class_description": "Description",
                }
            ).copy()
            orp_disp["Description"] = orp_disp["Description"].str.replace("\n", " ").str[:100]
            orp_evt = st.dataframe(
                orp_disp, width="stretch", hide_index=True,
                selection_mode="single-row", on_select="rerun", key="orp_sel",
            )
            if orp_evt.selection.rows:
                nav("detail", table=orp_view.iloc[orp_evt.selection.rows[0]]["sql_table_name"])

    # ── TAB 4: ER Diagram ────────────────────────────────────────────────────

    with tab_er:
        st.subheader("ER Diagram")
        st.markdown(
            "Visualise table schemas and their FK relationships as an entity-relationship diagram."
        )

        MAX_ER_TABLES = 20

        # ── Scope selector
        er_scope = st.radio(
            "Scope", ["By Module", "By Table (1-hop)", "Custom selection"],
            horizontal=True, key="er_scope",
        )

        er_tables: list = []
        center_er_table = None

        if er_scope == "By Module":
            ec1, ec2 = st.columns([2, 2])
            with ec1:
                er_module = st.selectbox(
                    "Module", sorted(tables["module_name"].unique()), key="er_module"
                )
            with ec2:
                cross_mod = st.checkbox(
                    "Include cross-module references", value=False, key="er_cross",
                    help="Also show tables from other modules that are referenced by this module's tables."
                )
            mod_tables = tables[tables["module_name"] == er_module]["sql_table_name"].tolist()
            if len(mod_tables) > MAX_ER_TABLES:
                st.warning(
                    f"Module has **{len(mod_tables)}** tables — showing the first {MAX_ER_TABLES} "
                    f"(sorted by name). Use **Custom selection** to pick specific ones."
                )
            er_tables = sorted(mod_tables)[:MAX_ER_TABLES]

        elif er_scope == "By Table (1-hop)":
            ec1, ec2 = st.columns([3, 1])
            with ec1:
                center_er_table = st.selectbox(
                    "Center table", sorted(tables["sql_table_name"].tolist()), key="er_center_tbl"
                )
            with ec2:
                hop_dir = st.radio("Include", ["Both", "Outgoing", "Incoming"],
                                   horizontal=False, key="er_hop_dir")
            cross_mod = False

            resolved_er_hop = fk[fk["resolve_status"] == "resolved"]
            if hop_dir in ("Both", "Outgoing"):
                out_tbls = resolved_er_hop[
                    resolved_er_hop["source_sql_table_name"] == center_er_table
                ]["target_sql_table_name"].unique().tolist()
            else:
                out_tbls = []
            if hop_dir in ("Both", "Incoming"):
                in_tbls = resolved_er_hop[
                    resolved_er_hop["target_sql_table_name"] == center_er_table
                ]["source_sql_table_name"].unique().tolist()
            else:
                in_tbls = []

            connected_er = list({center_er_table} | set(out_tbls) | set(in_tbls))
            if len(connected_er) > MAX_ER_TABLES:
                st.warning(
                    f"**{len(connected_er)}** connected tables — showing center + first "
                    f"{MAX_ER_TABLES - 1} neighbors. Use **Custom selection** for more control."
                )
                neighbors = sorted([t for t in connected_er if t != center_er_table])[:MAX_ER_TABLES - 1]
                connected_er = [center_er_table] + neighbors
            er_tables = connected_er

        else:  # Custom selection
            cross_mod = False
            er_tables = st.multiselect(
                "Select tables (max 20)",
                sorted(tables["sql_table_name"].tolist()),
                max_selections=MAX_ER_TABLES,
                key="er_custom_tables",
            )

        # ── Display options
        st.markdown("---")
        do1, do2, do3, do4 = st.columns([2, 1, 1, 1])
        with do1:
            show_fields = st.checkbox("Show fields", value=True, key="er_show_fields")
        with do2:
            max_f = st.number_input(
                "Max fields/table", min_value=3, max_value=30, value=8,
                step=1, key="er_max_fields",
                disabled=not show_fields,
            )
        with do3:
            er_dir = st.radio("Layout", ["TB", "LR"], horizontal=True, key="er_dir",
                              help="TB = top-to-bottom, LR = left-to-right")
        with do4:
            st.markdown("<br>", unsafe_allow_html=True)
            draw_er = st.button("Draw", type="primary", use_container_width=True, key="draw_er")

        # ── Render
        if er_tables:
            st.caption(f"Entities: **{len(er_tables)}** tables")
            er_html, er_code = build_er_mermaid(
                er_tables,
                include_fields=show_fields,
                max_fields=int(max_f),
                cross_module=cross_mod,
                direction=er_dir,
            )
            components.html(er_html, height=700, scrolling=True)

            with st.expander("Raw Mermaid code  ·  paste into mermaid.live or Notion"):
                st.code(er_code, language="text")
        else:
            st.info("Select a module, table, or custom set above to generate the diagram.")
