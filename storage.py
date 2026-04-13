"""Unified storage layer for IRIS Data Dictionary.

Switch backends via .streamlit/secrets.toml:

    backend = "file"        # default — flat JSON files (current behaviour)
    backend = "postgres"    # PostgreSQL via SQLAlchemy

    # required only when backend = "postgres":
    database_url = "postgresql://user:pass@host:5432/iris_dict"

The public interface is identical for both backends so app.py never needs
to know which one is active.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import pandas as pd
from config import (
    EXCEL_FILE       as EXCEL_PATH,
    TRANSLATIONS_FILE as TRANSLATIONS_PATH,
    TAGS_FILE        as TAGS_PATH,
    CHANGELOG_FILE   as CHANGELOG_PATH,
    METADATA_FILE    as METADATA_PATH,
    USAGE_LOG_FILE   as USAGE_LOG_PATH,
    MAX_CHANGELOG_ENTRIES,
    MAX_USAGE_LOG_ENTRIES,
)

def _detect_backend() -> str:
    """Read backend from st.secrets; fall back to 'file' on any error."""
    try:
        import streamlit as st
        return str(st.secrets.get("backend", "file")).strip().lower()
    except Exception:
        return "file"

BACKEND: str = _detect_backend()

# ─── SQLAlchemy engine (postgres only) ───────────────────────────────────────

_engine = None

def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:
        import streamlit as st
        from sqlalchemy import create_engine
        url = st.secrets["database_url"]
        _engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        return _engine
    except Exception as e:
        raise RuntimeError(f"Cannot connect to PostgreSQL: {e}") from e


# ─── load_data ────────────────────────────────────────────────────────────────

def load_data() -> tuple:
    """Return (tables, fields, fk, classes, members) as DataFrames.

    File backend  : reads iris_data_dict.xlsx (current behaviour).
    Postgres backend : reads dict_* tables from PostgreSQL.
    """
    if BACKEND == "postgres":
        return _pg_load_data()
    return _file_load_data()


def _file_load_data() -> tuple:
    xl = pd.ExcelFile(EXCEL_PATH)
    tables  = xl.parse("sql_tables").fillna("")
    fields  = xl.parse("sql_fields").fillna("")
    fk      = xl.parse("fk_relationships").fillna("")
    classes = xl.parse("classes").fillna("")
    members = xl.parse("members").fillna("")
    return tables, fields, fk, classes, members


def _pg_load_data() -> tuple:
    from sqlalchemy import text
    engine = _get_engine()
    with engine.connect() as conn:
        tables  = pd.read_sql(text("SELECT * FROM dict_tables"),  conn).fillna("")
        fields  = pd.read_sql(text("SELECT * FROM dict_fields"),  conn).fillna("")
        fk      = pd.read_sql(text("SELECT * FROM dict_fk"),      conn).fillna("")
        classes = pd.read_sql(text("SELECT * FROM dict_classes"),  conn).fillna("")
        members = pd.read_sql(text("SELECT * FROM dict_members"),  conn).fillna("")
    # drop internal id column added by postgres
    for df in (tables, fields, fk, classes, members):
        if "id" in df.columns:
            df.drop(columns=["id"], inplace=True)
        if "imported_at" in df.columns:
            df.drop(columns=["imported_at"], inplace=True)
    return tables, fields, fk, classes, members


# ─── Translations ─────────────────────────────────────────────────────────────

def load_translations() -> dict:
    if BACKEND == "postgres":
        return _pg_load_translations()
    return _file_load_json(TRANSLATIONS_PATH, {})


def save_translations(data: dict) -> None:
    if BACKEND == "postgres":
        _pg_save_translations(data)
    else:
        _file_save_json(TRANSLATIONS_PATH, data)


def _pg_load_translations() -> dict:
    from sqlalchemy import text
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text("SELECT class_name, field_name, thai_text FROM translations")
            ).fetchall()
        result: dict = {}
        for class_name, field_name, thai_text in rows:
            result.setdefault(class_name, {})[field_name] = thai_text
        return result
    except Exception:
        return {}


def _pg_save_translations(data: dict) -> None:
    """Upsert all translations — replace entire dataset for each class_name present."""
    from sqlalchemy import text
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            # delete existing entries for each class_name we're updating
            class_names = list(data.keys())
            if class_names:
                conn.execute(
                    text("DELETE FROM translations WHERE class_name = ANY(:names)"),
                    {"names": class_names},
                )
            rows = [
                {"class_name": cn, "field_name": fn, "thai_text": th}
                for cn, fields in data.items()
                for fn, th in fields.items()
                if th and str(th).strip()
            ]
            if rows:
                conn.execute(
                    text(
                        "INSERT INTO translations (class_name, field_name, thai_text) "
                        "VALUES (:class_name, :field_name, :thai_text)"
                    ),
                    rows,
                )
    except Exception as e:
        import streamlit as st
        st.warning(f"Could not save translations to database: {e}")


# ─── Tags ─────────────────────────────────────────────────────────────────────

def load_tags() -> dict:
    if BACKEND == "postgres":
        return _pg_load_tags()
    return _file_load_json(TAGS_PATH, {})


def save_tags(data: dict) -> None:
    if BACKEND == "postgres":
        _pg_save_tags(data)
    else:
        _file_save_json(TAGS_PATH, data)


def _pg_load_tags() -> dict:
    from sqlalchemy import text
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text("SELECT table_name, tag FROM table_tags ORDER BY added_at")
            ).fetchall()
        result: dict = {}
        for table_name, tag in rows:
            result.setdefault(table_name, []).append(tag)
        return result
    except Exception:
        return {}


def _pg_save_tags(data: dict) -> None:
    """Replace entire tag set for each table_name present in data."""
    from sqlalchemy import text
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            table_names = list(data.keys())
            if table_names:
                conn.execute(
                    text("DELETE FROM table_tags WHERE table_name = ANY(:names)"),
                    {"names": table_names},
                )
            rows = [
                {"table_name": tbl, "tag": tag}
                for tbl, tags in data.items()
                for tag in tags
            ]
            if rows:
                conn.execute(
                    text("INSERT INTO table_tags (table_name, tag) VALUES (:table_name, :tag)"),
                    rows,
                )
    except Exception as e:
        import streamlit as st
        st.warning(f"Could not save tags to database: {e}")


# ─── Metadata ─────────────────────────────────────────────────────────────────

def load_metadata() -> dict:
    if BACKEND == "postgres":
        return _pg_load_metadata()
    return _file_load_json(METADATA_PATH, {})


def save_metadata(data: dict) -> None:
    if BACKEND == "postgres":
        _pg_save_metadata(data)
    else:
        _file_save_json(METADATA_PATH, data)


def _pg_load_metadata() -> dict:
    from sqlalchemy import text
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name, owner, steward, contact, "
                    "certification, update_frequency, last_refresh "
                    "FROM table_metadata"
                )
            ).fetchall()
        result: dict = {}
        for row in rows:
            tbl = row[0]
            result[tbl] = {
                "owner":            row[1] or "",
                "steward":          row[2] or "",
                "contact":          row[3] or "",
                "certification":    row[4] or "",
                "update_frequency": row[5] or "",
                "last_refresh":     row[6] or "",
            }
            # remove empty keys (matches file backend behaviour)
            result[tbl] = {k: v for k, v in result[tbl].items() if v}
        return result
    except Exception:
        return {}


def _pg_save_metadata(data: dict) -> None:
    """Upsert one row per table."""
    from sqlalchemy import text
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            for tbl, meta in data.items():
                conn.execute(
                    text("""
                        INSERT INTO table_metadata
                            (table_name, owner, steward, contact,
                             certification, update_frequency, last_refresh)
                        VALUES
                            (:table_name, :owner, :steward, :contact,
                             :certification, :update_frequency, :last_refresh)
                        ON CONFLICT (table_name) DO UPDATE SET
                            owner            = EXCLUDED.owner,
                            steward          = EXCLUDED.steward,
                            contact          = EXCLUDED.contact,
                            certification    = EXCLUDED.certification,
                            update_frequency = EXCLUDED.update_frequency,
                            last_refresh     = EXCLUDED.last_refresh,
                            updated_at       = now()
                    """),
                    {
                        "table_name":       tbl,
                        "owner":            meta.get("owner", ""),
                        "steward":          meta.get("steward", ""),
                        "contact":          meta.get("contact", ""),
                        "certification":    meta.get("certification", ""),
                        "update_frequency": meta.get("update_frequency", ""),
                        "last_refresh":     meta.get("last_refresh", ""),
                    },
                )
    except Exception as e:
        import streamlit as st
        st.warning(f"Could not save metadata to database: {e}")


# ─── Changelog ────────────────────────────────────────────────────────────────

def load_changelog() -> list:
    if BACKEND == "postgres":
        return _pg_load_changelog()
    return _file_load_json(CHANGELOG_PATH, [])


def append_changelog(action: str, table: str, details: str) -> None:
    if BACKEND == "postgres":
        _pg_append_changelog(action, table, details)
    else:
        _file_append_changelog(action, table, details)


def _pg_load_changelog() -> list:
    from sqlalchemy import text
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT timestamp, action, table_name, details "
                    f"FROM changelog ORDER BY id DESC LIMIT {MAX_CHANGELOG_ENTRIES}"
                )
            ).fetchall()
        return [
            {
                "timestamp": str(r[0])[:19],
                "action":    r[1] or "",
                "table":     r[2] or "",
                "details":   r[3] or "",
            }
            for r in rows
        ]
    except Exception:
        return []


def _pg_append_changelog(action: str, table: str, details: str) -> None:
    from sqlalchemy import text
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO changelog (action, table_name, details) "
                    "VALUES (:action, :table_name, :details)"
                ),
                {"action": action, "table_name": table, "details": details},
            )
            # keep only latest 1000 rows
            conn.execute(
                text(
                    "DELETE FROM changelog WHERE id NOT IN "
                    f"(SELECT id FROM changelog ORDER BY id DESC LIMIT {MAX_CHANGELOG_ENTRIES})"
                )
            )
    except Exception:
        pass  # changelog must never crash the app


def _file_append_changelog(action: str, table: str, details: str) -> None:
    try:
        log = _file_load_json(CHANGELOG_PATH, [])
        log.insert(0, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action":    action,
            "table":     table,
            "details":   details,
        })
        _file_save_json(CHANGELOG_PATH, log[:MAX_CHANGELOG_ENTRIES])
    except Exception:
        pass


# ─── Usage log ────────────────────────────────────────────────────────────────

def load_usage_log() -> list:
    if BACKEND == "postgres":
        return _pg_load_usage_log()
    return _file_load_json(USAGE_LOG_PATH, [])


def log_event(event: str, details: dict | None = None) -> None:
    if BACKEND == "postgres":
        _pg_log_event(event, details or {})
    else:
        _file_log_event(event, details or {})


def _pg_load_usage_log() -> list:
    from sqlalchemy import text
    try:
        with _get_engine().connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT timestamp, event, details "
                    f"FROM usage_log ORDER BY id DESC LIMIT {MAX_USAGE_LOG_ENTRIES}"
                )
            ).fetchall()
        return [
            {
                "timestamp": str(r[0])[:19],
                "event":     r[1] or "",
                "details":   r[2] or {},
            }
            for r in rows
        ]
    except Exception:
        return []


def _pg_log_event(event: str, details: dict) -> None:
    from sqlalchemy import text
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO usage_log (event, details) "
                    "VALUES (:event, :details::jsonb)"
                ),
                {"event": event, "details": json.dumps(details)},
            )
            # keep only latest 10000 rows
            conn.execute(
                text(
                    "DELETE FROM usage_log WHERE id NOT IN "
                    f"(SELECT id FROM usage_log ORDER BY id DESC LIMIT {MAX_USAGE_LOG_ENTRIES})"
                )
            )
    except Exception:
        pass  # logging must never crash the app


def _file_log_event(event: str, details: dict) -> None:
    try:
        log = _file_load_json(USAGE_LOG_PATH, [])
        log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event":     event,
            "details":   details,
        })
        _file_save_json(USAGE_LOG_PATH, log[-MAX_USAGE_LOG_ENTRIES:])
    except Exception:
        pass


# ─── File backend helpers ─────────────────────────────────────────────────────

def _file_load_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def _file_save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        import streamlit as st
        st.warning(f"Could not save {os.path.basename(path)}: {e}")


# ─── Clear changelog ─────────────────────────────────────────────────────────

def clear_changelog() -> None:
    """Delete all changelog entries."""
    if BACKEND == "postgres":
        from sqlalchemy import text
        try:
            with _get_engine().begin() as conn:
                conn.execute(text("TRUNCATE TABLE changelog RESTART IDENTITY"))
        except Exception as e:
            import streamlit as st
            st.warning(f"Could not clear changelog: {e}")
    else:
        _file_save_json(CHANGELOG_PATH, [])


# ─── Utility: create all postgres tables ─────────────────────────────────────

def init_db() -> None:
    """Create all postgres tables if they don't exist.

    Call this from import_xlsx.py before importing data.
    Does nothing when backend = 'file'.
    """
    if BACKEND != "postgres":
        return
    from models import metadata as db_meta
    db_meta.create_all(_get_engine())
    print("All tables created (or already exist).")
