import json
import os
import re
import tempfile
from datetime import datetime

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

# ─── Constants ────────────────────────────────────────────────────────────────

EXCEL_PATH = "iris_data_dict.xlsx"
TRANSLATIONS_PATH = "translations.json"
TAGS_PATH = "tags.json"
CHANGELOG_PATH = "changelog.json"
METADATA_PATH = "metadata.json"
USAGE_LOG_PATH = "usage_log.json"
MAX_GRAPH_NODES = 60

PREDEFINED_TAGS = ["PII", "financial", "deprecated", "master-data", "staging", "lookup", "audit", "critical"]

TAG_COLORS = {
    "PII":         ("badge-red",    "#c00000"),
    "financial":   ("badge-green",  "#1a7040"),
    "deprecated":  ("badge-orange", "#b06000"),
    "master-data": ("badge-purple", "#6b3fbf"),
    "critical":    ("badge-red",    "#c00000"),
}

CERT_OPTIONS = ["", "Certified", "Draft", "Deprecated", "Experimental"]
CERT_COLORS = {
    "Certified":    ("badge-green",  "#1a7040"),
    "Draft":        ("badge-orange", "#b06000"),
    "Deprecated":   ("badge-red",    "#c00000"),
    "Experimental": ("badge-purple", "#6b3fbf"),
}
UPDATE_FREQ_OPTIONS = ["", "Real-time", "Daily", "Weekly", "Monthly", "Quarterly", "Ad-hoc"]

# ─── Theme helpers ────────────────────────────────────────────────────────────

def _is_dark() -> bool:
    return st.session_state.get("theme", "dark") == "dark"

def _theme():
    dark = _is_dark()
    return {
        "dark":        dark,
        "bg":          "#1e2130" if dark else "#ffffff",
        "sidebar_bg":  "#0f1117" if dark else "#f0f2f6",
        "sidebar_txt": "#e0e0e0" if dark else "#333333",
        "card_bg":     "#1e2130" if dark else "#ffffff",
        "border":      "#2e3250" if dark else "#d0d0d0",
        "text":        "#e0e0e0" if dark else "#333333",
        "mermaid":     "dark"    if dark else "default",
        "pyvis_bg":    "#1e2130" if dark else "#ffffff",
        "pyvis_font":  "#e0e0e0" if dark else "#333333",
        "pyvis_stroke":"#1e2130" if dark else "#ffffff",
        "plotly_bg":   "#1e2130" if dark else "#ffffff",
        "plotly_font": "#e0e0e0" if dark else "#333333",
        "hover_bg":    "#252a40" if dark else "#f0f4ff",
    }

# ─── Dynamic CSS ─────────────────────────────────────────────────────────────

def _apply_css():
    t = _theme()
    dark = t["dark"]
    if dark:
        css = f"""
[data-testid="stSidebar"] {{ background: {t["sidebar_bg"]}; }}
[data-testid="stSidebar"] * {{ color: {t["sidebar_txt"]} !important; }}
div[data-testid="column"] .stButton button {{
    background: {t["card_bg"]}; border: 1px solid {t["border"]}; border-radius: 8px;
    text-align: left; padding: 12px; color: {t["text"]};
    white-space: pre-line; min-height: 80px;
}}
div[data-testid="column"] .stButton button:hover {{
    border-color: #4c6ef5; background: {t["hover_bg"]};
}}
[data-testid="metric-container"] {{
    background: {t["card_bg"]}; border: 1px solid {t["border"]};
    border-radius: 8px; padding: 16px;
}}
.badge {{
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 12px; font-weight: 600;
    background: #1a3a5c; color: #7eb8f7; margin-right: 6px;
}}
.badge-purple {{ background: #2d1a5c; color: #b27ef7; }}
.badge-green  {{ background: #1a3a28; color: #6fcf97; }}
.badge-orange {{ background: #3a2a1a; color: #f7a96f; }}
.badge-red    {{ background: #3a1a1a; color: #f76f6f; }}
hr {{ border-color: {t["border"]}; }}
h2, h3 {{ color: #c5cae9; }}
.graph-legend span {{
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    font-size: 12px; margin-right: 8px; font-weight: 600;
}}
"""
    else:
        css = f"""
[data-testid="stSidebar"] {{ background: {t["sidebar_bg"]}; }}
[data-testid="stSidebar"] * {{ color: {t["sidebar_txt"]} !important; }}
div[data-testid="column"] .stButton button {{
    background: #ffffff; border: 1px solid {t["border"]}; border-radius: 8px;
    text-align: left; padding: 12px; color: {t["text"]};
    white-space: pre-line; min-height: 80px;
}}
div[data-testid="column"] .stButton button:hover {{
    border-color: #4c6ef5; background: {t["hover_bg"]};
}}
[data-testid="metric-container"] {{
    background: #ffffff; border: 1px solid {t["border"]};
    border-radius: 8px; padding: 16px;
}}
.badge {{
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 12px; font-weight: 600;
    background: #dce8ff; color: #1a5cbf; margin-right: 6px;
}}
.badge-purple {{ background: #ebe0ff; color: #6b3fbf; }}
.badge-green  {{ background: #d0f0e0; color: #1a7040; }}
.badge-orange {{ background: #fff0d0; color: #b06000; }}
.badge-red    {{ background: #ffe0e0; color: #c00000; }}
hr {{ border-color: {t["border"]}; }}
h2, h3 {{ color: #333333; }}
.graph-legend span {{
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    font-size: 12px; margin-right: 8px; font-weight: 600;
}}
"""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

_apply_css()

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
    t = _theme()
    net = Network(
        height="560px", width="100%", directed=True,
        bgcolor=t["pyvis_bg"], font_color=t["pyvis_font"],
    )
    COLORS = {"center": "#4c6ef5", "out": "#6fcf97", "in": "#f7a96f"}
    SIZES  = {"center": 40, "out": 22, "in": 22}

    for name, role in nodes_dict.items():
        net.add_node(
            name, label=name,
            color=COLORS[role], size=SIZES[role],
            title=f"<b>{name}</b>",
            font={"size": 11, "color": t["pyvis_font"], "strokeWidth": 3, "strokeColor": t["pyvis_stroke"]},
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
            font={"size": 9, "strokeWidth": 2, "strokeColor": t["pyvis_stroke"]},
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
    t = _theme()
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
    _code_js = mermaid_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0; padding: 14px;
    background: {t["bg"]}; overflow: auto;
    font-family: 'Segoe UI', sans-serif;
  }}
  #diagram svg {{ max-width: 100% !important; height: auto; }}
  .dl-btn {{
    padding: 4px 11px; border: 1px solid {t["border"]}; border-radius: 4px;
    cursor: pointer; font-size: 12px; background: {t["card_bg"]}; color: {t["text"]};
    margin-right: 6px;
  }}
  .dl-btn:hover {{ opacity: 0.8; }}
</style>
</head>
<body>
<div id="btn-bar" style="display:none; margin-bottom:8px">
  <button class="dl-btn" id="btn-svg">&#11015; SVG</button>
  <button class="dl-btn" id="btn-png">&#11015; PNG</button>
