"""config.py — Centralised application configuration.

Reads config.toml from the project root and exposes typed constants.
All constants fall back to sensible defaults so the app never fails to
start when config.toml is missing or a key is absent.

Usage
-----
    from config import APP_NAME, PREDEFINED_TAGS, MAX_CHANGELOG_ENTRIES, ...

Do NOT store secrets here.  Secrets (admin_passcode, database_url) belong
in .streamlit/secrets.toml which is git-ignored.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# ── TOML loader (stdlib on 3.11+, optional dep on 3.8–3.10) ──────────────────
try:
    import tomllib          # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib   # pip install tomli
    except ImportError:
        tomllib = None  # type: ignore

_CONFIG_PATH = Path(__file__).parent / "config.toml"


def _load() -> dict:
    if tomllib is None or not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


_cfg: dict = _load()


def _get(path: str, default: Any) -> Any:
    """Dot-notation getter with per-key default fallback."""
    parts = path.split(".")
    node: Any = _cfg
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


# ── App identity ──────────────────────────────────────────────────────────────
APP_NAME            = _get("app.name",        "Siriraj IRIS Data Dictionary")
APP_VERSION         = _get("app.version",     "v1.0")
APP_ENV             = _get("app.environment", "PROD")
PAGE_TITLE          = _get("app.page_title",  "IRIS Data Dictionary")
PAGE_ICON           = _get("app.page_icon",   "🗂️")
LOGO_FILE           = _get("app.logo_file",   "logo_banner.png")
REQUEST_CHANGE_URL  = _get("app.links.request_change_url",
                           "https://forms.gle/2ZXk5qw24ofLPP9t5")

# ── Data source ───────────────────────────────────────────────────────────────
EXCEL_FILE          = _get("data.excel_file", "iris_data_dict.xlsx")

# ── Storage file paths ────────────────────────────────────────────────────────
TRANSLATIONS_FILE   = _get("storage.translations_file", "translations.json")
TAGS_FILE           = _get("storage.tags_file",         "tags.json")
CHANGELOG_FILE      = _get("storage.changelog_file",    "changelog.json")
METADATA_FILE       = _get("storage.metadata_file",     "metadata.json")
USAGE_LOG_FILE      = _get("storage.usage_log_file",    "usage_log.json")

# ── Capacity limits ───────────────────────────────────────────────────────────
MAX_CHANGELOG_ENTRIES    = int(_get("limits.max_changelog_entries",    1000))
MAX_USAGE_LOG_ENTRIES    = int(_get("limits.max_usage_log_entries",   10000))
MAX_RECENTLY_VIEWED      = int(_get("limits.max_recently_viewed",         10))
NOTIFICATION_WINDOW_DAYS = int(_get("limits.notification_window_days",    7))
MAX_CUSTOM_TAG_CHARS     = int(_get("limits.max_custom_tag_chars",        40))

# ── UI — FK Diagram tab ───────────────────────────────────────────────────────
FK_MAX_ENTITIES_DEFAULT  = int(_get("ui.diagram.fk_max_entities_default",  25))
FK_MAX_ENTITIES_MAX      = int(_get("ui.diagram.fk_max_entities_max",     250))
FK_MAX_ENTITIES_STEP     = int(_get("ui.diagram.fk_max_entities_step",      5))
FK_MAX_FIELDS_DEFAULT    = int(_get("ui.diagram.fk_max_fields_default",     6))
ER_MAX_FIELDS_DEFAULT    = int(_get("ui.diagram.er_max_fields_default",     8))
CYTOSCAPE_HEIGHT         = int(_get("ui.diagram.cytoscape_height",        640))

# ── UI — Analytics page ───────────────────────────────────────────────────────
HUB_TOP_N_DEFAULT        = int(_get("ui.analytics.hub_top_n_default",      20))
MODULE_TOP_N_DEFAULT     = int(_get("ui.analytics.module_top_n_default",   12))
MIN_REFS_DEFAULT         = int(_get("ui.analytics.min_refs_default",        3))

# ── UI — Browse page ──────────────────────────────────────────────────────────
COMPLETENESS_LOW_THRESHOLD = int(_get("ui.browse.completeness_low_threshold", 50))

# ── Session state defaults ────────────────────────────────────────────────────
DEFAULT_PAGE          = _get("defaults.page",          "home")
DEFAULT_MODULE_FILTER = _get("defaults.module_filter", "All modules")
DEFAULT_THEME         = _get("defaults.theme",         "dark")

# ── Tags ──────────────────────────────────────────────────────────────────────
PREDEFINED_TAGS: list[str] = list(_get("tags.predefined", [
    "PII", "financial", "deprecated", "master-data",
    "staging", "lookup", "audit", "critical",
]))

# ── Metadata option lists ─────────────────────────────────────────────────────
CERT_OPTIONS: list[str] = list(_get("metadata.cert_options", [
    "", "Certified", "Draft", "Deprecated", "Experimental",
]))
UPDATE_FREQ_OPTIONS: list[str] = list(_get("metadata.update_freq_options", [
    "", "Real-time", "Daily", "Weekly", "Monthly", "Quarterly", "Ad-hoc",
]))

# ── Admin ─────────────────────────────────────────────────────────────────────
LOCKED_PAGES: set[str]   = set(_get("admin.locked_pages",    ["changelog", "usage"]))
ADMIN_PASSCODE_FALLBACK  = _get("admin.passcode_fallback",   "admin1234")

# ── AI Query Assistant ────────────────────────────────────────────────────────
AI_MAX_SCHEMA_TABLES     = int(_get("ai.max_schema_tables",    8))
AI_DEFAULT_PROVIDER      = _get("ai.default_provider",        "Claude (Anthropic)")
AI_DEFAULT_USE_CASE      = _get("ai.default_use_case",        "business")
AI_REQUEST_TIMEOUT_SECS  = int(_get("ai.request_timeout_secs", 120))
