# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Merges five CSV files exported from an InterSystems IRIS system into a single structured JSON data dictionary (`iris_data_dictionary_full.json`). The output is used as a reference for IRIS persistent classes and their SQL representations.

## Running the pipeline

The pipeline lives entirely in `Create_JSON.ipynb`. Run it via Jupyter or execute the cell directly as a Python script (the notebook has an `if __name__ == "__main__"` guard).

```bash
jupyter nbconvert --to notebook --execute Create_JSON.ipynb
# or, since the cell is also a standalone script:
python -c "$(jupyter nbconvert --to script Create_JSON.ipynb --stdout 2>/dev/null)"
```

Dependencies: `pandas`, `json`, `re`, `os` (standard library except pandas).

## Input CSV files

All five CSVs must be present in the working directory:

| File | Contents |
|---|---|
| `iris_data_dict-sql_tables.csv` | One row per table: `sql_table_name`, `class_name`, `module_name`, `module_prefix`, `class_description`, `class_decl` |
| `iris_data_dict-sql_fields.csv` | One row per field: maps `sql_field_name` + `class_name` to type, description, member metadata |
| `iris_data_dict-fk_relationships.csv` | Object references / FK relationships: `source_class_name` + `source_sql_field_name` → `target_sql_table_name` |
| `iris_data_dict-classes.csv` | Full class declarations with IRIS metadata (db, timestamps, `class_decl` string) |
| `iris_data_dict-members.csv` | All class members by `member_kind` (`property`, `parameter`, `trigger`) |

The join key throughout is `class_name` (e.g. `User.APCVendCat.cls`).

## Output JSON structure

Each entry in `iris_data_dictionary_full.json` represents one SQL table:

```json
{
  "tableName": "APC_VendCat",
  "className": "User.APCVendCat.cls",
  "module": { "name": "...", "prefix": "APC" },
  "tableDescription": { "en": "...", "th": "" },
  "irisClassDetails": {
    "storageStrategy": "SQLStorage",
    "parameters": [ { "name": "...", "value/type": "...", "description": "..." } ],
    "triggers": [ { "name": "...", "value/type": "...", "description": "..." } ]
  },
  "columns": [
    {
      "name": "FIELD_NAME",
      "dataType": "...",
      "description": { "en": "...", "th": "" },
      "isReference": true,
      "referenceTarget": "CT_Company",
      "arrowSyntaxHelp": "FIELD_NAME->[Field]"
    }
  ]
}
```

`th` (Thai) description fields are intentionally left empty — they are placeholders for future translation.

## Key logic notes

- `extract_storage_strategy()` parses `StorageStrategy = <value>` from the raw `class_decl` string using regex. Defaults to `"Default"` if not found.
- A column is marked `isReference: true` when a matching row exists in `fk_relationships.csv` for `(class_name, sql_field_name)`. This covers both `des_ref` (object reference) and `relationship` member kinds.
- `member_kind == 'parameter'` rows from `members.csv` go into `irisClassDetails.parameters`; `member_kind == 'trigger'` rows go into `irisClassDetails.triggers`. Properties go into `columns` via `fields.csv`.
- The Excel file `iris_data_dict.xlsx` appears to be the source from which the CSVs were exported; editing CSVs directly is the correct workflow.