</div>
<div id="diagram"></div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({{
  startOnLoad: false,
  theme: "{t["mermaid"]}",
  flowchart: {{ useMaxWidth: false, htmlLabels: true, curve: "basis", padding: 20 }},
  securityLevel: "loose"
}});
var _done = false;
var _svgStr = "";
var _code = `{_code_js}`;
async function _render() {{
  if (_done) return;
  if (document.body.offsetWidth === 0) {{ setTimeout(_render, 150); return; }}
  _done = true;
  try {{
    var r = await mermaid.render("flow-svg", _code);
    _svgStr = r.svg;
    document.getElementById("diagram").innerHTML = _svgStr;
    document.getElementById("btn-bar").style.display = "block";
  }} catch(e) {{
    document.getElementById("diagram").innerHTML =
      "<pre style='color:salmon;white-space:pre-wrap'>" + e.message + "</pre>";
  }}
}}
_render();
document.getElementById("btn-svg").onclick = function() {{
  var blob = new Blob([_svgStr], {{type: "image/svg+xml;charset=utf-8"}});
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a"); a.href = url; a.download = "graph_diagram.svg";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function() {{ URL.revokeObjectURL(url); }}, 1000);
}};
document.getElementById("btn-png").onclick = function() {{
  var svgEl = document.querySelector("#diagram svg");
  if (!svgEl) return;
  var w = svgEl.getBoundingClientRect().width || 1200;
  var h = svgEl.getBoundingClientRect().height || 800;
  var scale = 2;
  var canvas = document.createElement("canvas");
  canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale);
  var ctx = canvas.getContext("2d");
  ctx.fillStyle = "{t["bg"]}"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);
  var img = new Image();
  var blob = new Blob([_svgStr], {{type: "image/svg+xml;charset=utf-8"}});
  var url = URL.createObjectURL(blob);
  img.onload = function() {{
    try {{
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      var a = document.createElement("a");
      a.href = canvas.toDataURL("image/png"); a.download = "graph_diagram.png";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    }} catch(e) {{ URL.revokeObjectURL(url); alert("PNG export failed — use SVG instead."); }}
  }};
  img.onerror = function() {{ URL.revokeObjectURL(url); alert("PNG export failed — use SVG instead."); }};
  img.src = url;
}};
</script>
</body></html>"""

    return html, mermaid_code


def extract_storage(class_decl: str) -> str:
    m = re.search(r"StorageStrategy\s*=\s*([a-zA-Z0-9_]+)", class_decl)
    return m.group(1) if m else "Default"


# ─── Persistence helpers ──────────────────────────────────────────────────────

def load_translations() -> dict:
    if os.path.exists(TRANSLATIONS_PATH):
        with open(TRANSLATIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_translations(data: dict):
    with open(TRANSLATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_tags() -> dict:
    if os.path.exists(TAGS_PATH):
        with open(TAGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_tags(data: dict):
    with open(TAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_metadata() -> dict:
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_metadata(data: dict):
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_usage_log() -> list:
    if os.path.exists(USAGE_LOG_PATH):
        with open(USAGE_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def log_event(event: str, details: dict = None):
    log = load_usage_log()
    log.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "details": details or {},
    })
    with open(USAGE_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log[-10000:], f, ensure_ascii=False)


def load_changelog() -> list:
    if os.path.exists(CHANGELOG_PATH):
        with open(CHANGELOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def append_changelog(action: str, table: str, details: str):
    log = load_changelog()
    log.insert(0, {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "table": table,
        "details": details,
    })
    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log[:1000], f, ensure_ascii=False, indent=2)


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
            "IRIS Type": str(r["member_type"]),
            "MSSQL Type": iris_to_mssql(str(r["member_type"])),
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
            "IRIS Type": str(r["member_type"]),
            "MSSQL Type": iris_to_mssql(str(r["member_type"])),
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
    t = _theme()
    _code_js = mermaid_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  body {{ margin:0; padding:14px; background:{t["bg"]}; overflow:auto;
         font-family:'Segoe UI',sans-serif; }}
  #diagram svg {{ max-width:100% !important; height:auto; }}
  .dl-btn {{
    padding:4px 11px; border:1px solid {t["border"]}; border-radius:4px;
    cursor:pointer; font-size:12px; background:{t["card_bg"]}; color:{t["text"]};
    margin-right:6px;
  }}
  .dl-btn:hover {{ opacity:0.8; }}
</style></head><body>
<div id="btn-bar" style="display:none; margin-bottom:8px">
  <button class="dl-btn" id="btn-svg">&#11015; SVG</button>
  <button class="dl-btn" id="btn-png">&#11015; PNG</button>
</div>
<div id="diagram"></div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({{
  startOnLoad:false, theme:"{t["mermaid"]}",
  flowchart:{{ useMaxWidth:false, htmlLabels:true, curve:"basis", padding:24 }},
  securityLevel:"loose"
}});
var _done = false;
var _svgStr = "";
var _code = `{_code_js}`;
async function _render() {{
  if (_done) return;
  if (document.body.offsetWidth === 0) {{ setTimeout(_render, 150); return; }}
  _done = true;
  try {{
    var r = await mermaid.render("mod-svg", _code);
    _svgStr = r.svg;
    document.getElementById("diagram").innerHTML = _svgStr;
    document.getElementById("btn-bar").style.display = "block";
  }} catch(e) {{
    document.getElementById("diagram").innerHTML =
      "<pre style='color:salmon;white-space:pre-wrap'>" + e.message + "</pre>";
  }}
}}
_render();
document.getElementById("btn-svg").onclick = function() {{
  var blob = new Blob([_svgStr], {{type:"image/svg+xml;charset=utf-8"}});
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a"); a.href = url; a.download = "module_dependency.svg";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function() {{ URL.revokeObjectURL(url); }}, 1000);
}};
document.getElementById("btn-png").onclick = function() {{
  var svgEl = document.querySelector("#diagram svg");
  if (!svgEl) return;
  var w = svgEl.getBoundingClientRect().width || 1200;
  var h = svgEl.getBoundingClientRect().height || 800;
  var scale = 2;
  var canvas = document.createElement("canvas");
  canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale);
  var ctx = canvas.getContext("2d");
  ctx.fillStyle = "{t["bg"]}"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);
  var img = new Image();
  var blob = new Blob([_svgStr], {{type:"image/svg+xml;charset=utf-8"}});
  var url = URL.createObjectURL(blob);
  img.onload = function() {{
    try {{
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      var a = document.createElement("a");
      a.href = canvas.toDataURL("image/png"); a.download = "module_dependency.png";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    }} catch(e) {{ URL.revokeObjectURL(url); alert("PNG export failed — use SVG instead."); }}
  }};
  img.onerror = function() {{ URL.revokeObjectURL(url); alert("PNG export failed — use SVG instead."); }};
  img.src = url;
}};
</script>
</body></html>"""


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


# ─── Type helpers ─────────────────────────────────────────────────────────────

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


