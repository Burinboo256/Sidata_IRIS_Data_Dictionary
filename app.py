import json
import os
import re
import tempfile

import pandas as pd
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


# ─── Load all data ────────────────────────────────────────────────────────────

tables, fields, fk, classes, members = load_data()
COMPLETENESS = compute_completeness(fields)

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
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "translations" not in st.session_state:
    st.session_state.translations = load_translations()


def nav(page: str, table: str = None):
    st.session_state.page = page
    if table is not None:
        st.session_state.selected_table = table
    st.rerun()


# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🗂️ IRIS Data Dictionary")
    st.markdown("---")

    pages = {
        "home":   "🏠  Home",
        "search": "🔍  Search",
        "browse": "📁  Browse",
        "graph":  "🕸️  Graph",
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
                evt = st.dataframe(disp, use_container_width=True, hide_index=True,
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
                evt = st.dataframe(disp, use_container_width=True, hide_index=True,
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
        use_container_width=True, hide_index=True,
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
            hcol1, hcol2 = st.columns([6, 1])
            with hcol1:
                st.markdown(f"## 🗃️ {tbl_name}")
                st.markdown(
                    f'<span class="badge badge-purple">{tbl_row["module_prefix"]}</span>'
                    f'<span class="badge">{tbl_row["module_name"]}</span>',
                    unsafe_allow_html=True,
                )
            with hcol2:
                score = COMPLETENESS.get(class_name, 0)
                st.metric("EN Desc", f"{score}%")
                if st.button("🕸️ Graph", key="goto_graph", use_container_width=True):
                    st.session_state.graph_center = tbl_name
                    nav("graph")

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
                    st.dataframe(pd.DataFrame(col_rows), use_container_width=True, hide_index=True)
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
                            pd.DataFrame(rel_rows), use_container_width=True, hide_index=True,
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
                            inc_df, use_container_width=True, hide_index=True,
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
                                ), use_container_width=True, hide_index=True,
                            )
                        if not triggers.empty:
                            st.markdown("**Triggers**")
                            st.dataframe(
                                triggers[["member_name", "member_decl", "description"]].rename(
                                    columns={"member_name": "Name", "member_decl": "Declaration", "description": "Description"}
                                ), use_container_width=True, hide_index=True,
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
                        use_container_width=True,
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
