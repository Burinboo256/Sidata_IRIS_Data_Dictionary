"""SQLAlchemy table definitions for the IRIS Data Dictionary (postgres backend).

All dict_* tables are read-only from the app's perspective — they are
populated once by import_xlsx.py and refreshed whenever the xlsx changes.

The remaining tables (translations, table_tags, table_metadata, changelog,
usage_log) are written by the app at runtime.
"""

from sqlalchemy import (
    Column, Integer, Text, TIMESTAMP, Index,
    MetaData, Table, func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

# ─── Read-only: imported from xlsx ───────────────────────────────────────────

dict_tables = Table(
    "dict_tables", metadata,
    Column("id",                Integer, primary_key=True, autoincrement=True),
    Column("sql_table_name",    Text, nullable=False, unique=True),
    Column("class_name",        Text),
    Column("module_name",       Text),
    Column("module_prefix",     Text),
    Column("class_description", Text),
    Column("imported_at",       TIMESTAMP, server_default=func.now()),
)

dict_fields = Table(
    "dict_fields", metadata,
    Column("id",             Integer, primary_key=True, autoincrement=True),
    Column("class_name",     Text, nullable=False),
    Column("sql_field_name", Text),
    Column("member_type",    Text),
    Column("description",    Text),
    Column("member_order",   Integer),
    Index("ix_dict_fields_class", "class_name"),
)

dict_fk = Table(
    "dict_fk", metadata,
    Column("id",                       Integer, primary_key=True, autoincrement=True),
    Column("source_class_name",        Text),
    Column("source_sql_table_name",    Text),
    Column("source_sql_field_name",    Text),
    Column("source_member_name",       Text),
    Column("target_sql_table_name",    Text),
    Column("target_pk_fields",         Text),
    Column("resolve_status",           Text),
    Column("relationship_cardinality", Text),
    Column("evidence_source",          Text),
    Index("ix_dict_fk_src_tbl",  "source_sql_table_name"),
    Index("ix_dict_fk_tgt_tbl",  "target_sql_table_name"),
    Index("ix_dict_fk_resolve",  "resolve_status"),
)

dict_classes = Table(
    "dict_classes", metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("class_name", Text, nullable=False, unique=True),
    Column("class_decl", Text),
    Column("db",         Text),
)

dict_members = Table(
    "dict_members", metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("class_name",  Text, nullable=False),
    Column("member_name", Text),
    Column("member_kind", Text),
    Column("member_type", Text),
    Column("member_decl", Text),
    Column("description", Text),
    Index("ix_dict_members_class", "class_name"),
)

# ─── Writable: managed by the app at runtime ─────────────────────────────────

translations = Table(
    "translations", metadata,
    Column("class_name",  Text, nullable=False),
    Column("field_name",  Text, nullable=False),
    Column("thai_text",   Text, nullable=False, default=""),
    Column("updated_at",  TIMESTAMP, server_default=func.now(), onupdate=func.now()),
    # composite PK defined below to avoid duplicate column declarations
)

# Set composite PK manually (SQLAlchemy Table API)
from sqlalchemy import PrimaryKeyConstraint
translations.append_constraint(
    PrimaryKeyConstraint("class_name", "field_name", name="pk_translations")
)

table_tags = Table(
    "table_tags", metadata,
    Column("table_name", Text, nullable=False),
    Column("tag",        Text, nullable=False),
    Column("added_at",   TIMESTAMP, server_default=func.now()),
)
table_tags.append_constraint(
    PrimaryKeyConstraint("table_name", "tag", name="pk_table_tags")
)

table_metadata = Table(
    "table_metadata", metadata,
    Column("table_name",       Text, primary_key=True),
    Column("owner",            Text, default=""),
    Column("steward",          Text, default=""),
    Column("contact",          Text, default=""),
    Column("certification",    Text, default=""),
    Column("update_frequency", Text, default=""),
    Column("last_refresh",     Text, default=""),
    Column("updated_at",       TIMESTAMP, server_default=func.now()),
)

changelog = Table(
    "changelog", metadata,
    Column("id",         Integer, primary_key=True, autoincrement=True),
    Column("timestamp",  TIMESTAMP, server_default=func.now()),
    Column("action",     Text),
    Column("table_name", Text),
    Column("details",    Text),
)

usage_log = Table(
    "usage_log", metadata,
    Column("id",        Integer, primary_key=True, autoincrement=True),
    Column("timestamp", TIMESTAMP, server_default=func.now()),
    Column("event",     Text),
    Column("details",   JSONB, default={}),
)