def iris_to_mssql(type_str: str) -> str:
    """Map an IRIS persistent class type to the closest MS SQL Server type."""
    t = str(type_str).strip()
    if not t or t == "nan":
        return "NVARCHAR(255)"
    if t.lower().startswith("list"):
        return "NVARCHAR(MAX)"
    maxlen_m = re.search(r"MAXLEN\s*=\s*(\d+)", t, re.IGNORECASE)
    maxlen = int(maxlen_m.group(1)) if maxlen_m else None
    m = re.search(r"%(\w+)", t)
    if m:
        base = m.group(1).lower()
        mapping = {
            "string":    f"NVARCHAR({maxlen})" if maxlen else "NVARCHAR(255)",
            "integer":   "INT",
            "smallint":  "SMALLINT",
            "bigint":    "BIGINT",
            "tinyint":   "TINYINT",
            "date":      "DATE",
            "time":      "TIME",
            "datetime":  "DATETIME2",
            "timestamp": "DATETIME2",
            "boolean":   "BIT",
            "float":     "FLOAT",
            "double":    "FLOAT",
            "decimal":   "DECIMAL(18,4)",
            "numeric":   "NUMERIC(18,4)",
            "currency":  "MONEY",
            "binary":    "VARBINARY(MAX)",
            "stream":    "VARBINARY(MAX)",
            "globalcharacterstream": "NVARCHAR(MAX)",
            "globalcharacterbinarystream": "VARBINARY(MAX)",
        }
        return mapping.get(base, "NVARCHAR(255)")
    if "." in t or (t and t[0].isupper()):
        return "BIGINT"   # FK reference — stored as ID
    return "NVARCHAR(255)"


# ─── ER diagram helpers ───────────────────────────────────────────────────────

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
    t = _theme()
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

    _code_js = mermaid_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  body {{ margin:0; padding:14px; background:{t["bg"]}; overflow:auto;
         font-family:'Segoe UI',sans-serif; }}
  #diagram svg {{ max-width:100% !important; height:auto; }}
  .dl-btn {{
    padding:4px 11px; border:1px solid {t["border"]}; border-radius:4px;
    cursor:pointer; font-size:12px; background:{t["card_bg"]}; color:{t["text"]};
    margin-right:6px;
  }}
  .dl-btn:hover {{ opacity:0.8; }}
</style></head><body>
<div id="btn-bar" style="display:none; margin-bottom:8px">
  <button class="dl-btn" id="btn-svg">&#11015; SVG</button>
  <button class="dl-btn" id="btn-png">&#11015; PNG</button>
