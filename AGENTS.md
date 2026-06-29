# Repository Guidelines

## Project Structure & Module Organization

This repository is a Streamlit data dictionary application for Siriraj IRIS metadata. The main UI and workflow logic live in `app.py`. Configuration loading is in `config.py`, persistence helpers are in `storage.py`, data models are in `models.py`, and lineage search logic is in `lineage_finder.py`. Use `import_xlsx.py` to import `iris_data_dict.xlsx` into PostgreSQL when that backend is enabled. Generated or supporting documentation belongs in `doc/`; keep `README.md`, `CLAUDE.md`, and this file at the repository root. Local screenshots and images should stay in `pic/`, which is git-ignored.

## Build, Test, and Development Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app locally:

```bash
streamlit run app.py
```

Import Excel data into PostgreSQL:

```bash
python import_xlsx.py
python import_xlsx.py --drop
python import_xlsx.py --db postgresql://user:pass@host:5432/iris_dict
```

Regenerate the external JSON export from the source workbook with `Create_JSON.ipynb`.

## Coding Style & Naming Conventions

Use Python with 4-space indentation and descriptive snake_case names for functions, variables, and module-level helpers. Keep Streamlit rendering code readable by grouping related UI sections and placing reusable logic in helper functions instead of duplicating large blocks. Prefer centralized settings in `config.toml` and constants exposed by `config.py` over hard-coded environment-specific values.

## Testing Guidelines

There is currently no dedicated automated test suite in the repository. Before committing changes, run `streamlit run app.py` and manually verify affected tabs, filters, diagrams, and storage behavior. For data import changes, test against a disposable database or backup first, especially when using `python import_xlsx.py --drop`.

## Commit & Pull Request Guidelines

Recent commits use short imperative messages, for example `Add lineage finder feature` and `Update README and CLAUDE.md: document config.toml + config.py layer`. Follow that style: start with a verb, describe the user-visible change, and keep the subject concise.

Pull requests should include a summary of changes, manual verification steps, screenshots for UI changes, and notes about configuration, database, or data-file impacts. Link related issues when available.

## Security & Configuration Tips

Do not commit `.streamlit/secrets.toml`, database credentials, admin passcodes, generated logs, or local user data files such as `translations.json`, `tags.json`, `metadata.json`, `changelog.json`, and `usage_log.json`. Keep non-secret app settings in committed `config.toml`.
