#!/usr/bin/env python3
"""Import iris_data_dict.xlsx into PostgreSQL dict_* tables.

Run this once after initial setup, and again whenever the xlsx file changes.

Usage:
    python import_xlsx.py
    python import_xlsx.py --db postgresql://user:pass@host:5432/iris_dict
    python import_xlsx.py --xlsx /path/to/other.xlsx

The script reads DATABASE_URL from (in order of priority):
  1. --db command-line argument
  2. .streamlit/secrets.toml  (key: database_url)
  3. DATABASE_URL environment variable

Only dict_* tables are touched. User data (translations, tags, metadata,
changelog, usage_log) is never modified by this script.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd


# ─── Argument parsing ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import xlsx → PostgreSQL dict_* tables")
    p.add_argument("--db",   metavar="URL",  help="PostgreSQL connection URL")
    p.add_argument("--xlsx", metavar="PATH", default="iris_data_dict.xlsx",
                   help="Path to iris_data_dict.xlsx (default: iris_data_dict.xlsx)")
    p.add_argument("--drop", action="store_true",
                   help="Drop and recreate dict_* tables before importing (full refresh)")
    return p.parse_args()


# ─── Resolve DATABASE_URL ─────────────────────────────────────────────────────

def resolve_db_url(cli_url: str | None) -> str:
    if cli_url:
        return cli_url

    # try secrets.toml
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # pip install tomli for older Python
        except ImportError:
            tomllib = None  # type: ignore

    secrets_path = os.path.join(".streamlit", "secrets.toml")
    if tomllib and os.path.exists(secrets_path):
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        if "database_url" in secrets:
            return secrets["database_url"]

    # fallback: environment variable
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url

    print("ERROR: No database URL found.")
    print("  Pass --db postgresql://user:pass@host:5432/iris_dict")
    print("  or set DATABASE_URL environment variable")
    print("  or add database_url to .streamlit/secrets.toml")
    sys.exit(1)


# ─── Column mapping helpers ───────────────────────────────────────────────────

def _col(df: pd.DataFrame, *candidates: str, default: str = "") -> pd.Series:
    """Return the first matching column from candidates, or a blank Series."""
    for c in candidates:
        if c in df.columns:
            return df[c].fillna("").astype(str)
    return pd.Series([default] * len(df), dtype=str)


# ─── Main import ─────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    db_url = resolve_db_url(args.db)
    xlsx   = args.xlsx

    if not os.path.exists(xlsx):
        print(f"ERROR: xlsx file not found: {xlsx}")
        sys.exit(1)

    print(f"Connecting to database…")
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, pool_pre_ping=True)

    # Verify connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  Connected OK")
    except Exception as e:
        print(f"ERROR: Cannot connect: {e}")
        sys.exit(1)

    # Create/refresh schema
    print("Creating tables (if not exist)…")
    # Temporarily set BACKEND=postgres so storage.init_db works
    import storage as _storage
    _real_backend = _storage.BACKEND
    _storage.BACKEND = "postgres"
    _storage._engine = engine
    _storage.init_db()
    _storage.BACKEND = _real_backend

    if args.drop:
        print("  --drop: truncating dict_* tables…")
        with engine.begin() as conn:
            for tbl in ("dict_members", "dict_classes", "dict_fk",
                        "dict_fields", "dict_tables"):
                conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
        print("  Truncated.")

    # Read xlsx
    print(f"\nReading {xlsx}…")
    t0 = time.time()
    xl      = pd.ExcelFile(xlsx)
    tables  = xl.parse("sql_tables").fillna("")
    fields  = xl.parse("sql_fields").fillna("")
    fk      = xl.parse("fk_relationships").fillna("")
    classes = xl.parse("classes").fillna("")
    members = xl.parse("members").fillna("")
    print(f"  Loaded in {time.time()-t0:.1f}s — "
          f"{len(tables)} tables, {len(fields)} fields, "
          f"{len(fk)} fk rows, {len(classes)} classes, {len(members)} members")

    # ── dict_tables
    print("\nImporting dict_tables…")
    tbl_rows = [
        {
            "sql_table_name":    str(r.get("sql_table_name", "")),
            "class_name":        str(r.get("class_name", "")),
            "module_name":       str(r.get("module_name", "")),
            "module_prefix":     str(r.get("module_prefix", "")),
            "class_description": str(r.get("class_description", "")),
        }
        for _, r in tables.iterrows()
        if str(r.get("sql_table_name", "")).strip()
    ]
    _upsert(engine, "dict_tables", "sql_table_name", tbl_rows,
            update_cols=["class_name", "module_name", "module_prefix", "class_description"])
    print(f"  {len(tbl_rows)} rows upserted")

    # ── dict_fields
    print("Importing dict_fields…")
    fld_rows = [
        {
            "class_name":     str(r.get("class_name", "")),
            "sql_field_name": str(r.get("sql_field_name", "")),
            "member_type":    str(r.get("member_type", "")),
            "description":    str(r.get("description", "")),
            "member_order":   int(r["member_order"]) if str(r.get("member_order", "")).isdigit() else 0,
        }
        for _, r in fields.iterrows()
        if str(r.get("class_name", "")).strip()
    ]
    with engine.begin() as conn:
        # fields don't have a natural unique key per row — truncate + insert
        conn.execute(text("TRUNCATE TABLE dict_fields RESTART IDENTITY"))
        if fld_rows:
            conn.execute(
                text("INSERT INTO dict_fields "
                     "(class_name, sql_field_name, member_type, description, member_order) "
                     "VALUES (:class_name, :sql_field_name, :member_type, :description, :member_order)"),
                fld_rows,
            )
    print(f"  {len(fld_rows)} rows inserted")

    # ── dict_fk
    print("Importing dict_fk…")
    fk_rows = [
        {
            "source_class_name":        str(r.get("source_class_name", "")),
            "source_sql_table_name":    str(r.get("source_sql_table_name", "")),
            "source_sql_field_name":    str(r.get("source_sql_field_name", "")),
            "source_member_name":       str(r.get("source_member_name", "")),
            "target_sql_table_name":    str(r.get("target_sql_table_name", "")),
            "target_pk_fields":         str(r.get("target_pk_fields", "")),
            "resolve_status":           str(r.get("resolve_status", "")),
            "relationship_cardinality": str(r.get("relationship_cardinality", "")),
            "evidence_source":          str(r.get("evidence_source", "")),
        }
        for _, r in fk.iterrows()
    ]
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dict_fk RESTART IDENTITY"))
        if fk_rows:
            conn.execute(
                text("INSERT INTO dict_fk "
                     "(source_class_name, source_sql_table_name, source_sql_field_name, "
                     "source_member_name, target_sql_table_name, target_pk_fields, "
                     "resolve_status, relationship_cardinality, evidence_source) "
                     "VALUES (:source_class_name, :source_sql_table_name, :source_sql_field_name, "
                     ":source_member_name, :target_sql_table_name, :target_pk_fields, "
                     ":resolve_status, :relationship_cardinality, :evidence_source)"),
                fk_rows,
            )
    print(f"  {len(fk_rows)} rows inserted")

    # ── dict_classes
    print("Importing dict_classes…")
    cls_rows = [
        {
            "class_name": str(r.get("class_name", "")),
            "class_decl": str(r.get("class_decl", "")),
            "db":         str(r.get("db", "")),
        }
        for _, r in classes.iterrows()
        if str(r.get("class_name", "")).strip()
    ]
    _upsert(engine, "dict_classes", "class_name", cls_rows,
            update_cols=["class_decl", "db"])
    print(f"  {len(cls_rows)} rows upserted")

    # ── dict_members
    print("Importing dict_members…")
    mem_rows = [
        {
            "class_name":  str(r.get("class_name", "")),
            "member_name": str(r.get("member_name", "")),
            "member_kind": str(r.get("member_kind", "")),
            "member_type": str(r.get("member_type", "")),
            "member_decl": str(r.get("member_decl", "")),
            "description": str(r.get("description", "")),
        }
        for _, r in members.iterrows()
        if str(r.get("class_name", "")).strip()
    ]
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dict_members RESTART IDENTITY"))
        if mem_rows:
            conn.execute(
                text("INSERT INTO dict_members "
                     "(class_name, member_name, member_kind, member_type, member_decl, description) "
                     "VALUES (:class_name, :member_name, :member_kind, :member_type, :member_decl, :description)"),
                mem_rows,
            )
    print(f"  {len(mem_rows)} rows inserted")

    print(f"\nDone in {time.time()-t0:.1f}s total.")


# ─── Generic upsert helper ────────────────────────────────────────────────────

def _upsert(engine, table: str, conflict_col: str, rows: list[dict],
            update_cols: list[str]) -> None:
    if not rows:
        return
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    cols = ", ".join(rows[0].keys())
    vals = ", ".join(f":{k}" for k in rows[0].keys())
    sql = (
        f"INSERT INTO {table} ({cols}) VALUES ({vals}) "
        f"ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}"
    )
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(sql), rows)


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run(parse_args())