</div>
<div id="diagram"></div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
mermaid.initialize({{
  startOnLoad: false,
  theme: "{t["mermaid"]}",
  er: {{ useMaxWidth: false, layoutDirection: "{direction}", diagramPadding: 24, entityPadding: 12 }},
  securityLevel: "loose"
}});
var _done = false;
var _svgStr = "";
var _code = `{_code_js}`;
async function _render() {{
  if (_done) return;
  if (document.body.offsetWidth === 0) {{ setTimeout(_render, 150); return; }}
  _done = true;
  try {{
    var r = await mermaid.render("er-svg", _code);
    _svgStr = r.svg;
    document.getElementById("diagram").innerHTML = _svgStr;
    document.getElementById("btn-bar").style.display = "block";
  }} catch(e) {{
    document.getElementById("diagram").innerHTML =
      "<pre style='color:salmon;white-space:pre-wrap'>" + e.message + "</pre>";
  }}
}}
_render();
document.getElementById("btn-svg").onclick = function() {{
  var blob = new Blob([_svgStr], {{type:"image/svg+xml;charset=utf-8"}});
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a"); a.href = url; a.download = "er_diagram.svg";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function() {{ URL.revokeObjectURL(url); }}, 1000);
}};
document.getElementById("btn-png").onclick = function() {{
  var svgEl = document.querySelector("#diagram svg");
  if (!svgEl) return;
  var w = svgEl.getBoundingClientRect().width || 1200;
  var h = svgEl.getBoundingClientRect().height || 800;
  var scale = 2;
  var canvas = document.createElement("canvas");
  canvas.width = Math.round(w * scale); canvas.height = Math.round(h * scale);
  var ctx = canvas.getContext("2d");
  ctx.fillStyle = "{t["bg"]}"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);
  var img = new Image();
  var blob = new Blob([_svgStr], {{type:"image/svg+xml;charset=utf-8"}});
  var url = URL.createObjectURL(blob);
  img.onload = function() {{
    try {{
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      var a = document.createElement("a");
      a.href = canvas.toDataURL("image/png"); a.download = "er_diagram.png";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    }} catch(e) {{ URL.revokeObjectURL(url); alert("PNG export failed — use SVG instead."); }}
  }};
  img.onerror = function() {{ URL.revokeObjectURL(url); alert("PNG export failed — use SVG instead."); }};
  img.src = url;
}};
</script>
</body></html>"""

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
    ("theme", "dark"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if "translations" not in st.session_state:
    st.session_state.translations = load_translations()

if "tags" not in st.session_state:
    st.session_state.tags = load_tags()

if "metadata" not in st.session_state:
    st.session_state.metadata = load_metadata()

# Log once per browser session
if "session_logged" not in st.session_state:
    st.session_state.session_logged = True
    log_event("session_start")

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


# ─── Usage event logging ──────────────────────────────────────────────────────
_cur_page = st.session_state.page
if st.session_state.get("_last_logged_page") != _cur_page:
    st.session_state["_last_logged_page"] = _cur_page
    log_event("page_view", {"page": _cur_page})

if _cur_page == "detail" and st.session_state.selected_table:
    _cur_tbl = st.session_state.selected_table
    if st.session_state.get("_last_logged_table") != _cur_tbl:
        st.session_state["_last_logged_table"] = _cur_tbl
        log_event("table_view", {"table": _cur_tbl})

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
        "changelog": "📋  Changelog",
        "usage":     "📈  Usage Stats",
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

    # Theme toggle
    st.markdown("---")
    theme_label = "☀️ Light Mode" if st.session_state.theme == "dark" else "🌙 Dark Mode"
    if st.button(theme_label, use_container_width=True, key="theme_toggle"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()

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
        "Search", placeholder="e.g. vendor, patient, ราคา, invoice amount",
        label_visibility="collapsed",
    )

    if query and query != st.session_state.get("_last_logged_query"):
        st.session_state["_last_logged_query"] = query
        log_event("search", {"query": query})

    # ── Advanced Filters ──────────────────────────────────────────────────────
    with st.expander("🔍 Advanced Filters", expanded=False):
        af1, af2, af3 = st.columns(3)
        with af1:
            adv_cert = st.multiselect(
                "Certification status", CERT_OPTIONS[1:], key="adv_cert",
                help="Filter tables by certification status"
            )
            adv_tags = st.multiselect(
                "Tags", PREDEFINED_TAGS, key="adv_tags",
                help="Filter tables that have all selected tags"
            )
        with af2:
            adv_has_fk = st.checkbox("Has FK relationships", key="adv_has_fk")
            adv_no_fk = st.checkbox("No FK (orphan tables)", key="adv_no_fk")
            adv_low_completeness = st.checkbox(
                "Low EN description (<50%)", key="adv_low_comp",
                help="Show tables where less than 50% of fields have English descriptions"
            )
        with af3:
            _all_field_types = sorted(
                fields["member_type"].dropna().astype(str)
                .apply(lambda x: simplify_iris_type(x)).unique().tolist()
            )
            adv_dtype = st.multiselect(
                "Field datatype", _all_field_types, key="adv_dtype",
                help="Filter fields by simplified datatype"
            )
            adv_missing_desc = st.checkbox(
                "Fields missing EN description", key="adv_missing_desc",
                help="Show only fields that have no English description"
            )
            adv_fk_fields_only = st.checkbox(
                "FK fields only", key="adv_fk_only",
                help="Show only fields that are foreign keys"
            )

    has_adv_filters = any([adv_cert, adv_tags, adv_has_fk, adv_no_fk, adv_low_completeness,
                           adv_dtype, adv_missing_desc, adv_fk_fields_only])

    if query or has_adv_filters:
        q = query.strip().lower()

        if q:
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
        else:
            matched_tables = tables.copy()
            matched_fields = fields.copy()

        # Apply table advanced filters
        if adv_cert:
            cert_tables = {
                tbl for tbl, meta in st.session_state.metadata.items()
                if meta.get("certification", "") in adv_cert
            }
            matched_tables = matched_tables[matched_tables["sql_table_name"].isin(cert_tables)]

        if adv_tags:
            tag_tables = {
                tbl for tbl, tlist in st.session_state.tags.items()
                if all(tag in tlist for tag in adv_tags)
            }
            matched_tables = matched_tables[matched_tables["sql_table_name"].isin(tag_tables)]

        if adv_has_fk:
            fk_res = fk[fk["resolve_status"] == "resolved"]
            tbls_with_fk = set(fk_res["source_sql_table_name"]) | set(fk_res["target_sql_table_name"])
            matched_tables = matched_tables[matched_tables["sql_table_name"].isin(tbls_with_fk)]

        if adv_no_fk:
            fk_res = fk[fk["resolve_status"] == "resolved"]
            tbls_with_fk = set(fk_res["source_sql_table_name"]) | set(fk_res["target_sql_table_name"])
            matched_tables = matched_tables[~matched_tables["sql_table_name"].isin(tbls_with_fk)]

        if adv_low_completeness:
            low_tbls = {cn for cn, pct in COMPLETENESS.items() if pct < 50}
            matched_tables = matched_tables[matched_tables["class_name"].isin(low_tbls)]

        # Apply field advanced filters
        if adv_dtype:
            matched_fields = matched_fields[
                matched_fields["member_type"].astype(str).apply(simplify_iris_type).isin(adv_dtype)
            ]

        if adv_missing_desc:
            matched_fields = matched_fields[
                matched_fields["description"].astype(str).str.strip().isin(["", "nan"])
            ]

        if adv_fk_fields_only:
            fk_res = fk[fk["resolve_status"] == "resolved"]
            fk_field_keys = set(zip(fk_res["source_class_name"], fk_res["source_sql_field_name"]))
            matched_fields = matched_fields[
                matched_fields.apply(
                    lambda r: (r["class_name"], r["sql_field_name"]) in fk_field_keys, axis=1
                )
            ]

        # Also search Thai translations (text query only)
        tbl_map = tables.set_index("class_name")["sql_table_name"].to_dict()
        th_df = pd.DataFrame()
        if q:
            th_hits = []
            for class_nm, field_dict in st.session_state.translations.items():
                for field_nm, thai_txt in field_dict.items():
                    if q in str(thai_txt).lower():
                        th_hits.append({"class_name": class_nm, "sql_field_name": field_nm, "thai_text": thai_txt})
            if th_hits:
                th_df = pd.DataFrame(th_hits)
                th_df["Table"] = th_df["class_name"].map(tbl_map)
                th_df = th_df.merge(
                    fields[["class_name", "sql_field_name", "description", "member_type"]],
                    on=["class_name", "sql_field_name"], how="left",
                )
                th_field_keys = set(zip(th_df["class_name"], th_df["sql_field_name"]))
                existing_keys = set(zip(matched_fields["class_name"], matched_fields["sql_field_name"]))
                new_keys = th_field_keys - existing_keys
                new_rows = th_df[th_df.apply(lambda r: (r["class_name"], r["sql_field_name"]) in new_keys, axis=1)]
                if not new_rows.empty:
                    matched_fields = pd.concat([matched_fields, new_rows[matched_fields.columns]], ignore_index=True)

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
                disp["Certification"] = disp["Table"].map(
                    lambda t: st.session_state.metadata.get(t, {}).get("certification", "")
                )
                disp["Owner"] = disp["Table"].map(
                    lambda t: st.session_state.metadata.get(t, {}).get("owner", "")
                )
                evt = st.dataframe(disp, width="stretch", hide_index=True,
                                   selection_mode="single-row", on_select="rerun",
                                   key="search_t_sel")
                if evt.selection.rows:
                    nav("detail", table=matched_tables.iloc[evt.selection.rows[0]]["sql_table_name"])

        with tab_f:
            if matched_fields.empty:
                st.info("No fields matched.")
            else:
                matched_fields = matched_fields.copy()
                matched_fields["Table"] = matched_fields["class_name"].map(tbl_map)
                # Attach Thai text column
                def _get_thai(row):
                    return st.session_state.translations.get(
                        row["class_name"], {}
                    ).get(str(row["sql_field_name"]), "")
                matched_fields["TH Description"] = matched_fields.apply(_get_thai, axis=1)
                matched_fields["Datatype"] = matched_fields["member_type"].astype(str).apply(simplify_iris_type)
                disp = matched_fields[
                    ["sql_field_name", "Table", "Datatype", "description", "member_type", "TH Description"]
                ].rename(columns={
                    "sql_field_name": "Field", "description": "EN Description", "member_type": "IRIS Type",
                }).copy()
                disp["IRIS Type"] = disp["IRIS Type"].str[:60]
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

    col_m, col_f, col_tag, col_cert = st.columns([2, 3, 2, 2])
    with col_m:
        sel_module = st.selectbox("Module", module_options, index=default_mod_idx, key="browse_mod_select")
        st.session_state.browse_module = sel_module
    with col_f:
        name_filter = st.text_input("Filter by table name", value=st.session_state.browse_filter,
                                    placeholder="e.g. vendor", key="browse_name_filter")
        st.session_state.browse_filter = name_filter
    with col_tag:
        tag_filter = st.selectbox("Filter by tag", ["All"] + PREDEFINED_TAGS, key="browse_tag_filter")
    with col_cert:
        cert_filter = st.selectbox(
            "Filter by certification", ["All"] + CERT_OPTIONS[1:], key="browse_cert_filter"
        )

    filtered = tables.copy()
    if sel_module != "All modules":
        filtered = filtered[filtered["module_name"] == sel_module]
    if name_filter.strip():
        filtered = filtered[
            filtered["sql_table_name"].str.lower().str.contains(name_filter.strip().lower(), na=False)
        ]
    if tag_filter != "All":
        tag_tables = {tbl for tbl, tlist in st.session_state.tags.items() if tag_filter in tlist}
        filtered = filtered[filtered["sql_table_name"].isin(tag_tables)]
    if cert_filter != "All":
        cert_tables = {
            tbl for tbl, meta in st.session_state.metadata.items()
            if meta.get("certification", "") == cert_filter
        }
        filtered = filtered[filtered["sql_table_name"].isin(cert_tables)]
    filtered = filtered.sort_values("sql_table_name").reset_index(drop=True)

    st.caption(f"{len(filtered):,} tables")

    disp = filtered[
        ["sql_table_name", "module_prefix", "module_name", "class_description", "class_name"]
    ].copy()
    disp["Completeness"] = disp["class_name"].map(COMPLETENESS).fillna(0).astype(int)
    disp["Tags"] = disp["sql_table_name"].map(
        lambda t: ", ".join(st.session_state.tags.get(t, []))
    )
    disp["Certification"] = disp["sql_table_name"].map(
        lambda t: st.session_state.metadata.get(t, {}).get("certification", "")
    )
    disp["Owner"] = disp["sql_table_name"].map(
        lambda t: st.session_state.metadata.get(t, {}).get("owner", "")
    )
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
                # Module badges
                badge_html = (
                    f'<span class="badge badge-purple">{tbl_row["module_prefix"]}</span>'
                    f'<span class="badge">{tbl_row["module_name"]}</span>'
                )
                # Tag badges
                tbl_tags = st.session_state.tags.get(tbl_name, [])
                for tag in tbl_tags:
                    cls, _ = TAG_COLORS.get(tag, ("badge", "#7eb8f7"))
                    badge_html += f'<span class="badge {cls}">{tag}</span>'
                # Certification badge
                tbl_meta = st.session_state.metadata.get(tbl_name, {})
                cert = tbl_meta.get("certification", "")
                if cert:
                    cert_cls, _ = CERT_COLORS.get(cert, ("badge", "#7eb8f7"))
                    badge_html += f'<span class="badge {cert_cls}">✓ {cert}</span>'
                st.markdown(badge_html, unsafe_allow_html=True)

                # Owner / steward / contact row
                owner   = tbl_meta.get("owner", "")
                steward = tbl_meta.get("steward", "")
                contact = tbl_meta.get("contact", "")
                refresh_freq = tbl_meta.get("update_frequency", "")
                last_refresh = tbl_meta.get("last_refresh", "")
                meta_parts = []
                if owner:
                    meta_parts.append(f"👤 **Owner:** {owner}")
                if steward:
                    meta_parts.append(f"🛡️ **Steward:** {steward}")
                if contact:
                    meta_parts.append(f"📧 **Contact:** {contact}")
                if refresh_freq:
                    meta_parts.append(f"🔄 **Frequency:** {refresh_freq}")
                if last_refresh:
                    meta_parts.append(f"📅 **Last refresh:** {last_refresh}")
                if meta_parts:
                    st.markdown("  ·  ".join(meta_parts))

                st.caption(f"🔗 Share: `?table={tbl_name}`")

                # Tag management
                with st.expander("🏷️ Manage Tags"):
                    tc1, tc2 = st.columns([3, 1])
                    with tc1:
                        new_tag = st.selectbox(
                            "Add tag", [t for t in PREDEFINED_TAGS if t not in tbl_tags],
                            key=f"tag_add_sel_{tbl_name}",
                        )
                    with tc2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("Add", key=f"tag_add_btn_{tbl_name}", use_container_width=True):
                            tbl_tags = list(tbl_tags) + [new_tag]
                            st.session_state.tags[tbl_name] = tbl_tags
                            save_tags(st.session_state.tags)
                            append_changelog("tag_added", tbl_name, f"Added tag: {new_tag}")
                            st.rerun()
                    if tbl_tags:
                        st.markdown("**Current tags:**")
                        for tag in tbl_tags:
                            rm_col, lbl_col = st.columns([1, 5])
                            with rm_col:
                                if st.button("✕", key=f"tag_rm_{tbl_name}_{tag}"):
                                    updated = [t for t in tbl_tags if t != tag]
                                    st.session_state.tags[tbl_name] = updated
                                    save_tags(st.session_state.tags)
                                    append_changelog("tag_removed", tbl_name, f"Removed tag: {tag}")
                                    st.rerun()
                            with lbl_col:
                                st.markdown(f"`{tag}`")

                # Metadata management
                with st.expander("📊 Manage Metadata"):
                    cur_meta = st.session_state.metadata.get(tbl_name, {})
                    mc1, mc2 = st.columns(2)
                    with mc1:
                        m_owner = st.text_input(
                            "Data Owner", value=cur_meta.get("owner", ""),
                            key=f"meta_owner_{tbl_name}",
                            placeholder="e.g. Finance Team",
                        )
                        m_steward = st.text_input(
                            "Data Steward", value=cur_meta.get("steward", ""),
                            key=f"meta_steward_{tbl_name}",
                            placeholder="e.g. Jane Smith",
                        )
                        m_contact = st.text_input(
                            "Contact", value=cur_meta.get("contact", ""),
                            key=f"meta_contact_{tbl_name}",
                            placeholder="e.g. jane@company.com",
                        )
                    with mc2:
                        cert_idx = CERT_OPTIONS.index(cur_meta.get("certification", "")) if cur_meta.get("certification", "") in CERT_OPTIONS else 0
                        m_cert = st.selectbox(
                            "Certification Status", CERT_OPTIONS,
                            index=cert_idx,
                            key=f"meta_cert_{tbl_name}",
                        )
                        freq_idx = UPDATE_FREQ_OPTIONS.index(cur_meta.get("update_frequency", "")) if cur_meta.get("update_frequency", "") in UPDATE_FREQ_OPTIONS else 0
                        m_freq = st.selectbox(
                            "Update Frequency", UPDATE_FREQ_OPTIONS,
                            index=freq_idx,
                            key=f"meta_freq_{tbl_name}",
                        )
                        m_refresh = st.text_input(
                            "Last Refresh Date", value=cur_meta.get("last_refresh", ""),
                            key=f"meta_refresh_{tbl_name}",
                            placeholder="e.g. 2026-04-01",
                        )
                    if st.button("💾 Save Metadata", key=f"meta_save_{tbl_name}", type="primary"):
                        new_meta = {
                            "owner": m_owner.strip(),
                            "steward": m_steward.strip(),
                            "contact": m_contact.strip(),
                            "certification": m_cert,
                            "update_frequency": m_freq,
                            "last_refresh": m_refresh.strip(),
                        }
                        # Remove empty values
                        new_meta = {k: v for k, v in new_meta.items() if v}
                        st.session_state.metadata[tbl_name] = new_meta
                        save_metadata(st.session_state.metadata)
                        append_changelog("metadata_saved", tbl_name,
                            f"cert={new_meta.get('certification','')}, owner={new_meta.get('owner','')}, freq={new_meta.get('update_frequency','')}")
                        st.success("Metadata saved.")
                        st.rerun()

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
            # field → target PK
            fk_pk_map = (
                resolved_fk[resolved_fk["source_sql_field_name"] != ""]
                .set_index("source_sql_field_name")["target_pk_fields"]
                .to_dict()
            )

            # ── Tabs ────────────────────────────────────────────────────────

            tab_schema, tab_sql, tab_translate, tab_fk_er, tab_lineage = st.tabs(
                ["📋 Schema", "⚙️ SQL Builder", "🇹🇭 Thai Descriptions", "📐 FK Diagram", "🔗 Lineage"]
            )

            # ── TAB 1: Schema ────────────────────────────────────────────────

            with tab_schema:
                st.subheader("Columns")
                if not tbl_fields.empty:
                    col_rows = []
                    for _, fr in tbl_fields.iterrows():
                        sf = str(fr["sql_field_name"])
                        iris_type = str(fr["member_type"])
                        ref = fk_map.get(sf, "")
                        ref_pk = fk_pk_map.get(sf, "")
                        ref_display = f"{ref}.{ref_pk}" if ref and ref_pk and ref_pk not in ("", "nan") else ref
                        col_rows.append({
                            "Field": sf,
                            "IRIS Type": iris_type[:60],
                            "MSSQL Type": iris_to_mssql(iris_type),
                            "Description": str(fr["description"]),
                            "FK Reference →": ref_display,
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
                        # Include direct FK fields AND _DR display fields mapped to their base
                        ref_in_chosen = []
                        for f in chosen:
                            if f in fk_map:
                                ref_in_chosen.append((f, fk_map[f], f))
                            elif f.endswith("_DR") and f[:-3] in fk_map:
                                base = f[:-3]
                                ref_in_chosen.append((f, fk_map[base], base))

                        if ref_in_chosen:
                            with st.expander(f"Arrow syntax examples ({len(ref_in_chosen)} reference fields)"):
                                st.markdown(
                                    "IRIS SQL lets you traverse object references directly "
                                    "using `->`. Click-to-copy examples below:"
                                )
                                for chosen_field, target_tbl, arrow_field in ref_in_chosen:
                                    tgt_row = tables[tables["sql_table_name"] == target_tbl]
                                    if tgt_row.empty:
                                        continue
                                    tgt_class = tgt_row.iloc[0]["class_name"]
                                    tgt_fields = (
                                        fields[fields["class_name"] == tgt_class]["sql_field_name"]
                                        .head(4).tolist()
                                    )
                                    if tgt_fields:
                                        arrow_parts = ", ".join(f"{arrow_field}->{tf}" for tf in tgt_fields)
                                        if chosen_field != arrow_field:
                                            comment = f"-- {chosen_field} is display repr of {arrow_field} → references {target_tbl}"
                                        else:
                                            comment = f"-- {chosen_field} → references {target_tbl}"
                                        st.code(
                                            f"{comment}\nSELECT {arrow_parts}\nFROM {tbl_name}",
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
                        append_changelog(
                            "translation_saved", tbl_name,
                            f"Saved {len(new_trans)} Thai descriptions"
                        )
                        st.success(f"Saved {len(new_trans)} Thai descriptions for **{tbl_name}**.")
                        st.rerun()

            # ── TAB 4: FK Diagram ────────────────────────────────────────────

            with tab_fk_er:
                st.subheader("FK Diagram")
                st.markdown(
                    "Entity-relationship diagram showing **FK links** for this table — "
                    "outgoing references (→) and incoming references (←)."
                )

                fk_res_all = fk[fk["resolve_status"] == "resolved"]

                out_tbls = sorted(fk_res_all[
                    (fk_res_all["source_sql_table_name"] == tbl_name)
                    & (fk_res_all["source_sql_field_name"] != "")
                ]["target_sql_table_name"].unique().tolist())

                in_tbls = sorted(fk_res_all[
                    (fk_res_all["target_sql_table_name"] == tbl_name)
                    & (fk_res_all["source_sql_field_name"] != "")
                ]["source_sql_table_name"].unique().tolist())

                fk_ec1, fk_ec2, fk_ec3 = st.columns([2, 2, 3])
                with fk_ec1:
                    fk_include = st.radio(
                        "Show",
                        [
                            "Outgoing + Incoming",
                            "Outgoing only",
                            "Incoming only",
                            "Split view (Outgoing | Incoming)",
                        ],
                        horizontal=False,
                        key=f"fk_er_dir_{tbl_name}",
                    )
                with fk_ec2:
                    fk_show_fields = st.checkbox(
                        "Show fields", value=False, key=f"fk_er_fields_{tbl_name}"
                    )
                    fk_max_fields = st.number_input(
                        "Max fields/table", min_value=3, max_value=30, value=6,
                        step=1, key=f"fk_er_maxf_{tbl_name}",
                        disabled=not fk_show_fields,
                    )
                with fk_ec3:
                    fk_er_dir = st.radio(
                        "Layout", ["LR", "TB"],
                        horizontal=True,
                        key=f"fk_er_layout_{tbl_name}",
                        help="LR = left-to-right, TB = top-to-bottom",
                    )
                    fk_max_entities = st.slider(
                        "Max entities per diagram", min_value=5, max_value=100,
                        value=25, step=5,
                        key=f"fk_er_maxent_{tbl_name}",
                        help="Raise this to show more tables; lower it to keep the diagram readable.",
                    )

                st.caption(
                    f"**{tbl_name}** → outgoing FK to **{len(out_tbls)}** table(s) · "
                    f"incoming FK from **{len(in_tbls)}** table(s)"
                )

                # ── Split view: two diagrams side by side ──
                if fk_include == "Split view (Outgoing | Incoming)":
                    if not out_tbls and not in_tbls:
                        st.info("No FK relationships found for this table.")
                    else:
                        sv_col_out, sv_col_in = st.columns(2)

                        with sv_col_out:
                            st.markdown("**↗ Outgoing**")
                            out_candidates = [tbl_name] + out_tbls[:fk_max_entities - 1]
                            _out_trunc = len(out_tbls) >= fk_max_entities
                            if _out_trunc:
                                st.warning(
                                    f"Showing {fk_max_entities} of {len(out_tbls) + 1} — "
                                    "raise the slider to see more."
                                )
                            if len(out_candidates) == 1:
                                st.info("No outgoing FK.")
                            else:
                                _html, _code = build_er_mermaid(
                                    out_candidates,
                                    include_fields=fk_show_fields,
                                    max_fields=int(fk_max_fields),
                                    cross_module=False,
                                    direction=fk_er_dir,
                                )
                                components.html(_html, height=560, scrolling=True)
                                with st.expander("Raw Mermaid (Outgoing)"):
                                    st.code(_code, language="text")

                        with sv_col_in:
                            st.markdown("**↙ Incoming**")
                            in_candidates = [tbl_name] + in_tbls[:fk_max_entities - 1]
                            _in_trunc = len(in_tbls) >= fk_max_entities
                            if _in_trunc:
                                st.warning(
                                    f"Showing {fk_max_entities} of {len(in_tbls) + 1} — "
                                    "raise the slider to see more."
                                )
                            if len(in_candidates) == 1:
                                st.info("No incoming FK.")
                            else:
                                _html, _code = build_er_mermaid(
                                    in_candidates,
                                    include_fields=fk_show_fields,
                                    max_fields=int(fk_max_fields),
                                    cross_module=False,
                                    direction=fk_er_dir,
                                )
                                components.html(_html, height=560, scrolling=True)
                                with st.expander("Raw Mermaid (Incoming)"):
                                    st.code(_code, language="text")

                # ── Single diagram view ──
                else:
                    if fk_include == "Outgoing only":
                        candidate_tables = list({tbl_name} | set(out_tbls))
                    elif fk_include == "Incoming only":
                        candidate_tables = list({tbl_name} | set(in_tbls))
                    else:
                        candidate_tables = list({tbl_name} | set(out_tbls) | set(in_tbls))

                    _truncated = False
                    if len(candidate_tables) > fk_max_entities:
                        _truncated = True
                        _pool = [t for t in out_tbls if t != tbl_name] + [t for t in in_tbls if t != tbl_name]
                        _seen: set = set()
                        _ordered = []
                        for t in _pool:
                            if t not in _seen:
                                _seen.add(t)
                                _ordered.append(t)
                        candidate_tables = [tbl_name] + _ordered[:fk_max_entities - 1]

                    if _truncated:
                        st.warning(
                            f"Showing **{fk_max_entities}** of **{len(out_tbls) + len(in_tbls) + 1}** entities — "
                            "raise the slider or switch to **Split view** to see both sides in full."
                        )

                    if len(candidate_tables) == 1:
                        st.info("No FK relationships found for this table.")
                    else:
                        fk_er_html, fk_er_code = build_er_mermaid(
                            candidate_tables,
                            include_fields=fk_show_fields,
                            max_fields=int(fk_max_fields),
                            cross_module=False,
                            direction=fk_er_dir,
                        )
                        components.html(fk_er_html, height=620, scrolling=True)
                        with st.expander("Raw Mermaid code  ·  paste into mermaid.live or Notion"):
                            st.code(fk_er_code, language="text")

            # ── TAB 5: Lineage ───────────────────────────────────────────────

            with tab_lineage:
                st.subheader("Column-level Lineage")
                st.markdown(
                    "Shows the exact field-to-field paths for FK relationships — "
                    "which field in this table references which PK in the target table, "
                    "and which fields in other tables point here."
                )

                lin_col1, lin_col2 = st.columns(2)

                # ── Upstream: fields in THIS table that are FKs
                with lin_col1:
                    st.markdown("### ↗ Upstream (Outgoing FK)")
                    st.caption(f"Fields in **{tbl_name}** that reference other tables")

                    if resolved_fk.empty:
                        st.info("No outgoing FK relationships.")
                    else:
                        up_rows = []
                        for _, r in resolved_fk.iterrows():
                            src_field = str(r["source_sql_field_name"])
                            if src_field in ("", "nan"):
                                src_field = str(r["source_member_name"])
                            tgt_tbl = str(r["target_sql_table_name"])
                            tgt_pk  = str(r["target_pk_fields"])
                            # Get IRIS type of the source field
                            src_f_row = tbl_fields[tbl_fields["sql_field_name"] == src_field]
                            src_type = iris_to_mssql(str(src_f_row.iloc[0]["member_type"])) if not src_f_row.empty else ""
                            up_rows.append({
                                "This Field": src_field,
                                "MSSQL Type": src_type,
                                "→ Target Table": tgt_tbl,
                                "→ Target PK": tgt_pk if tgt_pk != "nan" else "",
                                "Cardinality": str(r.get("relationship_cardinality", "")),
                            })
                        up_df = pd.DataFrame(up_rows).drop_duplicates()
                        up_evt = st.dataframe(
                            up_df, width="stretch", hide_index=True,
                            selection_mode="single-row", on_select="rerun",
                            key=f"lin_up_{tbl_name}",
                        )
                        if up_evt.selection.rows:
                            nav("detail", table=up_df.iloc[up_evt.selection.rows[0]]["→ Target Table"])

                # ── Downstream: fields in OTHER tables that reference THIS table
                with lin_col2:
                    st.markdown("### ↙ Downstream (Incoming FK)")
                    st.caption(f"Fields in other tables that reference **{tbl_name}**")

                    if incoming.empty:
                        st.info("No incoming FK relationships.")
                    else:
                        down_rows = []
                        for _, r in incoming.iterrows():
                            src_tbl_row = tables[tables["class_name"] == r["source_class_name"]]
                            src_tbl_name = src_tbl_row.iloc[0]["sql_table_name"] if not src_tbl_row.empty else str(r["source_class_name"])
                            src_field = str(r["source_sql_field_name"])
                            if src_field in ("", "nan"):
                                src_field = str(r["source_member_name"])
                            # Get MSSQL type of source field
                            src_frow = fields[
                                (fields["class_name"] == r["source_class_name"]) &
                                (fields["sql_field_name"] == src_field)
                            ]
                            src_type = iris_to_mssql(str(src_frow.iloc[0]["member_type"])) if not src_frow.empty else ""
                            tgt_pk = str(r["target_pk_fields"])
                            down_rows.append({
                                "Source Table": src_tbl_name,
                                "Source Field": src_field,
                                "MSSQL Type": src_type,
                                "→ This PK": tgt_pk if tgt_pk != "nan" else "",
                                "Cardinality": str(r.get("relationship_cardinality", "")),
                            })
                        down_df = pd.DataFrame(down_rows).drop_duplicates()
                        down_evt = st.dataframe(
                            down_df, width="stretch", hide_index=True,
                            selection_mode="single-row", on_select="rerun",
                            key=f"lin_down_{tbl_name}",
                        )
                        if down_evt.selection.rows:
                            nav("detail", table=down_df.iloc[down_evt.selection.rows[0]]["Source Table"])

                # ── Type reference summary
                st.markdown("---")
                st.subheader("Field Type Reference")
                st.caption("IRIS types and their MS SQL Server equivalents for all fields in this table.")
                if not tbl_fields.empty:
                    type_rows = []
                    for _, fr in tbl_fields.iterrows():
                        iris_t = str(fr["member_type"])
                        type_rows.append({
                            "Field": str(fr["sql_field_name"]),
                            "IRIS Type": iris_t[:80],
                            "MS SQL Type": iris_to_mssql(iris_t),
                        })
                    st.dataframe(pd.DataFrame(type_rows), width="stretch", hide_index=True)

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
    t = _theme()
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
                paper_bgcolor=t["plotly_bg"], plot_bgcolor=t["plotly_bg"],
                font=dict(color=t["plotly_font"], size=11),
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
            paper_bgcolor=t["plotly_bg"], plot_bgcolor=t["plotly_bg"],
            font=dict(color=t["plotly_font"]),
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
                paper_bgcolor=t["plotly_bg"], plot_bgcolor=t["plotly_bg"],
                font=dict(color=t["plotly_font"]),
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
            show_fields = st.checkbox("Show fields", value=False, key="er_show_fields")
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

# ─── USAGE STATS ─────────────────────────────────────────────────────────────

elif st.session_state.page == "usage":
    t = _theme()
    st.title("📈 Usage Stats")
    st.markdown("Usage events recorded from this browser session and all previous sessions.")

    raw_log = load_usage_log()

    if not raw_log:
        st.info("No usage data yet. Start browsing to record events.")
    else:
        log_df = pd.DataFrame(raw_log)
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"])
        log_df["date"] = log_df["timestamp"].dt.date

        sessions  = log_df[log_df["event"] == "session_start"]
        pviews    = log_df[log_df["event"] == "page_view"]
        tviews    = log_df[log_df["event"] == "table_view"]
        searches  = log_df[log_df["event"] == "search"]

        # ── Summary metrics
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Sessions", f"{len(sessions):,}")
        mc2.metric("Page Views", f"{len(pviews):,}")
        mc3.metric("Table Views", f"{len(tviews):,}")
        mc4.metric("Searches", f"{len(searches):,}")

        st.markdown("---")

        chart_col1, chart_col2 = st.columns(2)

        # ── Sessions per day (last 30 days)
        with chart_col1:
            st.subheader("Sessions per Day")
            if not sessions.empty:
                sess_by_day = (
                    sessions.groupby("date").size()
                    .reset_index(name="count")
                    .sort_values("date")
                    .tail(30)
                )
                fig_sess = px.bar(
                    sess_by_day, x="date", y="count",
                    labels={"date": "Date", "count": "Sessions"},
                    color_discrete_sequence=["#4c6ef5"],
                )
                fig_sess.update_layout(
                    paper_bgcolor=t["plotly_bg"], plot_bgcolor=t["plotly_bg"],
                    font=dict(color=t["plotly_font"]),
                    margin=dict(l=10, r=10, t=10, b=10), height=260,
                )
                st.plotly_chart(fig_sess, use_container_width=True)
            else:
                st.info("No session data yet.")

        # ── Feature usage (page_view breakdown)
        with chart_col2:
            st.subheader("Feature Usage")
            if not pviews.empty:
                page_counts = (
                    pviews["details"].apply(lambda d: d.get("page", "unknown"))
                    .value_counts().reset_index()
                )
                page_counts.columns = ["Page", "Views"]
                fig_pages = px.pie(
                    page_counts, names="Page", values="Views",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                    hole=0.4,
                )
                fig_pages.update_layout(
                    paper_bgcolor=t["plotly_bg"],
                    font=dict(color=t["plotly_font"]),
                    margin=dict(l=10, r=10, t=10, b=10), height=260,
                    showlegend=True,
                )
                st.plotly_chart(fig_pages, use_container_width=True)
            else:
                st.info("No page view data yet.")

        st.markdown("---")

        chart_col3, chart_col4 = st.columns(2)

        # ── Top 15 tables viewed
        with chart_col3:
            st.subheader("Top Tables Viewed")
            if not tviews.empty:
                tbl_counts = (
                    tviews["details"].apply(lambda d: d.get("table", "unknown"))
                    .value_counts().head(15).reset_index()
                )
                tbl_counts.columns = ["Table", "Views"]
                fig_tbl = px.bar(
                    tbl_counts, x="Views", y="Table", orientation="h",
                    color_discrete_sequence=["#6fcf97"],
                )
                fig_tbl.update_layout(
                    paper_bgcolor=t["plotly_bg"], plot_bgcolor=t["plotly_bg"],
                    font=dict(color=t["plotly_font"]),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=max(260, len(tbl_counts) * 26),
                )
                st.plotly_chart(fig_tbl, use_container_width=True)
            else:
                st.info("No table view data yet.")

        # ── Top searches
        with chart_col4:
            st.subheader("Top Searches")
            if not searches.empty:
                q_counts = (
                    searches["details"].apply(lambda d: d.get("query", ""))
                    .value_counts().head(15).reset_index()
                )
                q_counts.columns = ["Query", "Count"]
                fig_q = px.bar(
                    q_counts, x="Count", y="Query", orientation="h",
                    color_discrete_sequence=["#f7a96f"],
                )
                fig_q.update_layout(
                    paper_bgcolor=t["plotly_bg"], plot_bgcolor=t["plotly_bg"],
                    font=dict(color=t["plotly_font"]),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=max(260, len(q_counts) * 26),
                )
                st.plotly_chart(fig_q, use_container_width=True)
            else:
                st.info("No search data yet.")

        # ── Recent activity
        st.markdown("---")
        st.subheader("Recent Activity")
        recent = log_df.sort_values("timestamp", ascending=False).head(50)
        recent_disp = recent[["timestamp", "event", "details"]].copy()
        recent_disp["details"] = recent_disp["details"].apply(
            lambda d: ", ".join(f"{k}: {v}" for k, v in d.items()) if d else ""
        )
        recent_disp.columns = ["Timestamp", "Event", "Details"]
        st.dataframe(recent_disp, width="stretch", hide_index=True)


# ─── CHANGELOG ───────────────────────────────────────────────────────────────

elif st.session_state.page == "changelog":
    st.title("📋 Changelog")
    st.markdown(
        "Audit log of all changes made through this tool — Thai translations saved, "
        "tags added or removed."
    )

    log = load_changelog()

    if not log:
        st.info("No changelog entries yet. Changes will appear here once you save translations or manage tags.")
    else:
        # Filter controls
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            action_options = ["All"] + sorted({e["action"] for e in log})
            log_action = st.selectbox("Filter by action", action_options, key="cl_action")
        with fc2:
            table_options = ["All"] + sorted({e["table"] for e in log if e["table"]})
            log_table = st.selectbox("Filter by table", table_options, key="cl_table")
        with fc3:
            log_search = st.text_input("Search details", placeholder="e.g. PII, 5 Thai", key="cl_search")

        filtered_log = log
        if log_action != "All":
            filtered_log = [e for e in filtered_log if e["action"] == log_action]
        if log_table != "All":
            filtered_log = [e for e in filtered_log if e["table"] == log_table]
        if log_search.strip():
            qs = log_search.strip().lower()
            filtered_log = [e for e in filtered_log if qs in str(e.get("details", "")).lower() or qs in str(e.get("table", "")).lower()]

        st.caption(f"**{len(filtered_log)}** entries")

        log_df = pd.DataFrame(filtered_log)
        if not log_df.empty:
            log_df = log_df[["timestamp", "action", "table", "details"]]
            log_df.columns = ["Timestamp", "Action", "Table", "Details"]
            cl_evt = st.dataframe(
                log_df, width="stretch", hide_index=True,
                selection_mode="single-row", on_select="rerun", key="cl_sel",
            )
            if cl_evt.selection.rows:
                selected_tbl = filtered_log[cl_evt.selection.rows[0]].get("table", "")
                if selected_tbl and selected_tbl in set(tables["sql_table_name"]):
                    nav("detail", table=selected_tbl)

        # Clear changelog
        st.markdown("---")
        if st.button("🗑️ Clear all changelog entries", type="secondary", key="cl_clear"):
            with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)
            st.success("Changelog cleared.")
            st.rerun()
